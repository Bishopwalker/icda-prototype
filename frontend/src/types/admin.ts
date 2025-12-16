/**
 * Admin UI Types for ICDA
 */

export interface ChunkData {
  chunk_id: string;
  doc_id: string;
  filename: string;
  content: string;
  content_length: number;
  category: string;
  tags: string[];
  quality_score: number;
  created_at: string;
  embedding_preview?: number[];
  embedding_dimensions?: number;
  metadata?: Record<string, unknown>;
}

export interface ChunkListResponse {
  success: boolean;
  chunks: ChunkData[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
  error?: string;
}

export interface IndexStats {
  knowledge: {
    available?: boolean;
    backend?: string;
    total_chunks?: number;
    unique_documents?: number;
    categories?: Record<string, number>;
    tags?: Record<string, number>;
  };
  customers: {
    indexed?: number;
    index_name?: string;
  };
  addresses: {
    available?: boolean;
    total_addresses?: number;
  };
  services: {
    redis: boolean;
    opensearch: boolean;
    embeddings: boolean;
    nova_ai: boolean;
  };
  enforcer: EnforcerMetrics;
}

export interface IndexHealth {
  overall: 'healthy' | 'degraded' | 'unavailable';
  indexes: {
    knowledge?: {
      status: string;
      chunks?: number;
      documents?: number;
    };
    customers?: {
      status: string;
      count?: number;
    };
  };
  issues: string[];
}

export interface EnforcerMetrics {
  available?: boolean;
  chunks_evaluated?: number;
  chunks_passed?: number;
  chunks_failed?: number;
  pass_rate?: number;
  average_quality_score?: number;
  queries_reviewed?: number;
  validations_run?: number;
  last_validation?: string;
}

export interface EnforcerConfig {
  model: string;
  chunk_threshold: number;
  query_sample_rate: number;
  validation_interval_hours: number;
}

export interface SearchTestResult {
  success: boolean;
  results: SearchHit[];
  debug?: {
    query: string;
    index: string;
    filters?: Record<string, unknown>;
    explain: boolean;
    backend?: string;
    search_type?: string;
    elapsed_ms: number;
    result_count: number;
  };
  error?: string;
}

export interface SearchHit {
  doc_id: string;
  filename: string;
  chunk_index?: number;
  text?: string;
  content?: string;
  category: string;
  tags: string[];
  score: number;
}

export interface SavedQuery {
  id: string;
  name: string;
  query: string;
  index?: string;
  filters?: Record<string, unknown>;
  notes?: string;
  created_at: string;
}

export interface ChunkQualityResult {
  passed: boolean;
  overall_score: number;
  coherence: number;
  completeness: number;
  relevance: number;
  issues: string[];
  suggestions: string[];
}

export interface IndexValidationReport {
  health_score: number;
  total_chunks: number;
  sampled_chunks: number;
  duplicate_groups: number;
  stale_chunks: number;
  coverage_gaps: string[];
  recommendations: string[];
}
