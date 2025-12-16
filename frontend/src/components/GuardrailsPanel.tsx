import React from 'react';
import {
  Box,
  Typography,
  ToggleButton,
  Tooltip,
  Stack,
  Button,
} from '@mui/material';
import {
  Security as SecurityIcon,
  Person as PersonIcon,
  AccountBalance as FinancialIcon,
  Key as CredentialsIcon,
  Block as BlockIcon,
} from '@mui/icons-material';
import { alpha } from '@mui/material/styles';
import { colors } from '../theme';
import type { GuardrailFlags } from '../types';

interface GuardrailsPanelProps {
  guardrails: GuardrailFlags;
  onToggle: (key: keyof GuardrailFlags) => void;
  onDisableAll: () => void;
  onEnableAll: () => void;
}

interface GuardrailConfig {
  key: keyof GuardrailFlags;
  label: string;
  description: string;
  icon: React.ReactNode;
  color: string;
}

const guardrailConfigs: GuardrailConfig[] = [
  {
    key: 'pii',
    label: 'Block PII',
    description: 'Blocks SSN and social security requests',
    icon: <PersonIcon />,
    color: colors.guardrails.pii,
  },
  {
    key: 'financial',
    label: 'Block Financial',
    description: 'Blocks credit card and bank account requests',
    icon: <FinancialIcon />,
    color: colors.guardrails.financial,
  },
  {
    key: 'credentials',
    label: 'Block Credentials',
    description: 'Blocks password, secret, and token requests',
    icon: <CredentialsIcon />,
    color: colors.guardrails.credentials,
  },
  {
    key: 'offtopic',
    label: 'Block Off-Topic',
    description: 'Blocks weather, poem, story, joke queries',
    icon: <BlockIcon />,
    color: colors.guardrails.offtopic,
  },
];

export const GuardrailsPanel: React.FC<GuardrailsPanelProps> = ({
  guardrails,
  onToggle,
  onDisableAll,
  onEnableAll,
}) => {
  const allDisabled = !guardrails.pii && !guardrails.financial && !guardrails.credentials && !guardrails.offtopic;
  const allEnabled = guardrails.pii && guardrails.financial && guardrails.credentials && guardrails.offtopic;
  return (
    <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <SecurityIcon sx={{ color: colors.error.main }} />
        <Typography variant="h6">Guardrails</Typography>
      </Box>

      <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
        <Button
          size="small"
          variant={allDisabled ? "contained" : "outlined"}
          color="error"
          onClick={onDisableAll}
          disabled={allDisabled}
          aria-label="Disable all guardrails"
          sx={{ flex: 1, textTransform: 'none' }}
        >
          Disable All
        </Button>
        <Button
          size="small"
          variant={allEnabled ? "contained" : "outlined"}
          color="success"
          onClick={onEnableAll}
          disabled={allEnabled}
          aria-label="Enable all guardrails"
          sx={{ flex: 1, textTransform: 'none' }}
        >
          Enable All
        </Button>
      </Box>

      <Stack spacing={1}>
        {guardrailConfigs.map((config) => {
          const isActive = guardrails[config.key];

          return (
            <Tooltip key={config.key} title={config.description} placement="right" arrow>
              <ToggleButton
                value={config.key}
                selected={isActive}
                onChange={() => onToggle(config.key)}
                aria-label={`Toggle ${config.label} guardrail`}
                sx={{
                  justifyContent: 'flex-start',
                  gap: 1.5,
                  px: 2,
                  py: 1,
                  borderRadius: 2,
                  border: 1,
                  textTransform: 'none',
                  width: '100%',
                  backgroundColor: isActive ? alpha(config.color, 0.15) : 'transparent',
                  borderColor: isActive ? config.color : 'divider',
                  color: isActive ? config.color : 'text.secondary',
                  '&:hover': {
                    backgroundColor: alpha(config.color, 0.1),
                  },
                  '&.Mui-selected': {
                    backgroundColor: alpha(config.color, 0.15),
                    '&:hover': {
                      backgroundColor: alpha(config.color, 0.25),
                    },
                  },
                }}
              >
                <Box sx={{ color: isActive ? config.color : 'text.secondary' }}>
                  {config.icon}
                </Box>
                <Typography variant="body2" fontWeight={isActive ? 600 : 400}>
                  {config.label}
                </Typography>
                {isActive && (
                  <Box
                    sx={{
                      ml: 'auto',
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      backgroundColor: config.color,
                    }}
                  />
                )}
              </ToggleButton>
            </Tooltip>
          );
        })}
      </Stack>

      <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
        Click to toggle guardrails on/off for testing
      </Typography>
    </Box>
  );
};

export default GuardrailsPanel;