import { describe, it, expect } from 'vitest';
import { validateLabel } from './validate';
import { emptyLabel, Label } from './labelModel';

describe('validateLabel', () => {
  const baseMeta = { frame_count: 90, width: 1920, height: 1080 };

  function createValidFinalLabel(): Label {
    return {
      schema_version: 1,
      clip_id: 'test_clip',
      split: 'dev',
      annotator: 'annotator_1',
      mode: 'assisted',
      status: 'final',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      ball_colour: 'white',
      batter_hand: 'right',
      bowler_type: 'pace',
      lighting: 'bright',
      release: { frame: 5, x: 800, y: 400 },
      bounce: { frame: 15, x: 850, y: 550 },
      impact: { type: 'bat', frame: 22, x: 900, y: 420 },
      last_visible_frame: 40,
      lbw: null,
      calibration_gt: {
        points: {
          bat_L: [778.0, 434.0],
          bat_R: [1083.0, 430.0],
          bowl_L: [739.0, 764.0],
          bowl_R: [1115.0, 768.0],
          bat_stump: [936.0, 426.0],
          bowl_stump: [922.0, 784.0],
        },
        source: 'system_verified',
        residual_px: 2.5,
        updated_at: new Date().toISOString(),
      },
      flags: [],
      notes: '',
    };
  }

  it('valid final label passes validation with 0 errors and 0 warnings', () => {
    const label = createValidFinalLabel();
    const issues = validateLabel(label, baseMeta, 'final');
    expect(issues).toEqual([]);
  });

  describe('rule: schema_version must be 1', () => {
    it('valid case: schema_version is 1', () => {
      const label = createValidFinalLabel();
      label.schema_version = 1;
      const issues = validateLabel(label, baseMeta);
      expect(issues.find((i) => i.path === 'schema_version')).toBeUndefined();
    });

    it('invalid case: schema_version is 2', () => {
      const label = createValidFinalLabel();
      label.schema_version = 2;
      const issues = validateLabel(label, baseMeta);
      const issue = issues.find((i) => i.path === 'schema_version');
      expect(issue).toBeDefined();
      expect(issue?.severity).toBe('error');
    });
  });

  describe('rule: impact type "none" requires null coordinates', () => {
    it('valid case: impact type "none" with null coordinates', () => {
      const label = createValidFinalLabel();
      label.impact = { type: 'none', frame: null, x: null, y: null };
      const issues = validateLabel(label, baseMeta);
      expect(issues.find((i) => i.path === 'impact')).toBeUndefined();
    });

    it('invalid case: impact type "none" with non-null coordinates', () => {
      const label = createValidFinalLabel();
      label.impact = { type: 'none', frame: 25, x: 500, y: 500 };
      const issues = validateLabel(label, baseMeta);
      const issue = issues.find((i) => i.path === 'impact');
      expect(issue).toBeDefined();
      expect(issue?.severity).toBe('error');
    });
  });

  describe('rule: lbw only allowed when impact.type == "pad"', () => {
    it('valid case: impact.type == "pad" with lbw="out"', () => {
      const label = createValidFinalLabel();
      label.impact = { type: 'pad', frame: 22, x: 900, y: 420 };
      label.lbw = 'out';
      const issues = validateLabel(label, baseMeta);
      expect(issues.find((i) => i.path === 'lbw')).toBeUndefined();
    });

    it('invalid case: impact.type == "bat" with lbw="out"', () => {
      const label = createValidFinalLabel();
      label.impact = { type: 'bat', frame: 22, x: 900, y: 420 };
      label.lbw = 'out';
      const issues = validateLabel(label, baseMeta);
      const issue = issues.find((i) => i.path === 'lbw');
      expect(issue).toBeDefined();
      expect(issue?.severity).toBe('error');
    });
  });

  describe('rule: release.frame < bounce.frame', () => {
    it('valid case: release.frame (5) < bounce.frame (15)', () => {
      const label = createValidFinalLabel();
      label.release = { frame: 5, x: 800, y: 400 };
      label.bounce = { frame: 15, x: 850, y: 550 };
      const issues = validateLabel(label, baseMeta);
      expect(issues.find((i) => i.path === 'release.frame')).toBeUndefined();
    });

    it('invalid case: release.frame (15) >= bounce.frame (15)', () => {
      const label = createValidFinalLabel();
      label.release = { frame: 15, x: 800, y: 400 };
      label.bounce = { frame: 15, x: 850, y: 550 };
      const issues = validateLabel(label, baseMeta);
      const issue = issues.find((i) => i.path === 'release.frame');
      expect(issue).toBeDefined();
      expect(issue?.severity).toBe('error');
    });
  });

  describe('rule: bounce.frame <= impact.frame', () => {
    it('valid case: bounce.frame (15) <= impact.frame (20)', () => {
      const label = createValidFinalLabel();
      label.bounce = { frame: 15, x: 850, y: 550 };
      label.impact = { type: 'bat', frame: 20, x: 900, y: 420 };
      const issues = validateLabel(label, baseMeta);
      expect(issues.find((i) => i.path === 'impact.frame')).toBeUndefined();
    });

    it('invalid case: bounce.frame (22) > impact.frame (20)', () => {
      const label = createValidFinalLabel();
      label.bounce = { frame: 22, x: 850, y: 550 };
      label.impact = { type: 'bat', frame: 20, x: 900, y: 420 };
      const issues = validateLabel(label, baseMeta);
      const issue = issues.find((i) => i.path === 'impact.frame');
      expect(issue).toBeDefined();
      expect(issue?.severity).toBe('error');
    });
  });

  describe('rule: impact.frame <= last_visible_frame', () => {
    it('valid case: impact.frame (22) <= last_visible_frame (40)', () => {
      const label = createValidFinalLabel();
      label.impact = { type: 'bat', frame: 22, x: 900, y: 420 };
      label.last_visible_frame = 40;
      const issues = validateLabel(label, baseMeta);
      expect(issues.find((i) => i.path === 'last_visible_frame' && i.severity === 'error')).toBeUndefined();
    });

    it('invalid case: impact.frame (45) > last_visible_frame (40)', () => {
      const label = createValidFinalLabel();
      label.impact = { type: 'bat', frame: 45, x: 900, y: 420 };
      label.last_visible_frame = 40;
      const issues = validateLabel(label, baseMeta);
      const issue = issues.find((i) => i.path === 'last_visible_frame' && i.severity === 'error');
      expect(issue).toBeDefined();
      expect(issue?.message).toContain('impact.frame');
    });
  });

  describe('rule: release.frame <= last_visible_frame', () => {
    it('valid case: release.frame (5) <= last_visible_frame (40)', () => {
      const label = createValidFinalLabel();
      label.release = { frame: 5, x: 800, y: 400 };
      label.last_visible_frame = 40;
      const issues = validateLabel(label, baseMeta);
      expect(issues.find((i) => i.path === 'last_visible_frame' && i.message.includes('release.frame'))).toBeUndefined();
    });

    it('invalid case: release.frame (50) > last_visible_frame (40)', () => {
      const label = createValidFinalLabel();
      label.release = { frame: 50, x: 800, y: 400 };
      label.bounce = { frame: 60, x: 850, y: 550 };
      label.last_visible_frame = 40;
      const issues = validateLabel(label, baseMeta);
      const issue = issues.find((i) => i.path === 'last_visible_frame' && i.message.includes('release.frame'));
      expect(issue).toBeDefined();
      expect(issue?.severity).toBe('error');
    });
  });

  describe('dimensional bounds: frame and coordinate limits', () => {
    it('valid case: frames in [0, 89] and coords in [0, 1920] x [0, 1080]', () => {
      const label = createValidFinalLabel();
      const issues = validateLabel(label, { frame_count: 90, width: 1920, height: 1080 });
      expect(issues.filter((i) => i.severity === 'error')).toEqual([]);
    });

    it('invalid case: frame out of bounds (frame 90 in clip of 90 frames)', () => {
      const label = createValidFinalLabel();
      label.last_visible_frame = 90;
      const issues = validateLabel(label, { frame_count: 90, width: 1920, height: 1080 });
      const issue = issues.find((i) => i.path === 'last_visible_frame' && i.message.includes('out of bounds'));
      expect(issue).toBeDefined();
    });

    it('invalid case: x coordinate out of bounds (x = 1925)', () => {
      const label = createValidFinalLabel();
      label.bounce = { frame: 15, x: 1925, y: 500 };
      const issues = validateLabel(label, { frame_count: 90, width: 1920, height: 1080 });
      const issue = issues.find((i) => i.path === 'bounce.x');
      expect(issue).toBeDefined();
    });
  });

  describe('status final: required fields', () => {
    it('draft label with missing fields has 0 errors for status "draft"', () => {
      const draft = emptyLabel({ clip_id: 'c1' }, null, 'tester');
      const issues = validateLabel(draft, baseMeta, 'draft');
      expect(issues.filter((i) => i.severity === 'error')).toEqual([]);
    });

    it('requires annotator, release, bounce, impact, last_visible_frame, ball_colour, batter_hand for "final"', () => {
      const draft = emptyLabel({ clip_id: 'c1' }, null, '');
      const issues = validateLabel(draft, baseMeta, 'final');

      const paths = issues.filter((i) => i.severity === 'error').map((i) => i.path);
      expect(paths).toContain('annotator');
      expect(paths).toContain('release');
      expect(paths).toContain('bounce');
      expect(paths).toContain('impact');
      expect(paths).toContain('last_visible_frame');
      expect(paths).toContain('ball_colour');
      expect(paths).toContain('batter_hand');
      expect(paths).toContain('calibration_gt');
      expect(paths).toContain('split');
      expect(paths).toContain('bowler_type');
      expect(paths).toContain('lighting');
    });

    it('requires lbw when impact type is pad in final', () => {
      const label = createValidFinalLabel();
      label.impact = { type: 'pad', frame: 22, x: 900, y: 420 };
      label.lbw = null;
      const issues = validateLabel(label, baseMeta, 'final');
      const issue = issues.find((i) => i.path === 'lbw');
      expect(issue).toBeDefined();
      expect(issue?.message).toContain("lbw is required for status 'final' when impact.type is 'pad'");

      // Valid when lbw is provided
      label.lbw = 'out';
      const issuesValid = validateLabel(label, baseMeta, 'final');
      expect(issuesValid.find((i) => i.path === 'lbw')).toBeUndefined();
    });

    it('requires impact coordinates when impact type is not "none" in final', () => {
      const label = createValidFinalLabel();
      label.impact = { type: 'bat', frame: null, x: null, y: null };
      const issues = validateLabel(label, baseMeta, 'final');
      const issue = issues.find((i) => i.path === 'impact');
      expect(issue).toBeDefined();
      expect(issue?.message).toContain("required when impact.type is 'bat'");
    });
  });

  describe('non-blocking warnings', () => {
    it('warns when release frame is later than frame 20', () => {
      const label = createValidFinalLabel();
      label.release = { frame: 22, x: 800, y: 400 };
      label.bounce = { frame: 30, x: 850, y: 550 };
      const issues = validateLabel(label, baseMeta);
      const warn = issues.find((i) => i.path === 'release.frame' && i.severity === 'warning');
      expect(warn).toBeDefined();
      expect(warn?.message).toContain('unusually late');
    });

    it('warns when bounce occurs within 3 frames of release', () => {
      const label = createValidFinalLabel();
      label.release = { frame: 5, x: 800, y: 400 };
      label.bounce = { frame: 7, x: 850, y: 550 }; // diff = 2 <= 3
      const issues = validateLabel(label, baseMeta);
      const warn = issues.find((i) => i.path === 'bounce.frame' && i.severity === 'warning');
      expect(warn).toBeDefined();
      expect(warn?.message).toContain('within 3 frames');
    });

    it('warns when last_visible_frame < bounce.frame', () => {
      const label = createValidFinalLabel();
      label.bounce = { frame: 25, x: 850, y: 550 };
      label.last_visible_frame = 20;
      const issues = validateLabel(label, baseMeta);
      const warn = issues.find((i) => i.path === 'last_visible_frame' && i.severity === 'warning');
      expect(warn).toBeDefined();
      expect(warn?.message).toContain('before bounce frame');
    });

    it('warns when calibration residual_px is between CALIB_WARN_PX and CALIB_ERROR_PX', () => {
      const label = createValidFinalLabel();
      label.calibration_gt!.residual_px = 6.5; // > 4.0 and <= 12.0
      const issues = validateLabel(label, baseMeta);
      const warn = issues.find((i) => i.path === 'calibration_gt.residual_px' && i.severity === 'warning');
      expect(warn).toBeDefined();
      expect(warn?.message).toContain('exceeds warning threshold');
    });

    it('errors when calibration residual_px exceeds CALIB_ERROR_PX without bad_calibration flag', () => {
      const label = createValidFinalLabel();
      label.flags = [];
      label.calibration_gt!.residual_px = 14.2; // > 12.0
      const issues = validateLabel(label, baseMeta);
      const err = issues.find((i) => i.path === 'calibration_gt.residual_px' && i.severity === 'error');
      expect(err).toBeDefined();
      expect(err?.message).toContain('exceeds maximum error limit');
    });

    it('warns when calibration residual_px exceeds CALIB_ERROR_PX with bad_calibration flag set', () => {
      const label = createValidFinalLabel();
      label.flags = ['bad_calibration'];
      label.calibration_gt!.residual_px = 14.2; // > 12.0
      const issues = validateLabel(label, baseMeta);
      const err = issues.find((i) => i.path === 'calibration_gt.residual_px' && i.severity === 'error');
      expect(err).toBeUndefined();
      const warn = issues.find((i) => i.path === 'calibration_gt.residual_px' && i.severity === 'warning');
      expect(warn).toBeDefined();
      expect(warn?.message).toContain('flagged as bad_calibration');
    });

    it('errors when calibration geometry is invalid', () => {
      const label = createValidFinalLabel();
      // Reverse horizontal ordering
      label.calibration_gt!.points.bat_L = [1100, 434];
      const issues = validateLabel(label, baseMeta);
      const err = issues.find((i) => i.path === 'calibration_gt' && i.severity === 'error');
      expect(err).toBeDefined();
      expect(err?.message).toContain('strictly less than');
    });
  });
});
