# Frontend Code Organization & Cleanup Enforcer

**Version:** 1.0.0
**Target:** 20% code reduction (~424 lines) while maintaining 100% functionality
**Current Lines:** 2,120 | **Target Lines:** ~1,700

---

## Executive Summary

This enforcer document provides a comprehensive, step-by-step refactoring plan using the **Enforcer Pattern** - a systematic approach to code cleanup that guarantees functionality preservation while achieving significant code reduction through:

1. **Consolidation** - Merging duplicate logic into shared utilities
2. **Extraction** - Moving embedded components to proper modules
3. **Elimination** - Removing dead code and unused patterns
4. **Optimization** - Replacing verbose patterns with concise alternatives

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [Target Directory Structure](#2-target-directory-structure)
3. [Enforcer Rules](#3-enforcer-rules)
4. [Phase 1: Quick Wins (100+ lines)](#4-phase-1-quick-wins)
5. [Phase 2: Component Extraction (80+ lines)](#5-phase-2-component-extraction)
6. [Phase 3: Utility Consolidation (100+ lines)](#6-phase-3-utility-consolidation)
7. [Phase 4: Pattern Optimization (100+ lines)](#7-phase-4-pattern-optimization)
8. [TypeScript/React Pattern Standards](#8-typescriptreact-pattern-standards)
9. [Validation Checklist](#9-validation-checklist)
10. [Implementation Order](#10-implementation-order)

---

## 1. Current State Analysis

### File Inventory (Lines of Code)

| File | Lines | Issues | Reduction Target |
|------|-------|--------|------------------|
| `QueryInput.tsx` | 332 | Oversized, mixed concerns | -80 lines |
| `theme/styles.ts` | 364 | Good but has unused styles | -40 lines |
| `theme/index.ts` | 232 | Clean, minor optimization | -10 lines |
| `ChatPanel.tsx` | 158 | Embedded sub-components | -30 lines |
| `Header.tsx` | 164 | Inline status logic duplication | -25 lines |
| `useQuery.ts` | 154 | Console.logs, verbose patterns | -20 lines |
| `api.ts` | 147 | Console.logs in interceptors | -15 lines |
| `GuardrailsPanel.tsx` | 138 | Verbose toggle button styling | -20 lines |
| `AWSToolingPanel.tsx` | 139 | Duplicate status color logic | -25 lines |
| `types/index.ts` | 117 | AWS_SERVICES const in wrong place | -10 lines |
| `useHealth.ts` | 73 | Clean, minor | -5 lines |
| `App.tsx` | 92 | Clean, minor | -5 lines |
| `App.css` | 43 | **UNUSED - DELETE** | -43 lines |
| `index.css` | 69 | Partially used | -20 lines |
| `main.tsx` | 10 | Trivial | 0 lines |

**Total Reduction Target: ~448 lines (21%)**

### Critical Issues Identified

1. **`App.css` is completely unused** - 43 lines of dead code
2. **Duplicate status color logic** in Header.tsx and AWSToolingPanel.tsx
3. **Embedded components** in ChatPanel.tsx (RouteChip, MessageBubble)
4. **Export utilities** hardcoded in QueryInput.tsx (should be shared)
5. **Console.log statements** throughout (should use logger or remove)
6. **Verbose inline styles** that duplicate theme/styles.ts patterns
7. **AWS_SERVICES const** in types file (should be in constants)

---

## 2. Target Directory Structure

```
frontend/src/
├── components/
│   ├── chat/                    # NEW: Chat feature components
│   │   ├── ChatPanel.tsx        # Refactored (imports sub-components)
│   │   ├── MessageBubble.tsx    # EXTRACTED from ChatPanel
│   │   ├── RouteChip.tsx        # EXTRACTED from ChatPanel
│   │   └── index.ts             # Barrel export
│   ├── input/                   # NEW: Input feature components
│   │   ├── QueryInput.tsx       # Refactored (lighter)
│   │   └── index.ts
│   ├── layout/                  # NEW: Layout components
│   │   ├── Header.tsx           # Refactored
│   │   ├── Sidebar.tsx          # Optional future extraction
│   │   └── index.ts
│   ├── panels/                  # NEW: Panel components
│   │   ├── AWSToolingPanel.tsx  # Refactored
│   │   ├── GuardrailsPanel.tsx  # Refactored
│   │   └── index.ts
│   └── common/                  # NEW: Shared UI components
│       ├── StatusChip.tsx       # NEW: Unified status indicator
│       └── index.ts
├── hooks/
│   ├── useHealth.ts
│   ├── useQuery.ts
│   └── index.ts                 # NEW: Barrel export
├── services/
│   ├── api.ts
│   └── index.ts
├── utils/                       # NEW: Utility functions
│   ├── constants.ts             # NEW: All magic values
│   ├── formatters.ts            # NEW: Export utilities (from QueryInput)
│   ├── download.ts              # NEW: Download utilities
│   └── index.ts
├── theme/
│   ├── index.ts                 # Theme config
│   └── styles.ts                # Component styles
├── types/
│   └── index.ts                 # Type definitions only
├── App.tsx
├── main.tsx
└── index.css                    # Minimal global styles
```

**Files to DELETE:**
- `App.css` (unused)

---

## 3. Enforcer Rules

### Rule E1: No Embedded Component Definitions
```typescript
// VIOLATION: Component defined inside another component file
const SubComponent: React.FC = () => { ... };
export const ParentComponent: React.FC = () => {
  return <SubComponent />;
};

// ENFORCED: Separate files with barrel exports
// SubComponent.tsx
export const SubComponent: React.FC = () => { ... };

// ParentComponent.tsx
import { SubComponent } from './SubComponent';
export const ParentComponent: React.FC = () => {
  return <SubComponent />;
};
```

### Rule E2: No Duplicate Logic Across Files
```typescript
// VIOLATION: Same function in multiple files
// File A: const getStatusColor = (status) => { switch... }
// File B: const getStatusColor = (status) => { switch... }

// ENFORCED: Single source in utils
// utils/status.ts
export const getStatusColor = (status: Status): string => { ... };
```

### Rule E3: No Console.log in Production Code
```typescript
// VIOLATION
console.log('[API]', data);

// ENFORCED: Remove or use conditional logging
if (import.meta.env.DEV) {
  console.log('[API]', data);
}
// OR: Remove entirely for production builds
```

### Rule E4: Constants in Dedicated Files
```typescript
// VIOLATION: Constants mixed with types
// types/index.ts
export const AWS_SERVICES = [...];

// ENFORCED: Separate concerns
// utils/constants.ts
export const AWS_SERVICES = [...];
// types/index.ts
export interface AWSService { ... }
```

### Rule E5: Styles Referenced, Not Duplicated
```typescript
// VIOLATION: Inline styles duplicating theme
sx={{ backgroundColor: `${colors.success.main}22`, color: colors.success.main }}

// ENFORCED: Use theme/styles.ts patterns
sx={styles.status.online}
```

### Rule E6: Single Responsibility Components (<200 lines)
```typescript
// VIOLATION: Component handling input, export, file upload, download
// QueryInput.tsx (332 lines)

// ENFORCED: Split by responsibility
// QueryInput.tsx (~150 lines) - Text input only
// utils/download.ts (~40 lines) - Download logic
// utils/formatters.ts (~30 lines) - Message conversion
```

### Rule E7: Type-Safe Event Handlers
```typescript
// VIOLATION: Inline arrow functions in JSX
onClick={(e) => handleClick(e.target.value)}

// ENFORCED: Named handlers with proper types
const handleClick = useCallback((e: React.MouseEvent<HTMLButtonElement>) => {
  // ...
}, [deps]);
```

### Rule E8: Barrel Exports for Features
```typescript
// VIOLATION: Deep imports
import { ChatPanel } from '../components/ChatPanel';
import { MessageBubble } from '../components/MessageBubble';

// ENFORCED: Barrel exports
// components/chat/index.ts
export { ChatPanel } from './ChatPanel';
export { MessageBubble } from './MessageBubble';

// Usage
import { ChatPanel, MessageBubble } from '../components/chat';
```

---

## 4. Phase 1: Quick Wins (100+ lines)

### 4.1 Delete Unused Files (-43 lines)

**Action:** Delete `src/App.css`

```bash
rm frontend/src/App.css
```

**Verification:** Grep for App.css imports - should find none.

### 4.2 Remove Console.log Statements (-25 lines)

**Files to modify:**
- `services/api.ts`: Remove interceptor console.logs
- `hooks/useQuery.ts`: Remove session console.logs

**Before (api.ts:26-34):**
```typescript
apiClient.interceptors.request.use(
  (config) => {
    console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);
```

**After:**
```typescript
apiClient.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error)
);
```

**Before (useQuery.ts:40, 124, 136):**
```typescript
console.log('[Session] New session started:', currentSessionId);
console.log('[Session] Cleared');
console.log('[Session] New session:', newId);
```

**After:** Remove all three lines.

### 4.3 Simplify index.css (-20 lines)

**Current:** 69 lines with animations that MUI handles
**Target:** ~49 lines - remove duplicate reset styles MUI provides

**Remove:**
```css
/* MUI CssBaseline handles these */
*, *::before, *::after { box-sizing: border-box; }
body { margin: 0; ... }
```

---

## 5. Phase 2: Component Extraction (80+ lines)

### 5.1 Extract RouteChip from ChatPanel (-15 lines net gain)

**Create:** `src/components/chat/RouteChip.tsx`

```typescript
import React from 'react';
import { Chip } from '@mui/material';
import {
  Cached as CacheIcon,
  Storage as DatabaseIcon,
  Cloud as NovaIcon,
} from '@mui/icons-material';
import { colors } from '../../theme';

const ROUTE_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  cache: { icon: <CacheIcon sx={{ fontSize: 14 }} />, color: colors.routes.cache, label: 'Cache' },
  database: { icon: <DatabaseIcon sx={{ fontSize: 14 }} />, color: colors.routes.database, label: 'Database' },
  nova: { icon: <NovaIcon sx={{ fontSize: 14 }} />, color: colors.routes.nova, label: 'Nova' },
};

interface RouteChipProps {
  route: string;
}

export const RouteChip: React.FC<RouteChipProps> = ({ route }) => {
  const config = ROUTE_CONFIG[route] || { icon: null, color: colors.info.main, label: route };
  return (
    <Chip
      icon={config.icon || undefined}
      label={config.label}
      size="small"
      sx={{
        backgroundColor: `${config.color}22`,
        color: config.color,
        fontSize: '0.7rem',
        height: 20,
      }}
    />
  );
};
```

### 5.2 Extract MessageBubble from ChatPanel (-30 lines net gain)

**Create:** `src/components/chat/MessageBubble.tsx`

```typescript
import React from 'react';
import { Box, Typography, Paper, Chip } from '@mui/material';
import {
  Cached as CacheIcon,
  AccessTime as TimeIcon,
  Block as BlockedIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import { styles } from '../../theme/styles';
import { colors } from '../../theme';
import { RouteChip } from './RouteChip';
import type { ChatMessage } from '../../types';

interface MessageBubbleProps {
  message: ChatMessage;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.type === 'user';
  const isBlocked = message.type === 'blocked';
  const isError = message.type === 'error';

  const bubbleStyle = {
    ...styles.chat.message.base,
    ...(isUser && styles.chat.message.user),
    ...(message.type === 'bot' && styles.chat.message.bot),
    ...(isBlocked && styles.chat.message.blocked),
    ...(isError && styles.chat.message.error),
  };

  return (
    <Paper sx={bubbleStyle} elevation={0}>
      {(isBlocked || isError) && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          {isBlocked ? <BlockedIcon sx={{ fontSize: 16, color: colors.warning.main }} />
                     : <ErrorIcon sx={{ fontSize: 16, color: colors.error.main }} />}
          <Typography variant="caption" fontWeight={600} color={isBlocked ? 'warning.main' : 'error.main'}>
            {isBlocked ? 'Blocked by Guardrail' : 'Error'}
          </Typography>
        </Box>
      )}
      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
        {message.content}
      </Typography>
      {message.metadata && (
        <Box sx={styles.chat.metadata}>
          {message.metadata.route && <RouteChip route={message.metadata.route} />}
          {message.metadata.cached && (
            <Chip icon={<CacheIcon sx={{ fontSize: 12 }} />} label="Cached" size="small"
              sx={{ fontSize: '0.65rem', height: 18, backgroundColor: `${colors.success.main}22`, color: colors.success.light }} />
          )}
          {message.metadata.tool && <Chip label={message.metadata.tool} size="small" sx={{ fontSize: '0.65rem', height: 18 }} />}
          {message.metadata.latency_ms !== undefined && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
              <TimeIcon sx={{ fontSize: 12 }} />
              <Typography variant="caption">{message.metadata.latency_ms}ms</Typography>
            </Box>
          )}
        </Box>
      )}
    </Paper>
  );
};
```

### 5.3 Refactored ChatPanel (-60 lines from original)

```typescript
import React, { useRef, useEffect } from 'react';
import { Box, Typography, CircularProgress } from '@mui/material';
import { styles } from '../../theme/styles';
import { MessageBubble } from './MessageBubble';
import type { ChatMessage } from '../../types';

interface ChatPanelProps {
  messages: ChatMessage[];
  loading: boolean;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ messages, loading }) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', flexGrow: 1, minHeight: 0, overflow: 'hidden' }}>
      <Box ref={scrollRef} sx={{ ...styles.chat.container, flexGrow: 1, minHeight: 200, maxHeight: 'none', overflowY: 'auto' }}>
        {messages.length === 0 ? (
          <Box sx={{ ...styles.utils.flexCenter, flexGrow: 1, flexDirection: 'column', gap: 2, opacity: 0.5 }}>
            <Typography variant="h6">ICDA Query Interface</Typography>
            <Typography variant="body2" color="text.secondary">
              Ask questions about customer data. Try "Show me John Smith's account" or "List customers in Texas".
            </Typography>
          </Box>
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
        )}
        {loading && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, alignSelf: 'flex-start', p: 2 }}>
            <CircularProgress size={20} />
            <Typography variant="body2" color="text.secondary">Processing query...</Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
};
```

---

## 6. Phase 3: Utility Consolidation (100+ lines)

### 6.1 Create utils/constants.ts

**Move from types/index.ts:**

```typescript
// utils/constants.ts
import type { AWSServiceStatus } from '../types';

export const AWS_SERVICES: AWSServiceStatus[] = [
  { name: 'Bedrock Nova', status: 'loading', description: 'NLP Query Processing' },
  { name: 'Titan Embeddings', status: 'loading', description: 'Vector Embeddings' },
  { name: 'ElastiCache', status: 'loading', description: 'Redis Caching' },
  { name: 'OpenSearch', status: 'loading', description: 'Vector Index' },
];

export const ALLOWED_FILE_EXTENSIONS = ['.json', '.md'] as const;
export const MAX_FILE_SIZE_MB = 10;

export const STATUS_COLORS = {
  online: '#4caf50',
  offline: '#d32f2f',
  loading: '#ed6c02',
} as const;
```

### 6.2 Create utils/download.ts (Extract from QueryInput)

```typescript
// utils/download.ts
import type { ChatMessage } from '../types';

export const messagesToJson = (messages: ChatMessage[]): string => {
  return JSON.stringify(messages.map(msg => ({
    id: msg.id,
    type: msg.type,
    content: msg.content,
    timestamp: msg.timestamp.toISOString(),
    route: msg.metadata?.route ?? null,
    latency_ms: msg.metadata?.latency_ms ?? null,
    cached: msg.metadata?.cached ?? false,
    tool: msg.metadata?.tool ?? null,
  })), null, 2);
};

export const messagesToCsv = (messages: ChatMessage[]): string => {
  const headers = ['ID', 'Type', 'Content', 'Timestamp', 'Route', 'Latency (ms)', 'Cached', 'Tool'];
  const rows = messages.map(msg => [
    msg.id,
    msg.type,
    `"${msg.content.replace(/"/g, '""')}"`,
    msg.timestamp.toISOString(),
    msg.metadata?.route ?? '',
    msg.metadata?.latency_ms?.toString() ?? '',
    msg.metadata?.cached ? 'Yes' : 'No',
    msg.metadata?.tool ?? '',
  ]);
  return [headers.join(','), ...rows.map(row => row.join(','))].join('\n');
};

export const downloadFile = (content: string, filename: string, mimeType: string): void => {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement('a'), { href: url, download: filename });
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

export const downloadMessages = (messages: ChatMessage[], format: 'json' | 'csv'): void => {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const content = format === 'json' ? messagesToJson(messages) : messagesToCsv(messages);
  const mimeType = format === 'json' ? 'application/json' : 'text/csv';
  downloadFile(content, `icda-chat-${timestamp}.${format}`, mimeType);
};
```

### 6.3 Create utils/status.ts (Consolidate duplicate logic)

```typescript
// utils/status.ts
import { colors } from '../theme';

export type Status = 'online' | 'offline' | 'loading';

export const getStatusColor = (status: Status): string => {
  const statusColors: Record<Status, string> = {
    online: colors.success.main,
    offline: colors.error.main,
    loading: colors.warning.main,
  };
  return statusColors[status];
};

export const getStatusBgColor = (status: Status, alpha = '22'): string =>
  `${getStatusColor(status)}${alpha}`;
```

### 6.4 Create Barrel Exports

```typescript
// utils/index.ts
export * from './constants';
export * from './download';
export * from './status';

// hooks/index.ts
export { useHealth } from './useHealth';
export { useQuery } from './useQuery';

// components/chat/index.ts
export { ChatPanel } from './ChatPanel';
export { MessageBubble } from './MessageBubble';
export { RouteChip } from './RouteChip';
```

---

## 7. Phase 4: Pattern Optimization (100+ lines)

### 7.1 Refactored QueryInput.tsx (Target: ~200 lines from 332)

```typescript
import React, { useState, useRef, useCallback } from 'react';
import type { KeyboardEvent, ChangeEvent } from 'react';
import {
  Box, TextField, IconButton, Tooltip, FormControlLabel, Switch,
  Button, Chip, Menu, MenuItem, ListItemIcon, ListItemText,
} from '@mui/material';
import {
  Send as SendIcon, Clear as ClearIcon, Add as AddIcon, UploadFile as UploadIcon,
  Close as CloseIcon, Download as DownloadIcon, DataObject as JsonIcon, TableChart as CsvIcon,
} from '@mui/icons-material';
import { styles } from '../theme/styles';
import { colors } from '../theme';
import { downloadMessages, ALLOWED_FILE_EXTENSIONS } from '../utils';
import type { ChatMessage } from '../types';

interface QueryInputProps {
  onSend: (query: string, file?: File) => Promise<void>;
  onClear: () => void;
  loading: boolean;
  bypassCache: boolean;
  onBypassCacheChange: (value: boolean) => void;
  messages: ChatMessage[];
}

export const QueryInput: React.FC<QueryInputProps> = ({
  onSend, onClear, loading, bypassCache, onBypassCacheChange, messages,
}) => {
  const [query, setQuery] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [downloadAnchor, setDownloadAnchor] = useState<HTMLElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = useCallback(async () => {
    const trimmed = query.trim();
    if (!trimmed || loading) return;
    const file = selectedFile;
    setQuery('');
    setSelectedFile(null);
    await onSend(trimmed, file ?? undefined);
  }, [query, loading, selectedFile, onSend]);

  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  }, [handleSend]);

  const handleFileSelect = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const ext = `.${file.name.split('.').pop()?.toLowerCase()}`;
      if (ALLOWED_FILE_EXTENSIONS.includes(ext as typeof ALLOWED_FILE_EXTENSIONS[number])) {
        setSelectedFile(file);
      } else {
        alert(`Only ${ALLOWED_FILE_EXTENSIONS.join(', ')} files supported`);
      }
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  return (
    <Box sx={styles.input.container}>
      <input type="file" ref={fileInputRef} onChange={handleFileSelect} accept=".json,.md" style={{ display: 'none' }} />

      {selectedFile && (
        <Box sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip icon={<UploadIcon sx={{ fontSize: 16 }} />} label={selectedFile.name}
            onDelete={() => setSelectedFile(null)} deleteIcon={<CloseIcon sx={{ fontSize: 16 }} />}
            sx={{ backgroundColor: `${colors.info.main}22`, borderColor: colors.info.main, border: 1 }} />
          <Box sx={{ fontSize: 12, color: 'text.secondary' }}>File will be sent with your query</Box>
        </Box>
      )}

      <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
        <TextField fullWidth multiline maxRows={4} placeholder="Ask a question about customer data..."
          value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={handleKeyDown}
          disabled={loading} sx={styles.input.field} slotProps={{ input: { sx: { py: 1.5, px: 2 } } }} />
        <Tooltip title="Send query">
          <span>
            <IconButton onClick={handleSend} disabled={loading || !query.trim()} color="primary"
              sx={{ backgroundColor: 'primary.main', color: 'white', '&:hover': { backgroundColor: 'primary.dark' }, '&:disabled': { backgroundColor: 'action.disabledBackground' } }}>
              <SendIcon />
            </IconButton>
          </span>
        </Tooltip>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mt: 1 }}>
        <FormControlLabel control={<Switch size="small" checked={bypassCache} onChange={(e) => onBypassCacheChange(e.target.checked)} />}
          label="Bypass Cache" slotProps={{ typography: { variant: 'caption', color: 'text.secondary' } }} />

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Attach .json or .md file">
            <Button size="small" startIcon={<AddIcon />} onClick={() => fileInputRef.current?.click()} disabled={loading}
              sx={{ color: colors.aws.orange, borderColor: colors.aws.orange, border: 1, '&:hover': { backgroundColor: `${colors.aws.orange}11` } }}>
              Add File
            </Button>
          </Tooltip>
          {messages.length > 0 && (
            <>
              <Tooltip title="Download chat results">
                <Button size="small" startIcon={<DownloadIcon />} onClick={(e) => setDownloadAnchor(e.currentTarget)}
                  sx={{ color: colors.info.light, borderColor: colors.info.light, border: 1, '&:hover': { backgroundColor: `${colors.info.main}11` } }}>
                  Download
                </Button>
              </Tooltip>
              <Menu anchorEl={downloadAnchor} open={Boolean(downloadAnchor)} onClose={() => setDownloadAnchor(null)}
                anchorOrigin={{ vertical: 'top', horizontal: 'right' }} transformOrigin={{ vertical: 'bottom', horizontal: 'right' }}>
                <MenuItem onClick={() => { downloadMessages(messages, 'json'); setDownloadAnchor(null); }}>
                  <ListItemIcon><JsonIcon fontSize="small" /></ListItemIcon>
                  <ListItemText>Download as JSON</ListItemText>
                </MenuItem>
                <MenuItem onClick={() => { downloadMessages(messages, 'csv'); setDownloadAnchor(null); }}>
                  <ListItemIcon><CsvIcon fontSize="small" /></ListItemIcon>
                  <ListItemText>Download as CSV</ListItemText>
                </MenuItem>
              </Menu>
            </>
          )}
        </Box>
        <Button size="small" startIcon={<ClearIcon />} onClick={onClear} disabled={messages.length === 0} sx={{ color: 'text.secondary' }}>
          New Chat
        </Button>
      </Box>
    </Box>
  );
};

