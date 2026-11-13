/**
 * Label data model and pure transformation functions for the Cricket Delivery Annotator.
 * Mirrors tools/annotator/backend/app/schema.py exactly.
 */

import { PrefillData } from '../api';
import {
  CalibrationPointName,
  CALIB_POINT_NAMES,
  WORLD_CALIB_POINTS,
} from './calibConstants';
import { fitHomography, classifySource, worldToPixel } from './calibration';

export type BallColour = 'white' | 'red' | 'pink';
export type BatterHand = 'right' | 'left';
export type BowlerType = 'pace' | 'spin';
export type Lighting = 'bright' | 'overcast' | 'low';
export type ImpactType = 'bat' | 'pad' | 'stumps' | 'none';
export type LBWDecision =
  | 'out'
  | 'not_out_pitched_leg'
  | 'not_out_impact_outside'
  | 'not_out_missing'
  | 'umpires_call'
  | 'not_out_unspecified'
  | 'not_available';
export type ReferenceDecision = 'out' | 'not_out';
export type LabelFlag = 'ball_not_visible' | 'camera_moved' | 'bad_calibration' | 'unclear';
export type LabelStatus = 'draft' | 'final' | 'flagged';
export type LabelMode = 'assisted' | 'blind';
export type SplitType = 'dev' | 'final';
export type CalibrationSource = 'system_verified' | 'system_adjusted' | 'manual';

export interface Point {
  frame: number;
  x: number;
  y: number;
}

export interface ImpactPoint {
  type: ImpactType;
  frame?: number | null;
  x?: number | null;
  y?: number | null;
}

export interface StumpConfirmed {
  bat_stump: boolean;
  bowl_stump: boolean;
}

export interface CalibrationGT {
  points: Record<CalibrationPointName, [number, number]>;
  source: CalibrationSource;
  residual_px: number | null;
  stump_confirmed?: StumpConfirmed;
  updated_at: string;
}

export interface Label {
  schema_version: number;
  clip_id: string;
  split: SplitType | null;
  annotator: string;
  mode: LabelMode;
  status: LabelStatus;
  created_at: string;
  updated_at: string;
  ball_colour: BallColour | null;
  batter_hand: BatterHand | null;
  bowler_type: BowlerType | null;
  lighting: Lighting | null;
  release: Point | null;
  bounce: Point | null;
  impact: ImpactPoint | null;
  last_visible_frame: number | null;
  lbw: LBWDecision | null;
  reference_decision?: ReferenceDecision | null;
  source_group?: string | null;
  calibration_gt: CalibrationGT | null;
  flags: LabelFlag[];
  notes: string;
}

export interface ClipMetaInput {
  clip_id: string;
  split?: SplitType | null;
  frame_count?: number;
  width?: number;
  height?: number;
  fps?: number;
  ball_type?: string | null;
  ball_colour_hint?: string | null;
  reference_decision?: ReferenceDecision | null;
  source_group?: string | null;
}

export interface EditContext {
  ghostVisible: boolean;
}

/**
 * Rounds coordinate to 1 decimal place.
 */
export function round1(val: number): number {
  return Math.round(val * 10) / 10;
}

/**
 * Computes next mode. Once mode is "assisted" or ghost was visible, it permanently remains "assisted".
 */
function nextMode(currentMode: LabelMode, ctx?: EditContext): LabelMode {
  if (currentMode === 'assisted') return 'assisted';
  if (ctx?.ghostVisible) return 'assisted';
  return 'blind';
}

/**
 * Creates an empty initial Label for a clip.
 * Ball colour is populated from prefill ball_type if it is "white"|"red"|"pink", else null.
 * All events start as null; status is "draft", mode is "blind".
 */
export function emptyLabel(
  meta: ClipMetaInput,
  prefill: (PrefillData & { ball_type?: string | null }) | null,
  annotator: string
): Label {
  const prefillBallType =
    (prefill as { ball_type?: string | null } | null)?.ball_type ??
    meta.ball_type ??
    meta.ball_colour_hint;
  let ballColour: BallColour | null = null;
  if (
    prefillBallType === 'white' ||
    prefillBallType === 'red' ||
    prefillBallType === 'pink'
  ) {
    ballColour = prefillBallType;
  }

  const now = new Date().toISOString();

  return {
    schema_version: 1,
    clip_id: meta.clip_id,
    split: meta.split ?? null,
    annotator,
    mode: 'blind',
    status: 'draft',
    created_at: now,
    updated_at: now,
    ball_colour: ballColour,
    batter_hand: null,
    bowler_type: null,
    lighting: null,
    release: null,
    bounce: null,
    impact: null,
    last_visible_frame: null,
    lbw: null,
    reference_decision: meta.reference_decision ?? null,
    source_group: meta.source_group ?? null,
    calibration_gt: null,
    flags: [],
    notes: '',
  };
}

