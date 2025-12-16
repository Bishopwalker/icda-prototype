import React, { useState, useEffect, useMemo } from 'react';
import { Box, Typography, Fade, Chip } from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  LocalPostOffice as MailIcon,
  Psychology as AIIcon,
  Verified as VerifiedIcon,
} from '@mui/icons-material';
import { colors, borderRadius, transitions } from '../theme';

/**
 * Dynamic greeting messages for ICDA AI.
 * These rotate to keep the experience fresh and conversational.
 */
const GREETINGS = [
  {
    main: "Hey there! I'm ICDA, USPS's latest AI from ECS.",
    sub: "I'm here to answer all your addressing needs. What can I help you with today?",
  },
  {
    main: "Welcome! I'm ICDA, your intelligent addressing assistant.",
    sub: "Got an address question? A lookup to run? I'm all ears. Fire away!",
  },
  {
    main: "Hi! ICDA here, powered by USPS and ECS.",
    sub: "Whether you need to verify an address or search customer data, I've got you covered.",
  },
  {
    main: "Good to see you! I'm ICDA, your AI addressing expert.",
    sub: "Let's solve some addressing puzzles together. What do you need?",
  },
  {
    main: "Hey! ICDA at your service, straight from ECS.",
    sub: "Addresses, lookups, analytics - you name it, I can help. What's on your mind?",
  },
  {
    main: "Welcome back! ICDA here, ready to assist.",
    sub: "I'm your go-to AI for all things USPS addressing. Let's get started!",
  },
  {
    main: "Hello! I'm ICDA, USPS's smart addressing assistant.",
    sub: "Need to complete a partial address? Find a customer? Just ask!",
  },
  {
    main: "Yo! ICDA in the house, courtesy of ECS.",
    sub: "I specialize in addresses, customer lookups, and making your life easier. What's up?",
  },
];

/**
 * Quick tip messages that appear below the greeting.
 */
const TIPS = [
  "Try typing a partial address and I'll suggest where it might go!",
  "Use the quick action buttons below to jump right in.",
  "I can look up customers by CRID, name, or address.",
  "Ask me for stats like 'How many customers in Nevada?'",
  "Upload a file with addresses and I'll verify them for you.",
  "I remember our conversation, so feel free to ask follow-up questions!",
];

interface WelcomePanelProps {
  visible: boolean;
}

export const WelcomePanel: React.FC<WelcomePanelProps> = ({ visible }) => {
  const [showContent, setShowContent] = useState(false);
  const [currentTipIndex, setCurrentTipIndex] = useState(0);
  // Styled ECS component - bright red and bold
  const ECSStyled: React.FC = () => (
    <span style={{
      color: '#FF0000',
      fontWeight: 900,
      textShadow: '0 0 2px rgba(255, 0, 0, 0.5)',
    }}>ECS</span>
  );

  // Helper to replace "ECS" in text with styled component
  const highlightECS = (text: string): React.ReactNode => {
    const parts = text.split(/(ECS)/g);
    return parts.map((part, i) =>
      part === 'ECS' ? <ECSStyled key={i} /> : part
    );
  };

  // Select a random greeting on mount (memoized so it doesn't change during session)
  const greeting = useMemo(() => {
    const randomIndex = Math.floor(Math.random() * GREETINGS.length);
    return GREETINGS[randomIndex];
  }, []);

  // Animate in the content after mount
  useEffect(() => {
    if (visible) {
      const timer = setTimeout(() => setShowContent(true), 100);
      return () => clearTimeout(timer);
    }
    setShowContent(false);
  }, [visible]);

  // Rotate tips every 8 seconds
  useEffect(() => {
    if (!visible) return;
    const interval = setInterval(() => {
      setCurrentTipIndex((prev) => (prev + 1) % TIPS.length);
    }, 8000);
    return () => clearInterval(interval);
  }, [visible]);

  if (!visible) return null;
  return (
    <Fade in={showContent} timeout={600}>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          textAlign: 'center',
          py: 6,
          px: 3,
          maxWidth: 700,
          mx: 'auto',
        }}
      >
        {/* AI Avatar/Logo */}
        <Box
          aria-label="AI Avatar"
          sx={{
            width: 100,
            height: 100,
            borderRadius: borderRadius.round,
            background: `linear-gradient(135deg, ${colors.primary.main}, ${colors.accent.main})`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            mb: 3,
            boxShadow: `0 0 40px ${alpha(colors.accent.main, 0.4)}`,
            animation: 'pulse 2s ease-in-out infinite',
            '@keyframes pulse': {
              '0%, 100%': {
                boxShadow: `0 0 20px ${alpha(colors.accent.main, 0.3)}`,
              },
              '50%': {
                boxShadow: `0 0 40px ${alpha(colors.accent.main, 0.5)}`,
              },
            },
          }}
        >
          <AIIcon sx={{ fontSize: 50, color: '#fff' }} />
        </Box>

        {/* Brand Chips */}
        <Box sx={{ display: 'flex', gap: 1, mb: 3, flexWrap: 'wrap', justifyContent: 'center' }}>
          <Chip
            icon={<MailIcon sx={{ fontSize: 16 }} />}
            label="USPS"
            size="small"
            aria-label="USPS Brand Chip"
            sx={{
              backgroundColor: alpha(colors.usps.blue, 0.2),
              color: colors.usps.lightBlue,
              border: `1px solid ${alpha(colors.usps.blue, 0.4)}`,
            }}
          />
          <Chip
            icon={<VerifiedIcon sx={{ fontSize: 16 }} />}
            label={<>Powered by <ECSStyled /></>}
            size="small"
            aria-label="Powered by ECS Brand Chip"
            sx={{
              backgroundColor: alpha(colors.accent.main, 0.2),
              color: colors.accent.light,
              border: `1px solid ${alpha(colors.accent.main, 0.4)}`,
            }}
          />
        </Box>

        {/* Main Greeting */}
        <Typography
          variant="h4"
          component="h1"
          sx={{
            fontWeight: 700,
            mb: 2,
            background: `linear-gradient(135deg, ${colors.text.primary}, ${colors.accent.light})`,
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
        >
          {highlightECS(greeting.main)}
        </Typography>

        {/* Sub Greeting */}
        <Typography
          variant="body1"
          sx={{
            color: 'text.secondary',
            mb: 4,
            maxWidth: 500,
            lineHeight: 1.7,
          }}
        >
          {greeting.sub}
        </Typography>

        {/* Rotating Tip */}
        <Box
          role="status"
          aria-live="polite"
          sx={{
            mt: 2,
            p: 2,
            borderRadius: borderRadius.lg,
            backgroundColor: alpha(colors.primary.main, 0.1),
            border: `1px solid ${alpha(colors.primary.main, 0.2)}`,
            transition: transitions.normal,
          }}
        >
          <Typography
            variant="body2"
            sx={{
              color: colors.accent.light,
              fontStyle: 'italic',
              display: 'flex',
              alignItems: 'center',
              gap: 1,
            }}
          >
            <Box
              component="span"
              sx={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                backgroundColor: colors.accent.main,
                animation: 'blink 1.5s ease-in-out infinite',
                '@keyframes blink': {
                  '0%, 100%': { opacity: 1 },
                  '50%': { opacity: 0.3 },
                },
              }}
            />
            💡 {TIPS[currentTipIndex]}
          </Typography>
        </Box>
      </Box>
    </Fade>
  );
};

export default WelcomePanel;