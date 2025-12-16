/**
 * Application constants - centralized magic values
 */

// File upload constraints
export const ALLOWED_FILE_EXTENSIONS = ['.json', '.md'] as const;
export type AllowedFileExtension = typeof ALLOWED_FILE_EXTENSIONS[number];

export const MAX_FILE_SIZE_MB = 10;
export const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

// API timeouts (ms)
export const API_TIMEOUT = 30000;
export const FILE_UPLOAD_TIMEOUT = 60000;
export const LARGE_FILE_UPLOAD_TIMEOUT = 120000;

// Polling intervals (ms)
export const HEALTH_POLL_INTERVAL = 30000;

// Session
export const SESSION_TTL_HOURS = 1;
