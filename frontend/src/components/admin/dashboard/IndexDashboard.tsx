/**
 * Index Dashboard - Overview of all indexes and system health
 */

import { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Chip,
  LinearProgress,
  Alert,
  Skeleton,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  CheckCircle as HealthyIcon,
  Warning as DegradedIcon,
  Error as ErrorIcon,
  Storage as StorageIcon,
  Security as SecurityIcon,
} from '@mui/icons-material';
import { alpha } from '@mui/material/styles';
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip } from 'recharts';

import { getIndexStats, getIndexHealth, getEnforcerMetrics } from '../../../services/adminApi';
import type { IndexStats, IndexHealth, EnforcerMetrics } from '../../../types/admin';
import { colors } from '../../../theme';
import ReindexProgress from './ReindexProgress';

const CHART_COLORS = ['#6366f1', '#8b5cf6', '#a855f7', '#d946ef', '#ec4899'];

function StatusChip({ status }: { status: string }) {
  const getProps = () => {
    switch (status) {
      case 'healthy':
        return { icon: <HealthyIcon />, color: 'success' as const, label: 'Healthy' };
      case 'degraded':
        return { icon: <DegradedIcon />, color: 'warning' as const, label: 'Degraded' };
      default:
        return { icon: <ErrorIcon />, color: 'error' as const, label: 'Unavailable' };
    }
  };
  const props = getProps();
  return <Chip icon={props.icon} label={props.label} color={props.color} size="small" />;
}

