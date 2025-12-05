import axios from 'axios';
import type { AxiosInstance } from 'axios';
import type {
  QueryRequest,
  QueryResponse,
  HealthStatus,
  CacheStats,
  AddressVerificationRequest,
  AddressVerificationResponse,
  FileQueryRequest,
} from '../types';

// API base URL - configurable via environment variable
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Create axios instance with defaults
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request/Response interceptors
apiClient.interceptors.request.use((config) => config, (error) => Promise.reject(error));
apiClient.interceptors.response.use((response) => response, (error) => Promise.reject(error));

// API Functions
export const api = {
  // Query endpoint (JSON body)
  query: async (request: QueryRequest): Promise<QueryResponse> => {
    const response = await apiClient.post<QueryResponse>('/api/query', request);
    return response.data;
  },

  // Query with optional file upload (multipart form data)
  queryWithFile: async (request: FileQueryRequest): Promise<QueryResponse> => {
    const formData = new FormData();
    formData.append('query', request.query);
    if (request.file) {
      formData.append('file', request.file);
    }
    formData.append('bypass_cache', String(request.bypass_cache ?? false));
    if (request.session_id) {
      formData.append('session_id', request.session_id);
    }
    if (request.guardrails) {
      formData.append('pii', String(request.guardrails.pii));
      formData.append('financial', String(request.guardrails.financial));
      formData.append('credentials', String(request.guardrails.credentials));
      formData.append('offtopic', String(request.guardrails.offtopic));
    }
    const response = await apiClient.post<QueryResponse>('/api/query-with-file', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 60000, // 1 minute for file uploads
    });
    return response.data;
  },

  // Health check endpoint
  health: async (): Promise<HealthStatus> => {
    const response = await apiClient.get<HealthStatus>('/api/health');
    return response.data;
  },

  // Cache stats endpoint
  cacheStats: async (): Promise<CacheStats> => {
    const response = await apiClient.get<CacheStats>('/api/cache/stats');
    return response.data;
  },

  // Clear cache endpoint
  clearCache: async (): Promise<void> => {
    await apiClient.delete('/api/cache');
  },

  // Session management
  newSession: async (): Promise<{ session_id: string }> => {
    const response = await apiClient.post<{ session_id: string }>('/api/session/new');
    return response.data;
  },

  deleteSession: async (sessionId: string): Promise<void> => {
    await apiClient.delete(`/api/session/${sessionId}`);
  },

  clearAllSessions: async (): Promise<{ count: number }> => {
    const response = await apiClient.delete<{ status: string; count: number }>('/api/sessions');
    return response.data;
  },

  // Address verification endpoint (for file upload)
  verifyAddresses: async (
    request: AddressVerificationRequest
  ): Promise<AddressVerificationResponse> => {
    const response = await apiClient.post<AddressVerificationResponse>(
      '/api/verify-addresses',
      request
    );
    return response.data;
  },

  // Bulk address upload endpoint
  uploadAddressFile: async (
    file: File,
    saveToPipeline: boolean
  ): Promise<AddressVerificationResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('save_to_pipeline', String(saveToPipeline));

    const response = await apiClient.post<AddressVerificationResponse>(
      '/api/upload-addresses',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 120000, // 2 minutes for large files
      }
    );
    return response.data;
  },
};

export default api;
