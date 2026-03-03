/**
 * Shared color palette for Veloro.
 * Mirrors the CSS custom properties in App.css :root.
 */
export const COLORS = {
  primary:  '#E8603C',
  success:  '#10B981',
  warning:  '#F59E0B',
  error:    '#EF4444',
  info:     '#3B82F6',
  neutral:  '#6B7280',
  teal:     '#0891B2',
  purple:   '#8B5CF6',
};

/**
 * Returns a color based on lead qualification score (0-100).
 */
export function scoreColor(score) {
  if (!score && score !== 0) return COLORS.neutral;
  if (score >= 70) return COLORS.success;
  if (score >= 40) return COLORS.warning;
  return COLORS.error;
}
