/**
 * Admin API Service for ICDA
 */

import axios from 'axios';
import type {
  ChunkListResponse,
  ChunkData,
  IndexStats,
  IndexHealth,
  EnforcerMetrics,
  EnforcerConfig,
  SearchTestResult,
  SavedQuery,
  ChunkQualityResult,
  IndexValidationReport,
} from '../types/admin';

const API_BASE = '/api/admin';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

// ==================== Chunks ====================

export async function listChunks(params: {
  offset?: number;
  limit?: number;
  category?: string;
  min_quality?: number;
  max_quality?: number;
  sort_by?: string;
  sort_order?: string;
}): Promise<ChunkListResponse> {
  const { data } = await api.get('/chunks', { params });
  return data;
}

export async function getChunk(chunkId: string): Promise<{ success: boolean; chunk?: ChunkData; error?: string }> {
  const { data } = await api.get(`/chunks/${chunkId}`);
  return data;
}

export async function updateChunk(
  chunkId: string,
  update: { tags?: string[]; category?: string; quality_score?: number }
): Promise<{ success: boolean; error?: string }> {
  const { data } = await api.patch(`/chunks/${chunkId}`, update);
  return data;
}

export async function deleteChunk(chunkId: string): Promise<{ success: boolean; error?: string }> {
  const { data } = await api.delete(`/chunks/${chunkId}`);
  return data;
}

export async function reembedChunk(chunkId: string): Promise<{ success: boolean; error?: string }> {
  const { data } = await api.post(`/chunks/${chunkId}/reembed`);
  return data;
}

export async function getEmbeddingVisualization(
  sampleSize: number = 100
): Promise<{ success: boolean; points: Array<{ x: number; y: number; label: string }>; message?: string }> {
  const { data } = await api.get('/chunks/embeddings/visualization', { params: { sample_size: sampleSize } });
  return data;
}

export async function getLowQualityChunks(
  threshold: number = 0.6,
  limit: number = 50
): Promise<{ success: boolean; chunks: ChunkData[]; total_below_threshold: number; threshold: number }> {
  const { data } = await api.get('/chunks/quality', { params: { threshold, limit } });
  return data;
}

// ==================== Index Stats ====================

export async function getIndexStats(): Promise<{ success: boolean; stats: IndexStats }> {
  const { data } = await api.get('/index/stats');
  return data;
}

export async function getIndexHealth(): Promise<{ success: boolean; health: IndexHealth }> {
  const { data } = await api.get('/index/health');
  return data;
}

export async function triggerReindex(
  indexName: string = 'all'
): Promise<{ success: boolean; results: Record<string, unknown> }> {
  const { data } = await api.post('/index/reindex', null, { params: { index_name: indexName } });
  return data;
}

export async function clearIndex(indexName: string): Promise<{ success: boolean; deleted?: number; error?: string }> {
  const { data } = await api.delete(`/index/${indexName}`);
  return data;
}

export async function exportStats(): Promise<{
  success: boolean;
  export: {
    timestamp: string;
    stats: IndexStats;
    health: IndexHealth;
    config: Record<string, unknown>;
  };
}> {
  const { data } = await api.get('/index/export');
  return data;
}

// ==================== Search Playground ====================

export async function testSearch(params: {
  query: string;
  limit?: number;
  index?: string;
  filters?: Record<string, unknown>;
  explain?: boolean;
}): Promise<SearchTestResult> {
  const { data } = await api.post('/search/test', params);
  return data;
}

export async function saveQuery(params: {
  name: string;
  query: string;
  index?: string;
  filters?: Record<string, unknown>;
  notes?: string;
}): Promise<{ success: boolean; query_id: string }> {
  const { data } = await api.post('/search/saved', params);
  return data;
}

export async function listSavedQueries(): Promise<{ success: boolean; queries: SavedQuery[]; count: number }> {
  const { data } = await api.get('/search/saved');
  return data;
}

export async function deleteSavedQuery(queryId: string): Promise<{ success: boolean; deleted?: string; error?: string }> {
  const { data } = await api.delete(`/search/saved/${queryId}`);
  return data;
}

export async function runSavedQuery(queryId: string): Promise<SearchTestResult> {
  const { data } = await api.post(`/search/saved/${queryId}/run`);
  return data;
}

// ==================== Enforcer ====================