function StatCard({ title, value, subtitle, icon, loading }: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  loading?: boolean;
}) {
  return (
    <Card sx={{ height: '100%', backgroundColor: alpha(colors.background.paper, 0.8) }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Typography variant="subtitle2" color="textSecondary">{title}</Typography>
          <Box sx={{ color: colors.primary.main }}>{icon}</Box>
        </Box>
        {loading ? (
          <Skeleton variant="text" width="60%" height={40} />
        ) : (
          <Typography variant="h4" sx={{ mb: 0.5 }}>{value}</Typography>
        )}
        {subtitle && <Typography variant="caption" color="textSecondary">{subtitle}</Typography>}
      </CardContent>
    </Card>
  );
}

function IndexDashboard() {
  const [stats, setStats] = useState<IndexStats | null>(null);
  const [health, setHealth] = useState<IndexHealth | null>(null);
  const [enforcer, setEnforcer] = useState<EnforcerMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsRes, healthRes, enforcerRes] = await Promise.all([
        getIndexStats(),
        getIndexHealth(),
        getEnforcerMetrics(),
      ]);

      if (statsRes.success) setStats(statsRes.stats);
      if (healthRes.success) setHealth(healthRes.health);
      if (enforcerRes.success && enforcerRes.metrics) setEnforcer(enforcerRes.metrics);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const categoryData = stats?.knowledge?.categories
    ? Object.entries(stats.knowledge.categories).map(([name, value]) => ({ name, value }))
    : [];

  const serviceData = stats?.services
    ? Object.entries(stats.services).map(([name, available]) => ({
        name: name.replace('_', ' '),
        status: available ? 1 : 0,
      }))
    : [];

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" gutterBottom>Index Dashboard</Typography>
          <Typography variant="body2" color="textSecondary">
            Monitor your RAG indexes and system health
          </Typography>
        </Box>
        <Box>
          <Tooltip title="Refresh">
            <IconButton onClick={fetchData} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Customer Reindex with Progress Tracking */}
      <ReindexProgress onComplete={fetchData} />

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Health Status */}
      {health && (
        <Card sx={{ mb: 3, backgroundColor: alpha(colors.background.paper, 0.8) }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
              <Typography variant="h6">System Health</Typography>
              <StatusChip status={health.overall} />
            </Box>
            {health.issues.length > 0 && (
              <Box>
                {health.issues.map((issue, i) => (
                  <Alert key={i} severity="warning" sx={{ mb: 1 }}>{issue}</Alert>
                ))}
              </Box>
            )}
          </CardContent>
        </Card>
      )}

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Chunks"
            value={stats?.knowledge?.total_chunks ?? 0}
            subtitle="In knowledge base"
            icon={<StorageIcon />}
            loading={loading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Documents"
            value={stats?.knowledge?.unique_documents ?? 0}
            subtitle="Unique files indexed"
            icon={<StorageIcon />}
            loading={loading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Customers"
            value={stats?.customers?.indexed ?? 0}
            subtitle="In customer index"
            icon={<StorageIcon />}
            loading={loading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Enforcer Pass Rate"
            value={enforcer?.pass_rate ? `${(enforcer.pass_rate * 100).toFixed(1)}%` : 'N/A'}
            subtitle={enforcer?.chunks_evaluated ? `${enforcer.chunks_evaluated} evaluated` : 'No data'}
            icon={<SecurityIcon />}
            loading={loading}
          />
        </Grid>
      </Grid>

      {/* Charts */}
      <Grid container spacing={3}>
        {/* Categories Pie Chart */}
        <Grid item xs={12} md={6}>
          <Card sx={{ height: 350, backgroundColor: alpha(colors.background.paper, 0.8) }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>Chunks by Category</Typography>
              {loading ? (
                <Skeleton variant="circular" width={200} height={200} sx={{ mx: 'auto', mt: 4 }} />
              ) : categoryData.length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie
                      data={categoryData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={2}
                      dataKey="value"
                      label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                    >
                      {categoryData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <RechartsTooltip />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 260 }}>
                  <Typography color="textSecondary">No category data</Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Services Status */}
        <Grid item xs={12} md={6}>
          <Card sx={{ height: 350, backgroundColor: alpha(colors.background.paper, 0.8) }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>Service Status</Typography>
              {loading ? (
                <Box sx={{ mt: 4 }}>
                  {[1, 2, 3, 4].map((i) => (
                    <Skeleton key={i} variant="text" height={50} sx={{ mb: 1 }} />
                  ))}
                </Box>
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={serviceData} layout="vertical">
                    <XAxis type="number" domain={[0, 1]} hide />
                    <YAxis type="category" dataKey="name" width={100} tick={{ fill: colors.text.primary }} />
                    <Bar dataKey="status" radius={[0, 4, 4, 0]}>
                      {serviceData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.status ? '#22c55e' : '#ef4444'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Enforcer Metrics */}
        <Grid item xs={12}>
          <Card sx={{ backgroundColor: alpha(colors.background.paper, 0.8) }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <SecurityIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
                Gemini Enforcer Metrics
              </Typography>
              {enforcer ? (
                <Grid container spacing={3} sx={{ mt: 1 }}>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="textSecondary">Chunks Evaluated</Typography>
                    <Typography variant="h5">{enforcer.chunks_evaluated ?? 0}</Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="textSecondary">Passed</Typography>
                    <Typography variant="h5" sx={{ color: '#22c55e' }}>{enforcer.chunks_passed ?? 0}</Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="textSecondary">Failed</Typography>
                    <Typography variant="h5" sx={{ color: '#ef4444' }}>{enforcer.chunks_failed ?? 0}</Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="textSecondary">Avg Quality Score</Typography>
                    <Typography variant="h5">
                      {enforcer.average_quality_score?.toFixed(2) ?? 'N/A'}
                    </Typography>
                  </Grid>
                  <Grid item xs={12}>
                    <Typography variant="body2" color="textSecondary" sx={{ mb: 1 }}>Pass Rate</Typography>
                    <LinearProgress
                      variant="determinate"
                      value={(enforcer.pass_rate ?? 0) * 100}
                      sx={{
                        height: 10,
                        borderRadius: 5,
                        backgroundColor: alpha(colors.primary.main, 0.2),
                        '& .MuiLinearProgress-bar': {
                          backgroundColor: (enforcer.pass_rate ?? 0) > 0.8 ? '#22c55e' :
                            (enforcer.pass_rate ?? 0) > 0.5 ? '#f59e0b' : '#ef4444',
                        },
                      }}
                    />
                  </Grid>
                </Grid>
              ) : (
                <Alert severity="info">Enforcer not enabled or no data available</Alert>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

export default IndexDashboard;
