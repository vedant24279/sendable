/**
 * UI helpers, handle hit-testing, point selection cycling, and pitch readout formatters
 * for calibration mode.
 */

import { CalibrationPointName, CALIB_POINT_NAMES } from './calibConstants';

export const CALIB_HANDLE_COLORS: Record<CalibrationPointName, string> = {
  bat_L: '#06b6d4',      // Cyan
  bat_R: '#3b82f6',      // Blue
  bowl_L: '#10b981',     // Emerald
  bowl_R: '#22c55e',     // Green
  bat_stump: '#f59e0b',  // Amber
  bowl_stump: '#a855f7', // Purple
};

export const CALIB_POINT_LABELS: Record<CalibrationPointName, string> = {
  bat_L: 'Bat Crease Left',
  bat_R: 'Bat Crease Right',
  bowl_L: 'Bowl Crease Left',
  bowl_R: 'Bowl Crease Right',
  bat_stump: 'Bat Middle Stump',
  bowl_stump: 'Bowl Middle Stump',
};

/**
 * Hit-test calibration point handles on the canvas.
 * Returns the nearest handle within radiusScreenPx, or null.
 */
export function hitTestCalibPoint(
  points: Partial<Record<CalibrationPointName, [number, number]>>,
  imgX: number,
  imgY: number,
  scale: number,
  radiusScreenPx = 10
): CalibrationPointName | null {
  let bestName: CalibrationPointName | null = null;
  let bestDist = Infinity;

  for (const name of CALIB_POINT_NAMES) {
    const pt = points[name];
    if (!pt) continue;
    const dx = (pt[0] - imgX) * scale;
    const dy = (pt[1] - imgY) * scale;
    const dist = Math.hypot(dx, dy);
    if (dist <= radiusScreenPx && dist < bestDist) {
      bestDist = dist;
      bestName = name;
    }
  }

  return bestName;
}

/**
 * Returns the next missing calibration point in sequence.
 * Starts checking immediately after current (or from beginning if current is null/not set),
 * wrapping around until all points are checked.
 * Returns null if all 6 points are present.
 */
export function nextMissingCalibPoint(
  points: Partial<Record<CalibrationPointName, [number, number]>>,
  current?: CalibrationPointName | null
): CalibrationPointName | null {
  const startIndex = current ? CALIB_POINT_NAMES.indexOf(current) : -1;
  const len = CALIB_POINT_NAMES.length;

  for (let i = 1; i <= len; i++) {
    const idx = (startIndex + i) % len;
    const name = CALIB_POINT_NAMES[idx];
    if (!points[name]) {
      return name;
    }
  }

  return null;
}

/**
 * Format pitch coordinates using exact axis names from constants module.
 */
export function formatPitchPos(pitch_x_m: number, pitch_z_m: number): string {
  const xSign = pitch_x_m >= 0 ? '+' : '';
  const zSign = pitch_z_m >= 0 ? '+' : '';
  return `pitch_x_m: ${xSign}${pitch_x_m.toFixed(2)} m, pitch_z_m: ${zSign}${pitch_z_m.toFixed(2)} m`;
}

/**
 * Cycles to next or previous calibration point name for Tab / Shift+Tab.
 */
export function cycleCalibPoint(
  current: CalibrationPointName | null,
  reverse = false
): CalibrationPointName {
  if (!current) return CALIB_POINT_NAMES[0];
  const idx = CALIB_POINT_NAMES.indexOf(current);
  if (idx === -1) return CALIB_POINT_NAMES[0];
  const step = reverse ? -1 : 1;
  const nextIdx = (idx + step + CALIB_POINT_NAMES.length) % CALIB_POINT_NAMES.length;
  return CALIB_POINT_NAMES[nextIdx];
}
