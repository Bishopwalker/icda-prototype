/**
 * Download utilities - extracted from QueryInput
 */
import type { ChatMessage } from '../types';

/**
 * Converts chat messages to JSON format.
 */
export const messagesToJson = (messages: ChatMessage[]): string =>
  JSON.stringify(
    messages.map((msg) => ({
      id: msg.id,
      type: msg.type,
      content: msg.content,
      timestamp: msg.timestamp.toISOString(),
      route: msg.metadata?.route ?? null,
      latency_ms: msg.metadata?.latency_ms ?? null,
      cached: msg.metadata?.cached ?? false,
      tool: msg.metadata?.tool ?? null,
    })),
    null,
    2
  );

/**
 * Converts chat messages to CSV format.
 */
export const messagesToCsv = (messages: ChatMessage[]): string => {
  const headers = ['ID', 'Type', 'Content', 'Timestamp', 'Route', 'Latency (ms)', 'Cached', 'Tool'];
  const rows = messages.map((msg) => [
    msg.id,
    msg.type,
    `"${msg.content.replace(/"/g, '""')}"`,
    msg.timestamp.toISOString(),
    msg.metadata?.route ?? '',
    msg.metadata?.latency_ms?.toString() ?? '',
    msg.metadata?.cached ? 'Yes' : 'No',
    msg.metadata?.tool ?? '',
  ]);
  return [headers.join(','), ...rows.map((row) => row.join(','))].join('\n');
};

/**
 * Triggers a file download in the browser.
 */
export const downloadFile = (content: string, filename: string, mimeType: string): void => {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement('a'), { href: url, download: filename });
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

/**
 * Downloads chat messages in the specified format.
 */
export const downloadMessages = (messages: ChatMessage[], format: 'json' | 'csv'): void => {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const content = format === 'json' ? messagesToJson(messages) : messagesToCsv(messages);
  const mimeType = format === 'json' ? 'application/json' : 'text/csv';
  downloadFile(content, `icda-chat-${timestamp}.${format}`, mimeType);
};