export default QueryInput;
```

### 7.2 Refactored AWSToolingPanel.tsx (Target: ~100 lines from 139)

```typescript
import React from 'react';
import { Box, Typography, Card, CardContent, Chip, Stack } from '@mui/material';
import { Cloud as CloudIcon, Storage as StorageIcon, Memory as MemoryIcon, Search as SearchIcon,
  CheckCircle as CheckIcon, Cancel as CancelIcon, HourglassEmpty as LoadingIcon } from '@mui/icons-material';
import { colors } from '../theme';
import { getStatusColor, getStatusBgColor, type Status } from '../utils/status';
import type { HealthStatus } from '../types';

interface AWSToolingPanelProps { health: HealthStatus | null; loading: boolean; }

const SERVICES = [
  { name: 'Bedrock Nova', desc: 'NLP Query Processing', icon: <CloudIcon />, key: 'nova' as const },
  { name: 'Titan Embeddings', desc: 'Vector Embeddings', icon: <MemoryIcon />, key: 'embedder' as const },
  { name: 'ElastiCache', desc: 'Redis Caching', icon: <StorageIcon />, key: 'redis' as const },
  { name: 'OpenSearch', desc: 'Vector Index', icon: <SearchIcon />, key: 'opensearch' as const },
] as const;

const StatusIcon: React.FC<{ status: Status }> = ({ status }) => {
  const icons = { online: CheckIcon, offline: CancelIcon, loading: LoadingIcon };
  const Icon = icons[status];
  return <Icon sx={{ color: getStatusColor(status), fontSize: 16 }} />;
};

