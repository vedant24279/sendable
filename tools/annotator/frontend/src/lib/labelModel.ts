/**
 * Label data model and pure transformation functions for the Cricket Delivery Annotator.
 * Mirrors tools/annotator/backend/app/schema.py exactly.
 */

import { PrefillData } from '../api';
import {
  CalibrationPointName,
  CALIB_POINT_NAMES,
} from './calibConstants';
import { fitHomography, classifySource } from './calibration';

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
  | 'umpires_call';
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

export interface CalibrationGT {
  points: Record<CalibrationPointName, [number, number]>;
  source: CalibrationSource;
  residual_px: number | null;
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
  const prefillBallType = (prefill as { ball_type?: string | null } | null)?.ball_type ?? meta.ball_type;
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

/**
 * Sets one calibration point coordinate, rounding x and y to 1 decimal place.
 * Recomputes source and residual_px.
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

  const updatedPoints: Record<CalibrationPointName, [number, number]> = {
    ...existingPoints,
    [name]: [round1(x), round1(y)],
  };

  let residual_px: number | null = null;
  const allPresent = CALIB_POINT_NAMES.every(
    (k) => updatedPoints[k] && updatedPoints[k].length === 2
  );
  if (allPresent) {
    try {
      const fit = fitHomography(updatedPoints);
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
      updated_at: now,
    },
    mode: nextMode(label.mode, ctx),
    updated_at: now,
  };
}

/**
 * Accepts system calibration points, setting source to "system_verified".
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

  let residual_px: number | null = null;
  try {
    const fit = fitHomography(normSys);
    residual_px = fit.residual_px;
  } catch {
    residual_px = null;
  }

  const now = new Date().toISOString();

  return {
    ...label,
    calibration_gt: {
      points: normSys,
      source: 'system_verified',
      residual_px,
      updated_at: now,
    },
    mode: nextMode(label.mode, ctx),
    updated_at: now,
  };
}

/**
 * Resets calibration to system calibration points.
 */
export function resetCalibrationToSystem(
  label: Label,
  systemPoints?:
    | Record<string, [number, number]>
    | Array<{ name: string; x: number; y: number }>
    | null,
  ctx?: EditContext
): Label {
  return acceptSystemCalibration(label, systemPoints, ctx);
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
