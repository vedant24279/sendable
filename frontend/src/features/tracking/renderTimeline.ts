import type { ImpactEvent, ReleaseEvent, TrackingResult } from "./types";

export type Phase = "before" | "segA" | "segB" | "segC" | "after";

export interface TimelineProgress {
  rb: number;
  bi: number;
  post: number;
}

export interface LegacyProgress {
  rb: number;
  bd: number;
}

export interface MarkerVisibility {
  release: boolean;
  bounce: boolean;
  impact: boolean;
}

export interface Point2D {
  x: number;
  y: number;
}

export function isRenderV2(segs: TrackingResult["segments"] | undefined | null): boolean {
  return segs?.render_mode === "v2";
}

function ramp(t: number, start: number, end: number): number {
  if (t <= start) return 0;
  if (t >= end) return 1;
  return Math.max(0, Math.min(1, (t - start) / Math.max(1e-6, end - start)));
}

export function currentPhase(t: number, segs: TrackingResult["segments"]): Phase {
  if (t < segs.seg_a_start_sec) return "before";
  if (t < segs.seg_a_end_sec) return "segA";
  if (t < segs.seg_b_end_sec) return "segB";
  if (segs.seg_c_end_sec != null && t < segs.seg_c_end_sec) return "segC";
  return "after";
}

export function parabolaProgress(
  t: number,
  segs: TrackingResult["segments"],
): LegacyProgress {
  const phase = currentPhase(t, segs);
  if (phase === "before" || phase === "segA") return { rb: 0, bd: 0 };

  if (phase === "segB") {
    const r = segs.seg_b_release_sec;
    const b = segs.seg_b_bounce_sec;
    const d = segs.seg_b_deviation_sec;
    if (r == null || b == null) return { rb: 0, bd: 0 };
    if (t < r) return { rb: 0, bd: 0 };
    if (t < b) return { rb: (t - r) / Math.max(1e-6, b - r), bd: 0 };
    if (d == null) return { rb: 1, bd: 0 };
    if (t < d) return { rb: 1, bd: (t - b) / Math.max(1e-6, d - b) };
    return { rb: 1, bd: 1 };
  }

  if (phase === "segC") {
    const s = segs.seg_c_start_sec;
    const rEnd = segs.seg_c_rb_end_sec;
    const bEnd = segs.seg_c_bd_end_sec;
    if (s == null || rEnd == null || bEnd == null) return { rb: 1, bd: 1 };
    if (t < rEnd) return { rb: (t - s) / Math.max(1e-6, rEnd - s), bd: 0 };
    if (t < bEnd) return { rb: 1, bd: (t - rEnd) / Math.max(1e-6, bEnd - rEnd) };
    return { rb: 1, bd: 1 };
  }

  return { rb: 1, bd: 1 };
}

export function progress(
  t: number,
  segs: TrackingResult["segments"],
): TimelineProgress {
  const phase = currentPhase(t, segs);
  if (phase === "before" || phase === "segA") {
    return { rb: 0, bi: 0, post: 0 };
  }

  if (phase === "segB") {
    const r = segs.seg_b_release_sec;
    const b = segs.seg_b_bounce_sec;
    const biEnd = segs.seg_b_impact_sec ?? segs.seg_b_deviation_sec;
    const pStart = segs.seg_b_impact_sec ?? null;
    const pEnd = segs.seg_b_post_end_sec ?? null;

    if (r == null || b == null || t < r) return { rb: 0, bi: 0, post: 0 };
    if (t < b) return { rb: ramp(t, r, b), bi: 0, post: 0 };
    if (biEnd == null) return { rb: 1, bi: 0, post: 0 };
    if (t < biEnd) return { rb: 1, bi: ramp(t, b, biEnd), post: 0 };
    if (pStart == null || pEnd == null || t < pStart) {
      return { rb: 1, bi: 1, post: 0 };
    }
    if (t < pEnd) return { rb: 1, bi: 1, post: ramp(t, pStart, pEnd) };
    return { rb: 1, bi: 1, post: 1 };
  }

  if (phase === "segC") {
    const s = segs.seg_c_start_sec;
    const rEnd = segs.seg_c_rb_end_sec;
    const biEnd = segs.seg_c_bi_end_sec ?? segs.seg_c_bd_end_sec;
    const pEnd = segs.seg_c_post_end_sec ?? null;

    if (s == null || rEnd == null) return { rb: 1, bi: 1, post: 1 };
    if (t < rEnd) return { rb: ramp(t, s, rEnd), bi: 0, post: 0 };
    if (biEnd != null && t < biEnd) {
      return { rb: 1, bi: ramp(t, rEnd, biEnd), post: 0 };
    }
    if (biEnd != null && pEnd != null && t < pEnd) {
      return { rb: 1, bi: 1, post: ramp(t, biEnd, pEnd) };
    }
    return { rb: 1, bi: 1, post: 1 };
  }

  return { rb: 1, bi: 1, post: 1 };
}

