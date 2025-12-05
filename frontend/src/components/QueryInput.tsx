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
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
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

  const handleDownload = useCallback((format: 'json' | 'csv') => {
    downloadMessages(messages, format);
    setDownloadAnchor(null);
  }, [messages]);

  return (
    <Box sx={styles.input.container}>
      <input type="file" ref={fileInputRef} onChange={handleFileSelect} accept=".json,.md" style={{ display: 'none' }} />

      {selectedFile && (
        <Box sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip
            icon={<UploadIcon sx={{ fontSize: 16 }} />}
            label={selectedFile.name}
            onDelete={() => setSelectedFile(null)}
            deleteIcon={<CloseIcon sx={{ fontSize: 16 }} />}
            sx={{ backgroundColor: `${colors.info.main}22`, borderColor: colors.info.main, border: 1 }}
          />
          <Box sx={{ fontSize: 12, color: 'text.secondary' }}>File will be sent with your query</Box>
        </Box>
      )}

      <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
        <TextField
          fullWidth multiline maxRows={4}
          placeholder="Ask a question about customer data..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          sx={styles.input.field}
          slotProps={{ input: { sx: { py: 1.5, px: 2 } } }}
        />
        <Tooltip title="Send query">
          <span>
            <IconButton
              onClick={handleSend}
              disabled={loading || !query.trim()}
              color="primary"
              sx={{
                backgroundColor: 'primary.main', color: 'white',
                '&:hover': { backgroundColor: 'primary.dark' },
                '&:disabled': { backgroundColor: 'action.disabledBackground' },
              }}
            >
              <SendIcon />
            </IconButton>
          </span>
        </Tooltip>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mt: 1 }}>
        <FormControlLabel
          control={<Switch size="small" checked={bypassCache} onChange={(e) => onBypassCacheChange(e.target.checked)} />}
          label="Bypass Cache"
          slotProps={{ typography: { variant: 'caption', color: 'text.secondary' } }}
        />

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Attach .json or .md file">
            <Button
              size="small" startIcon={<AddIcon />}
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
              sx={{ color: colors.aws.orange, borderColor: colors.aws.orange, border: 1, '&:hover': { backgroundColor: `${colors.aws.orange}11` } }}
            >
              Add File
            </Button>
          </Tooltip>

          {messages.length > 0 && (
            <>
              <Tooltip title="Download chat results">
                <Button
                  size="small" startIcon={<DownloadIcon />}
                  onClick={(e) => setDownloadAnchor(e.currentTarget)}
                  sx={{ color: colors.info.light, borderColor: colors.info.light, border: 1, '&:hover': { backgroundColor: `${colors.info.main}11` } }}
                >
                  Download
                </Button>
              </Tooltip>
              <Menu
                anchorEl={downloadAnchor}
                open={Boolean(downloadAnchor)}
                onClose={() => setDownloadAnchor(null)}
                anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
                transformOrigin={{ vertical: 'bottom', horizontal: 'right' }}
              >
                <MenuItem onClick={() => handleDownload('json')}>
                  <ListItemIcon><JsonIcon fontSize="small" /></ListItemIcon>
                  <ListItemText>Download as JSON</ListItemText>
                </MenuItem>
                <MenuItem onClick={() => handleDownload('csv')}>
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