export async function getEnforcerMetrics(): Promise<{
  success: boolean;
  available: boolean;
  metrics: EnforcerMetrics | null;
  config?: EnforcerConfig;
  message?: string;
}> {
  const { data } = await api.get('/enforcer/metrics');
  return data;
}

export async function evaluateChunk(
  chunkId: string,
  content: string,
  source: string = 'manual'
): Promise<{ success: boolean; result?: ChunkQualityResult; error?: string }> {
  const { data } = await api.post('/enforcer/evaluate-chunk', null, {
    params: { chunk_id: chunkId, content, source },
  });
  return data;
}

export async function validateIndex(): Promise<{ success: boolean; report?: IndexValidationReport; error?: string }> {
  const { data } = await api.post('/enforcer/validate-index');
  return data;
}

// ==================== Progress Tracking ====================

export interface ProgressState {
  operation_id: string;
  operation_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  total_items: number;
  processed_items: number;
  error_count: number;
  current_batch: number;
  total_batches: number;
  bytes_processed: number;
  context_tokens_used: number;
  embeddings_generated: number;
  start_time: number;
  last_update: number;
  elapsed_seconds: number;
  estimated_remaining_seconds: number;
  items_per_second: number;
  current_phase: string;
  last_message: string;
  error_message: string;
  percent_complete: number;
}

export interface ReindexResponse {
  success: boolean;
  async?: boolean;
  operation_id?: string;
  total_items?: number;
  stream_url?: string;
  status_url?: string;
  indexed?: number;
  errors?: number;
  previous_count?: number;
  db_count?: number;
  message?: string;
  error?: string;
}

export interface ProgressStatusResponse {
  success: boolean;
  operation?: ProgressState;
  formatted?: {
    elapsed: string;
    remaining: string;
    data_processed: string;
    rate: string;
  };
  error?: string;
}

/**
 * Start a customer data reindex operation with real-time progress tracking.
 */
export async function startReindexWithProgress(
  force: boolean = false
): Promise<ReindexResponse> {
  const { data } = await axios.post('/api/data/reindex', null, {
    params: { force, async_mode: true },
  });
  return data;
}

/**
 * Start a synchronous reindex (original behavior, no progress tracking).
 */
export async function startReindexSync(force: boolean = false): Promise<ReindexResponse> {
  const { data } = await axios.post('/api/data/reindex', null, {
    params: { force, async_mode: false },
  });
  return data;
}

/**
 * Get the current status of a reindex operation.
 */
export async function getReindexStatus(operationId: string): Promise<ProgressStatusResponse> {
  const { data } = await axios.get(`/api/data/reindex/status/${operationId}`);
  return data;
}

/**
 * Get all currently active reindex operations.
 */
export async function getActiveOperations(): Promise<{
  success: boolean;
  operations: ProgressState[];
  count: number;
}> {
  const { data } = await axios.get('/api/data/reindex/active');
  return data;
}

/**
 * Create an EventSource for real-time progress streaming.
 * Returns the stream URL and a helper to create the EventSource.
 */
export function createProgressStream(operationId: string): {
  url: string;
  connect: (
    onProgress: (state: ProgressState) => void,
    onComplete: (state: ProgressState) => void,
    onError: (error: string) => void
  ) => EventSource;
} {
  const url = `/api/data/reindex/stream/${operationId}`;

  return {
    url,
    connect: (onProgress, onComplete, onError) => {
      const eventSource = new EventSource(url);

      eventSource.addEventListener('progress', (event) => {
        try {
          const data = JSON.parse((event as MessageEvent).data);
          onProgress(data);
        } catch (e) {
          console.error('Failed to parse progress event:', e);
        }
      });

      eventSource.addEventListener('complete', (event) => {
        try {
          const data = JSON.parse((event as MessageEvent).data);
          onComplete(data);
          eventSource.close();
        } catch (e) {
          console.error('Failed to parse complete event:', e);
        }
      });

      eventSource.addEventListener('error', (event) => {
        try {
          const data = JSON.parse((event as MessageEvent).data);
          onError(data.error || 'Unknown error');
        } catch {
          onError('Connection error');
        }
        eventSource.close();
      });

      eventSource.onerror = () => {
        onError('Connection lost');
        eventSource.close();
      };

      return eventSource;
    },
  };
}
