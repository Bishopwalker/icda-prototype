import React from 'react';
import { Box, Typography, Paper, Tooltip, Fade } from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  Search as SearchIcon,
  Badge as BadgeIcon,
  Analytics as StatsIcon,
  LocationOn as AddressIcon,
  FormatListNumbered as ListIcon,
  HelpOutline as HelpIcon,
} from '@mui/icons-material';
import { colors, borderRadius, transitions } from '../theme';

/**
 * Quick action configurations - 6 smart query options for users.
 * Each action provides a pre-filled query to help users get started.
 */
const QUICK_ACTIONS = [
  {
    id: 'lookup',
    icon: BadgeIcon,
    label: 'Customer Lookup',
    description: 'Search by CRID or name',
    query: 'Look up CRID-001',
    color: colors.quickActions.lookup,
    examples: ['Look up CRID-042', 'Find customer John Smith'],
  },
  {
    id: 'address',
    icon: AddressIcon,
    label: 'Address Search',
    description: 'Find addresses or verify',
    query: 'Show me customers at 123 Main Street',
    color: colors.quickActions.address,
    examples: ['Find addresses in 89101', '101 turkey ok 22222'],
  },
  {
    id: 'search',
    icon: SearchIcon,
    label: 'Smart Search',
    description: 'Natural language queries',
    query: 'Show me Nevada customers who moved twice',
    color: colors.quickActions.search,
    examples: ['Active customers in Texas', 'Businesses in Las Vegas'],
  },
  {
    id: 'stats',
    icon: StatsIcon,
    label: 'Get Statistics',
    description: 'Analytics and summaries',
    query: 'How many customers per state?',
    color: colors.quickActions.stats,
    examples: ['Average move count', 'Customer distribution'],
  },
  {
    id: 'list',
    icon: ListIcon,
    label: 'List Addresses',
    description: 'View address records',
    query: 'Show me my first 25 addresses',
    color: colors.quickActions.list,
    examples: ['List all California addresses', 'Top 10 recent customers'],
  },
  {
    id: 'help',
    icon: HelpIcon,
    label: 'Help & Examples',
    description: 'What can I ask?',
    query: 'What kind of questions can you answer?',
    color: colors.quickActions.help,
    examples: ['Show capabilities', 'How to verify addresses'],
  },
];

interface QuickActionsProps {
  onSelectAction: (query: string) => void;
  visible: boolean;
}

export const QuickActions: React.FC<QuickActionsProps> = ({ onSelectAction, visible }) => {
  if (!visible) return null;

  return (
    <Fade in={visible} timeout={400}>
      <Box sx={{ px: 3, pb: 3 }}>
        <Typography
          variant="subtitle2"
          sx={{
            color: 'text.secondary',
            mb: 2,
            textAlign: 'center',
            textTransform: 'uppercase',
            letterSpacing: 1.5,
            fontSize: '0.7rem',
          }}
        >
          Quick Actions - Click to start
        </Typography>

        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: 'repeat(2, 1fr)',
              sm: 'repeat(3, 1fr)',
              md: 'repeat(6, 1fr)',
            },
            gap: 2,
            maxWidth: 1000,
            mx: 'auto',
          }}
        >
          {QUICK_ACTIONS.map((action, index) => (
            <Tooltip
              key={action.id}
              title={
                <Box sx={{ p: 0.5 }}>
                  <Typography variant="body2" fontWeight={600} sx={{ mb: 0.5 }}>
                    {action.description}
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    Examples:
                  </Typography>
                  <Box component="ul" sx={{ m: 0, pl: 2, mt: 0.5 }}>
                    {action.examples.map((ex, i) => (
                      <li key={i}>
                        <Typography variant="caption" sx={{ fontStyle: 'italic' }}>
                          {ex}
                        </Typography>
                      </li>
                    ))}
                  </Box>
                </Box>
              }
              arrow
              placement="bottom"
            >
              <Paper
                elevation={0}
                role="button"
                aria-label={action.label}
                onClick={() => onSelectAction(action.query)}
                sx={{
                  p: 2,
                  cursor: 'pointer',
                  textAlign: 'center',
                  borderRadius: borderRadius.lg,
                  backgroundColor: alpha(action.color, 0.08),
                  border: `1px solid ${alpha(action.color, 0.25)}`,
                  transition: `all ${transitions.fast}`,
                  animation: `fadeSlideIn 0.4s ease-out ${index * 0.08}s both`,
                  '@keyframes fadeSlideIn': {
                    from: {
                      opacity: 0,
                      transform: 'translateY(20px)',
                    },
                    to: {
                      opacity: 1,
                      transform: 'translateY(0)',
                    },
                  },
                  '&:hover': {
                    transform: 'translateY(-4px) scale(1.02)',
                    backgroundColor: alpha(action.color, 0.15),
                    borderColor: action.color,
                    boxShadow: `0 8px 24px ${alpha(action.color, 0.25)}`,
                  },
                  '&:active': {
                    transform: 'translateY(-2px) scale(1)',
                  },
                }}
              >
                <Box
                  sx={{
                    width: 48,
                    height: 48,
                    borderRadius: borderRadius.lg,
                    backgroundColor: alpha(action.color, 0.2),
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mx: 'auto',
                    mb: 1.5,
                  }}
                >
                  <action.icon sx={{ fontSize: 24, color: action.color }} />
                </Box>
                <Typography
                  variant="body2"
                  sx={{
                    fontWeight: 600,
                    color: action.color,
                    mb: 0.5,
                  }}
                >
                  {action.label}
                </Typography>
                <Typography
                  variant="caption"
                  sx={{
                    color: 'text.secondary',
                    display: 'block',
                    lineHeight: 1.3,
                  }}
                >
                  {action.description}
                </Typography>
              </Paper>
            </Tooltip>
          ))}
        </Box>

        {/* Hint text */}
        <Typography
          variant="caption"
          sx={{
            color: 'text.muted',
            textAlign: 'center',
            display: 'block',
            mt: 3,
          }}
        >
          Or type your own question below! I understand natural language.
        </Typography>
      </Box>
    </Fade>
  );
};

export default QuickActions;