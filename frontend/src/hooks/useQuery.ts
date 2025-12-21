import { useState, useCallback, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import type { GuardrailFlags, ChatMessage, EnhancedQueryResponse, EnhancedChatMetadata } from '../types';
import api from '../services/api';

// Session storage key for persistence
const SESSION_ID_STORAGE_KEY = 'icda_session_id';

// Helper to get session from localStorage
const getStoredSessionId = (): string | null => {
  try {
    return localStorage.getItem(SESSION_ID_STORAGE_KEY);
  } catch {
    return null;
  }
};

// Helper to persist session to localStorage
const storeSessionId = (sessionId: string | null): void => {
  try {
    if (sessionId) {
      localStorage.setItem(SESSION_ID_STORAGE_KEY, sessionId);
    } else {
      localStorage.removeItem(SESSION_ID_STORAGE_KEY);
    }
  } catch {
    // Ignore storage errors
  }
};

export interface UseQueryReturn {
  messages: ChatMessage[];
  loading: boolean;
  sessionId: string | null;
  sendQuery: (query: string, guardrails: GuardrailFlags, bypassCache?: boolean, file?: File) => Promise<void>;
  clearMessages: () => void;
  newSession: () => void;
  addSystemMessage: (content: string, type: 'bot' | 'error' | 'blocked') => void;
  downloadResults: (token: string, format: 'json' | 'csv') => Promise<void>;
}

export function useQuery(): UseQueryReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  // Initialize sessionId from localStorage for persistence across page refreshes
  const [sessionId, setSessionId] = useState<string | null>(() => getStoredSessionId());
  const sessionInitialized = useRef(!!getStoredSessionId());
  const abortControllerRef = useRef<AbortController | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const addMessage = useCallback((message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    const newMessage: ChatMessage = {
      ...message,
      id: uuidv4(),
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, newMessage]);
    return newMessage;
  }, []);

  const sendQuery = useCallback(
    async (query: string, guardrails: GuardrailFlags, bypassCache: boolean = false, file?: File) => {
      // Cancel any previous request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      // Initialize session on first query if not already set
      let currentSessionId = sessionId;
      if (!currentSessionId && !sessionInitialized.current) {
        currentSessionId = uuidv4();
        setSessionId(currentSessionId);
        storeSessionId(currentSessionId); // Persist to localStorage
        sessionInitialized.current = true;
      }

      // Add user message (include file info if present)
      const userContent = file ? `${query}\n\n📎 Attached: ${file.name}` : query;
      addMessage({
        type: 'user',
        content: userContent,
      });

      setLoading(true);

      try {
        // Use file upload endpoint if file is provided, otherwise use regular query
        const response = (file
          ? await api.queryWithFile({
              query,
              file,
              bypass_cache: bypassCache,
              guardrails,
              session_id: currentSessionId ?? undefined,
            })
          : await api.query({
              query,
              bypass_cache: bypassCache,
              guardrails,
              session_id: currentSessionId ?? undefined,
            })) as EnhancedQueryResponse;

        // Update session ID from response if provided
        if (response.session_id && response.session_id !== currentSessionId) {
          setSessionId(response.session_id);
          storeSessionId(response.session_id); // Persist to localStorage
          sessionInitialized.current = true;
        }

        // Build enhanced metadata from response
        const buildMetadata = (): EnhancedChatMetadata => ({
          route: response.route,
          latency_ms: response.latency_ms,
          cached: response.cached,
          tool: response.tool,
          token_usage: response.token_usage,
          trace: response.trace,
          pagination: response.pagination,
          model_used: response.model_used,
          quality_score: response.quality_score,
          guardrails_active: response.guardrails_active,
          guardrails_bypassed: response.guardrails_bypassed,
          results: response.results,
        });

        if (response.blocked) {
          addMessage({
            type: 'blocked',
            content: response.response,
            metadata: {
              latency_ms: response.latency_ms,
              guardrails_active: response.guardrails_active,
              guardrails_bypassed: response.guardrails_bypassed,
            },
          });
        } else if (!response.success) {
          addMessage({
            type: 'error',
            content: response.response || 'An error occurred',
            metadata: {
              latency_ms: response.latency_ms,
              trace: response.trace,
            },
          });
        } else {
          addMessage({
            type: 'bot',
            content: response.response,
            metadata: buildMetadata(),
          });
        }
      } catch (err) {
        // Ignore abort errors - they're expected when cancelling requests
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        const errorMessage = err instanceof Error ? err.message : 'Failed to send query';
        addMessage({
          type: 'error',
          content: errorMessage,
        });
      } finally {
        setLoading(false);
      }
    },
    [addMessage, sessionId]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    if (sessionId) {
      api.deleteSession(sessionId).catch((err) => {
        console.warn('Failed to delete session:', err);
      });
    }
    setSessionId(null);
    storeSessionId(null); // Clear from localStorage
    sessionInitialized.current = false;
  }, [sessionId]);

  const newSession = useCallback(() => {
    if (sessionId) {
      api.deleteSession(sessionId).catch((err) => {
        console.warn('Failed to delete previous session:', err);
      });
    }
    const newId = uuidv4();
    setSessionId(newId);
    storeSessionId(newId); // Persist new session to localStorage
    sessionInitialized.current = true;
    setMessages([]);
  }, [sessionId]);

  const addSystemMessage = useCallback((content: string, type: 'bot' | 'error' | 'blocked') => {
    addMessage({ type, content });
  }, [addMessage]);

  const downloadResults = useCallback(async (token: string, format: 'json' | 'csv') => {
    try {
      const data = await api.downloadResults(token, format);
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const filename = `icda-results-${timestamp}`;
      api.triggerDownload(data, filename, format);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to download results';
      console.error('Download error:', errorMessage);
      throw err;
    }
  }, []);

  return {
    messages,
    loading,
    sessionId,
    sendQuery,
    clearMessages,
    newSession,
    addSystemMessage,
    downloadResults,
  };
}

export default useQuery;
