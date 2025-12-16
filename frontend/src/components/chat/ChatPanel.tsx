import React, { useRef, useEffect } from 'react';
import { Box, Typography, CircularProgress } from '@mui/material';
import { alpha } from '@mui/material/styles';
import { colors, borderRadius } from '../../theme';
import { MessageBubble } from './MessageBubble';
import { WelcomePanel } from '../WelcomePanel';
import { QuickActions } from '../QuickActions';
import type { ChatMessage } from '../../types';

interface ChatPanelProps {
  messages: ChatMessage[];
  loading: boolean;
  onQuickAction?: (query: string) => void;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ messages, loading, onQuickAction }) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const hasMessages = messages.length > 0;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const handleQuickAction = (query: string) => {
    onQuickAction?.(query);
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0,
        overflow: 'hidden',
        background: `linear-gradient(180deg, ${colors.background.default} 0%, ${colors.background.paper} 100%)`,
      }}
    >
      <Box
        ref={scrollRef}
        role="log"
        aria-live="polite"
        aria-atomic="false"
        sx={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          overflowX: 'hidden',
          p: hasMessages ? 2 : 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        {!hasMessages ? (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              flex: 1,
              minHeight: 0,
            }}
          >
            {/* Welcome Panel with AI Greeting */}
            <WelcomePanel visible={!hasMessages} />

            {/* Quick Action Buttons */}
            <QuickActions
              visible={!hasMessages}
              onSelectAction={handleQuickAction}
            />
          </Box>
        ) : (
          <>
            {/* Conversation Header */}
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'center',
                mb: 2,
              }}
            >
              <Box
                sx={{
                  px: 3,
                  py: 1,
                  borderRadius: borderRadius.xl,
                  backgroundColor: alpha(colors.accent.main, 0.1),
                  border: `1px solid ${alpha(colors.accent.main, 0.2)}`,
                }}
              >
                <Typography
                  variant="caption"
                  sx={{
                    color: colors.accent.light,
                    fontWeight: 500,
                    letterSpacing: 0.5,
                  }}
                >
                  ICDA Conversation
                </Typography>
              </Box>
            </Box>

            {/* Messages */}
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
          </>
        )}

        {/* Loading Indicator */}
        {loading && (
          <Box
            role="status"
            aria-label="ICDA is thinking"
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              alignSelf: 'flex-start',
              p: 2,
              borderRadius: borderRadius.lg,
              backgroundColor: alpha(colors.accent.main, 0.1),
              border: `1px solid ${alpha(colors.accent.main, 0.2)}`,
              animation: 'fadeIn 0.3s ease-out',
              '@keyframes fadeIn': {
                from: { opacity: 0, transform: 'translateY(10px)' },
                to: { opacity: 1, transform: 'translateY(0)' },
              },
            }}
          >
            <CircularProgress size={20} sx={{ color: colors.accent.main }} />
            <Typography variant="body2" sx={{ color: colors.accent.light }}>
              ICDA is thinking...
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default ChatPanel;