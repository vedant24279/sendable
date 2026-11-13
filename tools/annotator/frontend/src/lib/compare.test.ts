import { describe, it, expect } from 'vitest';
import {
  systemPinsForFrame,
  formatCompareCsvRow,
  sortClipsByRunMetric,
} from './compare';
import type { ClipItem, PrefillEvents } from '../api';

describe('systemPinsForFrame', () => {
  const sampleEvents: PrefillEvents = {
    release: { frame: 10, x: 100.5, y: 200.25 },
    bounce: { frame: 25, x: 500.0, y: 600.0, zone: 'GOOD', length_m: 6.8 },
    impact: null,
    deviation: { frame: 32, x: 520.0, y: 740.0 },
  };

  it('returns exact system pin with full style when currentFrame equals event frame', () => {
    const pins = systemPinsForFrame(sampleEvents, 10);
    expect(pins).toHaveLength(1);
    expect(pins[0]).toMatchObject({
      kind: 'release',
      shortLabel: 'sys R',
      frame: 10,
      x: 100.5,
      y: 200.25,
      exact: true,
      frameOffset: 0,
    });
    expect(pins[0].tooltip).toContain('sys R');
    expect(pins[0].tooltip).toContain('10');
    expect(pins[0].tooltip).toContain('100.5');
  });

  it('includes adjacent pins within ±1 frame in lighter non-exact style', () => {
    const pinsAt24 = systemPinsForFrame(sampleEvents, 24);
    expect(pinsAt24).toHaveLength(1);
    expect(pinsAt24[0]).toMatchObject({
      kind: 'bounce',
      shortLabel: 'sys B',
      frame: 25,
      exact: false,
      frameOffset: 1,
    });

    const pinsAt33 = systemPinsForFrame(sampleEvents, 33);
    expect(pinsAt33).toHaveLength(1);
    expect(pinsAt33[0]).toMatchObject({
      kind: 'deviation',
      shortLabel: 'sys D',
      frame: 32,
      exact: false,
      frameOffset: -1,
    });
  });

  it('excludes system pins more than 1 frame away from currentFrame', () => {
    expect(systemPinsForFrame(sampleEvents, 8)).toEqual([]);
    expect(systemPinsForFrame(sampleEvents, 12)).toEqual([]);
    expect(systemPinsForFrame(sampleEvents, 23)).toEqual([]);
    expect(systemPinsForFrame(sampleEvents, 34)).toEqual([]);
  });
});

describe('formatCompareCsvRow', () => {
  it('formats complete CSV row values cleanly', () => {
    const formatted = formatCompareCsvRow({
      clip_id: 'c_09a18d5f',
      release_frame_error: '-2',
      release_px_error: '101.4787',
      bounce_frame_error: '1',
      bounce_px_error: '48.3037',
      bounce_ground_error_m: '0.53933',
      bounce_pitch_z_error_m: '0.45703',
      deviation_frame_error: '0',
      deviation_px_error: '7.083',
    });

    expect(formatted).toEqual({
      releaseError: '-2 f / 101.5 px',
      bounceError: '+1 f / 48.3 px / 0.539 m',
      pitchZError: '0.457 m',
      deviationVsImpact: '0 f / 7.1 px',
    });
  });

  it('returns dashes for missing or null CSV row fields', () => {
    expect(formatCompareCsvRow(null)).toEqual({
      releaseError: '—',
      bounceError: '—',
      pitchZError: '—',
      deviationVsImpact: '—',
    });

    expect(
      formatCompareCsvRow({
        release_frame_error: '2',
        release_px_error: '36.1',
        bounce_frame_error: '',
        bounce_px_error: '',
        bounce_ground_error_m: '',
        bounce_pitch_z_error_m: '',
        deviation_frame_error: '',
        deviation_px_error: '',
      })
    ).toEqual({
      releaseError: '+2 f / 36.1 px',
      bounceError: '—',
      pitchZError: '—',
      deviationVsImpact: '—',
    });
  });
});

describe('sortClipsByRunMetric', () => {
  const makeClip = (clip_id: string): ClipItem => ({
    clip_id,
    path: `${clip_id}.mp4`,
    fps: 30,
    frame_count: 60,
    width: 1920,
    height: 1080,
    ball_type: 'pink',
    has_results: false,
    has_calibration: false,
    label_status: 'final',
    split: 'dev',
  });

  it('sorts worst bounce and worst release errors first and places clips without a CSV row last', () => {
    const clips = [
      makeClip('c_no_row'),
      makeClip('c_small'),
      makeClip('c_missed_bounce'),
      makeClip('c_worst_bounce'),
      makeClip('c_worst_release'),
    ];

    const rows: Record<string, Record<string, string>> = {
      c_small: {
        bounce_ground_error_m: '0.12',
        release_px_error: '5.0',
      },
      c_missed_bounce: {
        bounce_ground_error_m: '',
        release_px_error: '30.0',
      },
      c_worst_bounce: {
        bounce_ground_error_m: '0.95',
        release_px_error: '50.0',
      },
      c_worst_release: {
        bounce_ground_error_m: '0.40',
        release_px_error: '190.0',
      },
    };

    const byBounce = sortClipsByRunMetric(clips, rows, 'worst_bounce').map((c) => c.clip_id);
    expect(byBounce).toEqual([
      'c_worst_bounce',
      'c_worst_release',
      'c_small',
      'c_missed_bounce',
      'c_no_row',
    ]);

    const byRelease = sortClipsByRunMetric(clips, rows, 'worst_release').map((c) => c.clip_id);
    expect(byRelease).toEqual([
      'c_worst_release',
      'c_worst_bounce',
      'c_missed_bounce',
      'c_small',
      'c_no_row',
    ]);
  });
});
