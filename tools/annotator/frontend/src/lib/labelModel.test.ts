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

    // 1. Accept system calibration
    const accepted = acceptSystemCalibration(base, systemPoints);
    expect(accepted.calibration_gt).toBeDefined();
    expect(accepted.calibration_gt?.source).toBe('system_verified');
    expect(accepted.calibration_gt?.points.bat_L).toEqual([778.0, 434.0]);
    expect(accepted.calibration_gt?.residual_px).toBeCloseTo(12.74, 1);

    // 2. Set one point (system_adjusted, rounds to 1 decimal)
    const modified = setCalibrationPoint(accepted, 'bat_L', 779.456, 435.123, systemPoints);
    expect(modified.calibration_gt?.points.bat_L).toEqual([779.5, 435.1]);
    expect(modified.calibration_gt?.source).toBe('system_adjusted');

    // 3. Reset calibration back to system
    const reset = resetCalibrationToSystem(modified, systemPoints);
    expect(reset.calibration_gt?.points.bat_L).toEqual([778.0, 434.0]);
    expect(reset.calibration_gt?.source).toBe('system_verified');

    // 4. Clear calibration
    const cleared = clearCalibration(reset);
    expect(cleared.calibration_gt).toBeNull();
  });
});
