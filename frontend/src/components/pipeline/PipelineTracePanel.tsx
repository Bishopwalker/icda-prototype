import React from 'react';
import {
  Box,
  Typography,
  Collapse,
  Chip,
  LinearProgress,
  Tooltip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  ExpandMore as ExpandIcon,
  Psychology as IntentIcon,
  History as ContextIcon,
  TextFields as ParserIcon,
  Link as ResolverIcon,
  Search as SearchIcon,
  MenuBook as KnowledgeIcon,
  Cloud as NovaIcon,
  Security as EnforcerIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  HourglassEmpty as PendingIcon,
  PlayCircle as RunningIcon,
  SkipNext as SkippedIcon,
  AccessTime as TimeIcon,
  Route as RouteIcon,
} from '@mui/icons-material';
import { colors, borderRadius } from '../../theme';
import type { PipelineTrace, PipelineStage, PipelineAgentType, PipelineStageStatus } from '../../types';

interface PipelineTracePanelProps {
  trace: PipelineTrace;
  defaultExpanded?: boolean;
}

// Agent configuration with icons and colors
const AGENT_CONFIG: Record<PipelineAgentType, {
  icon: React.ElementType;
  color: string;
  label: string;
  description: string;
}> = {
  intent: {
    icon: IntentIcon,
    color: '#03A9F4',
    label: 'Intent',
    description: 'Classifies query intent and complexity',
  },
  context: {
    icon: ContextIcon,
    color: '#00BFA5',
    label: 'Context',
    description: 'Extracts session context and history',
  },
  parser: {
    icon: ParserIcon,
    color: '#FF9800',
    label: 'Parser',
    description: 'Normalizes and extracts entities',
  },
  resolver: {
    icon: ResolverIcon,
    color: '#004B87',
    label: 'Resolver',
    description: 'Resolves entity references',
  },
  search: {
    icon: SearchIcon,
    color: '#4CAF50',
    label: 'Search',
    description: 'Executes database and vector search',
  },
  knowledge: {
    icon: KnowledgeIcon,
    color: '#DA291C',
    label: 'Knowledge',
    description: 'RAG retrieval from knowledge base',
  },
  nova: {
    icon: NovaIcon,
    color: '#9C27B0',
    label: 'Nova',
    description: 'AI response generation',
  },
  enforcer: {
    icon: EnforcerIcon,
    color: '#D32F2F',
    label: 'Enforcer',
    description: 'Quality gates and validation',
  },
};

// Status icons and colors
const STATUS_CONFIG: Record<PipelineStageStatus, {
  icon: React.ElementType;
  color: string;
}> = {
  pending: { icon: PendingIcon, color: colors.text.muted },
  running: { icon: RunningIcon, color: colors.info.main },
  completed: { icon: SuccessIcon, color: colors.success.main },
  failed: { icon: ErrorIcon, color: colors.error.main },
  skipped: { icon: SkippedIcon, color: colors.text.disabled },
};

/**
 * Formats time in milliseconds to a readable string.
 */
const formatTime = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
};

/**
 * Individual pipeline stage row component.
 */
