import { describe, expect, it } from "vitest";
import {
  bounceToContactPoints,
  contactEvent,
  currentPhase,
  isRenderV2,
  markersVisible,
  parabolaProgress,
  postPoints,
  progress,
} from "./renderTimeline";
import type { TrackingResult } from "./types";

// Copied verbatim from eval/runs/render_v2_1/c_3d27ed64/results.json
const C_3D27ED64_SEGMENTS: TrackingResult["segments"] = {
  render_mode: "v2",
  seg_a_bounce_sec: null,
  seg_a_deviation_sec: null,
  seg_a_end_sec: 0.0,
  seg_a_release_sec: null,
  seg_a_start_sec: 0.0,
  seg_b_bounce_sec: 1.4333,
  seg_b_deviation_sec: 1.9,
  seg_b_end_sec: 5.8,
  seg_b_impact_sec: 1.9,
  seg_b_post_end_sec: 5.7,
  seg_b_release_sec: 0.4667,
  seg_b_start_sec: 0.0,
  seg_c_bd_end_sec: 6.8,
  seg_c_bi_end_sec: 6.8,
  seg_c_end_sec: 10.4667,
  seg_c_post_end_sec: 9.4667,
  seg_c_rb_end_sec: 6.4667,
  seg_c_start_sec: 5.8,
  speed_b: 0.35,
};

const LEGACY_SEGMENTS: TrackingResult["segments"] = {
  seg_a_start_sec: 0.0,
  seg_a_end_sec: 1.9667,
  seg_a_release_sec: 0.3333,
  seg_a_bounce_sec: 0.7333,
  seg_a_deviation_sec: 0.9333,
  seg_b_start_sec: 1.9667,
  seg_b_end_sec: 3.9,
  seg_b_release_sec: 2.3,
  seg_b_bounce_sec: 3.1,
  seg_b_deviation_sec: 3.5,
  seg_c_start_sec: 3.9,
  seg_c_rb_end_sec: 4.7,
  seg_c_bd_end_sec: 5.1,
  seg_c_end_sec: 6.1,
};

