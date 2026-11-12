/**
 * Constants and world coordinate definitions for cricket pitch calibration.
 *
 * Source of regulation dimensions:
 *   backend/pipeline/reconstruct3d/world_points.py
 *   (Derived from official Laws of Cricket: Law 6 - 22 yards between stump lines,
 *    popping creases 1.22 m in front of each stump line, return crease half-width 1.32 m).
 *
 * Coordinate Frame:
 *   Origin: Middle stump base at STRIKER'S (batter's) end: (0.0, 0.0)
 *   pitch_x_m: Perpendicular across pitch, positive toward IMAGE-RIGHT
 *              (left return crease at -1.32 m, right return crease at +1.32 m).
 *   pitch_z_m: Along pitch length, positive toward the bowler (0.0 at striker's stump line).
 */

export const PITCH_LENGTH_M = 20.12;
export const POPPING_IN_FRONT_M = 1.22;
export const RETURN_HALF_WIDTH_M = 1.32;

// Bowler-end crease distance from striker's stump line (derived: 20.12 - 1.22 = 18.90 m)
export const BOWL_CREASE_Z_M = PITCH_LENGTH_M - POPPING_IN_FRONT_M;

export type CalibrationPointName =
  | 'bat_L'
  | 'bat_R'
  | 'bowl_L'
  | 'bowl_R'
  | 'bat_stump'
  | 'bowl_stump';

export const CALIB_POINT_NAMES: readonly CalibrationPointName[] = [
  'bat_L',
  'bat_R',
  'bowl_L',
  'bowl_R',
  'bat_stump',
  'bowl_stump',
] as const;

export const CORNER_NAMES: readonly CalibrationPointName[] = [
  'bat_L',
  'bat_R',
  'bowl_R',
  'bowl_L',
] as const;

export const WORLD_CALIB_POINTS: Readonly<Record<CalibrationPointName, [number, number]>> = {
  bat_stump: [0.0, 0.0],
  bat_L: [-RETURN_HALF_WIDTH_M, POPPING_IN_FRONT_M],
  bat_R: [+RETURN_HALF_WIDTH_M, POPPING_IN_FRONT_M],
  bowl_L: [-RETURN_HALF_WIDTH_M, BOWL_CREASE_Z_M],
  bowl_R: [+RETURN_HALF_WIDTH_M, BOWL_CREASE_Z_M],
  bowl_stump: [0.0, PITCH_LENGTH_M],
};

/**
 * Thresholds for stump residual error in pixels.
 * NOTE: Because stump points are extrapolated 1.22 m beyond the creases,
 * perspective and calibration errors are amplified at them; keep CALIB_WARN_PX = 4
 * and CALIB_ERROR_PX = 12 as PROVISIONAL.
 */
export const CALIB_WARN_PX = 4.0;
export const CALIB_ERROR_PX = 12.0;
