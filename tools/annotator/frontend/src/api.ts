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
  system_residual_px?: number | null;
  has_gt_calibration?: boolean;
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

import type { Label } from './lib/labelModel';

export type LabelData = Label;

export class ApiValidationError extends Error {
  readonly issues: string[];
  readonly detail: unknown;

  constructor(message: string, issues: string[], detail?: unknown) {
    super(message);
    this.name = 'ApiValidationError';
    this.issues = issues;
    this.detail = detail;
  }
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

export async function getLabel(clipId: string): Promise<Label | null> {
  const res = await fetch(`/api/clips/${encodeURIComponent(clipId)}/label`);
  if (res.status === 404) {
    return null;
  }
  if (!res.ok) {
    throw new Error(`Failed to get label: HTTP ${res.status}`);
  }
  return res.json() as Promise<Label>;
}

export const fetchLabel = getLabel;

export async function putLabel(clipId: string, label: Label): Promise<Label> {
  const res = await fetch(`/api/clips/${encodeURIComponent(clipId)}/label`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(label),
  });

  if (res.status === 422) {
    let detailMsg = 'Validation Error';
    let issues: string[] = [];
    let errData: unknown = null;
    try {
      errData = await res.json();
      if (errData && typeof errData === 'object' && 'detail' in errData) {
        const detail = (errData as { detail: unknown }).detail;
        if (Array.isArray(detail)) {
          issues = detail.map((d: any) => {
            if (typeof d === 'string') return d;
            if (d && typeof d === 'object') {
              const loc = Array.isArray(d.loc) ? d.loc.filter((x: any) => x !== 'body').join('.') : '';
              const prefix = loc ? `${loc}: ` : '';
              return `${prefix}${d.msg || JSON.stringify(d)}`;
            }
            return String(d);
          });
          detailMsg = issues.join('; ');
        } else if (typeof detail === 'string') {
          issues = [detail];
          detailMsg = detail;
        } else {
          issues = [JSON.stringify(detail)];
          detailMsg = issues[0];
        }
      }
    } catch {
      issues = [res.statusText || 'HTTP 422 Unprocessable Entity'];
      detailMsg = issues[0];
    }
    throw new ApiValidationError(detailMsg, issues, errData);
  }

  if (!res.ok) {
    throw new Error(`Failed to save label: HTTP ${res.status}`);
  }

  const data = await res.json();
  return (data.label ?? data) as Label;
}

export function frameUrl(clipId: string, n: number): string {
  return `/api/clips/${encodeURIComponent(clipId)}/frame/${n}`;
}
