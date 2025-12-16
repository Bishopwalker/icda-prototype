import React, { useState, useCallback } from 'react';
import { Box, Typography, Chip, IconButton, Tooltip } from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  Refresh as RefreshIcon, Storage as StorageIcon, Cloud as CloudIcon,
  DeleteSweep as ClearCacheIcon, AddComment as NewChatIcon, Forum as SessionIcon,
  Psychology as AIIcon, LocalPostOffice as MailIcon, AdminPanelSettings as AdminIcon,
} from '@mui/icons-material';
import { colors, borderRadius, transitions } from '../theme';
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
    role="status"
    aria-label={active ? activeLabel : inactiveLabel}
    sx={{
      backgroundColor: alpha(active ? activeColor : colors.neutral.main, 0.15),
      color: active ? activeColor : colors.neutral.light,
      border: `1px solid ${alpha(active ? activeColor : colors.neutral.main, 0.3)}`,
      transition: transitions.fast,
      '& .MuiChip-icon': {
        color: active ? activeColor : colors.neutral.light,
      },
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
    <Box
      component="header"
      sx={{
        py: 2,
        px: 3,
        borderBottom: `1px solid ${alpha(colors.primary.main, 0.2)}`,
        backgroundColor: alpha(colors.background.paper, 0.8),
        backdropFilter: 'blur(10px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 2,
      }}
    >
      {/* Left side - Logo and title */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        {/* ICDA Logo */}
        <Box
          role="img"
          aria-label="ICDA Logo"
          sx={{
            width: 44,
            height: 44,
            borderRadius: borderRadius.lg,
            background: `linear-gradient(135deg, ${colors.usps.blue} 0%, ${colors.accent.main} 100%)`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: `0 4px 12px ${alpha(colors.accent.main, 0.3)}`,
          }}
        >
          <AIIcon sx={{ fontSize: 26, color: '#fff' }} />
        </Box>

        <Box>
          <Typography
            variant="h5"
            component="h1"
            sx={{
              fontWeight: 700,
              color: 'text.primary',
              display: 'flex',
              alignItems: 'center',
              gap: 1,
            }}
          >
            ICDA
            <Chip
              icon={<MailIcon sx={{ fontSize: 14 }} />}
              label="USPS"
              size="small"
              aria-label="USPS Chip"
              sx={{
                height: 22,
                fontSize: '0.65rem',
                backgroundColor: alpha(colors.usps.blue, 0.2),
                color: colors.usps.lightBlue,
                border: `1px solid ${alpha(colors.usps.blue, 0.4)}`,
                '& .MuiChip-icon': {
                  color: colors.usps.lightBlue,
                },
              }}
            />
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Intelligent Customer Data Access • Powered by{' '}
            <span style={{ color: '#FF0000', fontWeight: 900, textShadow: '0 0 2px rgba(255, 0, 0, 0.5)' }}>ECS</span>
          </Typography>
        </Box>
      </Box>

      {/* Right side - Status indicators and actions */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
        {/* Session Status */}
        <Tooltip title={sessionId ? `Session: ${sessionId.slice(0, 8)}...` : 'No active session'}>
          <span>
            <StatusChip
              active={!!sessionId}
              icon={<SessionIcon sx={{ fontSize: 16 }} />}
              activeLabel="Context Active"
              inactiveLabel="No Context"
              activeColor={colors.accent.main}
            />
          </span>
        </Tooltip>

        {/* New Chat Button */}
        <Tooltip title="Start New Conversation">
          <IconButton
            onClick={onNewSession}
            aria-label="Start New Conversation"
            size="small"
            sx={{
              color: colors.primary.light,
              backgroundColor: alpha(colors.primary.main, 0.1),
              transition: transitions.fast,
              '&:hover': {
                backgroundColor: alpha(colors.primary.main, 0.2),
                transform: 'scale(1.05)',
              },
            }}
          >
            <NewChatIcon sx={{ fontSize: 20 }} />
          </IconButton>
        </Tooltip>

        {/* Nova Status */}
        <StatusChip
          active={isNovaConnected}
          icon={<CloudIcon sx={{ fontSize: 16 }} />}
          activeLabel="Nova Online"
          inactiveLabel="Nova Offline"
          activeColor={colors.success.light}
        />

        {/* Cache Stats */}
        <Chip
          icon={<StorageIcon sx={{ fontSize: 16 }} />}
          label={`${cacheStats?.keys ?? 0} cached`}
          size="small"
          aria-live="polite"
          aria-label={`${cacheStats?.keys ?? 0} items cached`}
          sx={{
            backgroundColor: alpha(colors.info.main, 0.15),
            color: colors.info.light,
            border: `1px solid ${alpha(colors.info.main, 0.3)}`,
            '& .MuiChip-icon': {
              color: colors.info.light,
            },
          }}
        />

        {/* Clear Cache Button */}
        <Tooltip title="Clear Redis Cache">
          <span>
            <IconButton
              onClick={handleClearCache}
              disabled={clearing || loading || (cacheStats?.keys ?? 0) === 0}
              aria-label="Clear Redis Cache"
              size="small"
              sx={{
                color: colors.error.light,
                backgroundColor: alpha(colors.error.main, 0.1),
                transition: transitions.fast,
                '&:hover': {
                  backgroundColor: alpha(colors.error.main, 0.2),
                },
                '&:disabled': {
                  opacity: 0.4,
                },
                '@keyframes spin': {
                  from: { transform: 'rotate(0deg)' },
                  to: { transform: 'rotate(360deg)' },
                },
              }}
            >
              <ClearCacheIcon
                sx={{
                  fontSize: 20,
                  animation: clearing ? 'spin 1s linear infinite' : 'none',
                  '@media (prefers-reduced-motion: reduce)': {
                    animation: 'none',
                  },
                }}
              />
            </IconButton>
          </span>
        </Tooltip>

        {/* Customer Count */}
        {health && health.customers != null && (
          <Chip
            label={`${health.customers.toLocaleString()} customers`}
            size="small"
            variant="outlined"
            aria-label={`${health.customers.toLocaleString()} customers`}
            sx={{
              borderColor: alpha(colors.text.primary, 0.2),
              color: 'text.secondary',
            }}
          />
        )}

        {/* Refresh Button */}
        <Tooltip title="Refresh status">
          <span>
            <IconButton
              onClick={onRefresh}
              disabled={loading}
              aria-label="Refresh status"
              size="small"
              sx={{
                color: 'text.secondary',
                transition: transitions.fast,
                '&:hover': {
                  color: colors.accent.light,
                  backgroundColor: alpha(colors.accent.main, 0.1),
                },
                '@keyframes spin': {
                  from: { transform: 'rotate(0deg)' },
                  to: { transform: 'rotate(360deg)' },
                },
              }}
            >
              <RefreshIcon
                sx={{
                  fontSize: 20,
                  animation: loading ? 'spin 1s linear infinite' : 'none',
                  '@media (prefers-reduced-motion: reduce)': {
                    animation: 'none',
                  },
                }}
              />
            </IconButton>
          </span>
        </Tooltip>

        {/* Admin Panel Button */}
        <Tooltip title="Admin Panel">
          <IconButton
            component="a"
            href="/admin"
            aria-label="Admin Panel"
            size="small"
            sx={{
              color: colors.warning.light,
              backgroundColor: alpha(colors.warning.main, 0.1),
              transition: transitions.fast,
              '&:hover': {
                backgroundColor: alpha(colors.warning.main, 0.2),
                transform: 'scale(1.05)',
              },
            }}
          >
            <AdminIcon sx={{ fontSize: 20 }} />
          </IconButton>
        </Tooltip>
      </Box>
    </Box>
  );
};

export default Header;