export const AWSToolingPanel: React.FC<AWSToolingPanelProps> = ({ health, loading }) => (
  <Box sx={{ p: 2 }}>
    <Typography variant="h6" sx={{ mb: 2, color: colors.aws.orange }}>AWS Tooling</Typography>
    <Stack spacing={1.5}>
      {SERVICES.map(({ name, desc, icon, key }) => {
        const status: Status = loading ? 'loading' : health === null ? 'loading' : health[key] ? 'online' : 'offline';
        return (
          <Card key={name} sx={{ backgroundColor: 'background.elevated', border: 1, borderColor: getStatusBgColor(status, '44') }}>
            <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                  <Box sx={{ color: colors.aws.orange }}>{icon}</Box>
                  <Box>
                    <Typography variant="body2" fontWeight={600}>{name}</Typography>
                    <Typography variant="caption" color="text.secondary">{desc}</Typography>
                  </Box>
                </Box>
                <Chip icon={<StatusIcon status={status} />} label={status} size="small"
                  sx={{ backgroundColor: getStatusBgColor(status), color: getStatusColor(status), textTransform: 'capitalize', fontSize: '0.7rem', height: 24 }} />
              </Box>
            </CardContent>
          </Card>
        );
      })}
    </Stack>
  </Box>
);

export default AWSToolingPanel;
```

### 7.3 Refactored Header.tsx (Target: ~120 lines from 164)

```typescript
import React, { useState, useCallback } from 'react';
import { Box, Typography, Chip, IconButton, Tooltip } from '@mui/material';
import { Refresh as RefreshIcon, Storage as StorageIcon, Cloud as CloudIcon,
  DeleteSweep as ClearCacheIcon, AddComment as NewChatIcon, Forum as SessionIcon } from '@mui/icons-material';
