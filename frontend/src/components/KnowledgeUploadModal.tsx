import React, { useState, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  IconButton,
  LinearProgress,
  Alert,
  Chip,
  Stack,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Tabs,
  Tab,
  Divider,
} from '@mui/material';
import {
  Close as CloseIcon,
  CloudUpload as UploadIcon,
  Delete as DeleteIcon,
  Description as DocIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import { api } from '../services/api';
import type { KnowledgeDocument, KnowledgeStats } from '../types';
import ConfirmDialog from './ConfirmDialog';

interface KnowledgeUploadModalProps {
  open: boolean;
  onClose: () => void;
}

const CATEGORIES = [
  { value: 'general', label: 'General' },
  { value: 'architecture', label: 'Architecture' },
  { value: 'api', label: 'API Documentation' },
  { value: 'requirements', label: 'Requirements' },
  { value: 'design', label: 'Design Docs' },
  { value: 'meeting-notes', label: 'Meeting Notes' },
  { value: 'runbook', label: 'Runbook / Operations' },
];

export const KnowledgeUploadModal: React.FC<KnowledgeUploadModalProps> = ({
  open,
  onClose,
}) => {
  const [tab, setTab] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Upload form state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [tags, setTags] = useState('');
  const [category, setCategory] = useState('general');

  // Documents list state
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [loadingDocs, setLoadingDocs] = useState(false);

  // Confirm dialog state
  const [deleteDocId, setDeleteDocId] = useState<string | null>(null);

  // Dropzone
  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setSelectedFile(acceptedFiles[0]);
      setError(null);
      setSuccess(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      // Text formats
      'text/plain': ['.txt', '.log', '.cfg', '.ini', '.env'],
      'text/markdown': ['.md', '.markdown'],
      'text/html': ['.html', '.htm'],
      'text/csv': ['.csv'],
      'text/xml': ['.xml'],
      'application/json': ['.json'],
      'application/rtf': ['.rtf'],
      // Documents
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/msword': ['.doc'],
      'application/vnd.oasis.opendocument.text': ['.odt', '.odf'],
      // Spreadsheets
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      // Code files
      'text/x-python': ['.py'],
      'text/javascript': ['.js', '.ts', '.jsx', '.tsx'],
      'text/x-java': ['.java'],
      'text/x-yaml': ['.yaml', '.yml'],
    },
    maxFiles: 1,
    maxSize: 25 * 1024 * 1024, // 25MB
  });

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await api.knowledgeUpload(selectedFile, tags, category);

      if (result.success) {
        setSuccess(
          `Uploaded "${result.filename}" - ${result.chunks_indexed} chunks indexed`
        );
        setSelectedFile(null);
        setTags('');
        // Refresh documents list
        loadDocuments();
      } else {
        setError(result.error || 'Upload failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const loadDocuments = async () => {
    setLoadingDocs(true);
    try {
      const [docsResult, statsResult] = await Promise.all([
        api.knowledgeListDocuments(),
        api.knowledgeStats(),
      ]);
      setDocuments(docsResult.documents || []);
      setStats(statsResult);
    } catch (err) {
      console.error('Failed to load documents:', err);
    } finally {
      setLoadingDocs(false);
    }
  };

  const handleDeleteClick = (docId: string) => {
    setDeleteDocId(docId);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteDocId) return;

    try {
      await api.knowledgeDelete(deleteDocId);
      loadDocuments();
    } catch {
      setError('Failed to delete document');
    } finally {
      setDeleteDocId(null);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDocId(null);
  };

  // Load documents when tab changes to "Manage"
  React.useEffect(() => {
    if (open && tab === 1) {
      loadDocuments();
    }
  }, [open, tab]);

  const handleClose = () => {
    setSelectedFile(null);
    setTags('');
    setCategory('general');
    setError(null);
    setSuccess(null);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <DocIcon color="primary" />
          <Typography variant="h6">Knowledge Base</Typography>
        </Box>
        <IconButton onClick={handleClose} size="small" aria-label="Close dialog">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ px: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Tab label="Upload Document" />
        <Tab label="Manage Documents" />
      </Tabs>

      <DialogContent sx={{ minHeight: 400 }}>
        {/* Upload Tab */}
        {tab === 0 && (
          <Box sx={{ pt: 2 }}>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                {error}
              </Alert>
            )}
            {success && (
              <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
                {success}
              </Alert>
            )}

            {/* Dropzone */}
            <Box
              {...getRootProps()}
              sx={{
                border: '2px dashed',
                borderColor: isDragActive ? 'primary.main' : 'divider',
                borderRadius: 2,
                p: 4,
                textAlign: 'center',
                cursor: 'pointer',
                backgroundColor: isDragActive ? 'action.hover' : 'background.paper',
                transition: 'all 0.2s',
                '&:hover': {
                  borderColor: 'primary.main',
                  backgroundColor: 'action.hover',
                },
                mb: 3,
              }}
            >
              <input {...getInputProps()} />
              <UploadIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
              {selectedFile ? (
                <Typography variant="body1" fontWeight={600}>
                  {selectedFile.name}
                  <Typography variant="caption" display="block" color="text.secondary">
                    {(selectedFile.size / 1024).toFixed(1)} KB
                  </Typography>
                </Typography>
              ) : (
                <>
                  <Typography variant="body1" fontWeight={500}>
                    {isDragActive ? 'Drop file here' : 'Drag & drop or click to select'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Supports: txt, md, pdf, docx, xlsx, csv, html, json, yaml, py, js, ts (max 25MB)
                  </Typography>
                </>
              )}
            </Box>

            {/* Category & Tags */}
            <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
              <FormControl sx={{ minWidth: 200 }}>
                <InputLabel>Category</InputLabel>
                <Select
                  value={category}
                  label="Category"
                  onChange={(e) => setCategory(e.target.value)}
                >
                  {CATEGORIES.map((cat) => (
                    <MenuItem key={cat.value} value={cat.value}>
                      {cat.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <TextField
                fullWidth
                label="Tags"
                placeholder="api, architecture, v2 (comma-separated)"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                helperText="Optional: Add tags for easier filtering"
              />
            </Stack>

            {uploading && <LinearProgress sx={{ mb: 2 }} />}
          </Box>
        )}

        {/* Manage Tab */}
        {tab === 1 && (
          <Box sx={{ pt: 2 }}>
            {/* Stats */}
            {stats && stats.available && (
              <Box sx={{ mb: 3, p: 2, backgroundColor: 'background.default', borderRadius: 1 }}>
                <Stack direction="row" spacing={4}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Documents
                    </Typography>
                    <Typography variant="h6">{stats.unique_documents || 0}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Total Chunks
                    </Typography>
                    <Typography variant="h6">{stats.total_chunks || 0}</Typography>
                  </Box>
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                      Categories
                    </Typography>
                    <Stack direction="row" spacing={0.5} flexWrap="wrap" sx={{ mt: 0.5 }}>
                      {stats.categories &&
                        Object.entries(stats.categories).map(([cat, count]) => (
                          <Chip
                            key={cat}
                            label={`${cat}: ${count}`}
                            size="small"
                            variant="outlined"
                          />
                        ))}
                    </Stack>
                  </Box>
                </Stack>
              </Box>
            )}

            {/* Refresh button */}
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
              <Button
                startIcon={<RefreshIcon />}
                onClick={loadDocuments}
                disabled={loadingDocs}
                size="small"
              >
                Refresh
              </Button>
            </Box>

            {loadingDocs && <LinearProgress sx={{ mb: 2 }} />}

            {/* Documents list */}
            <List sx={{ maxHeight: 300, overflow: 'auto' }}>
              {documents.length === 0 ? (
                <ListItem>
                  <ListItemText
                    primary="No documents indexed"
                    secondary="Upload documents in the Upload tab"
                  />
                </ListItem>
              ) : (
                documents.map((doc) => (
                  <React.Fragment key={doc.doc_id}>
                    <ListItem>
                      <ListItemText
                        primary={doc.filename}
                        secondary={
                          <Stack direction="row" spacing={1} alignItems="center">
                            <Chip label={doc.category} size="small" />
                            <Typography variant="caption">
                              {doc.chunk_count} chunks
                            </Typography>
                            {doc.tags.length > 0 && (
                              <Typography variant="caption" color="text.secondary">
                                Tags: {doc.tags.join(', ')}
                              </Typography>
                            )}
                          </Stack>
                        }
                      />
                      <ListItemSecondaryAction>
                        <IconButton
                          edge="end"
                          onClick={() => handleDeleteClick(doc.doc_id)}
                          size="small"
                          color="error"
                        >
                          <DeleteIcon />
                        </IconButton>
                      </ListItemSecondaryAction>
                    </ListItem>
                    <Divider />
                  </React.Fragment>
                ))
              )}
            </List>
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={handleClose}>Close</Button>
        {tab === 0 && (
          <Button
            variant="contained"
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
            startIcon={<UploadIcon />}
          >
            {uploading ? 'Uploading...' : 'Upload & Index'}
          </Button>
        )}
      </DialogActions>

      <ConfirmDialog
        open={deleteDocId !== null}
        title="Delete Document"
        message="Are you sure you want to delete this document? This action cannot be undone."
        confirmText="Delete"
        cancelText="Cancel"
        confirmColor="error"
        onConfirm={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
      />
    </Dialog>
  );
};

export default KnowledgeUploadModal;
