import { ClipItem } from '../api';

export const ALLOWED_VIDEO_EXTENSIONS = [
  '.mp4',
  '.mov',
  '.mkv',
  '.avi',
  '.m4v',
  '.webm',
] as const;

/**
 * Validates whether a file has one of the supported video extensions.
 */
export function filterAllowedVideoFile(filename: string): boolean {
  if (!filename) return false;
  const lower = filename.toLowerCase();
  const lastDot = lower.lastIndexOf('.');
  if (lastDot === -1) return false;
  const ext = lower.slice(lastDot);
  return ALLOWED_VIDEO_EXTENSIONS.includes(ext as any);
}

/**
 * Returns human-readable relative time ("just now", "5m ago", "2h ago", "3d ago", "2mo ago", "1y ago").
 */
export function timeAgo(isoString: string | null | undefined, now: Date = new Date()): string {
  if (!isoString) return '';
  const date = new Date(isoString);
  if (isNaN(date.getTime())) return '';

  const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (diffSec < 45) {
    return 'just now';
  }
  if (diffSec < 3600) {
    const mins = Math.max(1, Math.floor(diffSec / 60));
    return `${mins}m ago`;
  }
  if (diffSec < 86400) {
    const hours = Math.floor(diffSec / 3600);
    return `${hours}h ago`;
  }
  if (diffSec < 2592000) {
    // < 30 days
    const days = Math.floor(diffSec / 86400);
    return `${days}d ago`;
  }
  if (diffSec < 31536000) {
    // < 365 days
    const months = Math.floor(diffSec / 2592000);
    return `${months}mo ago`;
  }
  const years = Math.floor(diffSec / 31536000);
  return `${years}y ago`;
}

/**
 * Sorts clips by last_opened_at desc (falling back to added_at desc).
 */
export function sortRecents(items: ClipItem[]): ClipItem[] {
  return [...items].sort((a, b) => {
    const aTime = a.last_opened_at || a.added_at || '';
    const bTime = b.last_opened_at || b.added_at || '';
    if (!aTime && !bTime) return 0;
    if (!aTime) return 1;
    if (!bTime) return -1;
    return bTime.localeCompare(aTime);
  });
}

/**
 * Slices recents array based on showAll flag and limit (default 20).
 */
export function sliceRecents(
  items: ClipItem[],
  showAll: boolean,
  limit = 20
): { visible: ClipItem[]; hasMore: boolean } {
  if (showAll || items.length <= limit) {
    return { visible: items, hasMore: false };
  }
  return { visible: items.slice(0, limit), hasMore: items.length > limit };
}

/**
 * Filters clips by search query and label status.
 */
export function filterClipsByMeta(
  items: ClipItem[],
  options: {
    search?: string;
    statusFilter?: 'all' | 'none' | 'draft' | 'final' | 'flagged';
  }
): ClipItem[] {
  const q = (options.search ?? '').toLowerCase();
  const statusFilter = options.statusFilter ?? 'all';

  return items.filter((c) => {
    const name = (c.display_name || c.clip_id).toLowerCase();
    const matchesSearch =
      !q || name.includes(q) || c.clip_id.toLowerCase().includes(q);
    const matchesStatus =
      statusFilter === 'all' || c.label_status === statusFilter;

    return matchesSearch && matchesStatus;
  });
}

/**
 * Formats byte size into human-readable string (e.g. "2.4 MB", "512 KB").
 */
export function formatFileSize(bytes: number | null | undefined): string {
  if (bytes == null || !Number.isFinite(bytes) || bytes < 0) return 'N/A';
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  const gb = mb / 1024;
  return `${gb.toFixed(2)} GB`;
}
