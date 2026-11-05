/**
 * Typed API client for the Cricket Delivery Annotator.
 * Mirrors the backend schema and SPEC.md prefill shape.
 */

export interface ClipItem {
  clip_id: string;
  path: string;
  fps: number;
  frame_count: number;
  width: number;
  height: number;
  ball_type: "white" | "red" | "pink" | null;
  has_results: boolean;
  has_calibration: boolean;
  label_status: "none" | "draft" | "final" | "flagged";
  split: "dev" | "final" | null;
  frame_count_mismatch?: boolean;
  has_error?: boolean;
}

export interface EventRelease {
  frame: number;
  x: number;
  y: number;
  timestamp_sec?: number;
}

export interface EventBounce {
  frame: number;
  x: number;
  y: number;
  timestamp_sec?: number;
  zone?: string;
  length_m?: number;
  grid_cell?: [number, number];
}

export interface EventImpact {
  type?: "bat" | "pad" | "stumps" | "none";
  frame?: number | null;
  x?: number | null;
  y?: number | null;
}

export interface EventDeviation {
  frame: number;
  x: number;
  y: number;
  timestamp_sec?: number;
}

export interface PrefillEvents {
  release: EventRelease | null;
  bounce: EventBounce | null;
  impact: EventImpact | null;
  deviation: EventDeviation | null;
}

export interface TrajectoryPoint {
  frame: number;
  x: number;
  y: number;
  conf: number | null;
  interpolated: boolean;
}

export interface CalibrationPoint {
  name: string;
  x: number;
  y: number;
}

export interface PrefillData {
  clip_id: string;
  events: PrefillEvents;
  trajectory: TrajectoryPoint[];
  calibration: CalibrationPoint[];
}

export interface LabelPoint {
  frame: number;
  x: number;
  y: number;
}

export interface LabelImpactPoint {
  type: "bat" | "pad" | "stumps" | "none";
  frame?: number | null;
  x?: number | null;
  y?: number | null;
}

export interface LabelData {
  schema_version: number;
  clip_id: string;
  split: "dev" | "final" | null;
  annotator: string;
  mode: "assisted" | "blind";
  status: "draft" | "final" | "flagged";
  created_at: string;
  updated_at: string;
  ball_colour: "white" | "red" | "pink" | null;
  batter_hand: "right" | "left" | null;
  bowler_type: "pace" | "spin" | null;
  lighting: "bright" | "overcast" | "low" | null;
  release: LabelPoint | null;
  bounce: LabelPoint | null;
  impact: LabelImpactPoint | null;
  last_visible_frame: number | null;
  lbw: "out" | "not_out_pitched_leg" | "not_out_impact_outside" | "not_out_missing" | "umpires_call" | null;
  flags: Array<"ball_not_visible" | "camera_moved" | "bad_calibration" | "unclear">;
  notes: string;
}

export async function fetchClips(): Promise<ClipItem[]> {
  const res = await fetch("/api/clips");
  if (!res.ok) {
    throw new Error(`Failed to fetch clips: HTTP ${res.status}`);
  }
  return res.json() as Promise<ClipItem[]>;
}

export async function fetchPrefill(clipId: string): Promise<PrefillData | null> {
  const res = await fetch(`/api/clips/${encodeURIComponent(clipId)}/prefill`);
  if (res.status === 404) {
    return null;
  }
  if (!res.ok) {
    throw new Error(`Failed to fetch prefill: HTTP ${res.status}`);
  }
  return res.json() as Promise<PrefillData>;
}

export async function fetchLabel(clipId: string): Promise<LabelData | null> {
  const res = await fetch(`/api/clips/${encodeURIComponent(clipId)}/label`);
  if (res.status === 404) {
    return null;
  }
  if (!res.ok) {
    throw new Error(`Failed to fetch label: HTTP ${res.status}`);
  }
  return res.json() as Promise<LabelData>;
}

export function frameUrl(clipId: string, n: number): string {
  return `/api/clips/${encodeURIComponent(clipId)}/frame/${n}`;
}
