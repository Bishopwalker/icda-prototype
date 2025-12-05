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
