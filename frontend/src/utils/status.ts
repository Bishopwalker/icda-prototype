/**
 * Status utilities - consolidated status color/icon logic
 */
import { colors } from '../theme';

export type Status = 'online' | 'offline' | 'loading';

const STATUS_COLORS: Record<Status, string> = {
  online: colors.success.main,
  offline: colors.error.main,
  loading: colors.warning.main,
};

export const getStatusColor = (status: Status): string => STATUS_COLORS[status];

export const getStatusBgColor = (status: Status, alpha = '22'): string =>
  `${getStatusColor(status)}${alpha}`;