/**
 * Places release, bounce, or impact event coordinates on the label.
 * Coordinates x and y are rounded to 1 decimal place.
 * Placing impact coordinates requires an impact type first (otherwise throws an Error).
 * Mode becomes "assisted" permanently if ghostVisible is true.
 */
export function placeEvent(
  label: Label,
  kind: 'release' | 'bounce' | 'impact',
  frame: number,
  x: number,
  y: number,
  ctx: EditContext
): Label {
  const roundedPt: Point = {
    frame: Math.round(frame),
    x: round1(x),
    y: round1(y),
  };

  const mode = nextMode(label.mode, ctx);
  const now = new Date().toISOString();

  if (kind === 'release') {
    return {
      ...label,
      release: roundedPt,
      mode,
      updated_at: now,
    };
  }

  if (kind === 'bounce') {
    return {
      ...label,
      bounce: roundedPt,
      mode,
      updated_at: now,
    };
  }

  if (kind === 'impact') {
    if (!label.impact || !label.impact.type) {
      throw new Error("Cannot place impact coordinates without an impact type selected first.");
    }
    if (label.impact.type === 'none') {
      throw new Error("Cannot place impact coordinates when impact type is 'none'.");
    }

    return {
      ...label,
      impact: {
        ...label.impact,
        frame: roundedPt.frame,
        x: roundedPt.x,
        y: roundedPt.y,
      },
      mode,
      updated_at: now,
    };
  }

  return label;
}

/**
 * Sets the impact type.
 * If type is "none", sets impact frame, x, and y to null.
 * Changing impact type away from "pad" sets lbw to null.
 */
export function setImpactType(
  label: Label,
  type: ImpactType,
  ctx?: EditContext
): Label {
  const mode = nextMode(label.mode, ctx);
  const now = new Date().toISOString();

  let nextLbw = label.lbw;
  if (label.impact?.type === 'pad' && type !== 'pad') {
    nextLbw = null;
  }

  let nextImpact: ImpactPoint;
  if (type === 'none') {
    nextImpact = {
      type: 'none',
      frame: null,
      x: null,
      y: null,
    };
  } else {
    nextImpact = {
      type,
      frame: label.impact?.type === 'none' ? null : (label.impact?.frame ?? null),
      x: label.impact?.type === 'none' ? null : (label.impact?.x ?? null),
      y: label.impact?.type === 'none' ? null : (label.impact?.y ?? null),
    };
  }

  return {
    ...label,
    impact: nextImpact,
    lbw: nextLbw,
    mode,
    updated_at: now,
  };
}

/**
 * Sets last visible frame number.
 */
export function setLastVisible(
  label: Label,
  frame: number,
  ctx?: EditContext
): Label {
  return {
    ...label,
    last_visible_frame: Math.round(frame),
    mode: nextMode(label.mode, ctx),
    updated_at: new Date().toISOString(),
  };
}

/**
 * Clears an event or last visible frame.
 */
export function clearEvent(
  label: Label,
  kind: 'release' | 'bounce' | 'impact' | 'last_visible',
  ctx?: EditContext
): Label {
  const mode = nextMode(label.mode, ctx);
  const now = new Date().toISOString();

  if (kind === 'release') {
    return { ...label, release: null, mode, updated_at: now };
  }
  if (kind === 'bounce') {
    return { ...label, bounce: null, mode, updated_at: now };
  }
  if (kind === 'impact') {
    return { ...label, impact: null, lbw: null, mode, updated_at: now };
  }
  if (kind === 'last_visible') {
    return { ...label, last_visible_frame: null, mode, updated_at: now };
  }
  return label;
}

/**
 * Sets metadata field on label.
 */
