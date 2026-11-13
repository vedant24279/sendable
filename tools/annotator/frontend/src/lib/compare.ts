/**
 * Pure helpers for Read-Only Compare View:
 * - system pin selection for a frame (exact and ±1 frame window)
 * - CSV row error formatting
 * - clip sorting by run CSV error
 */

import type { ClipItem, PrefillEvents } from '../api';

export type SystemPinKind = 'release' | 'bounce' | 'deviation';

export interface SystemPin {
  kind: SystemPinKind;
  shortLabel: 'sys R' | 'sys B' | 'sys D';
  frame: number;
  x: number;
  y: number;
  exact: boolean;
  frameOffset: number;
  color: string;
  tooltip: string;
}

const SYSTEM_PIN_META: Record<
  SystemPinKind,
  { shortLabel: 'sys R' | 'sys B' | 'sys D'; color: string }
> = {
  release: { shortLabel: 'sys R', color: '#f97316' },
  bounce: { shortLabel: 'sys B', color: '#ec4899' },
  deviation: { shortLabel: 'sys D', color: '#06b6d4' },
};

/**
 * Selects system pins to render on `currentFrame`:
 * - Exact match (event.frame === currentFrame): `exact: true`
 * - Adjacent frame (|event.frame - currentFrame| === 1): `exact: false` (lighter style)
 */
export function systemPinsForFrame(
  events: PrefillEvents | null | undefined,
  currentFrame: number
): SystemPin[] {
  if (!events) return [];

  const result: SystemPin[] = [];
  const kinds: SystemPinKind[] = ['release', 'bounce', 'deviation'];

  for (const kind of kinds) {
    const ev = events[kind];
    if (
      !ev ||
      typeof ev.frame !== 'number' ||
      !Number.isFinite(ev.frame) ||
      ev.x == null ||
      ev.y == null ||
      !Number.isFinite(ev.x) ||
      !Number.isFinite(ev.y)
    ) {
      continue;
    }

    const diff = ev.frame - currentFrame;
    if (Math.abs(diff) > 1) {
      continue;
    }

    const meta = SYSTEM_PIN_META[kind];
    result.push({
      kind,
      shortLabel: meta.shortLabel,
      frame: ev.frame,
      x: ev.x,
      y: ev.y,
      exact: diff === 0,
      frameOffset: diff,
      color: meta.color,
      tooltip: `${meta.shortLabel} • frame ${ev.frame} • (${ev.x.toFixed(1)}, ${ev.y.toFixed(1)})`,
    });
  }

  return result;
}

/**
 * Hit tests system diamond pins in screen pixel space for tooltip hover.
 */
export function hitTestSystemPin(
  pins: SystemPin[],
  imgX: number,
  imgY: number,
  scale: number,
  radiusScreenPx = 14
): SystemPin | null {
  if (!pins || pins.length === 0 || scale <= 0) return null;

  let nearest: SystemPin | null = null;
  let minDist = Infinity;

  for (const pin of pins) {
    const dx = (pin.x - imgX) * scale;
    const dy = (pin.y - imgY) * scale;
    const dist = Math.hypot(dx, dy);
    if (dist <= radiusScreenPx && dist < minDist) {
      minDist = dist;
      nearest = pin;
    }
  }

  return nearest;
}

function parseFinite(raw: string | undefined): number | null {
  if (raw == null) return null;
  const trimmed = String(raw).trim();
  if (!trimmed) return null;
  const num = Number(trimmed);
  return Number.isFinite(num) ? num : null;
}

function formatFrameErr(raw: string | undefined): string {
  const n = parseFinite(raw);
  if (n === null) return '—';
  const rounded = Math.round(n);
  return `${rounded > 0 ? `+${rounded}` : rounded} f`;
}

function formatPxErr(raw: string | undefined): string {
  const n = parseFinite(raw);
  return n === null ? '—' : `${n.toFixed(1)} px`;
}

function formatMetreErr(raw: string | undefined): string {
  const n = parseFinite(raw);
  return n === null ? '—' : `${n.toFixed(3)} m`;
}

export interface FormattedCompareRow {
  releaseError: string;
  bounceError: string;
  pitchZError: string;
  deviationVsImpact: string;
}

/**
 * Formats a clip's per-clip CSV row dictionary into compact human-readable error strings.
 */
export function formatCompareCsvRow(
  csvRow: Record<string, string> | null | undefined
): FormattedCompareRow {
  if (!csvRow) {
    return {
      releaseError: '—',
      bounceError: '—',
      pitchZError: '—',
      deviationVsImpact: '—',
    };
  }

  const relF = formatFrameErr(csvRow.release_frame_error);
  const relPx = formatPxErr(csvRow.release_px_error);
  const releaseError = relF === '—' && relPx === '—' ? '—' : `${relF} / ${relPx}`;

  const bncF = formatFrameErr(csvRow.bounce_frame_error);
  const bncPx = formatPxErr(csvRow.bounce_px_error);
  const bncM = formatMetreErr(csvRow.bounce_ground_error_m);
  const bounceError =
    bncF === '—' && bncPx === '—' && bncM === '—'
      ? '—'
      : `${bncF} / ${bncPx} / ${bncM}`;

  const pitchZError = formatMetreErr(csvRow.bounce_pitch_z_error_m);

  const devF = formatFrameErr(csvRow.deviation_frame_error);
  const devPx = formatPxErr(csvRow.deviation_px_error);
  const deviationVsImpact =
    devF === '—' && devPx === '—' ? '—' : `${devF} / ${devPx}`;

  return {
    releaseError,
    bounceError,
    pitchZError,
    deviationVsImpact,
  };
}

export type CompareSortKey = 'worst_bounce' | 'worst_release';

function extractSortScore(
  row: Record<string, string> | undefined,
  sortBy: CompareSortKey
): { tier: number; value: number } {
  if (!row) {
    // Tier 2: clips without a CSV row always sort last
    return { tier: 2, value: 0 };
  }

  if (sortBy === 'worst_bounce') {
    const gnd = parseFinite(row.bounce_ground_error_m);
    if (gnd !== null) return { tier: 0, value: gnd };
    const px = parseFinite(row.bounce_px_error);
    if (px !== null) return { tier: 0, value: px };
    const frm = parseFinite(row.bounce_frame_error);
    if (frm !== null) return { tier: 0, value: Math.abs(frm) };
    return { tier: 1, value: 0 };
  }

  const px = parseFinite(row.release_px_error);
  if (px !== null) return { tier: 0, value: px };
  const frm = parseFinite(row.release_frame_error);
  if (frm !== null) return { tier: 0, value: Math.abs(frm) };
  return { tier: 1, value: 0 };
}

/**
 * Returns a new sorted clip array ordered by worst CSV error (descending).
 * Clips with a row but missing metric come after numeric errors; clips without a row come last.
 */
export function sortClipsByRunMetric(
  clips: ClipItem[],
  rowsByClipId: Record<string, Record<string, string>>,
  sortBy: CompareSortKey
): ClipItem[] {
  return [...clips].sort((a, b) => {
    const sa = extractSortScore(rowsByClipId[a.clip_id], sortBy);
    const sb = extractSortScore(rowsByClipId[b.clip_id], sortBy);
    if (sa.tier !== sb.tier) return sa.tier - sb.tier;
    if (sb.value !== sa.value) return sb.value - sa.value;
    return a.clip_id.localeCompare(b.clip_id);
  });
}