export function markersVisible(
  t: number,
  segs: TrackingResult["segments"],
): MarkerVisibility {
  const phase = currentPhase(t, segs);
  if (phase === "before") {
    return { release: false, bounce: false, impact: false };
  }
  if (phase === "segA") {
    return {
      release: segs.seg_a_release_sec != null && t >= segs.seg_a_release_sec,
      bounce: segs.seg_a_bounce_sec != null && t >= segs.seg_a_bounce_sec,
      impact: false,
    };
  }
  if (phase === "segB") {
    return {
      release: segs.seg_b_release_sec != null && t >= segs.seg_b_release_sec,
      bounce: segs.seg_b_bounce_sec != null && t >= segs.seg_b_bounce_sec,
      impact: segs.seg_b_impact_sec != null && t >= segs.seg_b_impact_sec,
    };
  }
  if (phase === "segC") {
    const { rb, bi } = progress(t, segs);
    return {
      release: true,
      bounce: rb >= 1,
      impact: segs.seg_b_impact_sec !== null && bi >= 1,
    };
  }
  return {
    release: segs.seg_b_release_sec != null,
    bounce: segs.seg_b_bounce_sec != null,
    impact: segs.seg_b_impact_sec != null,
  };
}

export function contactEvent(
  events: TrackingResult["events"],
): ImpactEvent | ReleaseEvent | null {
  return events.impact ?? events.deviation ?? null;
}

export function slicePolyline(pts: Point2D[], progressFrac: number): Point2D[] {
  if (pts.length < 2 || progressFrac <= 0) return [];
  const p = Math.max(0, Math.min(1, progressFrac));
  if (p >= 1) return pts.map((pt) => ({ x: pt.x, y: pt.y }));

  const nSegs = pts.length - 1;
  const pos = p * nSegs;
  const idx = Math.min(nSegs - 1, Math.floor(pos));
  const frac = pos - idx;

  const out: Point2D[] = pts.slice(0, idx + 1).map((pt) => ({ x: pt.x, y: pt.y }));
  if (frac > 0 || out.length < 2) {
    const a = pts[idx];
    const b = pts[idx + 1];
    out.push({
      x: a.x + frac * (b.x - a.x),
      y: a.y + frac * (b.y - a.y),
    });
  }
  return out;
}

export function postPoints(
  result: Pick<TrackingResult, "events" | "trajectory_post" | "segments">,
  progressFrac: number,
): Point2D[] {
  const impact = result.events.impact;
  const rawPost = result.trajectory_post;
  if (!impact || !rawPost || rawPost.length === 0 || progressFrac <= 0) {
    return [];
  }

  const maxFrame = result.segments?.seg_post_end_frame;
  const filtered =
    maxFrame != null ? rawPost.filter((pt) => pt.frame <= maxFrame) : rawPost;
  if (filtered.length === 0) return [];

  const fullPts: Point2D[] = [
    { x: impact.x, y: impact.y },
    ...filtered.map((pt) => ({ x: pt.x, y: pt.y })),
  ];
  return slicePolyline(fullPts, progressFrac);
}

export function bounceToContactPoints(
  result: Pick<TrackingResult, "events" | "trajectory">,
  biProgress: number,
): Point2D[] {
  const bounce = result.events.bounce;
  if (!bounce || biProgress <= 0) return [];

  const impact = result.events.impact;
  if (impact) {
    const inRange = result.trajectory
      .filter((p) => p.frame >= bounce.frame && p.frame <= impact.frame)
      .map((p) => ({ x: p.x, y: p.y }));
    const vertices =
      inRange.length >= 2
        ? inRange
        : [
            { x: bounce.x, y: bounce.y },
            { x: impact.x, y: impact.y },
          ];
    return slicePolyline(vertices, biProgress);
  }

  const afterBounce = result.trajectory
    .filter((p) => p.frame >= bounce.frame)
    .map((p) => ({ x: p.x, y: p.y }));
  if (afterBounce.length >= 2) {
    return slicePolyline(afterBounce, biProgress);
  }
  if (result.events.deviation) {
    return slicePolyline(
      [
        { x: bounce.x, y: bounce.y },
        { x: result.events.deviation.x, y: result.events.deviation.y },
      ],
      biProgress,
    );
  }
  return [];
}