export function setMeta<K extends keyof Label>(
  label: Label,
  key: K,
  value: Label[K],
  ctx?: EditContext
): Label {
  return {
    ...label,
    [key]: value,
    mode: nextMode(label.mode, ctx),
    updated_at: new Date().toISOString(),
  };
}

/**
 * Sets LBW decision.
 */
export function setLbw(
  label: Label,
  value: LBWDecision | null,
  ctx?: EditContext
): Label {
  return {
    ...label,
    lbw: value,
    mode: nextMode(label.mode, ctx),
    updated_at: new Date().toISOString(),
  };
}

/**
 * Toggles a label flag.
 */
export function toggleFlag(
  label: Label,
  flag: LabelFlag,
  ctx?: EditContext
): Label {
  const exists = label.flags.includes(flag);
  const nextFlags = exists
    ? label.flags.filter((f) => f !== flag)
    : [...label.flags, flag];

  return {
    ...label,
    flags: nextFlags,
    mode: nextMode(label.mode, ctx),
    updated_at: new Date().toISOString(),
  };
}

/**
 * Sets annotator notes.
 */
export function setNotes(
  label: Label,
  text: string,
  ctx?: EditContext
): Label {
  return {
    ...label,
    notes: text,
    mode: nextMode(label.mode, ctx),
    updated_at: new Date().toISOString(),
  };
}

/**
 * Sets delivery split.
 */
export function setSplit(
  label: Label,
  split: SplitType | null,
  ctx?: EditContext
): Label {
  return {
    ...label,
    split,
    mode: nextMode(label.mode, ctx),
    updated_at: new Date().toISOString(),
  };
}

/**
 * Copies release and bounce events from prefill only; impact remains unchanged.
 * Sets label mode to "assisted".
 */
export function adoptSystemEvents(
  label: Label,
  prefill: PrefillData | null
): Label {
  let release = label.release;
  let bounce = label.bounce;

  if (prefill?.events?.release) {
    release = {
      frame: Math.round(prefill.events.release.frame),
      x: round1(prefill.events.release.x),
      y: round1(prefill.events.release.y),
    };
  }

  if (prefill?.events?.bounce) {
    bounce = {
      frame: Math.round(prefill.events.bounce.frame),
      x: round1(prefill.events.bounce.x),
      y: round1(prefill.events.bounce.y),
    };
  }

  return {
    ...label,
    release,
    bounce,
    mode: 'assisted',
    updated_at: new Date().toISOString(),
  };
}

/**
 * Helper to normalize systemPoints into a Record<CalibrationPointName, [number, number]>
 */
function normalizeSystemPoints(
  systemPoints?:
    | Record<string, [number, number]>
    | Array<{ name: string; x: number; y: number }>
    | null
): Record<CalibrationPointName, [number, number]> | null {
  if (!systemPoints) return null;
  const map: Partial<Record<CalibrationPointName, [number, number]>> = {};
  if (Array.isArray(systemPoints)) {
    for (const item of systemPoints) {
      if (item && item.name && typeof item.x === 'number' && typeof item.y === 'number') {
        map[item.name as CalibrationPointName] = [round1(item.x), round1(item.y)];
      }
    }
  } else {
    for (const [k, v] of Object.entries(systemPoints)) {
      if (Array.isArray(v) && v.length >= 2) {
        map[k as CalibrationPointName] = [round1(v[0]), round1(v[1])];
      }
    }
  }
  for (const name of CALIB_POINT_NAMES) {
    if (!map[name]) return null;
  }
  return map as Record<CalibrationPointName, [number, number]>;
}

export function getStumpConfirmed(calibGT?: CalibrationGT | null): StumpConfirmed {
  return {
    bat_stump: Boolean(calibGT?.stump_confirmed?.bat_stump),
    bowl_stump: Boolean(calibGT?.stump_confirmed?.bowl_stump),
  };
}

/**
 * If the 4 corners are present, compute H and recompute any unconfirmed stumps to predicted positions.
 */
