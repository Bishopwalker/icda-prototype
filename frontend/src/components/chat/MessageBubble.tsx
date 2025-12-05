import React from 'react';
import { Box, Typography, Paper, Chip } from '@mui/material';
import {
  Cached as CacheIcon,
  AccessTime as TimeIcon,
  Block as BlockedIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import { styles } from '../../theme/styles';
import { colors } from '../../theme';
import { RouteChip } from './RouteChip';
import type { ChatMessage } from '../../types';

interface MessageBubbleProps {
  message: ChatMessage;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.type === 'user';
  const isBlocked = message.type === 'blocked';
  const isError = message.type === 'error';

  const bubbleStyle = {
    ...styles.chat.message.base,
    ...(isUser && styles.chat.message.user),
    ...(message.type === 'bot' && styles.chat.message.bot),
    ...(isBlocked && styles.chat.message.blocked),
    ...(isError && styles.chat.message.error),
  };

  return (
    <Paper sx={bubbleStyle} elevation={0}>
      {(isBlocked || isError) && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          {isBlocked ? (
            <BlockedIcon sx={{ fontSize: 16, color: colors.warning.main }} />
          ) : (
            <ErrorIcon sx={{ fontSize: 16, color: colors.error.main }} />
          )}
          <Typography variant="caption" fontWeight={600} color={isBlocked ? 'warning.main' : 'error.main'}>
            {isBlocked ? 'Blocked by Guardrail' : 'Error'}
          </Typography>
        </Box>
      )}

      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
        {message.content}
      </Typography>

      {message.metadata && (
        <Box sx={styles.chat.metadata}>
          {message.metadata.route && <RouteChip route={message.metadata.route} />}
          {message.metadata.cached && (
            <Chip
              icon={<CacheIcon sx={{ fontSize: 12 }} />}
              label="Cached"
              size="small"
              sx={{ fontSize: '0.65rem', height: 18, backgroundColor: `${colors.success.main}22`, color: colors.success.light }}
            />
          )}
          {message.metadata.tool && (
            <Chip label={message.metadata.tool} size="small" sx={{ fontSize: '0.65rem', height: 18 }} />
          )}
          {message.metadata.latency_ms !== undefined && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
              <TimeIcon sx={{ fontSize: 12 }} />
              <Typography variant="caption">{message.metadata.latency_ms}ms</Typography>
            </Box>
          )}
        </Box>
      )}
    </Paper>
  );
};

export default MessageBubble;
