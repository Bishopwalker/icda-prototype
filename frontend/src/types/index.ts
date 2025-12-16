// API Types
export interface GuardrailFlags {
  pii: boolean;
  financial: boolean;
  credentials: boolean;
  offtopic: boolean;
}

export interface QueryRequest {
  query: string;
  bypass_cache?: boolean;
  guardrails?: GuardrailFlags;
  session_id?: string;  // For conversation continuity
}

export interface QueryResponse {
  success: boolean;
  query: string;
  response: string;
  route: 'cache' | 'database' | 'nova';
  cached: boolean;
  blocked: boolean;
  tool?: string;
  latency_ms: number;
  session_id?: string;  // Returned session ID
  file_name?: string;
  file_type?: string;
  file_size?: number;
}

export interface FileQueryRequest {
  query: string;
  file?: File;
  bypass_cache?: boolean;
  guardrails?: GuardrailFlags;
  session_id?: string;  // For conversation continuity
}

export interface HealthStatus {
  status: string;
  redis: boolean;
  opensearch: boolean;
  embedder: boolean;
  nova: boolean;
  customers: number;
}

export interface CacheStats {
  keys: number;
  backend: string;
  ttl_hours: number;
}

// Address Verification Types
export interface AddressRecord {
  id: string;
  name: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  verified?: boolean;
  confidence?: number;
  suggestions?: string[];
}

export interface AddressVerificationRequest {
  addresses: AddressRecord[];
  save_to_pipeline: boolean;
}

export interface AddressVerificationResponse {
  success: boolean;
  total: number;
  verified: number;
  failed: number;
  results: AddressRecord[];
}

// UI Types
export interface ChatMessage {
  id: string;
  type: 'user' | 'bot' | 'error' | 'blocked';
  content: string;
  timestamp: Date;
  metadata?: {
    route?: string;
    latency_ms?: number;
    cached?: boolean;
    tool?: string;
  };
}

export type PaneSize = 'collapsed' | 'normal' | 'expanded' | 'maxExpanded';

export interface UploadedFile {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'error';
  progress: number;
  records?: AddressRecord[];
  error?: string;
}

// AWS Service Status
export interface AWSServiceStatus {
  name: string;
  status: 'online' | 'offline' | 'loading';
  description: string;
}

// Autocomplete Types
export interface AutocompleteItem {
  value: string;
  crid: string;
  name: string;
  city: string;
  state: string;
  score?: number;
  count?: number;  // For city autocomplete
}

export interface AutocompleteResult {
  success: boolean;
  field: 'address' | 'name' | 'city';
  count: number;
  data: AutocompleteItem[];
}

// Semantic Search Types
export interface CustomerSearchResult {
  crid: string;
  name: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  customer_type: 'BUSINESS' | 'INDIVIDUAL';
  status: string;
  move_count: number;
  score: number;
}

export interface SemanticSearchResult {
  success: boolean;
  query: string;
  count: number;
  data: CustomerSearchResult[];
}

// Street Suggestion Types
export interface StreetSuggestion {
  street_name: string;
  street_type: string;
  city: string;
}

export interface StreetSuggestionResult {
  suggestions: StreetSuggestion[];
  zip_code: string;
  partial: string;
}

// Knowledge Base Types
export interface KnowledgeDocument {
  doc_id: string;
  filename: string;
  category: string;
  tags: string[];
  chunk_count: number;
  indexed_at: string;
}

export interface KnowledgeStats {
  available: boolean;
  total_chunks: number;
  unique_documents: number;
  categories: Record<string, number>;
  tags: Record<string, number>;
}

export interface KnowledgeUploadResult {
  success: boolean;
  doc_id?: string;
  filename?: string;
  chunks_indexed?: number;
  errors?: number;
  category?: string;
  tags?: string[];
  error?: string;
}

export interface KnowledgeSearchResult {
  success: boolean;
  query: string;
  hits: KnowledgeHit[];
}

export interface KnowledgeHit {
  doc_id: string;
  filename: string;
  chunk_index: number;
  text: string;
  category: string;
  tags: string[];
  score: number;
}