export function deriveUnconfirmedStumps(
  points: Record<CalibrationPointName, [number, number]>,
  stumpConfirmed: StumpConfirmed
): Record<CalibrationPointName, [number, number]> {
  const corners: readonly CalibrationPointName[] = ['bat_L', 'bat_R', 'bowl_L', 'bowl_R'];
  if (!corners.every((c) => points[c] && points[c].length === 2)) {
    return points;
  }

  try {
    const fit = fitHomography(points, stumpConfirmed);
    const updated = { ...points };

    if (!stumpConfirmed.bat_stump) {
      const [wX, wZ] = WORLD_CALIB_POINTS.bat_stump;
      const [px, py] = worldToPixel(fit.H, wX, wZ, fit.H_inv);
      updated.bat_stump = [round1(px), round1(py)];
    }

    if (!stumpConfirmed.bowl_stump) {
      const [wX, wZ] = WORLD_CALIB_POINTS.bowl_stump;
      const [px, py] = worldToPixel(fit.H, wX, wZ, fit.H_inv);
      updated.bowl_stump = [round1(px), round1(py)];
    }

    return updated;
  } catch {
    return points;
  }
}

/**
 * Sets one calibration point coordinate, rounding x and y to 1 decimal place.
 * Recomputes source and residual_px.
 * When a corner changes, recomputes unconfirmed stumps.
 * Placing/moving a stump marks it confirmed.
 */
export function setCalibrationPoint(
  label: Label,
  name: CalibrationPointName,
  x: number,
  y: number,
  systemPoints?:
    | Record<string, [number, number]>
    | Array<{ name: string; x: number; y: number }>
    | null,
  ctx?: EditContext
): Label {
  const normSys = normalizeSystemPoints(systemPoints);
  const existingPoints =
    label.calibration_gt?.points ??
    normSys ??
    ({} as Record<CalibrationPointName, [number, number]>);

  const isStump = name === 'bat_stump' || name === 'bowl_stump';
  const existingConfirmed = getStumpConfirmed(label.calibration_gt);
  const updatedConfirmed: StumpConfirmed = isStump
    ? { ...existingConfirmed, [name]: true }
    : existingConfirmed;

  let updatedPoints: Record<CalibrationPointName, [number, number]> = {
    ...existingPoints,
    [name]: [round1(x), round1(y)],
  };

  if (!isStump) {
    updatedPoints = deriveUnconfirmedStumps(updatedPoints, updatedConfirmed);
  }

  let residual_px: number | null = null;
  const allPresent = CALIB_POINT_NAMES.every(
    (k) => updatedPoints[k] && updatedPoints[k].length === 2
  );
  if (allPresent) {
    try {
      const fit = fitHomography(updatedPoints, updatedConfirmed);
      residual_px = fit.residual_px;
    } catch {
      residual_px = null;
    }
  }

  const source = classifySource(updatedPoints, systemPoints);
  const now = new Date().toISOString();

  return {
    ...label,
    calibration_gt: {
      points: updatedPoints,
      source,
      residual_px,
      stump_confirmed: updatedConfirmed,
      updated_at: now,
    },
    mode: nextMode(label.mode, ctx),
    updated_at: now,
  };
}

/**
 * Unconfirms a stump and re-derives its position from the homography.
 */
export function unconfirmStump(
  label: Label,
  stumpName: 'bat_stump' | 'bowl_stump',
  systemPoints?:
    | Record<string, [number, number]>
    | Array<{ name: string; x: number; y: number }>
    | null,
  ctx?: EditContext
): Label {
  if (!label.calibration_gt) return label;
  const currentConfirmed = getStumpConfirmed(label.calibration_gt);
  const updatedConfirmed: StumpConfirmed = {
    ...currentConfirmed,
    [stumpName]: false,
  };

  const updatedPoints = deriveUnconfirmedStumps(label.calibration_gt.points, updatedConfirmed);

  let residual_px: number | null = null;
  try {
    const fit = fitHomography(updatedPoints, updatedConfirmed);
    residual_px = fit.residual_px;
  } catch {
    residual_px = null;
  }

  const source = classifySource(updatedPoints, systemPoints);
  const now = new Date().toISOString();

  return {
    ...label,
    calibration_gt: {
      points: updatedPoints,
      source,
      residual_px,
      stump_confirmed: updatedConfirmed,
      updated_at: now,
    },
    mode: nextMode(label.mode, ctx),
    updated_at: now,
  };
}

/**
 * Clears a single calibration point by name.
 */
