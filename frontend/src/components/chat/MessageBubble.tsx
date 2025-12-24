import React, { useState, useCallback } from 'react';
import { Box, Typography, Paper, Chip, Avatar } from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  Cached as CacheIcon,
  AccessTime as TimeIcon,
  Block as BlockedIcon,
  Error as ErrorIcon,
  Person as PersonIcon,
  Psychology as AIIcon,
  ShieldOutlined as GuardrailsIcon,
} from '@mui/icons-material';
import { colors, borderRadius, transitions } from '../../theme';
import { RouteChip } from './RouteChip';
import { TokenUsageMeter } from '../TokenUsageMeter';
import { PipelineTracePanel } from '../pipeline/PipelineTracePanel';
import { PaginatedResults } from '../results/PaginatedResults';
import type { ChatMessage } from '../../types';

interface MessageBubbleProps {
  message: ChatMessage;
  onDownload?: (token: string, format: 'json' | 'csv') => void;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message, onDownload }) => {
  const [isDownloading, setIsDownloading] = useState(false);
  const isUser = message.type === 'user';
  const isBlocked = message.type === 'blocked';
  const isError = message.type === 'error';
  const isBot = message.type === 'bot';

  // Check for enhanced metadata
  const hasTokenUsage = message.metadata?.token_usage;
  const hasPipelineTrace = message.metadata?.trace;
  const hasPagination = message.metadata?.pagination && message.metadata?.results;
  const isGuardrailsBypassed = message.metadata?.guardrails_bypassed;

  const handleDownload = useCallback(
    async (format: 'json' | 'csv') => {
      const token = message.metadata?.pagination?.download_token;
      if (!token || !onDownload) return;

      setIsDownloading(true);
      try {
        await onDownload(token, format);
      } finally {
        setIsDownloading(false);
      }
    },
    [message.metadata?.pagination?.download_token, onDownload]
  );

  return (
    <Box
      role="article"
      aria-label={`${isUser ? 'User' : 'Bot'} message`}
      sx={{
        display: 'flex',
        flexDirection: isUser ? 'row-reverse' : 'row',
        alignItems: 'flex-start',
        gap: 1.5,
        maxWidth: '90%',
        alignSelf: isUser ? 'flex-end' : 'flex-start',
        animation: 'messageSlideIn 0.3s ease-out',
        '@keyframes messageSlideIn': {
          from: {
            opacity: 0,
            transform: isUser ? 'translateX(20px)' : 'translateX(-20px)',
          },
          to: {
            opacity: 1,
            transform: 'translateX(0)',
          },
        },
      }}
    >
      {/* Avatar */}
      <Avatar
        aria-label={isUser ? 'User Avatar' : 'Bot Avatar'}
        sx={{
          width: 36,
          height: 36,
          backgroundColor: isUser
            ? colors.primary.main
            : isError
            ? colors.error.main
            : isBlocked
            ? colors.warning.main
            : colors.accent.main,
          boxShadow: `0 4px 12px ${alpha(
            isUser ? colors.primary.main : colors.accent.main,
            0.3
          )}`,
        }}
      >
        {isUser ? (
          <PersonIcon sx={{ fontSize: 20 }} />
        ) : (
          <AIIcon sx={{ fontSize: 20 }} />
        )}
      </Avatar>

      {/* Message Content */}
      <Paper
        elevation={0}
        sx={{
          p: 2,
          borderRadius: borderRadius.md,
          width: 'fit-content',
          minWidth: 0,
          maxWidth: '100%',
          transition: transitions.fast,
          // User message styling
          ...(isUser && {
            background: `linear-gradient(135deg, ${colors.primary.main} 0%, ${colors.primary.dark} 100%)`,
            color: 'white',
            borderBottomRightRadius: borderRadius.sm,
          }),
          // Bot message styling
          ...(isBot && {
            backgroundColor: alpha(colors.accent.main, 0.08),
            border: `1px solid ${alpha(colors.accent.main, 0.2)}`,
            borderBottomLeftRadius: borderRadius.sm,
          }),
          // Blocked message styling
          ...(isBlocked && {
            backgroundColor: alpha(colors.warning.main, 0.1),
            border: `1px solid ${alpha(colors.warning.main, 0.4)}`,
            borderBottomLeftRadius: borderRadius.sm,
          }),
          // Error message styling
          ...(isError && {
            backgroundColor: alpha(colors.error.main, 0.1),
            border: `1px solid ${alpha(colors.error.main, 0.4)}`,
            borderBottomLeftRadius: borderRadius.sm,
          }),
          '&:hover': {
            transform: 'scale(1.005)',
          },
        }}
      >
        {/* Error/Blocked Header */}
        {(isBlocked || isError) && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
            {isBlocked ? (
              <BlockedIcon sx={{ fontSize: 18, color: colors.warning.main }} />
            ) : (
              <ErrorIcon sx={{ fontSize: 18, color: colors.error.main }} />
            )}
            <Typography
              variant="subtitle2"
              fontWeight={600}
              color={isBlocked ? 'warning.main' : 'error.main'}
            >
              {isBlocked ? 'Blocked by Guardrail' : 'Error'}
            </Typography>
          </Box>
        )}

        {/* Message Content */}
        <Typography
          variant="body2"
          sx={{
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            overflowWrap: 'break-word',
            width: '100%',
            lineHeight: 1.6,
            color: isUser ? 'inherit' : 'text.primary',
          }}
        >
          {message.content}
        </Typography>

        {/* Metadata Section */}
        {message.metadata && (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 1,
              mt: 1.5,
              pt: 1.5,
              borderTop: `1px solid ${alpha(
                isUser ? '#fff' : colors.text.primary,
                0.1
              )}`,
            }}
          >
            {message.metadata.route && (
              <RouteChip route={message.metadata.route} />
            )}

            {message.metadata.cached && (
              <Chip
                icon={<CacheIcon sx={{ fontSize: 12 }} />}
                label="Cached"
                size="small"
                aria-label="Cached"
                sx={{
                  fontSize: '0.65rem',
                  height: 22,
                  backgroundColor: alpha(colors.success.main, 0.15),
                  color: colors.success.light,
                  border: `1px solid ${alpha(colors.success.main, 0.3)}`,
                  '& .MuiChip-icon': {
                    color: colors.success.light,
                  },
                }}
              />
            )}

            {message.metadata.tool && (
              <Chip
                label={message.metadata.tool}
                size="small"
                aria-label={`Tool: ${message.metadata.tool}`}
                sx={{
                  fontSize: '0.65rem',
                  height: 22,
                  backgroundColor: alpha(colors.info.main, 0.15),
                  color: colors.info.light,
                  border: `1px solid ${alpha(colors.info.main, 0.3)}`,
                }}
              />
            )}

            {message.metadata.latency_ms !== undefined && (
              <Box
                aria-label={`Latency: ${message.metadata.latency_ms} milliseconds`}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  color: isUser ? alpha('#fff', 0.7) : 'text.secondary',
                  fontSize: '0.7rem',
                }}
              >
                <TimeIcon sx={{ fontSize: 12 }} />
                <Typography variant="caption">
                  {message.metadata.latency_ms}ms
                </Typography>
              </Box>
            )}

            {/* Guardrails bypassed indicator */}
            {isGuardrailsBypassed && (
              <Chip
                icon={<GuardrailsIcon sx={{ fontSize: 12 }} />}
                label="Guardrails Off"
                size="small"
                aria-label="Guardrails bypassed"
                sx={{
                  fontSize: '0.65rem',
                  height: 22,
                  backgroundColor: alpha(colors.warning.main, 0.15),
                  color: colors.warning.light,
                  border: `1px solid ${alpha(colors.warning.main, 0.3)}`,
                  '& .MuiChip-icon': {
                    color: colors.warning.light,
                  },
                }}
              />
            )}

            {/* Token usage meter (compact) */}
            {hasTokenUsage && (
              <TokenUsageMeter usage={message.metadata.token_usage!} compact />
            )}
          </Box>
        )}

        {/* Enhanced components - only for bot messages */}
        {isBot && (
          <>
            {/* Pipeline trace panel */}
            {hasPipelineTrace && (
              <PipelineTracePanel trace={message.metadata!.trace!} />
            )}

            {/* Paginated results */}
            {hasPagination && (
              <PaginatedResults
                results={message.metadata!.results!}
                pagination={message.metadata!.pagination!}
                onDownload={handleDownload}
                isDownloading={isDownloading}
              />
            )}
          </>
        )}
      </Paper>
    </Box>
  );
};

export default MessageBubble;