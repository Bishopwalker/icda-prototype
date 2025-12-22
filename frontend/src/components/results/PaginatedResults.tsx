import React, { useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
  CircularProgress,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Paper,
  Alert,
  Divider,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  ViewList as ListIcon,
  TableChart as TableIcon,
  Download as DownloadIcon,
  ExpandMore as MoreIcon,
  InsertDriveFile as JsonIcon,
  Description as CsvIcon,
  CloudDownload as CloudDownloadIcon,
  Info as InfoIcon,
  KeyboardArrowDown as ShowMoreIcon,
} from '@mui/icons-material';
import { colors, borderRadius } from '../../theme';
import api from '../../services/api';
import type { PaginationInfo } from '../../types';

interface PaginatedResultsProps {
  results: Record<string, unknown>[];
  pagination: PaginationInfo;
  onDownload?: (format: 'json' | 'csv') => void;
  isDownloading?: boolean;
}

type ViewMode = 'list' | 'table';

/**
 * Formats a value for display.
 */
const formatValue = (value: unknown): string => {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

/**
 * Gets display-friendly column headers from result keys.
 */
const getColumnHeaders = (results: Record<string, unknown>[]): string[] => {
  if (results.length === 0) return [];
  // Get all unique keys from all results
  const allKeys = new Set<string>();
  results.forEach((result) => {
    Object.keys(result).forEach((key) => allKeys.add(key));
  });
  // Sort with common customer fields first
  const priority = ['crid', 'name', 'address', 'city', 'state', 'zip', 'status'];
  return Array.from(allKeys).sort((a, b) => {
    const aIdx = priority.indexOf(a.toLowerCase());
    const bIdx = priority.indexOf(b.toLowerCase());
    if (aIdx !== -1 && bIdx !== -1) return aIdx - bIdx;
    if (aIdx !== -1) return -1;
    if (bIdx !== -1) return 1;
    return a.localeCompare(b);
  });
};

/**
 * Formats column header for display.
 */
const formatHeader = (key: string): string => {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .split(' ')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

export const PaginatedResults: React.FC<PaginatedResultsProps> = ({
  results: initialResults,
  pagination,
  onDownload,
  isDownloading = false,
}) => {
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const [displayedResults, setDisplayedResults] = useState<Record<string, unknown>[]>(initialResults);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [currentOffset, setCurrentOffset] = useState(initialResults.length);
  const [hasMoreToLoad, setHasMoreToLoad] = useState(pagination.has_more);
  const [remainingCount, setRemainingCount] = useState(
    pagination.total_count - pagination.returned_count
  );

  const columns = React.useMemo(() => getColumnHeaders(displayedResults), [displayedResults]);

  const handleViewChange = (_: React.MouseEvent<HTMLElement>, newView: ViewMode | null) => {
    if (newView !== null) {
      setViewMode(newView);
    }
  };

  const handleDownloadClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setMenuAnchor(event.currentTarget);
  };

  const handleDownloadFormat = (format: 'json' | 'csv') => {
    setMenuAnchor(null);
    if (onDownload) {
      onDownload(format);
    }
  };

  const handleLoadMore = useCallback(async () => {
    if (!pagination.download_token || isLoadingMore) return;

    setIsLoadingMore(true);
    try {
      const response = await api.paginateResults(
        pagination.download_token,
        currentOffset,
        15
      );

      if (response.success && response.data) {
        setDisplayedResults((prev) => [...prev, ...response.data]);
        setCurrentOffset((prev) => prev + response.data.length);
        setHasMoreToLoad(response.has_more);
        setRemainingCount(response.remaining);
      }
    } catch (error) {
      console.error('Failed to load more results:', error);
    } finally {
      setIsLoadingMore(false);
    }
  }, [pagination.download_token, currentOffset, isLoadingMore]);

  return (
    <Box
      sx={{
        mt: 1.5,
        borderRadius: borderRadius.md,
        backgroundColor: alpha(colors.background.elevated, 0.3),
        border: `1px solid ${alpha(colors.text.primary, 0.08)}`,
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          p: 1,
          borderBottom: `1px solid ${alpha(colors.text.primary, 0.08)}`,
        }}
      >
        <Typography
          variant="caption"
          sx={{ fontWeight: 600, color: colors.text.primary }}
        >
          Results
        </Typography>

        {/* Count chip */}
        <Chip
          label={`${displayedResults.length} of ${pagination.total_count}`}
          size="small"
          sx={{
            height: 18,
            fontSize: '0.6rem',
            backgroundColor: alpha(colors.info.main, 0.15),
            color: colors.info.light,
          }}
        />

        {/* More available indicator */}
        {hasMoreToLoad && (
          <Chip
            icon={<InfoIcon sx={{ fontSize: 12 }} />}
            label={`+${remainingCount} more`}
            size="small"
            sx={{
              height: 18,
              fontSize: '0.6rem',
              backgroundColor: alpha(colors.warning.main, 0.15),
              color: colors.warning.light,
              '& .MuiChip-icon': {
                color: colors.warning.light,
                marginLeft: '4px',
              },
            }}
          />
        )}

        <Box sx={{ flex: 1 }} />

        {/* View toggle */}
        <ToggleButtonGroup
          value={viewMode}
          exclusive
          onChange={handleViewChange}
          size="small"
          sx={{
            '& .MuiToggleButton-root': {
              padding: '2px 6px',
              border: `1px solid ${alpha(colors.text.primary, 0.1)}`,
              '&.Mui-selected': {
                backgroundColor: alpha(colors.primary.main, 0.2),
                color: colors.primary.light,
              },
            },
          }}
        >
          <ToggleButton value="table" aria-label="table view">
            <TableIcon sx={{ fontSize: 14 }} />
          </ToggleButton>
          <ToggleButton value="list" aria-label="list view">
            <ListIcon sx={{ fontSize: 14 }} />
          </ToggleButton>
        </ToggleButtonGroup>

        {/* Download button */}
        {pagination.suggest_download && pagination.download_token && (
          <>
            <Button
              size="small"
              variant="outlined"
              startIcon={
                isDownloading ? (
                  <CircularProgress size={12} color="inherit" />
                ) : (
                  <DownloadIcon sx={{ fontSize: 14 }} />
                )
              }
              endIcon={<MoreIcon sx={{ fontSize: 14 }} />}
              onClick={handleDownloadClick}
              disabled={isDownloading}
              sx={{
                height: 24,
                fontSize: '0.65rem',
                textTransform: 'none',
                borderColor: alpha(colors.accent.main, 0.5),
                color: colors.accent.light,
                '&:hover': {
                  borderColor: colors.accent.main,
                  backgroundColor: alpha(colors.accent.main, 0.1),
                },
              }}
            >
              Download All
            </Button>
            <Menu
              anchorEl={menuAnchor}
              open={Boolean(menuAnchor)}
              onClose={() => setMenuAnchor(null)}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
              transformOrigin={{ vertical: 'top', horizontal: 'right' }}
              PaperProps={{
                sx: {
                  backgroundColor: colors.background.elevated,
                  border: `1px solid ${alpha(colors.text.primary, 0.1)}`,
                },
              }}
            >
              <MenuItem onClick={() => handleDownloadFormat('json')}>
                <ListItemIcon>
                  <JsonIcon sx={{ fontSize: 16, color: colors.info.light }} />
                </ListItemIcon>
                <ListItemText
                  primary="JSON"
                  primaryTypographyProps={{ fontSize: '0.75rem' }}
                />
              </MenuItem>
              <MenuItem onClick={() => handleDownloadFormat('csv')}>
                <ListItemIcon>
                  <CsvIcon sx={{ fontSize: 16, color: colors.success.light }} />
                </ListItemIcon>
                <ListItemText
                  primary="CSV"
                  primaryTypographyProps={{ fontSize: '0.75rem' }}
                />
              </MenuItem>
            </Menu>
          </>
        )}
      </Box>

      {/* Suggestion alert */}
      {pagination.suggest_download && hasMoreToLoad && (
        <Alert
          severity="info"
          icon={<CloudDownloadIcon sx={{ fontSize: 16 }} />}
          sx={{
            py: 0.5,
            px: 1,
            backgroundColor: alpha(colors.info.main, 0.08),
            borderRadius: 0,
            '& .MuiAlert-message': {
              fontSize: '0.7rem',
            },
            '& .MuiAlert-icon': {
              color: colors.info.light,
              py: 0,
            },
          }}
        >
          Large result set detected. Use "See More" to view inline or download all {pagination.total_count} results.
        </Alert>
      )}

      {/* Results display */}
      <Box sx={{ maxHeight: 400, overflow: 'auto' }}>
        {viewMode === 'table' ? (
          <TableContainer>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  {columns.map((column) => (
                    <TableCell
                      key={column}
                      sx={{
                        backgroundColor: colors.background.elevated,
                        color: colors.text.primary,
                        fontSize: '0.7rem',
                        fontWeight: 600,
                        py: 0.75,
                        borderBottom: `1px solid ${alpha(colors.text.primary, 0.1)}`,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {formatHeader(column)}
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {displayedResults.map((result, idx) => (
                  <TableRow
                    key={idx}
                    sx={{
                      '&:hover': {
                        backgroundColor: alpha(colors.text.primary, 0.03),
                      },
                    }}
                  >
                    {columns.map((column) => (
                      <TableCell
                        key={column}
                        sx={{
                          fontSize: '0.65rem',
                          color: colors.text.secondary,
                          py: 0.5,
                          borderBottom: `1px solid ${alpha(colors.text.primary, 0.05)}`,
                          maxWidth: 200,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {formatValue(result[column])}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        ) : (
          <Box sx={{ p: 1 }}>
            {displayedResults.map((result, idx) => (
              <Paper
                key={idx}
                elevation={0}
                sx={{
                  p: 1,
                  mb: 1,
                  backgroundColor: alpha(colors.background.paper, 0.5),
                  border: `1px solid ${alpha(colors.text.primary, 0.05)}`,
                  borderRadius: borderRadius.sm,
                  '&:last-child': { mb: 0 },
                }}
              >
                {columns.slice(0, 6).map((column) => (
                  <Box
                    key={column}
                    sx={{
                      display: 'flex',
                      gap: 1,
                      mb: 0.25,
                      '&:last-child': { mb: 0 },
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{
                        fontSize: '0.6rem',
                        color: colors.text.muted,
                        minWidth: 60,
                        fontWeight: 600,
                      }}
                    >
                      {formatHeader(column)}:
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{
                        fontSize: '0.65rem',
                        color: colors.text.secondary,
                        flex: 1,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {formatValue(result[column])}
                    </Typography>
                  </Box>
                ))}
              </Paper>
            ))}
          </Box>
        )}
      </Box>

      {/* See More Button - inline pagination */}
      {hasMoreToLoad && pagination.download_token && (
        <>
          <Divider sx={{ borderColor: alpha(colors.text.primary, 0.08) }} />
          <Box
            sx={{
              p: 1,
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              gap: 1,
              backgroundColor: alpha(colors.accent.main, 0.05),
            }}
          >
            <Button
              size="small"
              variant="text"
              startIcon={
                isLoadingMore ? (
                  <CircularProgress size={14} color="inherit" />
                ) : (
                  <ShowMoreIcon sx={{ fontSize: 16 }} />
                )
              }
              onClick={handleLoadMore}
              disabled={isLoadingMore}
              sx={{
                fontSize: '0.7rem',
                textTransform: 'none',
                color: colors.accent.light,
                fontWeight: 500,
                '&:hover': {
                  backgroundColor: alpha(colors.accent.main, 0.1),
                },
              }}
            >
              {isLoadingMore
                ? 'Loading...'
                : `See More (${remainingCount} remaining)`}
            </Button>
          </Box>
        </>
      )}

      {/* Footer with pagination info */}
      {pagination.download_expires_at && (
        <Box
          sx={{
            p: 0.75,
            borderTop: `1px solid ${alpha(colors.text.primary, 0.08)}`,
            display: 'flex',
            justifyContent: 'flex-end',
          }}
        >
          <Typography
            variant="caption"
            sx={{ fontSize: '0.6rem', color: colors.text.muted }}
          >
            Download token expires: {new Date(pagination.download_expires_at).toLocaleTimeString()}
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default PaginatedResults;