export function clearCalibrationPoint(
  label: Label,
  name: CalibrationPointName,
  systemPoints?:
    | Record<string, [number, number]>
    | Array<{ name: string; x: number; y: number }>
    | null,
  ctx?: EditContext
): Label {
  if (!label.calibration_gt) return label;
  const newPoints = { ...label.calibration_gt.points } as Record<string, [number, number]>;
  delete newPoints[name];

  const currentConfirmed = getStumpConfirmed(label.calibration_gt);
  const updatedConfirmed: StumpConfirmed =
    name === 'bat_stump'
      ? { ...currentConfirmed, bat_stump: false }
      : name === 'bowl_stump'
      ? { ...currentConfirmed, bowl_stump: false }
      : currentConfirmed;

  let residual_px: number | null = null;
  const allPresent = CALIB_POINT_NAMES.every((k) => newPoints[k]);
  if (allPresent) {
    try {
      const fit = fitHomography(newPoints as Record<CalibrationPointName, [number, number]>, updatedConfirmed);
      residual_px = fit.residual_px;
    } catch {
      residual_px = null;
    }
  }

  const normSys =
    normalizeSystemPoints(systemPoints) ??
    ({} as Record<CalibrationPointName, [number, number]>);
  const source = classifySource(newPoints, normSys);
  const now = new Date().toISOString();

  return {
    ...label,
    calibration_gt: {
      points: newPoints as Record<CalibrationPointName, [number, number]>,
      source,
      residual_px,
      stump_confirmed: updatedConfirmed,
      updated_at: now,
    },
    mode: nextMode(label.mode, ctx),
    updated_at: now,
  };
}

/**
 * Accepts system calibration points: copies the four system CORNERS and derives both stumps (unconfirmed).
 */
export function acceptSystemCalibration(
  label: Label,
  systemPoints?:
    | Record<string, [number, number]>
    | Array<{ name: string; x: number; y: number }>
    | null,
  ctx?: EditContext
): Label {
  const normSys = normalizeSystemPoints(systemPoints);
  if (!normSys) {
    throw new Error(
      'Cannot accept system calibration: missing or incomplete system calibration points'
    );
  }

  const corners: readonly CalibrationPointName[] = ['bat_L', 'bat_R', 'bowl_L', 'bowl_R'];
  if (!corners.every((c) => normSys[c])) {
    throw new Error('Missing system corner points');
  }

  const stumpConfirmed: StumpConfirmed = { bat_stump: false, bowl_stump: false };
  const basePoints: Record<CalibrationPointName, [number, number]> = {
    bat_L: normSys.bat_L,
    bat_R: normSys.bat_R,
    bowl_L: normSys.bowl_L,
    bowl_R: normSys.bowl_R,
    bat_stump: normSys.bat_stump ?? [0, 0],
    bowl_stump: normSys.bowl_stump ?? [0, 0],
  };

  const derivedPoints = deriveUnconfirmedStumps(basePoints, stumpConfirmed);
  const source = classifySource(derivedPoints, systemPoints);
  const now = new Date().toISOString();

  return {
    ...label,
    calibration_gt: {
      points: derivedPoints,
      source,
      residual_px: null,
      stump_confirmed: stumpConfirmed,
      updated_at: now,
    },
    mode: nextMode(label.mode, ctx),
    updated_at: now,
  };
}

/**
 * Resets calibration to system calibration points: copies all six system points with both unconfirmed.
 */
export function resetCalibrationToSystem(
  label: Label,
  systemPoints?:
    | Record<string, [number, number]>
    | Array<{ name: string; x: number; y: number }>
    | null,
  ctx?: EditContext
): Label {
  const normSys = normalizeSystemPoints(systemPoints);
  if (!normSys) {
    throw new Error(
      'Cannot reset to system calibration: missing or incomplete system calibration points'
    );
  }

  const stumpConfirmed: StumpConfirmed = { bat_stump: false, bowl_stump: false };
  const source = classifySource(normSys, systemPoints);
  const now = new Date().toISOString();

  return {
    ...label,
    calibration_gt: {
      points: { ...normSys },
      source,
      residual_px: null,
      stump_confirmed: stumpConfirmed,
      updated_at: now,
    },
    mode: nextMode(label.mode, ctx),
    updated_at: now,
  };
}

/**
 * Clears calibration from label (sets calibration_gt to null).
 */
export function clearCalibration(label: Label, ctx?: EditContext): Label {
  return {
    ...label,
    calibration_gt: null,
    mode: nextMode(label.mode, ctx),
    updated_at: new Date().toISOString(),
  };
}