import { styles } from '../theme/styles';
import { colors } from '../theme';
import type { HealthStatus, CacheStats } from '../types';

interface HeaderProps {
  health: HealthStatus | null;
  cacheStats: CacheStats | null;
  sessionId: string | null;
  onRefresh: () => void;
  onClearCache: () => void;
  onNewSession: () => void;
  loading: boolean;
}

const StatusChip: React.FC<{ active: boolean; icon: React.ReactNode; activeLabel: string; inactiveLabel: string; color: string }> =
  ({ active, icon, activeLabel, inactiveLabel, color }) => (
    <Chip icon={icon} label={active ? activeLabel : inactiveLabel} size="small"
      sx={{ backgroundColor: `${active ? color : colors.neutral.main}22`, color: active ? color : colors.neutral.light,
        borderColor: active ? color : colors.neutral.main, border: 1 }} />
  );

export const Header: React.FC<HeaderProps> = ({ health, cacheStats, sessionId, onRefresh, onClearCache, onNewSession, loading }) => {
  const [clearing, setClearing] = useState(false);
  const handleClearCache = useCallback(async () => { setClearing(true); await onClearCache(); setClearing(false); }, [onClearCache]);

  return (
    <Box sx={styles.header.root}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Typography variant="h4" sx={styles.header.title}>USPS ICDA Prototype</Typography>
        <Typography variant="body2" color="text.secondary">Intelligent Customer Data Access by ECS</Typography>
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Tooltip title={sessionId ? `Session: ${sessionId.slice(0, 8)}...` : 'No active session'}>
          <span><StatusChip active={!!sessionId} icon={<SessionIcon />} activeLabel="Context Active" inactiveLabel="No Context" color={colors.primary.main} /></span>
        </Tooltip>
        <Tooltip title="Start New Conversation">
          <IconButton onClick={onNewSession} size="small" sx={{ color: colors.primary.light, '&:hover': { backgroundColor: `${colors.primary.main}22` } }}>
            <NewChatIcon />
          </IconButton>
        </Tooltip>
        <StatusChip active={health?.nova ?? false} icon={<CloudIcon />} activeLabel="Nova Connected" inactiveLabel="Nova Unavailable" color={colors.success.main} />
        <Chip icon={<StorageIcon />} label={`${cacheStats?.keys ?? 0} cached`} size="small"
          sx={{ backgroundColor: `${colors.info.main}22`, color: colors.info.light, borderColor: colors.info.main, border: 1 }} />
        <Tooltip title="Clear Redis Cache">
          <IconButton onClick={handleClearCache} disabled={clearing || loading || (cacheStats?.keys ?? 0) === 0} size="small"
            sx={{ color: colors.error.light, '&:hover': { backgroundColor: `${colors.error.main}22` } }}>
            <ClearCacheIcon sx={{ animation: clearing ? 'spin 1s linear infinite' : 'none' }} />
          </IconButton>
        </Tooltip>
        {health && <Chip label={`${health.customers.toLocaleString()} customers`} size="small" variant="outlined" />}
        <Tooltip title="Refresh status">
          <IconButton onClick={onRefresh} disabled={loading} size="small" sx={{ color: 'text.secondary' }}>
            <RefreshIcon sx={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          </IconButton>
        </Tooltip>
      </Box>
    </Box>
  );
};

export default Header;
```

---

## 8. TypeScript/React Pattern Standards

### 8.1 Component Definition Standard

```typescript
// ENFORCED PATTERN: Named exports with React.FC typing
interface ComponentProps {
  requiredProp: string;
  optionalProp?: number;
}

export const Component: React.FC<ComponentProps> = ({ requiredProp, optionalProp = 10 }) => {
  // Implementation
};

// Also export as default for lazy loading compatibility
export default Component;
```

### 8.2 Hook Return Type Standard

```typescript
// ENFORCED PATTERN: Explicit return type interface
export interface UseHookReturn {
  data: DataType | null;
  loading: boolean;
  error: string | null;
  actions: {
    refresh: () => Promise<void>;
    clear: () => void;
  };
}

export function useHook(): UseHookReturn {
  // Implementation
  return { data, loading, error, actions: { refresh, clear } };
}
```

### 8.3 Event Handler Standard

```typescript
// ENFORCED PATTERN: Named handlers with proper typing
const handleClick = useCallback((event: React.MouseEvent<HTMLButtonElement>) => {
  event.preventDefault();
  // Logic
}, [dependencies]);

const handleChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
  setValue(event.target.value);
}, []);
```

### 8.4 Style Application Standard

```typescript
// ENFORCED PATTERN: Use centralized styles, spread for variants
import { styles } from '../theme/styles';

