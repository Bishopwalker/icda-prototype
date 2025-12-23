/**
 * ReindexProgress - Real-time progress indicator for customer data reindexing
 *
 * Shows:
 * - Progress bar with percentage
 * - Chunks processed / remaining
 * - Data size being indexed
 * - Rate (items/sec)
 * - Estimated time remaining
 * - Embeddings generated
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  LinearProgress,
  Button,
  IconButton,
  Collapse,
  Grid,
  Chip,
  Alert,
} from '@mui/material';
import {
  PlayArrow as StartIcon,
  Close as CloseIcon,
  ExpandMore as ExpandIcon,
  ExpandLess as CollapseIcon,
  Speed as SpeedIcon,
  Timer as TimerIcon,
  Storage as StorageIcon,
  Memory as MemoryIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import { alpha } from '@mui/material/styles';
import { colors } from '../../../theme';
import {
  startReindexWithProgress,
  createProgressStream,
  getActiveOperations,
  type ProgressState,
} from '../../../services/adminApi';

interface ReindexProgressProps {
  onComplete?: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins < 60) return `${mins}m ${secs}s`;
  const hours = Math.floor(mins / 60);
  const remainingMins = mins % 60;
  return `${hours}h ${remainingMins}m`;
}

function StatBox({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Box sx={{ color: colors.primary.main, display: 'flex', alignItems: 'center' }}>
        {icon}
      </Box>
      <Box>
        <Typography variant="caption" color="textSecondary">{label}</Typography>
        <Typography variant="body2" fontWeight="medium">{value}</Typography>
      </Box>
    </Box>
  );
}

export default function ReindexProgress({ onComplete }: ReindexProgressProps) {
  const [state, setState] = useState<ProgressState | null>(null);
  const [expanded, setExpanded] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Check for active operations on mount
  useEffect(() => {
    const checkActive = async () => {
      try {
        const result = await getActiveOperations();
        if (result.success && result.operations.length > 0) {
          const active = result.operations[0];
          setState(active);
          connectToStream(active.operation_id);
        }
      } catch (e) {
        console.error('Failed to check active operations:', e);
      }
    };
    checkActive();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const connectToStream = useCallback((operationId: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const stream = createProgressStream(operationId);
    eventSourceRef.current = stream.connect(
      // onProgress
      (progressState) => {
        setState(progressState);
        setError(null);
      },
      // onComplete
      (finalState) => {
        setState(finalState);
        eventSourceRef.current = null;
        if (onComplete) {
          onComplete();
        }
      },
      // onError
      (errorMsg) => {
        setError(errorMsg);
        eventSourceRef.current = null;
      }
    );
  }, [onComplete]);

  const handleStart = async (force: boolean = false) => {
    setStarting(true);
    setError(null);

    try {
      const result = await startReindexWithProgress(force);

      if (result.success && result.async && result.operation_id) {
        setState({
          operation_id: result.operation_id,
          operation_type: 'customer_index',
          status: 'running',
          total_items: result.total_items || 0,
          processed_items: 0,
          error_count: 0,
          current_batch: 0,
          total_batches: Math.ceil((result.total_items || 0) / 100),
          bytes_processed: 0,
          context_tokens_used: 0,
          embeddings_generated: 0,
          start_time: Date.now() / 1000,
          last_update: Date.now() / 1000,
          elapsed_seconds: 0,
          estimated_remaining_seconds: 0,
          items_per_second: 0,
          current_phase: 'Starting',
          last_message: '',
          error_message: '',
          percent_complete: 0,
        });
        connectToStream(result.operation_id);
      } else if (result.message === 'Index already in sync') {
        setError('Index is already in sync. Use Force Reindex to rebuild.');
      } else if (result.error) {
        setError(result.error);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start reindex');
    } finally {
      setStarting(false);
    }
  };

  const handleClose = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setState(null);
    setError(null);
  };

  const isActive = state && (state.status === 'running' || state.status === 'pending');
  const isComplete = state && state.status === 'completed';
  const isFailed = state && state.status === 'failed';

  // Nothing to show if no active operation
  if (!state && !error) {
    return (
      <Card sx={{ mb: 3, backgroundColor: alpha(colors.background.paper, 0.8) }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Box>
              <Typography variant="h6">Customer Data Reindex</Typography>
              <Typography variant="body2" color="textSecondary">
                Rebuild the customer search index with progress tracking
              </Typography>
            </Box>
            <Box>
              <Button
                variant="outlined"
                onClick={() => handleStart(false)}
                disabled={starting}
                startIcon={<StartIcon />}
                sx={{ mr: 1 }}
              >
                {starting ? 'Starting...' : 'Reindex'}
              </Button>
              <Button
                variant="contained"
                onClick={() => handleStart(true)}
                disabled={starting}
                startIcon={<StartIcon />}
              >
                Force Reindex
              </Button>
            </Box>
          </Box>
          {error && (
            <Alert severity="warning" sx={{ mt: 2 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}
        </CardContent>
      </Card>
    );
  }

  // Guard for TypeScript - state is guaranteed non-null at this point
  if (!state) {
    return null;
  }

  return (
    <Card
      sx={{
        mb: 3,
        backgroundColor: alpha(colors.background.paper, 0.9),
        border: isComplete ? `1px solid ${colors.success?.main || '#22c55e'}` :
          isFailed ? `1px solid ${colors.error?.main || '#ef4444'}` :
            `1px solid ${colors.primary.main}`,
      }}
    >
      <CardContent>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="h6">
              {isComplete ? 'Reindex Complete' : isFailed ? 'Reindex Failed' : 'Reindexing Customers'}
            </Typography>
            <Chip
              size="small"
              icon={isComplete ? <SuccessIcon /> : isFailed ? <ErrorIcon /> : undefined}
              label={state.current_phase}
              color={isComplete ? 'success' : isFailed ? 'error' : 'primary'}
            />
          </Box>
          <Box>
            <IconButton size="small" onClick={() => setExpanded(!expanded)}>
              {expanded ? <CollapseIcon /> : <ExpandIcon />}
            </IconButton>
            {!isActive && (
              <IconButton size="small" onClick={handleClose}>
                <CloseIcon />
              </IconButton>
            )}
          </Box>
        </Box>

        {/* Progress Bar */}
        <Box sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography variant="body2">
              {state.processed_items.toLocaleString()} / {state.total_items.toLocaleString()} items
            </Typography>
            <Typography variant="body2" fontWeight="bold">
              {state.percent_complete.toFixed(1)}%
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={state.percent_complete}
            sx={{
              height: 12,
              borderRadius: 6,
              backgroundColor: alpha(colors.primary.main, 0.2),
              '& .MuiLinearProgress-bar': {
                borderRadius: 6,
                backgroundColor: isComplete ? '#22c55e' : isFailed ? '#ef4444' : colors.primary.main,
              },
            }}
          />
        </Box>

        {/* Status Message */}
        {state.last_message && (
          <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
            {state.last_message}
          </Typography>
        )}

        {/* Error Message */}
        {state.error_message && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {state.error_message}
          </Alert>
        )}

        {/* Detailed Stats */}
        <Collapse in={expanded}>
          <Grid container spacing={3} sx={{ mt: 1 }}>
            <Grid item xs={6} sm={3}>
              <StatBox
                icon={<SpeedIcon fontSize="small" />}
                label="Rate"
                value={state.items_per_second > 0 ? `${state.items_per_second.toFixed(0)}/sec` : 'starting...'}
              />
            </Grid>
            <Grid item xs={6} sm={3}>
              <StatBox
                icon={<TimerIcon fontSize="small" />}
                label="Time Remaining"
                value={
                  state.estimated_remaining_seconds > 0
                    ? formatDuration(state.estimated_remaining_seconds)
                    : isComplete ? 'Done' : 'calculating...'
                }
              />
            </Grid>
            <Grid item xs={6} sm={3}>
              <StatBox
                icon={<StorageIcon fontSize="small" />}
                label="Data Processed"
                value={formatBytes(state.bytes_processed)}
              />
            </Grid>
            <Grid item xs={6} sm={3}>
              <StatBox
                icon={<MemoryIcon fontSize="small" />}
                label="Embeddings"
                value={state.embeddings_generated.toLocaleString()}
              />
            </Grid>
          </Grid>

          {/* Additional Info */}
          <Box sx={{ mt: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Typography variant="caption" color="textSecondary">
              Batch: {state.current_batch} / {state.total_batches}
            </Typography>
            <Typography variant="caption" color="textSecondary">
              Elapsed: {formatDuration(state.elapsed_seconds)}
            </Typography>
            {state.error_count > 0 && (
              <Typography variant="caption" color="error">
                Errors: {state.error_count}
              </Typography>
            )}
          </Box>
        </Collapse>
      </CardContent>
    </Card>
  );
}
