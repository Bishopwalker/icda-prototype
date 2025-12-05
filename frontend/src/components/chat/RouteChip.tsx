import React from 'react';
import { Chip } from '@mui/material';
import {
  Cached as CacheIcon,
  Storage as DatabaseIcon,
  Cloud as NovaIcon,
} from '@mui/icons-material';
import { colors } from '../../theme';

const ROUTE_CONFIG: Record<string, { icon: React.ReactElement; color: string; label: string }> = {
  cache: { icon: <CacheIcon sx={{ fontSize: 14 }} />, color: colors.routes.cache, label: 'Cache' },
  database: { icon: <DatabaseIcon sx={{ fontSize: 14 }} />, color: colors.routes.database, label: 'Database' },
  nova: { icon: <NovaIcon sx={{ fontSize: 14 }} />, color: colors.routes.nova, label: 'Nova' },
};

interface RouteChipProps {
  route: string;
}

export const RouteChip: React.FC<RouteChipProps> = ({ route }) => {
  const config = ROUTE_CONFIG[route];
  if (!config) {
    return (
      <Chip label={route} size="small" sx={{ backgroundColor: `${colors.info.main}22`, color: colors.info.main, fontSize: '0.7rem', height: 20 }} />
    );
  }
  return (
    <Chip
      icon={config.icon}
      label={config.label}
      size="small"
      sx={{ backgroundColor: `${config.color}22`, color: config.color, fontSize: '0.7rem', height: 20 }}
    />
  );
};

export default RouteChip;
