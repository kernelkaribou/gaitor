/**
 * Shared utility functions for gAItor frontend.
 */

/**
 * Format byte sizes into human-readable strings.
 */
export function formatSize(bytes) {
  if (!bytes) return '-';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let size = bytes;
  while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
  return `${size.toFixed(1)} ${units[i]}`;
}

/**
 * Validate that a URL uses a safe protocol (http/https only).
 */
export function isSafeUrl(url) {
  if (!url || typeof url !== 'string') return false;
  return /^https?:\/\//i.test(url);
}
