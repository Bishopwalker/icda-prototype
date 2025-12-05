import React from 'react';
import { Box, Typography, Card, CardContent, Chip, Stack } from '@mui/material';
import {
  Cloud as CloudIcon, Storage as StorageIcon, Memory as MemoryIcon, Search as SearchIcon,
  CheckCircle as CheckIcon, Cancel as CancelIcon, HourglassEmpty as LoadingIcon,
} from '@mui/icons-material';
import { colors } from '../theme';
import { getStatusColor, getStatusBgColor, type Status } from '../utils';
import type { HealthStatus } from '../types';

interface AWSToolingPanelProps {
  health: HealthStatus | null;
  loading: boolean;
}

const SERVICES = [
  { name: 'Bedrock Nova', desc: 'NLP Query Processing', icon: <CloudIcon />, key: 'nova' as const },
  { name: 'Titan Embeddings', desc: 'Vector Embeddings', icon: <MemoryIcon />, key: 'embedder' as const },
  { name: 'ElastiCache', desc: 'Redis Caching', icon: <StorageIcon />, key: 'redis' as const },
  { name: 'OpenSearch', desc: 'Vector Index', icon: <SearchIcon />, key: 'opensearch' as const },
] as const;

const STATUS_ICONS = { online: CheckIcon, offline: CancelIcon, loading: LoadingIcon };

const StatusIcon: React.FC<{ status: Status }> = ({ status }) => {
  const Icon = STATUS_ICONS[status];
  return <Icon sx={{ color: getStatusColor(status), fontSize: 16 }} />;
};

export const AWSToolingPanel: React.FC<AWSToolingPanelProps> = ({ health, loading }) => (
  <Box sx={{ p: 2 }}>
    <Typography variant="h6" sx={{ mb: 2, color: colors.aws.orange }}>AWS Tooling</Typography>
    <Stack spacing={1.5}>
      {SERVICES.map(({ name, desc, icon, key }) => {
        const status: Status = loading ? 'loading' : !health ? 'loading' : health[key] ? 'online' : 'offline';
        return (
          <Card key={name} sx={{ backgroundColor: 'background.elevated', border: 1, borderColor: getStatusBgColor(status, '44') }}>
            <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                  <Box sx={{ color: colors.aws.orange }}>{icon}</Box>
                  <Box>
                    <Typography variant="body2" fontWeight={600}>{name}</Typography>
                    <Typography variant="caption" color="text.secondary">{desc}</Typography>
                  </Box>
                </Box>
                <Chip
                  icon={<StatusIcon status={status} />}
                  label={status}
                  size="small"
                  sx={{
                    backgroundColor: getStatusBgColor(status),
                    color: getStatusColor(status),
                    textTransform: 'capitalize',
                    fontSize: '0.7rem',
                    height: 24,
                  }}
                />
              </Box>
            </CardContent>
          </Card>
        );
      })}
    </Stack>
  </Box>
);

export default AWSToolingPanel;