// Good - Reference centralized styles
<Box sx={styles.layout.root} />

// Good - Spread with conditional additions
<Paper sx={{ ...styles.chat.message.base, ...(isUser && styles.chat.message.user) }} />

// Avoid - Inline object literals
<Box sx={{ display: 'flex', padding: 2 }} /> // Only for truly one-off styles
```

### 8.5 Import Organization Standard

```typescript
// ENFORCED ORDER:
// 1. React/framework imports
import React, { useState, useCallback, useEffect } from 'react';
import type { FC, ReactNode } from 'react';

// 2. Third-party libraries
import { Box, Typography } from '@mui/material';
import { Cloud as CloudIcon } from '@mui/icons-material';

// 3. Internal absolute imports (utils, hooks, services)
import { useHealth, useQuery } from '../hooks';
import { downloadMessages } from '../utils';
import api from '../services/api';

// 4. Internal relative imports (components, styles)
import { styles } from '../theme/styles';
import { colors } from '../theme';

// 5. Type imports (always last)
import type { ComponentProps, DataType } from '../types';
```

---

## 9. Validation Checklist

### Pre-Refactor Validation

- [ ] All existing tests pass
- [ ] App runs without errors
- [ ] All features work as expected
- [ ] Git working tree is clean (commit current state)

### Per-Phase Validation

After each phase:
- [ ] `npm run build` succeeds
- [ ] `npm run lint` passes with no errors
- [ ] App starts without console errors
- [ ] Test affected features manually:
  - [ ] Query submission works
  - [ ] File upload works
  - [ ] Download (JSON/CSV) works
  - [ ] Guardrail toggles work
  - [ ] Cache clear works
  - [ ] Session management works
  - [ ] AWS status indicators update

### Post-Refactor Validation

- [ ] Total lines reduced by 20%+ (target: 1,700 or less)
- [ ] All original features still work
- [ ] No TypeScript errors
- [ ] No console errors in browser
- [ ] Lighthouse performance score maintained or improved
- [ ] All components render correctly
- [ ] Responsive layout intact

---

## 10. Implementation Order

### Execution Sequence

```
Phase 1: Quick Wins (Day 1)
├── 1.1 Delete App.css
├── 1.2 Remove console.logs from api.ts
├── 1.3 Remove console.logs from useQuery.ts
├── 1.4 Trim index.css
└── VALIDATE: Build + Manual Test

