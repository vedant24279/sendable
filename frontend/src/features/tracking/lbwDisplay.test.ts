import { describe, expect, it } from "vitest";
import {
  ACCURACY_NOTE,
  HEIGHT_NOTE,
  hasLbwGraphic,
  inSegmentC,
  lbwColor,
  mapWorldToInset,
  verdictText,
  visibleAt,
} from "./lbwDisplay";
import { PitchMapInset } from "./PitchMapInset";
import type { LbwResult, TrackingResult } from "./types";

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
};

function lbw(overrides: Partial<LbwResult> = {}, wickets: Partial<LbwResult["wickets"]> = {}): LbwResult {
  return {
    mode: "line",
    batter_hand: "right",
    pitching: { x: 0.02, z: 6.4, side: "centre", verdict: "in_line" },
    impact: { x: 0.05, side: "centre", verdict: "in_line" },
    wickets: {
      x: 0.03, sigma: 0.081, sigma_stat: 0.041,
      verdict: "HITTING", margin_m: -0.084, stable: true,
      ...wickets,
    },
    height: null,
    overall: "OUT_LINE",
    notes: [],
    slope_flag: false,
    ...overrides,
  };
}

describe("verdictText", () => {
  it("OUT_LINE stable", () => {
    expect(verdictText(lbw())).toEqual({
      headline: "OUT (line)",
      detail: ["Pitching: in line", "Impact: in line", "Wickets: Hitting", HEIGHT_NOTE],
    });
  });

  it("OUT_LINE not stable adds close call", () => {
    expect(verdictText(lbw({}, { stable: false }))!.headline).toBe("OUT (line) - close call");
  });

  it("NOT_OUT_LINE missing, stable and not stable", () => {
    const miss = lbw(
      {
        overall: "NOT_OUT_LINE",
        impact: { x: 0.4, side: "leg", verdict: "outside_leg" },
        pitching: { x: 0.5, z: 5, side: "leg", verdict: "outside_leg" },
      },
      { x: 0.36, verdict: "MISSING", margin_m: 0.2457, sigma: 0.0812, stable: true },
    );
    expect(verdictText(miss)).toEqual({
      headline: "NOT OUT (line)",
      detail: [
        "Pitching: outside leg",
        "Impact: outside leg",
        "Wickets: Missing by 25 cm (±8 cm)",
        HEIGHT_NOTE,
      ],
    });
    const close = { ...miss, wickets: { ...miss.wickets, stable: false } };
    expect(verdictText(close)!.headline).toBe("NOT OUT (line) - close call");
  });

  it("UMPIRES_CALL stable and not stable", () => {
    const uc = lbw(
      { overall: "UMPIRES_CALL", impact: { x: 0.13, side: "off", verdict: "umpires_call" } },
      { x: 0.14, verdict: "UMPIRES_CALL", margin_m: 0.0257, stable: true },
    );
    const t = verdictText(uc)!;
    expect(t.headline).toBe("UMPIRE'S CALL");
    expect(t.detail).toEqual([
      "Pitching: in line",
      "Impact: umpire's call",
      "Wickets: Umpire's call",
      HEIGHT_NOTE,
    ]);
    expect(verdictText({ ...uc, wickets: { ...uc.wickets, stable: false } })!.headline).toBe(
      "UMPIRE'S CALL - close call",
    );
  });

  it("NO_IMPACT", () => {
    expect(verdictText(lbw({ overall: "NO_IMPACT" }))).toEqual({
      headline: "No impact",
      detail: [HEIGHT_NOTE],
    });
  });

  it("batter_hand null gives side unknown", () => {
    const t = verdictText(
      lbw({
        batter_hand: null,
        pitching: { x: 0.4, z: 5, side: null, verdict: "outside_side_unknown" },
        impact: { x: 0.3, side: null, verdict: "outside_side_unknown" },
        overall: "NOT_OUT_LINE",
      }),
    )!;
    expect(t.detail[0]).toBe("Pitching: side unknown");
    expect(t.detail[1]).toBe("Impact: side unknown");
  });

  it("no lbw returns nothing", () => {
    expect(verdictText(undefined)).toBeNull();
    expect(verdictText(null)).toBeNull();
  });

  it("accuracy note text and colours", () => {
    expect(ACCURACY_NOTE).toBe("Indicative: lateral accuracy about ±8 cm on one broadcast camera");
    expect(lbwColor("OUT_LINE")).not.toBe(lbwColor("NOT_OUT_LINE"));
    expect(lbwColor("UMPIRES_CALL")).not.toBe(lbwColor("OUT_LINE"));
  });
});

