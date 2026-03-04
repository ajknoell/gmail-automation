/**
 * Shared constants and utilities for the Intelligence section
 * (Radar, Triggers, Sources pages).
 */

// ─── Source Types (Signal collectors) ────────────────────────────
export const SOURCE_LABELS = {
  website: 'Website',
  job_posting: 'Job Posting',
  news: 'News',
  funding: 'Funding',
  tech_change: 'Tech Stack',
};

export const SOURCE_ICONS = {
  website: '\u{1F310}',
  job_posting: '\u{1F4BC}',
  news: '\u{1F4F0}',
  funding: '\u{1F4B0}',
  tech_change: '\u{1F527}',
};

export const SOURCE_DESCRIPTIONS = {
  website: {
    name: 'Website Monitoring',
    description: 'Checks contact websites for SSL issues, downtime, content changes, and outdated elements.',
    icon: '\u{1F310}',
  },
  news: {
    name: 'News & Funding',
    description: 'Searches for funding rounds, leadership changes, expansions, and industry news about your contacts\' companies.',
    icon: '\u{1F4F0}',
  },
  job_posting: {
    name: 'Job Postings',
    description: 'Tracks hiring activity at prospect companies to identify growth signals and potential needs.',
    icon: '\u{1F4BC}',
  },
  funding: {
    name: 'Funding Events',
    description: 'Monitors venture capital and funding activity for signals of growth and new budget.',
    icon: '\u{1F4B0}',
  },
  tech_change: {
    name: 'Tech Stack Changes',
    description: 'Detects changes in the technologies a company uses, signaling potential integration opportunities.',
    icon: '\u{1F527}',
  },
};

// ─── Trigger Types (Website monitoring) ──────────────────────────
export const TRIGGER_LABELS = {
  ssl_expiry: 'SSL Expiring',
  content_change: 'Content Changed',
  review_change: 'Reviews Changed',
  downtime: 'Site Down',
  copyright_outdated: 'Copyright Outdated',
};

export const TRIGGER_ICONS = {
  ssl_expiry: '\u{1F512}',
  content_change: '\u{1F4DD}',
  review_change: '\u2B50',
  downtime: '\u{1F534}',
  copyright_outdated: '\u{1F4C5}',
};

// ─── Severity ────────────────────────────────────────────────────
export const SEVERITY_COLORS = {
  critical: '#EF4444',
  important: '#F59E0B',
  info: '#6B7280',
};

// ─── Helpers ─────────────────────────────────────────────────────

/**
 * Detect whether an item is a website trigger (vs a signal).
 */
export function isWebsiteTrigger(item) {
  return 'trigger_type' in item;
}

/**
 * Get human-readable title for any trigger or signal.
 */
export function getItemTitle(item) {
  if (isWebsiteTrigger(item)) {
    return TRIGGER_LABELS[item.trigger_type] || item.trigger_type;
  }
  return item.title || (SOURCE_LABELS[item.source_type] || item.source_type) + ': ' + item.signal_type;
}

/**
 * Get the icon for any trigger or signal.
 */
export function getItemIcon(item) {
  if (isWebsiteTrigger(item)) {
    return TRIGGER_ICONS[item.trigger_type] || '\u{1F514}';
  }
  return SOURCE_ICONS[item.source_type] || '\u{1F514}';
}

/**
 * Get the source label for any trigger or signal.
 */
export function getItemSourceLabel(item) {
  if (isWebsiteTrigger(item)) {
    return 'Website Monitor';
  }
  return SOURCE_LABELS[item.source_type] || item.source_type;
}

/**
 * Get a human-readable summary for any trigger or signal.
 * For signals, returns the existing summary. For triggers,
 * transforms raw JSON values into plain English.
 */
export function getHumanSummary(item) {
  if (isWebsiteTrigger(item)) {
    const val = item.current_value || {};
    switch (item.trigger_type) {
      case 'ssl_expiry':
        return `Their SSL certificate expires in ${val.days_remaining || '?'} days. Websites with expired certificates show security warnings to visitors \u2014 a natural reason to reach out.`;
      case 'downtime':
        return `Their website is currently down${val.status_code ? ` (HTTP ${val.status_code})` : ''}. This is an urgent issue that needs immediate attention.`;
      case 'content_change':
        return 'Their website content was recently updated, which may indicate they\'re actively working on their online presence.';
      case 'copyright_outdated':
        return `Their website shows a ${val.copyright_year || 'outdated'} copyright year, suggesting it hasn\'t been maintained recently.`;
      case 'review_change':
        if (val.old_rating && val.new_rating) {
          return `Their Google review rating changed from ${val.old_rating} to ${val.new_rating}.`;
        }
        return 'Their Google review rating or count has changed recently.';
      default:
        return typeof val === 'object' ? '' : String(val);
    }
  }
  // Signals already have a summary from the backend
  return item.summary || '';
}

/**
 * Format a date string as relative time ("2h ago", "3d ago", etc.)
 */
export function timeAgo(dateStr) {
  if (!dateStr) return '';
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 0) return 'just now';
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return new Date(dateStr).toLocaleDateString();
}
