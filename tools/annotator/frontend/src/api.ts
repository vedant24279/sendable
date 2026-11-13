/**
 * Typed API client for the Cricket Delivery Annotator.
 * Mirrors the backend schema and SPEC.md prefill shape.
 */

export interface ClipItem {
  clip_id: string;
  path: string;
  display_name?: string;
  pool?: 'library' | 'debug';
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
  added_at?: string;
  last_opened_at?: string | null;
  warnings?: string[];
  size_bytes?: number;
  reference_decision?: 'out' | 'not_out' | null;
  ball_colour_hint?: 'white' | 'red' | 'pink' | null;
  source_group?: string | null;
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

export interface LibraryInfo {
  folder: string;
  count: number;
}

export async function fetchLibraryInfo(): Promise<LibraryInfo> {
  const res = await fetch('/api/library/info');
  if (!res.ok) {
    throw new Error(`Failed to fetch library info: HTTP ${res.status}`);
  }
  return res.json() as Promise<LibraryInfo>;
}

export async function fetchLibraryRecents(limit = 20): Promise<ClipItem[]> {
  const res = await fetch(`/api/library/recents?limit=${limit}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch recents: HTTP ${res.status}`);
  }
  return res.json() as Promise<ClipItem[]>;
}

export async function fetchLibraryAll(): Promise<ClipItem[]> {
  const res = await fetch('/api/library');
  if (!res.ok) {
    throw new Error(`Failed to fetch library clips: HTTP ${res.status}`);
  }
  return res.json() as Promise<ClipItem[]>;
}

export async function markClipOpened(clipId: string): Promise<void> {
  try {
    await fetch(`/api/library/${encodeURIComponent(clipId)}/opened`, {
      method: 'POST',
    });
  } catch (err) {
    console.warn(`Failed to mark clip ${clipId} opened:`, err);
  }
}

export async function hideClip(clipId: string): Promise<void> {
  const res = await fetch(`/api/library/${encodeURIComponent(clipId)}/hide`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error(`Failed to hide clip: HTTP ${res.status}`);
  }
}

export interface LibraryClipPatch {
  reference_decision?: 'out' | 'not_out' | null;
  ball_colour_hint?: 'white' | 'red' | 'pink' | null;
  source_group?: string | null;
}

export async function patchLibraryClip(
  clipId: string,
  patch: LibraryClipPatch
): Promise<ClipItem> {
  const res = await fetch(`/api/library/${encodeURIComponent(clipId)}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail) {
        detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // keep HTTP status
    }
    throw new Error(`Failed to update library clip: ${detail}`);
  }
  const data = await res.json();
  return (data.entry ?? data) as ClipItem;
}

export interface UploadResult {
  status: 'added' | 'duplicate';
  entry: ClipItem;
}

/**
 * Uploads a video file as raw body stream using XMLHttpRequest for progress reporting.
 */
export function uploadVideoFile(
  file: File,
  onProgress?: (percent: number) => void
): Promise<UploadResult> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const url = `/api/library/upload?name=${encodeURIComponent(file.name)}`;
    xhr.open('POST', url, true);
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');

    if (xhr.upload && onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && e.total > 0) {
          const pct = Math.round((e.loaded / e.total) * 100);
          onProgress(pct);
        }
      };
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText) as UploadResult;
          resolve(data);
        } catch (err) {
          reject(new Error('Invalid JSON response from server'));
        }
      } else {
        let msg = `HTTP ${xhr.status} ${xhr.statusText}`;
        try {
          const errData = JSON.parse(xhr.responseText);
          if (errData && errData.detail) {
            msg = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
          }
        } catch {
          // Keep status text
        }
        reject(new Error(msg));
      }
    };

    xhr.onerror = () => {
      reject(new Error('Network error during video upload'));
    };

    xhr.send(file);
  });
}