describe("visibleAt (c_3d27ed64 v2 segments)", () => {
  const s = C_3D27ED64_SEGMENTS;
  it("hidden before the impact in segment B", () => {
    expect(visibleAt(0.0, s)).toBe(false);
    expect(visibleAt(1.4333, s)).toBe(false);
    expect(visibleAt(1.89, s)).toBe(false);
  });
  it("visible from the impact to the end of segment B", () => {
    expect(visibleAt(1.9, s)).toBe(true);
    expect(visibleAt(4.0, s)).toBe(true);
    expect(visibleAt(5.79, s)).toBe(true);
  });
  it("visible for all of segment C, hidden after", () => {
    expect(visibleAt(5.8, s)).toBe(true);
    expect(visibleAt(8.0, s)).toBe(true);
    expect(visibleAt(10.4667, s)).toBe(true);
    expect(visibleAt(10.5, s)).toBe(false);
  });
  it("inset only during segment C", () => {
    expect(inSegmentC(5.79, s)).toBe(false);
    expect(inSegmentC(5.8, s)).toBe(true);
    expect(inSegmentC(10.4667, s)).toBe(true);
    expect(inSegmentC(10.5, s)).toBe(false);
  });
  it("without an impact only segment C shows it", () => {
    const noImp = { ...s, seg_b_impact_sec: null };
    expect(visibleAt(3.0, noImp)).toBe(false);
    expect(visibleAt(6.0, noImp)).toBe(true);
  });
});

describe("mapWorldToInset", () => {
  it("maps the corners", () => {
    expect(mapWorldToInset(-1.32, 0, 120, 400)).toEqual({ x: 0, y: 0 });
    expect(mapWorldToInset(1.32, 0, 120, 400)).toEqual({ x: 120, y: 0 });
    const bl = mapWorldToInset(-1.32, 18.9, 120, 400);
    expect(bl.x).toBeCloseTo(0, 9);
    expect(bl.y).toBeCloseTo(400, 9);
    const br = mapWorldToInset(1.32, 18.9, 120, 400);
    expect(br.x).toBeCloseTo(120, 9);
    expect(br.y).toBeCloseTo(400, 9);
  });
  it("centre line and batter's end at the top", () => {
    expect(mapWorldToInset(0, 0, 120, 400).x).toBeCloseTo(60, 9);
    expect(mapWorldToInset(0, 9.45, 120, 400).y).toBeCloseTo(200, 9);
  });
});

describe("no lbw renders nothing", () => {
  const base = { segments: C_3D27ED64_SEGMENTS } as Pick<TrackingResult, "segments" | "lbw">;
  it("hasLbwGraphic needs v2 and a lbw block", () => {
    expect(hasLbwGraphic(base)).toBe(false);
    expect(hasLbwGraphic({ ...base, lbw: null })).toBe(false);
    expect(hasLbwGraphic({ ...base, lbw: lbw() })).toBe(true);
    const legacy = { ...C_3D27ED64_SEGMENTS, render_mode: undefined };
    expect(hasLbwGraphic({ segments: legacy, lbw: lbw() })).toBe(false);
  });
  it("PitchMapInset returns null without lbw", () => {
    expect(PitchMapInset({ lbw: undefined, width: 140, height: 420 })).toBeNull();
    expect(PitchMapInset({ lbw: lbw(), width: 140, height: 420 })).not.toBeNull();
  });
});
