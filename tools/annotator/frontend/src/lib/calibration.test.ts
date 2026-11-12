import { describe, it, expect } from 'vitest';
import {
  fitHomography,
  pixelToWorld,
  worldToPixel,
  classifySource,
  validateCalibrationGeometry,
  pitchGridSegments,
} from './calibration';
import { CALIB_WARN_PX } from './calibConstants';
import golden from '../../../fixtures/calibration_golden.json';

describe('calibration geometry & parity', () => {
  it('matches golden fixture parity within tolerances (1e-6 m, 1e-3 px)', () => {
    const pts = golden.points as unknown as Record<string, [number, number]>;
    const res = fitHomography(pts);

    // 1. Residual parity (default calculates over both stumps)
    expect(res.residual_px).not.toBeNull();
    expect(Math.abs(res.residual_px! - golden.expected_residual_px)).toBeLessThan(1e-3);

    // 1b. stumpConfirmed parity: both, bat-only, bowl-only, none
    const resBoth = fitHomography(pts, { bat_stump: true, bowl_stump: true });
    expect(resBoth.residual_px).not.toBeNull();
    expect(Math.abs(resBoth.residual_px! - golden.expected_residual_px)).toBeLessThan(1e-3);

    const resBatOnly = fitHomography(pts, { bat_stump: true, bowl_stump: false });
    expect(resBatOnly.residual_px).not.toBeNull();
    expect(Math.abs(resBatOnly.residual_px! - golden.expected_residual_px_bat_only)).toBeLessThan(1e-3);

    const resBowlOnly = fitHomography(pts, { bat_stump: false, bowl_stump: true });
    expect(resBowlOnly.residual_px).not.toBeNull();
    expect(Math.abs(resBowlOnly.residual_px! - golden.expected_residual_px_bowl_only)).toBeLessThan(1e-3);

    const resNone = fitHomography(pts, { bat_stump: false, bowl_stump: false });
    expect(resNone.residual_px).toBeNull();

    // 2. Homography matrix parity
    for (let r = 0; r < 3; r++) {
      for (let c = 0; c < 3; c++) {
        expect(Math.abs(res.H[r][c] - golden.expected_H[r][c])).toBeLessThan(1e-6);
        expect(Math.abs(res.H_inv[r][c] - golden.expected_H_inv[r][c])).toBeLessThan(1e-6);
      }
    }

    // 3. Pixel -> World parity
    for (const item of golden.test_pixels) {
      const [px, py] = item.pixel as [number, number];
      const [wX, wZ] = pixelToWorld(res.H, px, py);
      expect(Math.abs(wX - item.expected_world[0])).toBeLessThan(1e-6);
      expect(Math.abs(wZ - item.expected_world[1])).toBeLessThan(1e-6);
    }

    // 4. World -> Pixel parity
    for (const item of golden.test_world) {
      const [wX, wZ] = item.world as [number, number];
      const [px, py] = worldToPixel(res.H, wX, wZ);
      expect(Math.abs(px - item.expected_pixel[0])).toBeLessThan(1e-3);
      expect(Math.abs(py - item.expected_pixel[1])).toBeLessThan(1e-3);
    }
  });

  it('moving bat_stump by 6 px from zero residual gives residual > CALIB_WARN_PX', () => {
    // Generate a perfectly aligned calibration (zero residual)
    const pts: Record<string, [number, number]> = {
      bat_L: [778.0, 434.0],
      bat_R: [1083.0, 430.0],
      bowl_L: [739.0, 764.0],
      bowl_R: [1115.0, 768.0],
      bat_stump: [0, 0],
      bowl_stump: [0, 0],
    };

    const initial = fitHomography(pts);
    const perfectBat = worldToPixel(initial.H, 0.0, 0.0);
    const perfectBowl = worldToPixel(initial.H, 0.0, 20.12);

    pts.bat_stump = [perfectBat[0], perfectBat[1]];
    pts.bowl_stump = [perfectBowl[0], perfectBowl[1]];

    const zeroRes = fitHomography(pts);
    expect(zeroRes.residual_px).toBeLessThan(1e-6);

    // Shift bat_stump by exactly 6 pixels
    pts.bat_stump = [perfectBat[0] + 6.0, perfectBat[1]];
    const shifted = fitHomography(pts);

    // sqrt(6^2 / 2) = sqrt(18) = 4.2426 > 4.0
    expect(shifted.residual_px).toBeGreaterThan(CALIB_WARN_PX);
    expect(shifted.residual_px).toBeCloseTo(Math.sqrt(18), 3);
  });

  it('classifies calibration source correctly', () => {
    const pts: Record<string, [number, number]> = {
      bat_L: [778.0, 434.0],
      bat_R: [1083.0, 430.0],
      bowl_L: [739.0, 764.0],
      bowl_R: [1115.0, 768.0],
      bat_stump: [936.0, 426.0],
      bowl_stump: [922.0, 784.0],
    };

    // Manual when systemPoints is null or empty
    expect(classifySource(pts, null)).toBe('manual');
    expect(classifySource(pts, {})).toBe('manual');

    // System verified when all points within 0.05 px
    const sysVerified = { ...pts };
    expect(classifySource(pts, sysVerified)).toBe('system_verified');

    // System verified even if stumps differ (source classification only compares 4 corners)
    const stumpDiffer = { ...pts, bat_stump: [950.0, 440.0] as [number, number] };
    expect(classifySource(stumpDiffer, pts)).toBe('system_verified');

    // System adjusted when any corner differs > 0.05 px
    const sysAdjusted = { ...pts, bat_L: [778.1, 434.0] as [number, number] };
    expect(classifySource(pts, sysAdjusted)).toBe('system_adjusted');
  });

  it('validates calibration geometry: convexity, area, horizontal ordering, and bounds', () => {
    const validPts: Record<string, [number, number]> = {
      bat_L: [778.0, 434.0],
      bat_R: [1083.0, 430.0],
      bowl_L: [739.0, 764.0],
      bowl_R: [1115.0, 768.0],
      bat_stump: [936.0, 426.0],
      bowl_stump: [922.0, 784.0],
    };

    // Valid case
    expect(validateCalibrationGeometry(validPts, 1920, 1080)).toEqual([]);

    // Missing point
    const missing = { ...validPts };
    delete (missing as any).bowl_stump;
    expect(validateCalibrationGeometry(missing, 1920, 1080).length).toBeGreaterThan(0);

    // Coordinate out of bounds
    const oob = { ...validPts, bat_L: [-5, 434] as [number, number] };
    expect(validateCalibrationGeometry(oob, 1920, 1080).some((e) => e.includes('out of bounds'))).toBe(true);

    // Horizontal ordering violation (bat_L.x >= bat_R.x)
    const badOrder = { ...validPts, bat_L: [1100, 434] as [number, number] };
    expect(validateCalibrationGeometry(badOrder, 1920, 1080).some((e) => e.includes('strictly less than'))).toBe(true);

    // Stump outside crease range
    const badStump = { ...validPts, bat_stump: [750, 426] as [number, number] };
    expect(validateCalibrationGeometry(badStump, 1920, 1080).some((e) => e.includes('must be between'))).toBe(true);

    // Non-convex / self-intersecting quadrilateral
    const nonConvex = {
      ...validPts,
      bowl_L: [1150, 764] as [number, number],
      bowl_R: [720, 768] as [number, number], // inverted corners causing self-intersection
    };
    expect(validateCalibrationGeometry(nonConvex, 1920, 1080).some((e) => e.includes('convex'))).toBe(true);

    // Area too small (< 2% frame area: 1920*1080*0.02 = 41472 px^2)
    const tiny = {
      bat_L: [100, 100] as [number, number],
      bat_R: [110, 100] as [number, number],
      bowl_R: [110, 110] as [number, number],
      bowl_L: [100, 110] as [number, number],
      bat_stump: [105, 100] as [number, number],
      bowl_stump: [105, 110] as [number, number],
    };
    expect(validateCalibrationGeometry(tiny, 1920, 1080).some((e) => e.includes('must be > 2% of frame area'))).toBe(true);
  });

  it('generates pitch grid segments', () => {
    const pts = golden.points as unknown as Record<string, [number, number]>;
    const res = fitHomography(pts);
    const segments = pitchGridSegments(res.H, 1.0);

    expect(segments.length).toBeGreaterThan(20);
    for (const [p1, p2] of segments) {
      expect(p1.length).toBe(2);
      expect(p2.length).toBe(2);
      expect(Number.isFinite(p1[0])).toBe(true);
      expect(Number.isFinite(p1[1])).toBe(true);
      expect(Number.isFinite(p2[0])).toBe(true);
      expect(Number.isFinite(p2[1])).toBe(true);
    }
  });
});
