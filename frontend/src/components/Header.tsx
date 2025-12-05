import React, { useState, useCallback } from 'react';
import { Box, Typography, Chip, IconButton, Tooltip } from '@mui/material';
import {
  Refresh as RefreshIcon, Storage as StorageIcon, Cloud as CloudIcon,
  DeleteSweep as ClearCacheIcon, AddComment as NewChatIcon, Forum as SessionIcon,
} from '@mui/icons-material';
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

interface StatusChipProps {
  active: boolean;
  icon: React.ReactElement;
  activeLabel: string;
  inactiveLabel: string;
  activeColor: string;
}

const StatusChip: React.FC<StatusChipProps> = ({ active, icon, activeLabel, inactiveLabel, activeColor }) => (
  <Chip
    icon={icon}
    label={active ? activeLabel : inactiveLabel}
    size="small"
    sx={{
      backgroundColor: `${active ? activeColor : colors.neutral.main}22`,
      color: active ? activeColor : colors.neutral.light,
      borderColor: active ? activeColor : colors.neutral.main,
      border: 1,
    }}
  />
);

export const Header: React.FC<HeaderProps> = ({
  health, cacheStats, sessionId, onRefresh, onClearCache, onNewSession, loading,
}) => {
  const [clearing, setClearing] = useState(false);

  const handleClearCache = useCallback(async () => {
    setClearing(true);
    await onClearCache();
    setClearing(false);
  }, [onClearCache]);

  const isNovaConnected = health?.nova ?? false;

  return (
    <Box sx={styles.header.root}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Typography variant="h4" sx={styles.header.title}>USPS ICDA Prototype</Typography>
        <Typography variant="body2" color="text.secondary">Intelligent Customer Data Access by ECS</Typography>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Tooltip title={sessionId ? `Session: ${sessionId.slice(0, 8)}...` : 'No active session'}>
          <span>
            <StatusChip
              active={!!sessionId}
              icon={<SessionIcon />}
              activeLabel="Context Active"
              inactiveLabel="No Context"
              activeColor={colors.primary.main}
            />
          </span>
        </Tooltip>

        <Tooltip title="Start New Conversation">
          <IconButton onClick={onNewSession} size="small" sx={{ color: colors.primary.light, '&:hover': { backgroundColor: `${colors.primary.main}22` } }}>
            <NewChatIcon />
          </IconButton>
        </Tooltip>

        <StatusChip
          active={isNovaConnected}
          icon={<CloudIcon />}
          activeLabel="Nova Connected"
          inactiveLabel="Nova Unavailable"
          activeColor={colors.success.main}
        />

        <Chip
          icon={<StorageIcon />}
          label={`${cacheStats?.keys ?? 0} cached`}
          size="small"
          sx={{ backgroundColor: `${colors.info.main}22`, color: colors.info.light, borderColor: colors.info.main, border: 1 }}
        />

        <Tooltip title="Clear Redis Cache">
          <IconButton
            onClick={handleClearCache}
            disabled={clearing || loading || (cacheStats?.keys ?? 0) === 0}
            size="small"
            sx={{ color: colors.error.light, '&:hover': { backgroundColor: `${colors.error.main}22` } }}
          >
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
