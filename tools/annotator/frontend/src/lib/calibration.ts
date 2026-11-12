/**
 * Cricket pitch calibration geometry and homography estimation.
 * Pure mathematical algorithms matching tools/annotator/backend/app/calib.py.
 */

import {
  CALIB_POINT_NAMES,
  CORNER_NAMES,
  WORLD_CALIB_POINTS,
  PITCH_LENGTH_M,
  POPPING_IN_FRONT_M,
  BOWL_CREASE_Z_M,
  RETURN_HALF_WIDTH_M,
  CalibrationPointName,
} from './calibConstants';

export interface FitResult {
  H: number[][]; // 3x3 homography: image (px) -> world (m)
  residual_px: number; // RMS pixel reprojection error of stump bases
  H_inv: number[][]; // 3x3 inverse homography: world (m) -> image (px)
}

/**
 * Solve an N x N linear system Ax = b using Gaussian elimination with partial pivoting.
 */
function solveLinearSystem(A_in: number[][], b_in: number[]): number[] {
  const n = b_in.length;
  // Deep copy A and b
  const A = A_in.map((row) => [...row]);
  const b = [...b_in];

  for (let i = 0; i < n; i++) {
    // Find pivot row
    let maxRow = i;
    let maxVal = Math.abs(A[i][i]);
    for (let r = i + 1; r < n; r++) {
      const val = Math.abs(A[r][i]);
      if (val > maxVal) {
        maxVal = val;
        maxRow = r;
      }
    }

    if (maxVal < 1e-14) {
      throw new Error('Degenerate linear system: matrix is singular or close to singular');
    }

    // Swap rows
    if (maxRow !== i) {
      const tempRow = A[i];
      A[i] = A[maxRow];
      A[maxRow] = tempRow;

      const tempB = b[i];
      b[i] = b[maxRow];
      b[maxRow] = tempB;
    }

    // Eliminate below
    for (let r = i + 1; r < n; r++) {
      const factor = A[r][i] / A[i][i];
      A[r][i] = 0;
      for (let c = i + 1; c < n; c++) {
        A[r][c] -= factor * A[i][c];
      }
      b[r] -= factor * b[i];
    }
  }

  // Back-substitution
  const x = new Array<number>(n).fill(0);
  for (let i = n - 1; i >= 0; i--) {
    let sum = b[i];
    for (let c = i + 1; c < n; c++) {
      sum -= A[i][c] * x[c];
    }
    x[i] = sum / A[i][i];
  }

  return x;
}

/**
 * Analytic 3x3 matrix inverse using adjugate matrix and determinant.
 * Normalized such that H_inv[2][2] == 1.0.
 */
export function invertHomography(H: number[][]): number[][] {
  const a = H[0][0], b = H[0][1], c = H[0][2];
  const d = H[1][0], e = H[1][1], f = H[1][2];
  const g = H[2][0], h = H[2][1], i = H[2][2];

  const A = e * i - f * h;
  const B = f * g - d * i;
  const C = d * h - e * g;

  const det = a * A + b * B + c * C;
  if (Math.abs(det) < 1e-14) {
    throw new Error('Degenerate homography matrix (determinant close to zero)');
  }

  const inv = [
    [A / det, (c * h - b * i) / det, (b * f - c * e) / det],
    [B / det, (a * i - c * g) / det, (c * d - a * f) / det],
    [C / det, (b * g - a * h) / det, (a * e - b * d) / det],
  ];

  if (Math.abs(inv[2][2]) > 1e-14) {
    const scale = inv[2][2];
    for (let r = 0; r < 3; r++) {
      for (let cl = 0; cl < 3; cl++) {
        inv[r][cl] /= scale;
      }
    }
  }

  return inv;
}

/**
 * Fit an exact 4-point homography mapping image pixels (x, y) to ground world coordinates (X, Z).
 * Computes residual_px as the RMS reprojection error of the two stump positions (bat_stump, bowl_stump).
 */
