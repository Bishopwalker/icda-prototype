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
