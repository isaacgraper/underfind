/**
 * Formats large numbers into human-readable compact notation (e.g. 1.2M, 45.3k)
 */
export function formatCompact(num?: number | null): string {
  if (num === null || num === undefined) return '0';
  if (num >= 1_000_000) return (num / 1_000_000).toFixed(1) + 'M';
  if (num >= 1_000) return (num / 1_000).toFixed(1) + 'k';
  return num.toLocaleString();
}

/**
 * Formats duration in seconds to standard MM:SS string
 */
export function formatDuration(seconds?: number | null): string {
  if (!seconds || seconds <= 0) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Formats a viral ratio multiplier with + and x symbols
 */
export function formatViralRatio(ratio?: number | null): string {
  if (!ratio && ratio !== 0) return '+0.0x';
  return `+${ratio.toFixed(1)}x`;
}
