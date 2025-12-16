/**
 * Search Playground - Test and debug search queries
 */

import { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Alert,
  Grid,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Switch,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  CircularProgress,
} from '@mui/material';
import {
  Search as SearchIcon,
  Save as SaveIcon,
  Delete as DeleteIcon,
  PlayArrow as RunIcon,
  ExpandMore as ExpandIcon,
  BugReport as DebugIcon,
  Speed as SpeedIcon,
} from '@mui/icons-material';
import { alpha } from '@mui/material/styles';

import {
  testSearch,
  saveQuery,
  listSavedQueries,
  deleteSavedQuery,
  runSavedQuery,
} from '../../../services/adminApi';
import type { SearchHit, SavedQuery, SearchTestResult } from '../../../types/admin';
import { colors } from '../../../theme';

function ResultCard({ hit, rank }: { hit: SearchHit; rank: number }) {
  return (
    <Card sx={{ mb: 2, backgroundColor: alpha(colors.background.paper, 0.6) }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Chip label={`#${rank}`} size="small" color="primary" />
            <Typography variant="subtitle2">{hit.filename}</Typography>
          </Box>
          <Chip
            label={`Score: ${hit.score.toFixed(4)}`}
            size="small"
            sx={{ backgroundColor: alpha(colors.primary.main, 0.2) }}
          />
        </Box>
        <Box sx={{ display: 'flex', gap: 0.5, mb: 1, flexWrap: 'wrap' }}>
          <Chip label={hit.category} size="small" variant="outlined" />
          {hit.tags?.map((tag) => (
            <Chip key={tag} label={tag} size="small" variant="outlined" />
          ))}
        </Box>
        <Typography
          variant="body2"
          sx={{
            backgroundColor: alpha(colors.background.default, 0.5),
            p: 1.5,
            borderRadius: 1,
            maxHeight: 150,
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
            fontFamily: 'monospace',
            fontSize: '0.8rem',
          }}
        >
          {hit.text || hit.content}
        </Typography>
      </CardContent>
    </Card>
  );
}

function SaveQueryDialog({ open, onClose, onSave, query }: {
  open: boolean;
  onClose: () => void;
  onSave: (name: string, notes: string) => void;
  query: string;
}) {
  const [name, setName] = useState('');
  const [notes, setNotes] = useState('');

  const handleSave = () => {
    if (name.trim()) {
      onSave(name.trim(), notes.trim());
      setName('');
      setNotes('');
      onClose();
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Save Query</DialogTitle>
      <DialogContent>
        <TextField
          fullWidth
          label="Query Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          margin="normal"
          autoFocus
        />
        <TextField
          fullWidth
          label="Query"
          value={query}
          disabled
          margin="normal"
        />
        <TextField
          fullWidth
          label="Notes (optional)"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          margin="normal"
          multiline
          rows={2}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleSave} variant="contained" disabled={!name.trim()}>
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function SearchPlayground() {
  // Search state
  const [query, setQuery] = useState('');
  const [index, setIndex] = useState<string>('knowledge');
  const [limit, setLimit] = useState(10);
  const [explain, setExplain] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SearchTestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Saved queries
  const [savedQueries, setSavedQueries] = useState<SavedQuery[]>([]);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);

  useEffect(() => {
    fetchSavedQueries();
  }, []);

  const fetchSavedQueries = async () => {
    try {
      const res = await listSavedQueries();
      if (res.success) {
        setSavedQueries(res.queries);
      }
    } catch (err) {
      console.error('Failed to fetch saved queries:', err);
    }
  };

  const handleSearch = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const res = await testSearch({
        query: query.trim(),
        limit,
        index,
        explain,
      });
      setResult(res);
      if (!res.success) {
        setError(res.error || 'Search failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveQuery = async (name: string, notes: string) => {
    try {
      await saveQuery({
        name,
        query: query.trim(),
        index,
        notes: notes || undefined,
      });
      await fetchSavedQueries();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save query');
    }
  };

  const handleDeleteSavedQuery = async (queryId: string) => {
    try {
      await deleteSavedQuery(queryId);
      await fetchSavedQueries();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete query');
    }
  };

  const handleRunSavedQuery = async (savedQuery: SavedQuery) => {
    setQuery(savedQuery.query);
    setIndex(savedQuery.index || 'knowledge');
    setLoading(true);
    setError(null);
    try {
      const res = await runSavedQuery(savedQuery.id);
      setResult(res);
      if (!res.success) {
        setError(res.error || 'Search failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>Search Playground</Typography>
        <Typography variant="body2" color="textSecondary">
          Test and debug search queries with full explain mode
        </Typography>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}

      <Grid container spacing={3}>
        {/* Left Panel - Query Input */}
        <Grid item xs={12} md={8}>
          <Card sx={{ mb: 3, backgroundColor: alpha(colors.background.paper, 0.8) }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <SearchIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
                Query
              </Typography>
              <TextField
                fullWidth
                label="Search Query"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Enter your search query..."
                multiline
                rows={2}
                sx={{ mb: 2 }}
              />
              <Grid container spacing={2} sx={{ mb: 2 }}>
                <Grid item xs={12} sm={4}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Index</InputLabel>
                    <Select
                      value={index}
                      label="Index"
                      onChange={(e) => setIndex(e.target.value)}
                    >
                      <MenuItem value="knowledge">Knowledge</MenuItem>
                      <MenuItem value="customers">Customers</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Limit"
                    value={limit}
                    onChange={(e) => setLimit(parseInt(e.target.value) || 10)}
                    size="small"
                    inputProps={{ min: 1, max: 100 }}
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={explain}
                        onChange={(e) => setExplain(e.target.checked)}
                      />
                    }
                    label="Debug Mode"
                  />
                </Grid>
              </Grid>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                  variant="contained"
                  onClick={handleSearch}
                  disabled={!query.trim() || loading}
                  startIcon={loading ? <CircularProgress size={20} /> : <SearchIcon />}
                >
                  {loading ? 'Searching...' : 'Search'}
                </Button>
                <Button
                  variant="outlined"
                  onClick={() => setSaveDialogOpen(true)}
                  disabled={!query.trim()}
                  startIcon={<SaveIcon />}
                >
                  Save Query
                </Button>
              </Box>
            </CardContent>
          </Card>

          {/* Results */}
          {result && (
            <Box>
              {/* Debug Info */}
              {result.debug && (
                <Accordion sx={{ mb: 2, backgroundColor: alpha(colors.background.paper, 0.8) }}>
                  <AccordionSummary expandIcon={<ExpandIcon />}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <DebugIcon />
                      <Typography>Debug Information</Typography>
                    </Box>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Grid container spacing={2}>
                      <Grid item xs={6} sm={3}>
                        <Typography variant="caption" color="textSecondary">Backend</Typography>
                        <Typography variant="body2">{result.debug.backend || 'N/A'}</Typography>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Typography variant="caption" color="textSecondary">Search Type</Typography>
                        <Typography variant="body2">{result.debug.search_type || 'N/A'}</Typography>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Typography variant="caption" color="textSecondary">Results</Typography>
                        <Typography variant="body2">{result.debug.result_count}</Typography>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Typography variant="caption" color="textSecondary">
                          <SpeedIcon sx={{ fontSize: 14, verticalAlign: 'middle', mr: 0.5 }} />
                          Latency
                        </Typography>
                        <Typography variant="body2">{result.debug.elapsed_ms}ms</Typography>
                      </Grid>
                    </Grid>
                  </AccordionDetails>
                </Accordion>
              )}

              {/* Results List */}
              <Typography variant="h6" gutterBottom>
                Results ({result.results.length})
              </Typography>
              {result.results.length > 0 ? (
                result.results.map((hit, i) => (
                  <ResultCard key={`${hit.doc_id}-${i}`} hit={hit} rank={i + 1} />
                ))
              ) : (
                <Alert severity="info">No results found for this query</Alert>
              )}
            </Box>
          )}
        </Grid>

        {/* Right Panel - Saved Queries */}
        <Grid item xs={12} md={4}>
          <Card sx={{ backgroundColor: alpha(colors.background.paper, 0.8) }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <SaveIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
                Saved Queries
              </Typography>
              {savedQueries.length > 0 ? (
                <List dense>
                  {savedQueries.map((sq) => (
                    <ListItem
                      key={sq.id}
                      sx={{
                        borderRadius: 1,
                        mb: 0.5,
                        '&:hover': { backgroundColor: alpha(colors.primary.main, 0.1) },
                      }}
                      secondaryAction={
                        <Box>
                          <Tooltip title="Run">
                            <IconButton
                              size="small"
                              onClick={() => handleRunSavedQuery(sq)}
                            >
                              <RunIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Delete">
                            <IconButton
                              size="small"
                              onClick={() => handleDeleteSavedQuery(sq.id)}
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      }
                    >
                      <ListItemText
                        primary={sq.name}
                        secondary={
                          <Box component="span">
                            <Typography variant="caption" component="span" display="block">
                              {sq.query.slice(0, 50)}{sq.query.length > 50 ? '...' : ''}
                            </Typography>
                            {sq.index && (
                              <Chip label={sq.index} size="small" sx={{ mt: 0.5 }} />
                            )}
                          </Box>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              ) : (
                <Typography variant="body2" color="textSecondary" sx={{ textAlign: 'center', py: 2 }}>
                  No saved queries yet
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Save Dialog */}
      <SaveQueryDialog
        open={saveDialogOpen}
        onClose={() => setSaveDialogOpen(false)}
        onSave={handleSaveQuery}
        query={query}
      />
    </Box>
  );
}

export default SearchPlayground;