export function fitHomography(points: Record<string, [number, number]>): FitResult {
  for (const name of CALIB_POINT_NAMES) {
    if (!points[name]) {
      throw new Error(`Missing required calibration point: ${name}`);
    }
  }

  const corners: readonly CalibrationPointName[] = ['bat_L', 'bat_R', 'bowl_L', 'bowl_R'];
  const A: number[][] = [];
  const b: number[] = [];

  for (let idx = 0; idx < corners.length; idx++) {
    const name = corners[idx];
    const [px, py] = points[name];
    const [wX, wZ] = WORLD_CALIB_POINTS[name];

    // Row 1: X correspondence
    A.push([px, py, 1.0, 0.0, 0.0, 0.0, -wX * px, -wX * py]);
    b.push(wX);

    // Row 2: Z correspondence
    A.push([0.0, 0.0, 0.0, px, py, 1.0, -wZ * px, -wZ * py]);
    b.push(wZ);
  }

  const sol = solveLinearSystem(A, b);

  const H = [
    [sol[0], sol[1], sol[2]],
    [sol[3], sol[4], sol[5]],
    [sol[6], sol[7], 1.0],
  ];

  const H_inv = invertHomography(H);

  // Project world stump positions to image space
  const [batWorldX, batWorldZ] = WORLD_CALIB_POINTS.bat_stump;
  const [bowlWorldX, bowlWorldZ] = WORLD_CALIB_POINTS.bowl_stump;

  const [predBatX, predBatY] = worldToPixel(H, batWorldX, batWorldZ, H_inv);
  const [predBowlX, predBowlY] = worldToPixel(H, bowlWorldX, bowlWorldZ, H_inv);

  const [clickedBatX, clickedBatY] = points.bat_stump;
  const [clickedBowlX, clickedBowlY] = points.bowl_stump;

  const dBatSq = (clickedBatX - predBatX) ** 2 + (clickedBatY - predBatY) ** 2;
  const dBowlSq = (clickedBowlX - predBowlX) ** 2 + (clickedBowlY - predBowlY) ** 2;

  const residual_px = Math.sqrt((dBatSq + dBowlSq) / 2.0);

  return { H, residual_px, H_inv };
}

/**
 * Map image pixel (x, y) to world plane coordinates (pitch_x_m, pitch_z_m).
 */
export function pixelToWorld(H: number[][], x: number, y: number): [number, number] {
  const w = H[2][0] * x + H[2][1] * y + H[2][2];
  if (Math.abs(w) < 1e-12) {
    throw new Error('Point maps to infinity under homography');
  }
  const X = (H[0][0] * x + H[0][1] * y + H[0][2]) / w;
  const Z = (H[1][0] * x + H[1][1] * y + H[1][2]) / w;
  return [X, Z];
}

/**
 * Map world coordinates (pitch_x_m, pitch_z_m) to image pixel coordinates (x, y).
 */
export function worldToPixel(
  H: number[][],
  X: number,
  Z: number,
  H_inv?: number[][]
): [number, number] {
  const inv = H_inv ?? invertHomography(H);
  const w = inv[2][0] * X + inv[2][1] * Z + inv[2][2];
  if (Math.abs(w) < 1e-12) {
    throw new Error('World point maps to infinity in image space');
  }
  const x = (inv[0][0] * X + inv[0][1] * Z + inv[0][2]) / w;
  const y = (inv[1][0] * X + inv[1][1] * Z + inv[1][2]) / w;
  return [x, y];
}

/**
 * Generate image-pixel line segments for the full pitch rectangle and grid lines every spacing_m.
 * Segments are returned as pairs of [[x1, y1], [x2, y2]] in pixel coordinates.
 */
export function pitchGridSegments(
  H: number[][],
  spacingM = 1.0
): Array<[[number, number], [number, number]]> {
  const H_inv = invertHomography(H);
  const segments: Array<[[number, number], [number, number]]> = [];

  const hw = RETURN_HALF_WIDTH_M;
  const lenM = PITCH_LENGTH_M;

  const addSeg = (wX1: number, wZ1: number, wX2: number, wZ2: number) => {
    const p1 = worldToPixel(H, wX1, wZ1, H_inv);
    const p2 = worldToPixel(H, wX2, wZ2, H_inv);
    segments.push([p1, p2]);
  };

  // 1. Pitch perimeter rectangle
  addSeg(-hw, 0.0, +hw, 0.0); // Striker stump line
  addSeg(+hw, 0.0, +hw, lenM); // Right return crease
  addSeg(+hw, lenM, -hw, lenM); // Bowler stump line
  addSeg(-hw, lenM, -hw, 0.0); // Left return crease

  // 2. Popping crease lines
  addSeg(-hw, POPPING_IN_FRONT_M, +hw, POPPING_IN_FRONT_M);
  addSeg(-hw, BOWL_CREASE_Z_M, +hw, BOWL_CREASE_Z_M);

  // 3. Transverse grid lines across pitch
  let z = spacingM;
  while (z < lenM) {
    if (Math.abs(z - POPPING_IN_FRONT_M) > 0.1 && Math.abs(z - BOWL_CREASE_Z_M) > 0.1) {
      addSeg(-hw, z, +hw, z);
    }
    z += spacingM;
  }

  // 4. Centerline along pitch
  addSeg(0.0, 0.0, 0.0, lenM);

  return segments;
}

