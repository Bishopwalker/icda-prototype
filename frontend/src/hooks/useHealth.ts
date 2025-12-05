import { useState, useEffect, useCallback } from 'react';
import type { HealthStatus, CacheStats } from '../types';
import api from '../services/api';

export interface UseHealthReturn {
  health: HealthStatus | null;
  cacheStats: CacheStats | null;
  loading: boolean;
  error: string | null;
  refreshHealth: () => Promise<void>;
  refreshCacheStats: () => Promise<void>;
  clearCache: () => Promise<void>;
}

export function useHealth(pollInterval: number = 30000): UseHealthReturn {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [cacheStats, setCacheStats] = useState<CacheStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshHealth = useCallback(async () => {
    try {
      const data = await api.health();
      setHealth(data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch health status');
      setHealth(null);
    }
  }, []);

  const refreshCacheStats = useCallback(async () => {
    try {
      const data = await api.cacheStats();
      setCacheStats(data);
    } catch (err) {
      setCacheStats(null);
    }
  }, []);

  const clearCache = useCallback(async () => {
    try {
      await api.clearCache();
      await refreshCacheStats();
    } catch (err) {
      setError('Failed to clear cache');
    }
  }, [refreshCacheStats]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([refreshHealth(), refreshCacheStats()]);
    setLoading(false);
  }, [refreshHealth, refreshCacheStats]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, pollInterval);
    return () => clearInterval(interval);
  }, [fetchAll, pollInterval]);

  return {
    health,
    cacheStats,
    loading,
    error,
    refreshHealth,
    refreshCacheStats,
    clearCache,
  };
}

export default useHealth;
