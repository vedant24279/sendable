import { describe, it, expect } from 'vitest';
import {
  hitTestCalibPoint,
  nextMissingCalibPoint,
  formatPitchPos,
  cycleCalibPoint,
} from './calibUi';
import { CalibrationPointName } from './calibConstants';

describe('calibUi helpers', () => {
  describe('hitTestCalibPoint', () => {
    const points: Partial<Record<CalibrationPointName, [number, number]>> = {
      bat_L: [778.0, 434.0],
      bat_R: [1083.0, 430.0],
      bat_stump: [936.0, 426.0],
    };

    it('returns exact match within radiusScreenPx', () => {
      // Scale 1.0, exact pixel
      expect(hitTestCalibPoint(points, 778.0, 434.0, 1.0, 10)).toBe('bat_L');
      expect(hitTestCalibPoint(points, 1083.0, 430.0, 1.0, 10)).toBe('bat_R');
    });

    it('returns null when outside radiusScreenPx', () => {
      // 15 px away with radius 10 at scale 1.0
      expect(hitTestCalibPoint(points, 778.0 + 15, 434.0, 1.0, 10)).toBeNull();
    });

    it('scales screen distance properly with zoom level', () => {
      // At zoom 2.0, an image offset of 4 px equals 8 screen px <= 10 screen px
      expect(hitTestCalibPoint(points, 778.0 + 4, 434.0, 2.0, 10)).toBe('bat_L');
      // At zoom 2.0, an image offset of 6 px equals 12 screen px > 10 screen px
      expect(hitTestCalibPoint(points, 778.0 + 6, 434.0, 2.0, 10)).toBeNull();
    });

    it('picks the nearest point when multiple are within radius', () => {
      const closePoints: Partial<Record<CalibrationPointName, [number, number]>> = {
        bat_L: [100.0, 100.0],
        bat_R: [105.0, 100.0],
      };
      // Cursor at 101.0, 100.0 is 1px from bat_L and 4px from bat_R
      expect(hitTestCalibPoint(closePoints, 101.0, 100.0, 1.0, 20)).toBe('bat_L');
      // Cursor at 104.0, 100.0 is 4px from bat_L and 1px from bat_R
      expect(hitTestCalibPoint(closePoints, 104.0, 100.0, 1.0, 20)).toBe('bat_R');
    });
  });

  describe('nextMissingCalibPoint', () => {
    it('returns first point if points map is empty', () => {
      expect(nextMissingCalibPoint({})).toBe('bat_L');
    });

    it('advances to next missing point after current', () => {
      const partial: Partial<Record<CalibrationPointName, [number, number]>> = {
        bat_L: [100, 100],
      };
      // After bat_L, bat_R is missing
      expect(nextMissingCalibPoint(partial, 'bat_L')).toBe('bat_R');
    });

    it('skips existing points and wraps around', () => {
      const partial: Partial<Record<CalibrationPointName, [number, number]>> = {
        bat_L: [100, 100],
        bat_R: [200, 100],
        bowl_L: [100, 300],
        bowl_R: [200, 300],
        bowl_stump: [150, 310],
      };
      // Only bat_stump is missing. From bowl_stump, it wraps around to bat_stump
      expect(nextMissingCalibPoint(partial, 'bowl_stump')).toBe('bat_stump');
    });

    it('returns null when all 6 points are present', () => {
      const full: Partial<Record<CalibrationPointName, [number, number]>> = {
        bat_L: [100, 100],
        bat_R: [200, 100],
        bowl_L: [100, 300],
        bowl_R: [200, 300],
        bat_stump: [150, 90],
        bowl_stump: [150, 310],
      };
      expect(nextMissingCalibPoint(full, 'bat_L')).toBeNull();
      expect(nextMissingCalibPoint(full, 'bowl_stump')).toBeNull();
    });
  });

  describe('formatPitchPos', () => {
    it('formats coordinates with exact axis names, signs, and 2 decimal places', () => {
      expect(formatPitchPos(0.0614, 0.8315)).toBe('pitch_x_m: +0.06 m, pitch_z_m: +0.83 m');
      expect(formatPitchPos(-1.32, 18.9)).toBe('pitch_x_m: -1.32 m, pitch_z_m: +18.90 m');
      expect(formatPitchPos(0.0, 0.0)).toBe('pitch_x_m: +0.00 m, pitch_z_m: +0.00 m');
      expect(formatPitchPos(-0.015, -0.452)).toBe('pitch_x_m: -0.01 m, pitch_z_m: -0.45 m');
    });
  });

  describe('cycleCalibPoint', () => {
    it('cycles forward in sequence on Tab', () => {
      expect(cycleCalibPoint('bat_L', false)).toBe('bat_R');
      expect(cycleCalibPoint('bat_R', false)).toBe('bowl_L');
      expect(cycleCalibPoint('bowl_L', false)).toBe('bowl_R');
      expect(cycleCalibPoint('bowl_R', false)).toBe('bat_stump');
      expect(cycleCalibPoint('bat_stump', false)).toBe('bowl_stump');
      expect(cycleCalibPoint('bowl_stump', false)).toBe('bat_L');
    });

    it('cycles backward in sequence on Shift+Tab', () => {
      expect(cycleCalibPoint('bat_L', true)).toBe('bowl_stump');
      expect(cycleCalibPoint('bowl_stump', true)).toBe('bat_stump');
      expect(cycleCalibPoint('bat_stump', true)).toBe('bowl_R');
    });
  });
});
