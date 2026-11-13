import { describe, it, expect } from 'vitest';
import {
  emptyLabel,
  placeEvent,
  setImpactType,
  setLastVisible,
  clearEvent,
  setMeta,
  setLbw,
  toggleFlag,
  setNotes,
  setSplit,
  adoptSystemEvents,
  setCalibrationPoint,
  acceptSystemCalibration,
  resetCalibrationToSystem,
  clearCalibration,
  unconfirmStump,
  getStumpConfirmed,
  round1,
  Label,
} from './labelModel';
import { PrefillData } from '../api';

describe('labelModel', () => {
  it('creates emptyLabel with defaults and prefill ball_type', () => {
    const meta = { clip_id: 'clip_01', split: 'dev' as const, ball_type: 'white' };
    const label = emptyLabel(meta, null, 'tester');

    expect(label.schema_version).toBe(1);
    expect(label.clip_id).toBe('clip_01');
    expect(label.split).toBe('dev');
    expect(label.annotator).toBe('tester');
    expect(label.mode).toBe('blind');
    expect(label.status).toBe('draft');
    expect(label.ball_colour).toBe('white');
    expect(label.release).toBeNull();
    expect(label.bounce).toBeNull();
    expect(label.impact).toBeNull();
    expect(label.last_visible_frame).toBeNull();
    expect(label.lbw).toBeNull();
    expect(label.flags).toEqual([]);
    expect(label.notes).toBe('');
  });

  it('places release, bounce, and impact events and survives JSON round trip', () => {
    const base = emptyLabel({ clip_id: 'clip_01' }, null, 'tester');
    const ctxBlind = { ghostVisible: false };

    // Place release
    const l1 = placeEvent(base, 'release', 5, 123.456, 789.012, ctxBlind);
    expect(l1.release).toEqual({ frame: 5, x: 123.5, y: 789.0 });

    // Place bounce
    const l2 = placeEvent(l1, 'bounce', 15, 345.678, 654.321, ctxBlind);
    expect(l2.bounce).toEqual({ frame: 15, x: 345.7, y: 654.3 });

    // Set impact type then place impact
    const l3 = setImpactType(l2, 'bat', ctxBlind);
    const l4 = placeEvent(l3, 'impact', 22, 555.55, 444.44, ctxBlind);
    expect(l4.impact).toEqual({ type: 'bat', frame: 22, x: 555.6, y: 444.4 });

    // JSON round trip
    const serialized = JSON.stringify(l4);
    const deserialized: Label = JSON.parse(serialized);

    expect(deserialized).toEqual(l4);
  });

  it('rounds coordinates to 1 decimal place', () => {
    expect(round1(12.34)).toBe(12.3);
    expect(round1(12.36)).toBe(12.4);
    expect(round1(12.05)).toBe(12.1);
    expect(round1(100)).toBe(100);
  });

  it('impact type "none" clears frame, x, and y coordinates', () => {
    const base = emptyLabel({ clip_id: 'clip_01' }, null, 'tester');
    const l1 = setImpactType(base, 'bat');
    const l2 = placeEvent(l1, 'impact', 20, 100, 200, { ghostVisible: false });
    expect(l2.impact?.frame).toBe(20);

    const l3 = setImpactType(l2, 'none');
    expect(l3.impact).toEqual({ type: 'none', frame: null, x: null, y: null });
  });

  it('changing impact type away from "pad" clears lbw', () => {
    const base = emptyLabel({ clip_id: 'clip_01' }, null, 'tester');
    const l1 = setImpactType(base, 'pad');
    const l2 = setLbw(l1, 'out');
    expect(l2.lbw).toBe('out');

    // Change to "bat"
    const l3 = setImpactType(l2, 'bat');
    expect(l3.impact?.type).toBe('bat');
    expect(l3.lbw).toBeNull();
  });

  it('throws an error if placing impact position before impact type is set', () => {
    const base = emptyLabel({ clip_id: 'clip_01' }, null, 'tester');

    expect(() => {
      placeEvent(base, 'impact', 20, 100, 200, { ghostVisible: false });
    }).toThrow(/Cannot place impact coordinates without an impact type/);
  });

  it('throws an error if placing impact position when impact type is "none"', () => {
    const base = emptyLabel({ clip_id: 'clip_01' }, null, 'tester');
    const l1 = setImpactType(base, 'none');

    expect(() => {
      placeEvent(l1, 'impact', 20, 100, 200, { ghostVisible: false });
    }).toThrow(/Cannot place impact coordinates when impact type is 'none'/);
  });

  it('mode becomes "assisted" after one ghostVisible edit and stays "assisted"', () => {
    const base = emptyLabel({ clip_id: 'clip_01' }, null, 'tester');
    expect(base.mode).toBe('blind');

    // Blind edit
    const l1 = placeEvent(base, 'release', 4, 100, 200, { ghostVisible: false });
    expect(l1.mode).toBe('blind');

    // Edit with ghostVisible true
    const l2 = placeEvent(l1, 'bounce', 14, 200, 300, { ghostVisible: true });
    expect(l2.mode).toBe('assisted');

    // Subsequent edit with ghostVisible false remains assisted
    const l3 = setImpactType(l2, 'bat', { ghostVisible: false });
    expect(l3.mode).toBe('assisted');

    const l4 = placeEvent(l3, 'impact', 20, 300, 400, { ghostVisible: false });
    expect(l4.mode).toBe('assisted');
  });

  it('adoptSystemEvents copies release and bounce only, keeps impact, and sets mode "assisted"', () => {
    const base = emptyLabel({ clip_id: 'clip_01' }, null, 'tester');
    const withImpact = setImpactType(base, 'bat');
    const placedImpact = placeEvent(withImpact, 'impact', 25, 450.2, 350.8, { ghostVisible: false });

    const mockPrefill: PrefillData = {
      clip_id: 'clip_01',
      events: {
        release: { frame: 2, x: 776.44, y: 456.12 },
        bounce: { frame: 12, x: 850.88, y: 546.77 },
        impact: { type: 'stumps', frame: 22, x: 900, y: 400 },
        deviation: null,
      },
      trajectory: [],
      calibration: [],
    };

    const adopted = adoptSystemEvents(placedImpact, mockPrefill);

    expect(adopted.release).toEqual({ frame: 2, x: 776.4, y: 456.1 });
    expect(adopted.bounce).toEqual({ frame: 12, x: 850.9, y: 546.8 });
    // impact was unchanged
    expect(adopted.impact).toEqual({ type: 'bat', frame: 25, x: 450.2, y: 350.8 });
    expect(adopted.mode).toBe('assisted');
  });

  it('sets last visible, clearEvent, flags, notes, and metadata', () => {
    let l = emptyLabel({ clip_id: 'clip_01' }, null, 'tester');
    l = setLastVisible(l, 35);
    expect(l.last_visible_frame).toBe(35);

    l = clearEvent(l, 'last_visible');
    expect(l.last_visible_frame).toBeNull();

    l = toggleFlag(l, 'camera_moved');
    expect(l.flags).toContain('camera_moved');
    l = toggleFlag(l, 'camera_moved');
    expect(l.flags).not.toContain('camera_moved');

    l = setNotes(l, 'Tricky delivery');
    expect(l.notes).toBe('Tricky delivery');

    l = setSplit(l, 'final');
    expect(l.split).toBe('final');

    l = setMeta(l, 'batter_hand', 'left');
    expect(l.batter_hand).toBe('left');
  });

  it('handles calibration pure functions (accept, setPoint, reset, clear)', () => {
    const base = emptyLabel({ clip_id: 'clip_01' }, null, 'tester');
    expect(base.calibration_gt).toBeNull();

    const systemPoints: Record<string, [number, number]> = {
      bat_L: [778.0, 434.0],
      bat_R: [1083.0, 430.0],
      bowl_L: [739.0, 764.0],
      bowl_R: [1115.0, 768.0],
      bat_stump: [936.0, 426.0],
      bowl_stump: [922.0, 784.0],
    };

    // 1. Accept system calibration: copies corners, derives unconfirmed stumps, residual is null
    const accepted = acceptSystemCalibration(base, systemPoints);
    expect(accepted.calibration_gt).toBeDefined();
    expect(accepted.calibration_gt?.source).toBe('system_verified');
    expect(accepted.calibration_gt?.points.bat_L).toEqual([778.0, 434.0]);
    expect(accepted.calibration_gt?.residual_px).toBeNull();
    expect(accepted.calibration_gt?.stump_confirmed).toEqual({ bat_stump: false, bowl_stump: false });
    // Both stumps should be derived (not null, rounded to 1 decimal)
    expect(accepted.calibration_gt?.points.bat_stump).toBeDefined();
    expect(accepted.calibration_gt?.points.bowl_stump).toBeDefined();

    // 2. Set one corner point (system_adjusted, rounds to 1 decimal, unconfirmed stumps re-derived)
    const modified = setCalibrationPoint(accepted, 'bat_L', 779.456, 435.123, systemPoints);
    expect(modified.calibration_gt?.points.bat_L).toEqual([779.5, 435.1]);
    expect(modified.calibration_gt?.source).toBe('system_adjusted');
    expect(modified.calibration_gt?.residual_px).toBeNull();

    // 3. Reset calibration back to system: copies 6 system points with both unconfirmed
    const reset = resetCalibrationToSystem(modified, systemPoints);
    expect(reset.calibration_gt?.points.bat_L).toEqual([778.0, 434.0]);
    expect(reset.calibration_gt?.points.bat_stump).toEqual([936.0, 426.0]);
    expect(reset.calibration_gt?.points.bowl_stump).toEqual([922.0, 784.0]);
    expect(reset.calibration_gt?.source).toBe('system_verified');
    expect(reset.calibration_gt?.residual_px).toBeNull();
    expect(reset.calibration_gt?.stump_confirmed).toEqual({ bat_stump: false, bowl_stump: false });

    // 4. Clear calibration
    const cleared = clearCalibration(reset);
    expect(cleared.calibration_gt).toBeNull();
  });

  it('moving a corner re-derives unconfirmed stumps while confirmed stumps stay put', () => {
    const base = emptyLabel({ clip_id: 'clip_02' }, null, 'tester');
    const systemPoints: Record<string, [number, number]> = {
      bat_L: [778.0, 434.0],
      bat_R: [1083.0, 430.0],
      bowl_L: [739.0, 764.0],
      bowl_R: [1115.0, 768.0],
      bat_stump: [936.0, 426.0],
      bowl_stump: [922.0, 784.0],
    };

    // 1. Accept system points -> both derived (unconfirmed)
    const accepted = acceptSystemCalibration(base, systemPoints);
    const initialBowlStump = accepted.calibration_gt!.points.bowl_stump;

    // 2. Setting/moving a stump manually marks that stump confirmed
    const confirmedBat = setCalibrationPoint(accepted, 'bat_stump', 940.0, 420.0, systemPoints);
    expect(confirmedBat.calibration_gt?.stump_confirmed).toEqual({
      bat_stump: true,
      bowl_stump: false,
    });
    expect(confirmedBat.calibration_gt?.points.bat_stump).toEqual([940.0, 420.0]);
    // Single confirmed stump calculates partial residual
    expect(confirmedBat.calibration_gt?.residual_px).not.toBeNull();
    expect(confirmedBat.calibration_gt?.residual_px).toBeGreaterThan(0);

    // 3. Move a corner: confirmed stump stays put, unconfirmed bowl_stump re-derived
    const movedCorner = setCalibrationPoint(confirmedBat, 'bat_L', 760.0, 440.0, systemPoints);
    // bat_stump was confirmed, so it STAYS at 940.0, 420.0
    expect(movedCorner.calibration_gt?.points.bat_stump).toEqual([940.0, 420.0]);
    expect(movedCorner.calibration_gt?.stump_confirmed?.bat_stump).toBe(true);
    // bowl_stump was unconfirmed, so its coordinates re-derived and changed
    expect(movedCorner.calibration_gt?.stump_confirmed?.bowl_stump).toBe(false);
    expect(movedCorner.calibration_gt?.points.bowl_stump).not.toEqual(initialBowlStump);

    // 4. Unconfirm bat_stump -> snaps back to homography-predicted position, residual becomes null
    const unconfirmed = unconfirmStump(movedCorner, 'bat_stump', systemPoints);
    expect(unconfirmed.calibration_gt?.stump_confirmed).toEqual({
      bat_stump: false,
      bowl_stump: false,
    });
    expect(unconfirmed.calibration_gt?.points.bat_stump).not.toEqual([940.0, 420.0]);
    expect(unconfirmed.calibration_gt?.residual_px).toBeNull();
  });

  it('defaults old labels missing stump_confirmed to false', () => {
    const oldCalib = {
      points: {
        bat_L: [778.0, 434.0] as [number, number],
        bat_R: [1083.0, 430.0] as [number, number],
        bowl_L: [739.0, 764.0] as [number, number],
        bowl_R: [1115.0, 768.0] as [number, number],
        bat_stump: [936.0, 426.0] as [number, number],
        bowl_stump: [922.0, 784.0] as [number, number],
      },
      source: 'system_verified' as const,
      residual_px: 12.7,
      updated_at: '2026-11-05T10:00:00Z',
    };

    const confirmed = getStumpConfirmed(oldCalib as any);
    expect(confirmed).toEqual({ bat_stump: false, bowl_stump: false });
  });

  it('prefills reference_decision, ball_colour_hint fallback, and source_group in emptyLabel', () => {
    const label = emptyLabel(
      {
        clip_id: 'c_abc',
        reference_decision: 'out',
        ball_colour_hint: 'red',
        source_group: 'ind_vs_aus',
      },
      null,
      'tester',
    );
    expect(label.reference_decision).toBe('out');
    expect(label.ball_colour).toBe('red');
    expect(label.source_group).toBe('ind_vs_aus');

    label.lbw = 'not_out_unspecified';
    expect(label.lbw).toBe('not_out_unspecified');
    label.lbw = 'not_available';
    expect(label.lbw).toBe('not_available');
  });
});