describe("renderTimeline", () => {
  it("phases and progress for v2 timestamps of c_3d27ed64", () => {
    expect(isRenderV2(C_3D27ED64_SEGMENTS)).toBe(true);

    // Phase routing
    expect(currentPhase(-0.01, C_3D27ED64_SEGMENTS)).toBe("before");
    expect(currentPhase(0.0, C_3D27ED64_SEGMENTS)).toBe("segB");
    expect(currentPhase(3.0, C_3D27ED64_SEGMENTS)).toBe("segB");
    expect(currentPhase(5.8, C_3D27ED64_SEGMENTS)).toBe("segC");
    expect(currentPhase(10.0, C_3D27ED64_SEGMENTS)).toBe("segC");
    expect(currentPhase(10.4667, C_3D27ED64_SEGMENTS)).toBe("after");

    // Progress in Segment B
    expect(progress(0.2, C_3D27ED64_SEGMENTS)).toEqual({ rb: 0, bi: 0, post: 0 });
    const midRbB = (0.4667 + 1.4333) / 2;
    const pMidRbB = progress(midRbB, C_3D27ED64_SEGMENTS);
    expect(pMidRbB.rb).toBeCloseTo(0.5, 4);
    expect(pMidRbB.bi).toBe(0);
    expect(pMidRbB.post).toBe(0);

    const midBiB = (1.4333 + 1.9) / 2;
    const pMidBiB = progress(midBiB, C_3D27ED64_SEGMENTS);
    expect(pMidBiB.rb).toBe(1);
    expect(pMidBiB.bi).toBeCloseTo(0.5, 4);
    expect(pMidBiB.post).toBe(0);

    const midPostB = (1.9 + 5.7) / 2;
    const pMidPostB = progress(midPostB, C_3D27ED64_SEGMENTS);
    expect(pMidPostB.rb).toBe(1);
    expect(pMidPostB.bi).toBe(1);
    expect(pMidPostB.post).toBeCloseTo(0.5, 4);

    expect(progress(5.75, C_3D27ED64_SEGMENTS)).toEqual({
      rb: 1,
      bi: 1,
      post: 1,
    });

    // Progress in Segment C
    const midRbC = (5.8 + 6.4667) / 2;
    const pMidRbC = progress(midRbC, C_3D27ED64_SEGMENTS);
    expect(pMidRbC.rb).toBeCloseTo(0.5, 4);
    expect(pMidRbC.bi).toBe(0);
    expect(pMidRbC.post).toBe(0);

    const midBiC = (6.4667 + 6.8) / 2;
    const pMidBiC = progress(midBiC, C_3D27ED64_SEGMENTS);
    expect(pMidBiC.rb).toBe(1);
    expect(pMidBiC.bi).toBeCloseTo(0.5, 4);
    expect(pMidBiC.post).toBe(0);

    const midPostC = (6.8 + 9.4667) / 2;
    const pMidPostC = progress(midPostC, C_3D27ED64_SEGMENTS);
    expect(pMidPostC.rb).toBe(1);
    expect(pMidPostC.bi).toBe(1);
    expect(pMidPostC.post).toBeCloseTo(0.5, 4);

    // Hold interval [9.4667, 10.4667) and after
    expect(progress(9.8, C_3D27ED64_SEGMENTS)).toEqual({
      rb: 1,
      bi: 1,
      post: 1,
    });
    expect(progress(11.0, C_3D27ED64_SEGMENTS)).toEqual({
      rb: 1,
      bi: 1,
      post: 1,
    });
  });

  it("legacy path unchanged when render_mode is absent", () => {
    expect(isRenderV2(LEGACY_SEGMENTS)).toBe(false);
    expect(currentPhase(0.5, LEGACY_SEGMENTS)).toBe("segA");
    expect(currentPhase(2.5, LEGACY_SEGMENTS)).toBe("segB");
    expect(currentPhase(4.5, LEGACY_SEGMENTS)).toBe("segC");
    expect(currentPhase(6.5, LEGACY_SEGMENTS)).toBe("after");

    expect(parabolaProgress(1.0, LEGACY_SEGMENTS)).toEqual({ rb: 0, bd: 0 });
    const pB = parabolaProgress(2.7, LEGACY_SEGMENTS);
    expect(pB.rb).toBeCloseTo(0.5, 4);
    expect(pB.bd).toBe(0);
    const pB2 = parabolaProgress(3.3, LEGACY_SEGMENTS);
    expect(pB2.rb).toBe(1);
    expect(pB2.bd).toBeCloseTo(0.5, 4);
    expect(parabolaProgress(5.5, LEGACY_SEGMENTS)).toEqual({ rb: 1, bd: 1 });
  });

  it("markersVisible per phase for c_3d27ed64", () => {
    // before
    expect(markersVisible(-0.1, C_3D27ED64_SEGMENTS)).toEqual({
      release: false,
      bounce: false,
      impact: false,
    });

    // segB progressive reveal
    expect(markersVisible(0.1, C_3D27ED64_SEGMENTS)).toEqual({
      release: false,
      bounce: false,
      impact: false,
    });
    expect(markersVisible(0.4667, C_3D27ED64_SEGMENTS)).toEqual({
      release: true,
      bounce: false,
      impact: false,
    });
    expect(markersVisible(1.4333, C_3D27ED64_SEGMENTS)).toEqual({
      release: true,
      bounce: true,
      impact: false,
    });
    expect(markersVisible(1.9, C_3D27ED64_SEGMENTS)).toEqual({
      release: true,
      bounce: true,
      impact: true,
    });

    // segC: release from start, bounce when rb reaches 1, impact when bi reaches 1
    expect(markersVisible(5.8, C_3D27ED64_SEGMENTS)).toEqual({
      release: true,
      bounce: false,
      impact: false,
    });
    expect(markersVisible(6.4667, C_3D27ED64_SEGMENTS)).toEqual({
      release: true,
      bounce: true,
      impact: false,
    });
    expect(markersVisible(6.8, C_3D27ED64_SEGMENTS)).toEqual({
      release: true,
      bounce: true,
      impact: true,
    });
    expect(markersVisible(10.0, C_3D27ED64_SEGMENTS)).toEqual({
      release: true,
      bounce: true,
      impact: true,
    });
  });

  it("contactEvent prefers impact and falls back to deviation", () => {
    const impact = { frame: 20, timestamp_sec: 0.6667, x: 976, y: 408 };
    const deviation = { frame: 22, timestamp_sec: 0.7333, x: 1028, y: 387 };

    expect(
      contactEvent({ release: null, bounce: null, impact, deviation }),
    ).toEqual(impact);
    expect(
      contactEvent({ release: null, bounce: null, impact: null, deviation }),
    ).toEqual(deviation);
    expect(
      contactEvent({
        release: null,
        bounce: null,
        impact: null,
        deviation: null,
      }),
    ).toBeNull();
  });

  it("postPoints with and without seg_post_end_frame at progress 0, 0.5, and 1", () => {
    const baseResult = {
      events: {
        release: null,
        bounce: null,
        impact: { frame: 20, timestamp_sec: 0.6667, x: 100, y: 200 },
        deviation: null,
      },
      trajectory_post: [
        { frame: 21, x: 110, y: 190, conf: 0.8 },
        { frame: 22, x: 120, y: 180, conf: 0.8 },
        { frame: 23, x: 130, y: 170, conf: 0.8 },
        { frame: 24, x: 140, y: 160, conf: 0.8 },
      ],
      segments: {
        ...C_3D27ED64_SEGMENTS,
      },
    };

    // Without seg_post_end_frame: 5 vertices (impact + 4 post points = 4 segments)
    expect(postPoints(baseResult, 0)).toEqual([]);
    expect(postPoints(baseResult, 0.5)).toEqual([
      { x: 100, y: 200 },
      { x: 110, y: 190 },
      { x: 120, y: 180 },
    ]);
    expect(postPoints(baseResult, 1)).toEqual([
      { x: 100, y: 200 },
      { x: 110, y: 190 },
      { x: 120, y: 180 },
      { x: 130, y: 170 },
      { x: 140, y: 160 },
    ]);

    // With seg_post_end_frame = 22: 3 vertices (impact + 2 post points = 2 segments)
    const cappedResult = {
      ...baseResult,
      segments: {
        ...C_3D27ED64_SEGMENTS,
        seg_post_end_frame: 22,
      },
    };
    expect(postPoints(cappedResult, 0)).toEqual([]);
    expect(postPoints(cappedResult, 0.5)).toEqual([
      { x: 100, y: 200 },
      { x: 110, y: 190 },
    ]);
    expect(postPoints(cappedResult, 1)).toEqual([
      { x: 100, y: 200 },
      { x: 110, y: 190 },
      { x: 120, y: 180 },
    ]);
  });

  it("no-impact case suppresses impact marker and post-impact line", () => {
    const noImpactSegs: TrackingResult["segments"] = {
      ...C_3D27ED64_SEGMENTS,
      seg_b_impact_sec: null,
      seg_b_post_end_sec: null,
      seg_c_post_end_sec: null,
    };

    // markersVisible never shows impact in B, C, or after
    expect(markersVisible(2.5, noImpactSegs)).toEqual({
      release: true,
      bounce: true,
      impact: false,
    });
    expect(markersVisible(7.5, noImpactSegs)).toEqual({
      release: true,
      bounce: true,
      impact: false,
    });
    expect(markersVisible(11.0, noImpactSegs)).toEqual({
      release: true,
      bounce: true,
      impact: false,
    });

    // progress in B still advances bi using seg_b_deviation_sec, with post = 0
    const pB = progress((1.4333 + 1.9) / 2, noImpactSegs);
    expect(pB.rb).toBe(1);
    expect(pB.bi).toBeCloseTo(0.5, 4);
    expect(pB.post).toBe(0);

    // postPoints is empty when events.impact is null
    const noImpactResult = {
      events: {
        release: { frame: 5, timestamp_sec: 0.1667, x: 1101, y: 541 },
        bounce: {
          frame: 15,
          timestamp_sec: 0.5,
          x: 1011,
          y: 615,
          interpolated: false,
          zone: "GOOD" as const,
          length_m: 6.48,
          grid_cell: [62, 11] as [number, number],
        },
        impact: null,
        deviation: { frame: 22, timestamp_sec: 0.7333, x: 1028, y: 387 },
      },
      trajectory: [
        { frame: 15, x: 1011, y: 607, interpolated: false, conf: 0.78 },
        { frame: 18, x: 975, y: 489, interpolated: false, conf: 0.71 },
        { frame: 22, x: 1028, y: 387, interpolated: false, conf: 0.76 },
      ],
      trajectory_post: [{ frame: 23, x: 1074, y: 378, conf: 0.71 }],
      segments: noImpactSegs,
    };
    expect(postPoints(noImpactResult, 0.5)).toEqual([]);
    expect(postPoints(noImpactResult, 1)).toEqual([]);

    // bounceToContactPoints falls back to trajectory points after bounce when no impact
    expect(bounceToContactPoints(noImpactResult, 1)).toEqual([
      { x: 1011, y: 607 },
      { x: 975, y: 489 },
      { x: 1028, y: 387 },
    ]);
  });
});
