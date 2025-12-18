import { useState, useCallback, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import type { GuardrailFlags, ChatMessage, QueryResponse } from '../types';
import api from '../services/api';

export interface UseQueryReturn {
  messages: ChatMessage[];
  loading: boolean;
  sessionId: string | null;
  sendQuery: (query: string, guardrails: GuardrailFlags, bypassCache?: boolean, file?: File) => Promise<void>;
  clearMessages: () => void;
  newSession: () => void;
  addSystemMessage: (content: string, type: 'bot' | 'error' | 'blocked') => void;
}

export function useQuery(): UseQueryReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const sessionInitialized = useRef(false);
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
        const response: QueryResponse = file
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
            });

        // Update session ID from response if provided
        if (response.session_id && response.session_id !== currentSessionId) {
          setSessionId(response.session_id);
          sessionInitialized.current = true;
        }

        if (response.blocked) {
          addMessage({
            type: 'blocked',
            content: response.response,
            metadata: {
              latency_ms: response.latency_ms,
            },
          });
        } else if (!response.success) {
          addMessage({
            type: 'error',
            content: response.response || 'An error occurred',
            metadata: {
              latency_ms: response.latency_ms,
            },
          });
        } else {
          addMessage({
            type: 'bot',
            content: response.response,
            metadata: {
              route: response.route,
              latency_ms: response.latency_ms,
              cached: response.cached,
              tool: response.tool,
            },
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
    sessionInitialized.current = false;
  }, [sessionId]);

  const newSession = useCallback(() => {
    if (sessionId) {
      api.deleteSession(sessionId).catch((err) => {
        console.warn('Failed to delete previous session:', err);
      });
    }
    setSessionId(uuidv4());
    sessionInitialized.current = true;
    setMessages([]);
  }, [sessionId]);

  const addSystemMessage = useCallback((content: string, type: 'bot' | 'error' | 'blocked') => {
    addMessage({ type, content });
  }, [addMessage]);

  return {
    messages,
    loading,
    sessionId,
    sendQuery,
    clearMessages,
    newSession,
    addSystemMessage,
  };
}

export default useQuery;
