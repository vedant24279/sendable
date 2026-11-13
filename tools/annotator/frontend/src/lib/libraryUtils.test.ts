import { describe, it, expect } from 'vitest';
import {
  timeAgo,
  filterAllowedVideoFile,
  sortRecents,
  sliceRecents,
  filterClipsByMeta,
  formatFileSize,
} from './libraryUtils';
import { ClipItem } from '../api';

describe('libraryUtils', () => {
  describe('timeAgo', () => {
    const baseNow = new Date('2026-11-12T12:00:00Z');

    it('returns empty string for null, undefined, or invalid date', () => {
      expect(timeAgo(null, baseNow)).toBe('');
      expect(timeAgo(undefined, baseNow)).toBe('');
      expect(timeAgo('not-a-date', baseNow)).toBe('');
    });

    it('returns "just now" for dates within 45 seconds', () => {
      const d1 = new Date('2026-11-12T11:59:45Z').toISOString();
      expect(timeAgo(d1, baseNow)).toBe('just now');
      const d2 = new Date('2026-11-12T11:59:20Z').toISOString();
      expect(timeAgo(d2, baseNow)).toBe('just now');
    });

    it('returns minutes ago', () => {
      const d = new Date('2026-11-12T11:55:00Z').toISOString();
      expect(timeAgo(d, baseNow)).toBe('5m ago');
    });

    it('returns hours ago', () => {
      const d = new Date('2026-11-12T09:00:00Z').toISOString();
      expect(timeAgo(d, baseNow)).toBe('3h ago');
    });

    it('returns days ago', () => {
      const d = new Date('2026-11-09T12:00:00Z').toISOString();
      expect(timeAgo(d, baseNow)).toBe('3d ago');
    });

    it('returns months ago', () => {
      const d = new Date('2026-09-12T12:00:00Z').toISOString();
      expect(timeAgo(d, baseNow)).toBe('2mo ago');
    });

    it('returns years ago', () => {
      const d = new Date('2024-11-12T12:00:00Z').toISOString();
      expect(timeAgo(d, baseNow)).toBe('2y ago');
    });
  });

  describe('filterAllowedVideoFile', () => {
    it('accepts allowed video extensions case-insensitively', () => {
      expect(filterAllowedVideoFile('delivery.mp4')).toBe(true);
      expect(filterAllowedVideoFile('match.MOV')).toBe(true);
      expect(filterAllowedVideoFile('clip.mkv')).toBe(true);
      expect(filterAllowedVideoFile('camera.AVI')).toBe(true);
      expect(filterAllowedVideoFile('slowmo.m4v')).toBe(true);
      expect(filterAllowedVideoFile('web.webm')).toBe(true);
    });

    it('rejects unsupported extensions', () => {
      expect(filterAllowedVideoFile('notes.txt')).toBe(false);
      expect(filterAllowedVideoFile('image.jpg')).toBe(false);
      expect(filterAllowedVideoFile('data.csv')).toBe(false);
      expect(filterAllowedVideoFile('no_extension')).toBe(false);
      expect(filterAllowedVideoFile('')).toBe(false);
    });
  });

  describe('sortRecents and sliceRecents', () => {
    const mockClips: ClipItem[] = [
      {
        clip_id: 'c_1',
        path: '',
        fps: 30,
        frame_count: 50,
        width: 1280,
        height: 720,
        ball_type: null,
        has_results: false,
        has_calibration: false,
        label_status: 'none',
        split: null,
        added_at: '2026-11-10T10:00:00Z',
        last_opened_at: '2026-11-11T12:00:00Z',
      },
      {
        clip_id: 'c_2',
        path: '',
        fps: 30,
        frame_count: 50,
        width: 1280,
        height: 720,
        ball_type: null,
        has_results: false,
        has_calibration: false,
        label_status: 'none',
        split: null,
        added_at: '2026-11-12T08:00:00Z',
        last_opened_at: null,
      },
      {
        clip_id: 'c_3',
        path: '',
        fps: 30,
        frame_count: 50,
        width: 1280,
        height: 720,
        ball_type: null,
        has_results: false,
        has_calibration: false,
        label_status: 'none',
        split: null,
        added_at: '2026-11-09T08:00:00Z',
        last_opened_at: '2026-11-12T10:00:00Z',
      },
    ];

    it('sorts clips by last_opened_at falling back to added_at desc', () => {
      const sorted = sortRecents(mockClips);
      // c_3 (opened Nov 12 10:00) > c_2 (added Nov 12 08:00) > c_1 (opened Nov 11 12:00)
      expect(sorted.map((c) => c.clip_id)).toEqual(['c_3', 'c_2', 'c_1']);
    });

    it('slices recents honoring limit and showAll', () => {
      const manyClips = Array.from({ length: 25 }, (_, i) => ({
        ...mockClips[0],
        clip_id: `c_${i}`,
      }));

      const slicedDefault = sliceRecents(manyClips, false, 20);
      expect(slicedDefault.visible.length).toBe(20);
      expect(slicedDefault.hasMore).toBe(true);

      const slicedAll = sliceRecents(manyClips, true, 20);
      expect(slicedAll.visible.length).toBe(25);
      expect(slicedAll.hasMore).toBe(false);
    });
  });

  describe('filterClipsByMeta and formatFileSize', () => {
    const baseClip: ClipItem = {
      clip_id: 'c_0',
      path: '',
      fps: 30,
      frame_count: 50,
      width: 1280,
      height: 720,
      ball_type: null,
      has_results: false,
      has_calibration: false,
      label_status: 'none',
      split: null,
    };
    const items: ClipItem[] = [
      {
        ...baseClip,
        clip_id: 'c_1',
        display_name: 'ind_vs_aus_out.mp4',
        label_status: 'draft',
        reference_decision: 'out',
      },
      {
        ...baseClip,
        clip_id: 'c_2',
        display_name: 'over_12_not_out.mp4',
        label_status: 'final',
        reference_decision: 'not_out',
      },
      {
        ...baseClip,
        clip_id: 'c_3',
        display_name: 'practice_clip.mp4',
        label_status: 'none',
        reference_decision: null,
      },
    ];

    it('filters by decisionFilter and statusFilter', () => {
      expect(filterClipsByMeta(items, { decisionFilter: 'out' }).map((c) => c.clip_id)).toEqual(['c_1']);
      expect(filterClipsByMeta(items, { decisionFilter: 'not_out' }).map((c) => c.clip_id)).toEqual(['c_2']);
      expect(filterClipsByMeta(items, { decisionFilter: 'unknown' }).map((c) => c.clip_id)).toEqual(['c_3']);
      expect(filterClipsByMeta(items, { statusFilter: 'final', decisionFilter: 'not_out' }).map((c) => c.clip_id)).toEqual(['c_2']);
      expect(filterClipsByMeta(items, { statusFilter: 'draft', decisionFilter: 'not_out' })).toEqual([]);
    });

    it('formats file size cleanly', () => {
      expect(formatFileSize(null)).toBe('N/A');
      expect(formatFileSize(500)).toBe('500 B');
      expect(formatFileSize(2048)).toBe('2.0 KB');
      expect(formatFileSize(2.5 * 1024 * 1024)).toBe('2.5 MB');
    });
  });
});
