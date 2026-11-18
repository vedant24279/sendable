// Pure helpers for the line-only LBW graphic (no React, unit-tested).
import type {
  LbwImpactVerdict,
  LbwOverall,
  LbwResult,
  TrackingResult,
} from "./types";
import { isRenderV2 } from "./renderTimeline";

export interface VerdictText {
  headline: string;
  detail: string[];
}

export const HEIGHT_NOTE = "Height not evaluated (single camera)";
export const ACCURACY_NOTE =
  "Indicative: lateral accuracy about ±8 cm on one broadcast camera";

// Inset world extents (metres): pitch width 2.64 m, Z from the batter's stump line.
export const INSET_HALF_WIDTH_M = 1.32;
export const INSET_LENGTH_M = 18.9;

const HEADLINES: Record<LbwOverall, string> = {
  OUT_LINE: "OUT (line)",
  NOT_OUT_LINE: "NOT OUT (line)",
  UMPIRES_CALL: "UMPIRE'S CALL",
  NO_IMPACT: "No impact",
};

export const LBW_COLORS: Record<LbwOverall, string> = {
  OUT_LINE: "#22c55e",      // green
  NOT_OUT_LINE: "#ef4444",  // red
  UMPIRES_CALL: "#f59e0b",  // amber
  NO_IMPACT: "#9ca3af",     // grey
};

export function lbwColor(overall: LbwOverall | undefined | null): string {
  return (overall && LBW_COLORS[overall]) || LBW_COLORS.NO_IMPACT;
}

function lineText(
  verdict: LbwImpactVerdict,
  hand: LbwResult["batter_hand"],
): string {
  if (verdict === "in_line") return "in line";
  if (verdict === "umpires_call") return "umpire's call";
  if (hand == null || verdict === "outside_side_unknown") return "side unknown";
  return verdict === "outside_off" ? "outside off" : "outside leg";
}

function wicketsText(w: LbwResult["wickets"]): string {
  if (w.verdict === "HITTING") return "Hitting";
  if (w.verdict === "UMPIRES_CALL") return "Umpire's call";
  const miss = Math.round(w.margin_m * 100);
  const sig = Math.round(w.sigma * 100);
  return `Missing by ${miss} cm (±${sig} cm)`;
}

/** Headline + detail lines for the LBW card; null when there is no lbw block. */
export function verdictText(lbw: LbwResult | null | undefined): VerdictText | null {
  if (!lbw) return null;
  let headline = HEADLINES[lbw.overall] ?? lbw.overall;
  if (lbw.overall !== "NO_IMPACT" && lbw.wickets && lbw.wickets.stable === false) {
    headline += " - close call";
  }
  const detail: string[] = [];
  if (lbw.overall !== "NO_IMPACT") {
    detail.push(`Pitching: ${lineText(lbw.pitching.verdict, lbw.batter_hand)}`);
    detail.push(`Impact: ${lineText(lbw.impact.verdict, lbw.batter_hand)}`);
    detail.push(`Wickets: ${wicketsText(lbw.wickets)}`);
  }
  detail.push(HEIGHT_NOTE);
  return { headline, detail };
}

/** True during the whole of segment C (end inclusive, so the last frame keeps it). */
export function inSegmentC(t: number, segs: TrackingResult["segments"]): boolean {
  const s = segs.seg_c_start_sec;
  const e = segs.seg_c_end_sec;
  return s != null && e != null && t >= s && t <= e;
}

/** LBW video graphic: from the impact moment to the end of segment B, and all of segment C. */
export function visibleAt(t: number, segs: TrackingResult["segments"]): boolean {
  const imp = segs.seg_b_impact_sec;
  if (imp != null && t >= imp && t < segs.seg_b_end_sec) return true;
  return inSegmentC(t, segs);
}

/** Top-down inset mapping: X in [-1.32, 1.32] -> [0, w] (image right = +X);
 *  Z in [0, 18.9] -> [0, h] with the batter's end at the top. Not clamped. */
export function mapWorldToInset(
  X: number,
  Z: number,
  w: number,
  h: number,
): { x: number; y: number } {
  return {
    x: ((X + INSET_HALF_WIDTH_M) / (2 * INSET_HALF_WIDTH_M)) * w,
    y: (Z / INSET_LENGTH_M) * h,
  };
}

/** The LBW graphic, toggle, card and inset apply only to v2 results with a lbw block. */
export function hasLbwGraphic(
  result: Pick<TrackingResult, "segments" | "lbw">,
): boolean {
  return isRenderV2(result.segments) && !!result.lbw;
}
