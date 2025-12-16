/**
 * Chunk Browser - Browse and inspect indexed chunks
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Alert,
  Pagination,
  Slider,
  Grid,
  LinearProgress,
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import type { GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import {
  Refresh as RefreshIcon,
  Visibility as ViewIcon,
  ContentCopy as CopyIcon,
  FilterList as FilterIcon,
} from '@mui/icons-material';
import { alpha } from '@mui/material/styles';

import { listChunks, getChunk } from '../../../services/adminApi';
import type { ChunkData } from '../../../types/admin';
import { colors } from '../../../theme';

const PAGE_SIZE = 25;

function QualityBadge({ score }: { score: number }) {
  const getColor = () => {
    if (score >= 0.8) return '#22c55e';
    if (score >= 0.6) return '#f59e0b';
    return '#ef4444';
  };
  return (
    <Chip
      label={score.toFixed(2)}
      size="small"
      sx={{
        backgroundColor: alpha(getColor(), 0.2),
        color: getColor(),
        fontWeight: 'bold',
      }}
    />
  );
}

function ChunkDetailDialog({ chunk, open, onClose }: {
  chunk: ChunkData | null;
  open: boolean;
  onClose: () => void;
}) {
  if (!chunk) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(chunk.content);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">Chunk Details</Typography>
          <Box>
            <QualityBadge score={chunk.quality_score} />
          </Box>
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" color="textSecondary">Chunk ID</Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>
              {chunk.chunk_id}
            </Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" color="textSecondary">Document ID</Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>
              {chunk.doc_id}
            </Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" color="textSecondary">Filename</Typography>
            <Typography variant="body2">{chunk.filename}</Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" color="textSecondary">Category</Typography>
            <Chip label={chunk.category} size="small" />
          </Grid>
          <Grid item xs={12}>
            <Typography variant="subtitle2" color="textSecondary">Tags</Typography>
            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5 }}>
              {chunk.tags?.length > 0 ? (
                chunk.tags.map((tag) => <Chip key={tag} label={tag} size="small" variant="outlined" />)
              ) : (
                <Typography variant="body2" color="textSecondary">No tags</Typography>
              )}
            </Box>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" color="textSecondary">Content Length</Typography>
            <Typography variant="body2">{chunk.content_length} characters</Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" color="textSecondary">Created At</Typography>
            <Typography variant="body2">
              {chunk.created_at ? new Date(chunk.created_at).toLocaleString() : 'Unknown'}
            </Typography>
          </Grid>
          {chunk.embedding_dimensions !== undefined && (
            <Grid item xs={12}>
              <Typography variant="subtitle2" color="textSecondary">Embedding</Typography>
              <Typography variant="body2">
                {chunk.embedding_dimensions} dimensions
                {chunk.embedding_preview && ` [${chunk.embedding_preview.slice(0, 5).map(v => v.toFixed(4)).join(', ')}...]`}
              </Typography>
            </Grid>
          )}
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="subtitle2" color="textSecondary">Content</Typography>
              <IconButton size="small" onClick={handleCopy} title="Copy content">
                <CopyIcon fontSize="small" />
              </IconButton>
            </Box>
            <Box
              sx={{
                p: 2,
                backgroundColor: alpha(colors.background.default, 0.5),
                borderRadius: 1,
                maxHeight: 300,
                overflow: 'auto',
                fontFamily: 'monospace',
                fontSize: '0.875rem',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {chunk.content}
            </Box>
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

function ChunkBrowser() {
  const [chunks, setChunks] = useState<ChunkData[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  // Filters
  const [category, setCategory] = useState<string>('');
  const [qualityRange, setQualityRange] = useState<[number, number]>([0, 1]);
  const [sortBy, setSortBy] = useState<string>('created_at');
  const [sortOrder, setSortOrder] = useState<string>('desc');
  const [showFilters, setShowFilters] = useState(false);

  // Detail dialog
  const [selectedChunk, setSelectedChunk] = useState<ChunkData | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const fetchChunks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listChunks({
        offset: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
        category: category || undefined,
        min_quality: qualityRange[0] > 0 ? qualityRange[0] : undefined,
        max_quality: qualityRange[1] < 1 ? qualityRange[1] : undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      if (res.success) {
        setChunks(res.chunks);
        setTotal(res.total);
      } else {
        setError(res.error || 'Failed to fetch chunks');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch chunks');
    } finally {
      setLoading(false);
    }
  }, [page, category, qualityRange, sortBy, sortOrder]);

  useEffect(() => {
    fetchChunks();
  }, [fetchChunks]);

  const handleViewChunk = async (chunkId: string) => {
    try {
      const res = await getChunk(chunkId);
      if (res.success && res.chunk) {
        setSelectedChunk(res.chunk);
        setDetailOpen(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch chunk details');
    }
  };

  const columns: GridColDef[] = [
    {
      field: 'filename',
      headerName: 'Filename',
      flex: 1,
      minWidth: 150,
    },
    {
      field: 'category',
      headerName: 'Category',
      width: 120,
      renderCell: (params: GridRenderCellParams) => (
        <Chip label={params.value} size="small" variant="outlined" />
      ),
    },
    {
      field: 'content',
      headerName: 'Preview',
      flex: 2,
      minWidth: 200,
      renderCell: (params: GridRenderCellParams) => (
        <Typography variant="body2" sx={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {params.value}
        </Typography>
      ),
    },
    {
      field: 'content_length',
      headerName: 'Length',
      width: 80,
      align: 'right',
    },
    {
      field: 'quality_score',
      headerName: 'Quality',
      width: 100,
      renderCell: (params: GridRenderCellParams) => <QualityBadge score={params.value} />,
    },
    {
      field: 'actions',
      headerName: '',
      width: 60,
      sortable: false,
      renderCell: (params: GridRenderCellParams) => (
        <Tooltip title="View Details">
          <IconButton size="small" onClick={() => handleViewChunk(params.row.chunk_id)}>
            <ViewIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      ),
    },
  ];

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" gutterBottom>Chunk Browser</Typography>
          <Typography variant="body2" color="textSecondary">
            Browse and inspect indexed knowledge chunks
          </Typography>
        </Box>
        <Box>
          <Tooltip title="Toggle Filters">
            <IconButton onClick={() => setShowFilters(!showFilters)}>
              <FilterIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Refresh">
            <IconButton onClick={fetchChunks} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Filters */}
      {showFilters && (
        <Card sx={{ mb: 3, backgroundColor: alpha(colors.background.paper, 0.8) }}>
          <CardContent>
            <Grid container spacing={2} alignItems="center">
              <Grid item xs={12} sm={3}>
                <FormControl fullWidth size="small">
                  <InputLabel>Category</InputLabel>
                  <Select
                    value={category}
                    label="Category"
                    onChange={(e) => { setCategory(e.target.value); setPage(1); }}
                  >
                    <MenuItem value="">All Categories</MenuItem>
                    <MenuItem value="general">General</MenuItem>
                    <MenuItem value="addressing">Addressing</MenuItem>
                    <MenuItem value="puerto-rico">Puerto Rico</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={3}>
                <FormControl fullWidth size="small">
                  <InputLabel>Sort By</InputLabel>
                  <Select
                    value={sortBy}
                    label="Sort By"
                    onChange={(e) => setSortBy(e.target.value)}
                  >
                    <MenuItem value="created_at">Date Created</MenuItem>
                    <MenuItem value="quality_score">Quality Score</MenuItem>
                    <MenuItem value="content_length">Content Length</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={2}>
                <FormControl fullWidth size="small">
                  <InputLabel>Order</InputLabel>
                  <Select
                    value={sortOrder}
                    label="Order"
                    onChange={(e) => setSortOrder(e.target.value)}
                  >
                    <MenuItem value="desc">Descending</MenuItem>
                    <MenuItem value="asc">Ascending</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={4}>
                <Typography variant="caption" color="textSecondary">Quality Range</Typography>
                <Slider
                  value={qualityRange}
                  onChange={(_, value) => { setQualityRange(value as [number, number]); setPage(1); }}
                  min={0}
                  max={1}
                  step={0.1}
                  valueLabelDisplay="auto"
                  valueLabelFormat={(v) => v.toFixed(1)}
                  size="small"
                />
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Stats Bar */}
      <Box sx={{ mb: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
        <Chip label={`${total} chunks`} variant="outlined" />
        {category && <Chip label={`Category: ${category}`} onDelete={() => setCategory('')} />}
        {(qualityRange[0] > 0 || qualityRange[1] < 1) && (
          <Chip
            label={`Quality: ${qualityRange[0].toFixed(1)} - ${qualityRange[1].toFixed(1)}`}
            onDelete={() => setQualityRange([0, 1])}
          />
        )}
      </Box>

      {/* Data Grid */}
      <Card sx={{ backgroundColor: alpha(colors.background.paper, 0.8) }}>
        {loading && <LinearProgress />}
        <DataGrid
          rows={chunks}
          columns={columns}
          getRowId={(row) => row.chunk_id}
          autoHeight
          disableRowSelectionOnClick
          hideFooter
          sx={{
            border: 'none',
            '& .MuiDataGrid-cell': {
              borderColor: alpha(colors.primary.main, 0.1),
            },
            '& .MuiDataGrid-columnHeaders': {
              backgroundColor: alpha(colors.primary.main, 0.05),
              borderColor: alpha(colors.primary.main, 0.1),
            },
          }}
        />
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
          <Pagination
            count={totalPages}
            page={page}
            onChange={(_, p) => setPage(p)}
            color="primary"
          />
        </Box>
      )}

      {/* Detail Dialog */}
      <ChunkDetailDialog
        chunk={selectedChunk}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
      />
    </Box>
  );
}

export default ChunkBrowser;