Phase 2: Utility Extraction (Day 1-2)
├── 2.1 Create utils/constants.ts
├── 2.2 Create utils/download.ts
├── 2.3 Create utils/status.ts
├── 2.4 Create utils/index.ts barrel
├── 2.5 Update types/index.ts (remove AWS_SERVICES)
└── VALIDATE: Build + Manual Test

Phase 3: Component Extraction (Day 2)
├── 3.1 Create components/chat/ directory
├── 3.2 Extract RouteChip.tsx
├── 3.3 Extract MessageBubble.tsx
├── 3.4 Refactor ChatPanel.tsx
├── 3.5 Create components/chat/index.ts barrel
└── VALIDATE: Build + Manual Test

Phase 4: Component Optimization (Day 3)
├── 4.1 Refactor QueryInput.tsx
├── 4.2 Refactor AWSToolingPanel.tsx
├── 4.3 Refactor Header.tsx
├── 4.4 Update App.tsx imports
└── VALIDATE: Full Test Suite

Phase 5: Cleanup & Documentation (Day 3)
├── 5.1 Run lint --fix
├── 5.2 Verify no unused imports
├── 5.3 Final line count audit
├── 5.4 Update README if needed
└── FINAL VALIDATION: Complete Feature Test
```

### Git Commit Strategy

```bash
# Phase 1
git add -A && git commit -m "refactor(frontend): remove unused App.css and console.logs"

# Phase 2
git add -A && git commit -m "refactor(frontend): extract utility functions to utils/"

# Phase 3
git add -A && git commit -m "refactor(frontend): extract chat sub-components"

# Phase 4
git add -A && git commit -m "refactor(frontend): optimize component implementations"

# Phase 5
git add -A && git commit -m "chore(frontend): cleanup and final validation"
```

---

## Summary

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Total Lines | 2,120 | ~1,700 | -20% |
| Files | 13 | 18 | +5 (better organization) |
| Components | 5 | 8 | +3 (extracted) |
| Utility Files | 0 | 4 | +4 (centralized) |
| Duplicate Logic | 3 instances | 0 | Eliminated |
| Dead Code | 43 lines | 0 | Deleted |

**Key Benefits:**
1. **Maintainability**: Smaller, focused components
2. **Reusability**: Shared utilities prevent duplication
3. **Testability**: Extracted logic is unit-testable
4. **Type Safety**: Stricter patterns enforce correctness
5. **Performance**: Smaller bundle potential with code splitting

---

**Document Version:** 1.0.0
**Created:** 2025-12-05
**Author:** Code Enforcer Pattern System
