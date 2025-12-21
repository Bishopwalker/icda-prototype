import { useState, useCallback } from 'react';
import type { TokenUsage } from '../types';

/**
 * Default context limit for Nova Lite model.
 */
const DEFAULT_CONTEXT_LIMIT = 300000;

/**
 * Initial token usage state.
 */
const initialUsage: TokenUsage = {
  input_tokens: 0,
  output_tokens: 0,
  total_tokens: 0,
  context_limit: DEFAULT_CONTEXT_LIMIT,
  percentage_used: 0,
};

/**
 * Hook for tracking cumulative token usage across a session.
 *
 * @returns Object with current usage, cumulative usage, and functions to update/reset.
 */
export function useTokenUsage() {
  const [currentUsage, setCurrentUsage] = useState<TokenUsage>(initialUsage);
  const [cumulativeUsage, setCumulativeUsage] = useState<TokenUsage>(initialUsage);
  const [history, setHistory] = useState<TokenUsage[]>([]);

  /**
   * Updates the current usage with a new token usage response.
   * Also adds to cumulative usage.
   */
  const updateUsage = useCallback((usage: TokenUsage | undefined) => {
    if (!usage) return;

    setCurrentUsage(usage);
    setHistory((prev) => [...prev, usage]);

    setCumulativeUsage((prev) => {
      const newInput = prev.input_tokens + usage.input_tokens;
      const newOutput = prev.output_tokens + usage.output_tokens;
      const newTotal = newInput + newOutput;
      const limit = usage.context_limit || prev.context_limit;

      return {
        input_tokens: newInput,
        output_tokens: newOutput,
        total_tokens: newTotal,
        context_limit: limit,
        percentage_used: limit > 0 ? (newTotal / limit) * 100 : 0,
      };
    });
  }, []);

  /**
   * Resets all token usage tracking.
   */
  const resetUsage = useCallback(() => {
    setCurrentUsage(initialUsage);
    setCumulativeUsage(initialUsage);
    setHistory([]);
  }, []);

  /**
   * Gets the average tokens per query.
   */
  const getAverageUsage = useCallback((): TokenUsage => {
    if (history.length === 0) return initialUsage;

    const totalInput = history.reduce((sum, u) => sum + u.input_tokens, 0);
    const totalOutput = history.reduce((sum, u) => sum + u.output_tokens, 0);
    const avgInput = Math.round(totalInput / history.length);
    const avgOutput = Math.round(totalOutput / history.length);
    const avgTotal = avgInput + avgOutput;
    const limit = history[history.length - 1]?.context_limit || DEFAULT_CONTEXT_LIMIT;

    return {
      input_tokens: avgInput,
      output_tokens: avgOutput,
      total_tokens: avgTotal,
      context_limit: limit,
      percentage_used: limit > 0 ? (avgTotal / limit) * 100 : 0,
    };
  }, [history]);

  /**
   * Gets estimated remaining queries based on average usage.
   */
  const getEstimatedRemainingQueries = useCallback((): number => {
    const avg = getAverageUsage();
    if (avg.total_tokens === 0) return -1; // Unknown

    const remaining = cumulativeUsage.context_limit - cumulativeUsage.total_tokens;
    return Math.max(0, Math.floor(remaining / avg.total_tokens));
  }, [getAverageUsage, cumulativeUsage]);

  return {
    currentUsage,
    cumulativeUsage,
    history,
    queryCount: history.length,
    updateUsage,
    resetUsage,
    getAverageUsage,
    getEstimatedRemainingQueries,
  };
}

export default useTokenUsage;
