import React, { useState, useRef, useCallback, useEffect } from 'react';
import type { KeyboardEvent, ChangeEvent } from 'react';
import {
  Box, TextField, IconButton, Tooltip, FormControlLabel, Switch,
  Button, Chip, Menu, MenuItem, ListItemIcon, ListItemText,
  Paper, List, ListItem, ListItemButton, Typography,
  InputAdornment, CircularProgress,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  Send as SendIcon, Clear as ClearIcon, Add as AddIcon, UploadFile as UploadIcon,
  Close as CloseIcon, Download as DownloadIcon, DataObject as JsonIcon, TableChart as CsvIcon,
  LocationOn as LocationIcon, Search as SearchIcon,
} from '@mui/icons-material';
import { colors, borderRadius, transitions } from '../theme';
import { downloadMessages, ALLOWED_FILE_EXTENSIONS } from '../utils';
import api from '../services/api';
import type { ChatMessage, AutocompleteItem } from '../types';

interface QueryInputProps {
  onSend: (query: string, file?: File) => Promise<void>;
  onClear: () => void;
  loading: boolean;
  bypassCache: boolean;
  onBypassCacheChange: (value: boolean) => void;
  messages: ChatMessage[];
  initialQuery?: string;  // For pre-filling from quick actions
}

export const QueryInput: React.FC<QueryInputProps> = ({
  onSend, onClear, loading, bypassCache, onBypassCacheChange, messages, initialQuery,
}) => {
  const [query, setQuery] = useState(initialQuery || '');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [downloadAnchor, setDownloadAnchor] = useState<HTMLElement | null>(null);
  const [suggestions, setSuggestions] = useState<AutocompleteItem[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Update query when initialQuery changes (from quick actions)
  useEffect(() => {
    if (initialQuery) {
      setQuery(initialQuery);
      inputRef.current?.focus();
    }
  }, [initialQuery]);

  // Fetch address suggestions with debouncing
  const fetchSuggestions = useCallback(async (value: string) => {
    if (value.length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    // Check if query looks like an address
    const looksLikeAddress = /^\d+\s+\w/.test(value) || /^[a-zA-Z]+\s+\d/.test(value);
    if (!looksLikeAddress) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    setLoadingSuggestions(true);
    try {
      const result = await api.autocomplete('address', value, 5, true);
      if (result.success && result.data.length > 0) {
        setSuggestions(result.data);
        setShowSuggestions(true);
      } else {
        setSuggestions([]);
        setShowSuggestions(false);
      }
    } catch {
      setSuggestions([]);
      setShowSuggestions(false);
    } finally {
      setLoadingSuggestions(false);
    }
  }, []);

  const handleQueryChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);

    // Debounce autocomplete
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }
    debounceRef.current = setTimeout(() => {
      fetchSuggestions(value);
    }, 300);
  }, [fetchSuggestions]);

  const handleSend = useCallback(async () => {
    const trimmed = query.trim();
    if (!trimmed || loading) return;
    const file = selectedFile;
    setQuery('');
    setSelectedFile(null);
    setShowSuggestions(false);
    await onSend(trimmed, file ?? undefined);
  }, [query, loading, selectedFile, onSend]);

  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
    if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  }, [handleSend]);

  const handleSuggestionSelect = useCallback((suggestion: AutocompleteItem) => {
    // Format the selection as a query
    const formattedQuery = `Show me ${suggestion.name} at ${suggestion.value}, ${suggestion.city}, ${suggestion.state}`;
    setQuery(formattedQuery);
    setShowSuggestions(false);
    inputRef.current?.focus();
  }, []);

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
    <Box
      sx={{
        p: 2,
        borderTop: `1px solid ${alpha(colors.primary.main, 0.2)}`,
        backgroundColor: colors.background.paper,
        position: 'relative',
      }}
    >
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelect}
        accept=".json,.md"
        style={{ display: 'none' }}
        aria-label="File Upload"
      />

      {/* Address Suggestions Dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <Paper
          elevation={8}
          aria-live="assertive"
          sx={{
            position: 'absolute',
            bottom: '100%',
            left: 16,
            right: 16,
            mb: 1,
            maxHeight: 300,
            overflow: 'auto',
            zIndex: 1000,
            borderRadius: borderRadius.lg,
            border: `1px solid ${alpha(colors.accent.main, 0.3)}`,
            backgroundColor: colors.background.elevated,
          }}
        >
          <Box sx={{ p: 1, borderBottom: `1px solid ${alpha(colors.text.primary, 0.1)}` }}>
            <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 500 }}>
              <LocationIcon sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'middle' }} />
              Address Suggestions - Click to use
            </Typography>
          </Box>
          <List dense disablePadding>
            {suggestions.map((suggestion, index) => (
              <ListItem key={`${suggestion.crid}-${index}`} disablePadding>
                <ListItemButton
                  onClick={() => handleSuggestionSelect(suggestion)}
                  aria-label={`Select suggestion: ${suggestion.value}`}
                  sx={{
                    py: 1.5,
                    '&:hover': {
                      backgroundColor: alpha(colors.accent.main, 0.1),
                    },
                  }}
                >
                  <Box sx={{ width: '100%' }}>
                    <Typography variant="body2" fontWeight={500}>
                      {suggestion.value}
                    </Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                      {suggestion.name} • {suggestion.city}, {suggestion.state}
                      {suggestion.score !== undefined && (
                        <Chip
                          label={`${Math.round(suggestion.score * 100)}% match`}
                          size="small"
                          aria-label={`${Math.round(suggestion.score * 100)}% match`}
                          sx={{
                            ml: 1,
                            height: 18,
                            fontSize: '0.65rem',
                            backgroundColor: alpha(colors.success.main, 0.15),
                            color: colors.success.light,
                          }}
                        />
                      )}
                    </Typography>
                  </Box>
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Paper>
      )}

      {/* File Preview */}
      {selectedFile && (
        <Box sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip
            icon={<UploadIcon sx={{ fontSize: 16 }} />}
            label={selectedFile.name}
            onDelete={() => setSelectedFile(null)}
            deleteIcon={<CloseIcon sx={{ fontSize: 16 }} />}
            aria-label={`Selected file: ${selectedFile.name}. Click to remove.`}
            sx={{
              backgroundColor: alpha(colors.info.main, 0.15),
              borderColor: colors.info.main,
              border: 1,
              color: colors.info.light,
            }}
          />
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            File will be sent with your query
          </Typography>
        </Box>
      )}

      {/* Main Input Row */}
      <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-end' }}>
        <TextField
          fullWidth
          multiline
          maxRows={4}
          inputRef={inputRef}
          placeholder="Ask ICDA anything about addresses or customers..."
          value={query}
          onChange={handleQueryChange}
          onKeyDown={handleKeyDown}
          onFocus={() => query.length >= 2 && suggestions.length > 0 && setShowSuggestions(true)}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
          disabled={loading}
          aria-label="Query Input"
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ color: colors.accent.main }} />
              </InputAdornment>
            ),
            endAdornment: loadingSuggestions ? (
              <InputAdornment position="end">
                <CircularProgress size={20} sx={{ color: colors.accent.main }} />
              </InputAdornment>
            ) : null,
          }}
          sx={{
            '& .MuiOutlinedInput-root': {
              borderRadius: borderRadius.lg,
              backgroundColor: alpha(colors.background.elevated, 0.5),
              transition: transitions.fast,
              '&:hover': {
                backgroundColor: colors.background.elevated,
              },
              '&.Mui-focused': {
                backgroundColor: colors.background.elevated,
                '& .MuiOutlinedInput-notchedOutline': {
                  borderColor: colors.accent.main,
                  borderWidth: 2,
                },
              },
            },
            '& .MuiInputBase-input': {
              py: 1.5,
              px: 1,
            },
          }}
        />

        <Tooltip title="Send query (Enter)">
          <span>
            <IconButton
              onClick={handleSend}
              disabled={loading || !query.trim()}
              aria-label="Send Query"
              sx={{
                width: 48,
                height: 48,
                backgroundColor: colors.accent.main,
                color: 'white',
                transition: transitions.fast,
                '&:hover': {
                  backgroundColor: colors.accent.dark,
                  transform: 'scale(1.05)',
                },
                '&:disabled': {
                  backgroundColor: alpha(colors.accent.main, 0.3),
                  color: alpha('#fff', 0.5),
                },
              }}
            >
              <SendIcon />
            </IconButton>
          </span>
        </Tooltip>
      </Box>

      {/* Bottom Controls Row */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mt: 1.5,
          flexWrap: 'wrap',
          gap: 1,
        }}
      >
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={bypassCache}
              onChange={(e) => onBypassCacheChange(e.target.checked)}
              aria-label="Bypass Cache"
              sx={{
                '& .MuiSwitch-switchBase.Mui-checked': {
                  color: colors.warning.main,
                },
                '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                  backgroundColor: colors.warning.main,
                },
              }}
            />
          }
          label="Bypass Cache"
          slotProps={{
            typography: {
              variant: 'caption',
              color: bypassCache ? 'warning.main' : 'text.secondary',
            },
          }}
        />

        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Tooltip title="Attach .json or .md file">
            <Button
              size="small"
              startIcon={<AddIcon />}
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
              aria-label="Add File"
              sx={{
                color: colors.aws.orange,
                borderColor: alpha(colors.aws.orange, 0.5),
                border: 1,
                '&:hover': {
                  backgroundColor: alpha(colors.aws.orange, 0.1),
                  borderColor: colors.aws.orange,
                },
              }}
            >
              Add File
            </Button>
          </Tooltip>

          {messages.length > 0 && (
            <>
              <Tooltip title="Download chat results">
                <Button
                  size="small"
                  startIcon={<DownloadIcon />}
                  onClick={(e) => setDownloadAnchor(e.currentTarget)}
                  aria-label="Download Chat"
                  sx={{
                    color: colors.info.light,
                    borderColor: alpha(colors.info.main, 0.5),
                    border: 1,
                    '&:hover': {
                      backgroundColor: alpha(colors.info.main, 0.1),
                      borderColor: colors.info.main,
                    },
                  }}
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
                slotProps={{
                  paper: {
                    sx: {
                      backgroundColor: colors.background.elevated,
                      border: `1px solid ${alpha(colors.text.primary, 0.1)}`,
                    },
                  },
                }}
              >
                <MenuItem onClick={() => handleDownload('json')} aria-label="Download as JSON">
                  <ListItemIcon>
                    <JsonIcon fontSize="small" sx={{ color: colors.info.light }} />
                  </ListItemIcon>
                  <ListItemText>Download as JSON</ListItemText>
                </MenuItem>
                <MenuItem onClick={() => handleDownload('csv')} aria-label="Download as CSV">
                  <ListItemIcon>
                    <CsvIcon fontSize="small" sx={{ color: colors.success.light }} />
                  </ListItemIcon>
                  <ListItemText>Download as CSV</ListItemText>
                </MenuItem>
              </Menu>
            </>
          )}
        </Box>

        <Button
          size="small"
          startIcon={<ClearIcon />}
          onClick={onClear}
          disabled={messages.length === 0}
          aria-label="New Chat"
          sx={{
            color: 'text.secondary',
            '&:hover': {
              color: colors.secondary.light,
              backgroundColor: alpha(colors.secondary.main, 0.1),
            },
          }}
        >
          New Chat
        </Button>
      </Box>
    </Box>
  );
};

export default QueryInput;