const PipelineStageRow: React.FC<{ stage: PipelineStage }> = ({
  stage,
}) => {
  const agentConfig = AGENT_CONFIG[stage.agent as PipelineAgentType];
  const statusConfig = STATUS_CONFIG[stage.status] || STATUS_CONFIG.pending;
  
  // Guard against unknown agent types
  if (!agentConfig) {
    console.warn(`Unknown pipeline agent type: ${stage.agent}`);
    return null;
  }
  
  const AgentIcon = agentConfig.icon;
  const StatusIcon = statusConfig.icon;

  const hasDetails = stage.output_summary || stage.debug_info || stage.error;

  return (
    <Accordion
      disableGutters
      elevation={0}
      sx={{
        backgroundColor: 'transparent',
        '&:before': { display: 'none' },
        '&.Mui-expanded': { margin: 0 },
      }}
    >
      <AccordionSummary
        expandIcon={hasDetails ? <ExpandIcon sx={{ fontSize: 16, color: colors.text.muted }} /> : null}
        sx={{
          minHeight: 40,
          px: 1,
          py: 0.5,
          '& .MuiAccordionSummary-content': {
            margin: '4px 0',
            alignItems: 'center',
          },
          '&:hover': {
            backgroundColor: alpha(colors.text.primary, 0.03),
          },
          cursor: hasDetails ? 'pointer' : 'default',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', gap: 1 }}>
          {/* Agent icon and name */}
          <Tooltip title={agentConfig.description} arrow placement="top">
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.75,
                minWidth: 90,
              }}
            >
              <Box
                sx={{
                  width: 24,
                  height: 24,
                  borderRadius: borderRadius.sm,
                  backgroundColor: alpha(agentConfig.color, 0.15),
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <AgentIcon sx={{ fontSize: 14, color: agentConfig.color }} />
              </Box>
              <Typography
                variant="caption"
                sx={{
                  fontWeight: 600,
                  color: colors.text.primary,
                  fontSize: '0.7rem',
                }}
              >
                {agentConfig.label}
              </Typography>
            </Box>
          </Tooltip>

          {/* Confidence bar (if available) */}
          {stage.confidence !== undefined && (
            <Tooltip title={`Confidence: ${(stage.confidence * 100).toFixed(1)}%`} arrow>
              <Box sx={{ width: 60, mx: 1 }}>
                <LinearProgress
                  variant="determinate"
                  value={stage.confidence * 100}
                  sx={{
                    height: 4,
                    borderRadius: 2,
                    backgroundColor: alpha(colors.text.primary, 0.1),
                    '& .MuiLinearProgress-bar': {
                      backgroundColor:
                        stage.confidence >= 0.8
                          ? colors.success.main
                          : stage.confidence >= 0.6
                          ? colors.warning.main
                          : colors.error.main,
                    },
                  }}
                />
              </Box>
            </Tooltip>
          )}

          {/* Spacer */}
          <Box sx={{ flex: 1 }} />

          {/* Time */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minWidth: 50 }}>
            <TimeIcon sx={{ fontSize: 12, color: colors.text.muted }} />
            <Typography
              variant="caption"
              sx={{ fontSize: '0.65rem', color: colors.text.secondary }}
            >
              {formatTime(stage.time_ms)}
            </Typography>
          </Box>

          {/* Status icon */}
          <StatusIcon
            sx={{
              fontSize: 14,
              color: statusConfig.color,
              ml: 0.5,
            }}
          />
        </Box>
      </AccordionSummary>

      {hasDetails && (
        <AccordionDetails
          sx={{
            px: 1,
            py: 1,
            backgroundColor: alpha(colors.background.paper, 0.5),
            borderRadius: borderRadius.sm,
            mx: 1,
            mb: 1,
          }}
        >
          {stage.error && (
            <Box sx={{ mb: 1 }}>
              <Typography
                variant="caption"
                sx={{ color: colors.error.main, fontWeight: 600 }}
              >
                Error:
              </Typography>
              <Typography
                variant="caption"
                sx={{ color: colors.error.light, display: 'block', ml: 1 }}
              >
                {stage.error}
              </Typography>
            </Box>
          )}

          {stage.output_summary && (
            <Box sx={{ mb: 1 }}>
              <Typography
                variant="caption"
                sx={{ color: colors.text.muted, fontWeight: 600 }}
              >
                Output:
              </Typography>
              <Box
                component="pre"
                sx={{
                  fontSize: '0.65rem',
                  color: colors.text.secondary,
                  m: 0,
                  mt: 0.5,
                  p: 1,
                  backgroundColor: alpha(colors.background.default, 0.5),
                  borderRadius: borderRadius.sm,
                  overflow: 'auto',
                  maxHeight: 150,
                }}
              >
                {JSON.stringify(stage.output_summary, null, 2)}
              </Box>
            </Box>
          )}

          {stage.route_decision && (
            <Box>
              <Typography
                variant="caption"
                sx={{ color: colors.text.muted, fontWeight: 600 }}
              >
                Route Decision:
              </Typography>
              <Box
                component="pre"
                sx={{
                  fontSize: '0.65rem',
                  color: colors.accent.light,
                  m: 0,
                  mt: 0.5,
                  p: 1,
                  backgroundColor: alpha(colors.background.default, 0.5),
                  borderRadius: borderRadius.sm,
                  overflow: 'auto',
                }}
              >
                {JSON.stringify(stage.route_decision, null, 2)}
              </Box>
            </Box>
          )}
        </AccordionDetails>
      )}
    </Accordion>
  );
};

export const PipelineTracePanel: React.FC<PipelineTracePanelProps> = ({
  trace,
  defaultExpanded = false,
}) => {
  const [expanded, setExpanded] = React.useState(defaultExpanded);

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
        onClick={() => setExpanded(!expanded)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          p: 1,
          cursor: 'pointer',
          '&:hover': {
            backgroundColor: alpha(colors.text.primary, 0.03),
          },
        }}
      >
        <RouteIcon sx={{ fontSize: 16, color: colors.accent.main }} />
        <Typography
          variant="caption"
          sx={{ fontWeight: 600, color: colors.text.primary }}
        >
          Pipeline Trace
        </Typography>

        {/* Stage count */}
        <Chip
          label={`${trace.stages.length} agents`}
          size="small"
          sx={{
            height: 18,
            fontSize: '0.6rem',
            backgroundColor: alpha(colors.accent.main, 0.15),
            color: colors.accent.light,
          }}
        />

        {/* Model routing decision */}
        {trace.model_routing_decision && (
          <Chip
            label={trace.model_routing_decision.model_tier.toUpperCase()}
            size="small"
            sx={{
              height: 18,
              fontSize: '0.6rem',
              backgroundColor: alpha(
                trace.model_routing_decision.model_tier === 'pro'
                  ? colors.secondary.main
                  : trace.model_routing_decision.model_tier === 'lite'
                  ? colors.warning.main
                  : colors.success.main,
                0.15
              ),
              color:
                trace.model_routing_decision.model_tier === 'pro'
                  ? colors.secondary.light
                  : trace.model_routing_decision.model_tier === 'lite'
                  ? colors.warning.light
                  : colors.success.light,
            }}
          />
        )}

        <Box sx={{ flex: 1 }} />

        {/* Total time */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <TimeIcon sx={{ fontSize: 12, color: colors.text.muted }} />
          <Typography
            variant="caption"
            sx={{ fontSize: '0.65rem', color: colors.text.secondary }}
          >
            {formatTime(trace.total_time_ms)}
          </Typography>
        </Box>

        {/* Success/failure indicator */}
        {trace.success ? (
          <SuccessIcon sx={{ fontSize: 14, color: colors.success.main }} />
        ) : (
          <ErrorIcon sx={{ fontSize: 14, color: colors.error.main }} />
        )}

        <ExpandIcon
          sx={{
            fontSize: 16,
            color: colors.text.muted,
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s ease',
          }}
        />
      </Box>

      {/* Stages */}
      <Collapse in={expanded}>
        <Box
          sx={{
            borderTop: `1px solid ${alpha(colors.text.primary, 0.08)}`,
          }}
        >
          {/* Visual pipeline connection */}
          <Box
            sx={{
              position: 'relative',
              '&::before': {
                content: '""',
                position: 'absolute',
                left: 22,
                top: 8,
                bottom: 8,
                width: 2,
                backgroundColor: alpha(colors.text.primary, 0.1),
                borderRadius: 1,
              },
            }}
          >
            {trace.stages.map((stage, index) => (
              <PipelineStageRow key={`${stage.agent}-${index}`} stage={stage} />
            ))}
          </Box>

          {/* Min confidence indicator */}
          {trace.min_confidence !== undefined && (
            <Box
              sx={{
                p: 1,
                borderTop: `1px solid ${alpha(colors.text.primary, 0.08)}`,
                display: 'flex',
                alignItems: 'center',
                gap: 1,
              }}
            >
              <Typography
                variant="caption"
                sx={{ color: colors.text.muted, fontSize: '0.65rem' }}
              >
                Min Confidence:
              </Typography>
              <Chip
                label={`${(trace.min_confidence * 100).toFixed(1)}%`}
                size="small"
                sx={{
                  height: 18,
                  fontSize: '0.6rem',
                  backgroundColor: alpha(
                    trace.min_confidence >= 0.8
                      ? colors.success.main
                      : trace.min_confidence >= 0.6
                      ? colors.warning.main
                      : colors.error.main,
                    0.15
                  ),
                  color:
                    trace.min_confidence >= 0.8
                      ? colors.success.light
                      : trace.min_confidence >= 0.6
                      ? colors.warning.light
                      : colors.error.light,
                }}
              />
              {trace.model_routing_decision && (
                <Tooltip title={trace.model_routing_decision.reason} arrow>
                  <Typography
                    variant="caption"
                    sx={{
                      color: colors.text.muted,
                      fontSize: '0.6rem',
                      ml: 1,
                      cursor: 'help',
                    }}
                  >
                    Routed to {trace.model_routing_decision.model_tier}
                  </Typography>
                </Tooltip>
              )}
            </Box>
          )}
        </Box>
      </Collapse>
    </Box>
  );
};

export default PipelineTracePanel;