export function classifySource(
  points: Record<string, [number, number]>,
  systemPoints?:
    | Record<string, [number, number]>
    | Array<{ name: string; x: number; y: number }>
    | null
): 'system_verified' | 'system_adjusted' | 'manual' {
  if (!systemPoints) return 'manual';

  const sysMap: Record<string, [number, number]> = {};
  if (Array.isArray(systemPoints)) {
    for (const item of systemPoints) {
      sysMap[item.name] = [item.x, item.y];
    }
  } else {
    for (const [k, v] of Object.entries(systemPoints)) {
      if (Array.isArray(v) && v.length >= 2) {
        sysMap[k] = [v[0], v[1]];
      } else if (typeof v === 'object' && v !== null && 'x' in v && 'y' in v) {
        sysMap[k] = [(v as { x: number; y: number }).x, (v as { x: number; y: number }).y];
      }
    }
  }

  if (Object.keys(sysMap).length < 6) return 'manual';

  for (const name of CALIB_POINT_NAMES) {
    const pt = points[name];
    const sys = sysMap[name];
    if (!pt || !sys) return 'system_adjusted';
    const dist = Math.sqrt((pt[0] - sys[0]) ** 2 + (pt[1] - sys[1]) ** 2);
    if (dist > 0.05) {
      return 'system_adjusted';
    }
  }

  return 'system_verified';
}

export function validateCalibrationGeometry(
  points: Record<string, [number, number]>,
  width?: number,
  height?: number
): string[] {
  const errors: string[] = [];

  // 1. All six points present
  for (const name of CALIB_POINT_NAMES) {
    if (!points[name] || points[name].length < 2) {
      errors.push(`Missing required calibration point: ${name}`);
    }
  }
  if (errors.length > 0) return errors;

  // 2. Coordinate bounds checks
  for (const name of CALIB_POINT_NAMES) {
    const [px, py] = points[name];
    if (width != null && (px < 0.0 || px > width)) {
      errors.push(`${name}.x (${px}) out of bounds [0, ${width}]`);
    }
    if (height != null && (py < 0.0 || py > height)) {
      errors.push(`${name}.y (${py}) out of bounds [0, ${height}]`);
    }
  }
  if (errors.length > 0) return errors;

  const [batLX] = points.bat_L;
  const [batRX] = points.bat_R;
  const [bowlLX] = points.bowl_L;
  const [bowlRX] = points.bowl_R;
  const [batStumpX] = points.bat_stump;
  const [bowlStumpX] = points.bowl_stump;

  // 3. Horizontal ordering
  if (batLX >= batRX) {
    errors.push(`bat_L.x (${batLX}) must be strictly less than bat_R.x (${batRX})`);
  }
  if (bowlLX >= bowlRX) {
    errors.push(`bowl_L.x (${bowlLX}) must be strictly less than bowl_R.x (${bowlRX})`);
  }

  // 4. Stump horizontal position between left and right points
  if (batStumpX < batLX || batStumpX > batRX) {
    errors.push(`bat_stump.x (${batStumpX}) must be between bat_L.x (${batLX}) and bat_R.x (${batRX})`);
  }
  if (bowlStumpX < bowlLX || bowlStumpX > bowlRX) {
    errors.push(`bowl_stump.x (${bowlStumpX}) must be between bowl_L.x (${bowlLX}) and bowl_R.x (${bowlRX})`);
  }

  // 5. Convex non-degenerate quadrilateral and area > 2% of frame area
  const cornerPts = CORNER_NAMES.map((name) => points[name]);

  let shoelace = 0.0;
  for (let i = 0; i < 4; i++) {
    const [x1, y1] = cornerPts[i];
    const [x2, y2] = cornerPts[(i + 1) % 4];
    shoelace += x1 * y2 - x2 * y1;
  }
  const quadArea = 0.5 * Math.abs(shoelace);

  if (width != null && height != null) {
    const minArea = 0.02 * width * height;
    if (quadArea <= minArea) {
      errors.push(
        `Calibration quadrilateral area (${quadArea.toFixed(1)} px^2) must be > 2% of frame area (${minArea.toFixed(1)} px^2)`
      );
    }
  }

  // Convexity check: edge cross products must have same sign
  const crosses: number[] = [];
  for (let i = 0; i < 4; i++) {
    const p0 = cornerPts[i];
    const p1 = cornerPts[(i + 1) % 4];
    const p2 = cornerPts[(i + 2) % 4];
    const v1 = [p1[0] - p0[0], p1[1] - p0[1]];
    const v2 = [p2[0] - p1[0], p2[1] - p1[1]];
    const cp = v1[0] * v2[1] - v1[1] * v2[0];
    crosses.push(cp);
  }

  const isConvex = crosses.every((c) => c > 1e-4) || crosses.every((c) => c < -1e-4);
  if (!isConvex) {
    errors.push(
      'Calibration corner points (bat_L, bat_R, bowl_R, bowl_L) must form a strictly convex quadrilateral'
    );
  }

  return errors;
}
