"""Synthetic unit tests for backend.pipeline.track_engine."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pipeline.track_engine import analyse_track  # noqa: E402


SYNTH_CORNERS: Dict[str, List[float]] = {
    "bat_L": [770.0, 448.0],
    "bat_R": [1130.0, 448.0],
    "bowl_L": [735.0, 750.0],
    "bowl_R": [1185.0, 750.0],
}


def _make_bouncing_track(
    *,
    t_rel: int = 10,
    t_bnc: float = 24.4,
    t_imp: float | None = 31.3,
    t_end: int = 38,
    noise_px: float = 0.8,
    seed: int = 7,
    drop_frames: set[int] | None = None,
    dup_at: set[int] | None = None,
) -> Dict[int, List[Dict[str, Any]]]:
    rng = np.random.default_rng(seed)
    drop = drop_frames or set()
    dups = dup_at or set()
    out: Dict[int, List[Dict[str, Any]]] = {}

    # Bounce pixel well inside pitch strip around (950, 560)
    xb, yb = 950.0, 560.0
    # Pre-bounce: descends toward (950, 560)
    # Post-bounce: ascends toward batter (940, 420) around t_imp
    # Post-impact: sharp deflection right & upward (+vx, steeper -vy)
    vx1 = -1.2
    vy1_b = 18.0
    g1 = 0.6

    vx2 = -1.5
    vy2_b = -18.5
    g2 = 0.3

    if t_imp is not None:
        xc = xb + vx2 * (t_imp - t_bnc)
        yc = yb + vy2_b * (t_imp - t_bnc) + 0.5 * g2 * (t_imp - t_bnc) ** 2
    else:
        xc, yc = 0.0, 0.0

    vx3 = 16.0
    vy3 = -9.0

    cum_dup = 0
    prev_xy: tuple[float, float] | None = None
    for f in range(t_rel, t_end + 1):
        if f in dups and prev_xy is not None:
            cum_dup += 1
            if f not in drop:
                out[f] = [{"cx": prev_xy[0], "cy": prev_xy[1], "conf": 0.85}]
            continue

        t_eff = float(f - cum_dup)
        if t_eff <= t_bnc:
            dt = t_eff - t_bnc
            x = xb + vx1 * dt
            y = yb + vy1_b * dt + 0.5 * g1 * dt * dt
        elif t_imp is None or t_eff <= t_imp:
            dt = t_eff - t_bnc
            x = xb + vx2 * dt
            y = yb + vy2_b * dt + 0.5 * g2 * dt * dt
        else:
            dt = t_eff - t_imp
            x = xc + vx3 * dt
            y = yc + vy3 * dt

        if f in drop:
            prev_xy = (x, y)
            continue
        nx = float(x + rng.normal(0.0, noise_px))
        ny = float(y + rng.normal(0.0, noise_px))
        prev_xy = (nx, ny)
        out[f] = [{"cx": nx, "cy": ny, "conf": 0.82}]
    return out


def test_known_bounce_and_impact_kink_with_noise() -> None:
    ball = _make_bouncing_track(noise_px=1.0, seed=11)
    res = analyse_track(ball, 30.0, SYNTH_CORNERS, batter_hand="right")

    assert res["evidence"]["hypothesis"] == "H_c"
    assert res["events"]["release"]["frame"] == 10
    assert abs(res["events"]["bounce"]["subframe"] - 24.4) < 0.75
    assert abs(res["events"]["impact"]["subframe"] - 31.3) < 0.75
    assert res["evidence"]["angle_deg"] > 30.0
    assert res["evidence"]["kink_snr"] >= 3.0
    assert res["events"]["bounce"]["sigma_frames"] is not None
    assert len(res["events"]["bounce"]["observed_neighbors"]) >= 1


def test_viterbi_drops_static_and_short_fp_chains() -> None:
    ball = _make_bouncing_track(noise_px=0.5, seed=21)
    # Add a long static false-positive blob across all frames (high conf)
    for f in range(1, 45):
        ball.setdefault(f, []).append({"cx": 420.0, "cy": 310.0, "conf": 0.95})
    # Add a short 3-frame false positive chain near pitch
    for f in (2, 3, 4):
        ball.setdefault(f, []).append({"cx": 880.0 + f * 5.0, "cy": 600.0, "conf": 0.90})

    res = analyse_track(ball, 30.0, SYNTH_CORNERS)
    assert res["evidence"]["hypothesis"] == "H_c"
    assert res["events"]["release"]["frame"] == 10
    assert abs(res["events"]["bounce"]["subframe"] - 24.4) < 0.8
    assert all(pt["x"] > 700.0 for pt in res["track"])


def test_gap_bridge_and_kink_recovery() -> None:
    # Delete 3 detections around bounce and 2 around impact
    drops = {23, 24, 25, 31, 32}
    ball = _make_bouncing_track(noise_px=0.6, seed=31, drop_frames=drops)
    res = analyse_track(ball, 30.0, SYNTH_CORNERS)

    assert res["evidence"]["hypothesis"] in ("H_b", "H_c")
    assert abs(res["events"]["bounce"]["subframe"] - 24.4) < 1.2
    bridge_frames = {pt["frame"] for pt in res["bridge"]}
    assert drops.issubset(bridge_frames)
    assert all(pt["predicted"] and pt["interpolated"] for pt in res["bridge"])


def test_no_contact_selects_hb_and_suppresses_impact() -> None:
    ball = _make_bouncing_track(t_imp=None, t_end=35, noise_px=0.7, seed=41)
    res = analyse_track(ball, 30.0, SYNTH_CORNERS)

    assert res["evidence"]["hypothesis"] == "H_b"
    assert res["events"]["bounce"] is not None
    assert abs(res["events"]["bounce"]["subframe"] - 24.4) < 0.8
    assert res["events"]["impact"] is None


def test_full_toss_selects_ha_no_bounce() -> None:
    rng = np.random.default_rng(51)
    ball: Dict[int, List[Dict[str, Any]]] = {}
    # Smooth airborne full toss: y descends steadily (vy > 0 throughout)
    for f in range(8, 32):
        dt = f - 8
        x = 965.0 - 1.1 * dt + float(rng.normal(0.0, 0.5))
        y = 240.0 + 6.0 * dt + 0.35 * dt * dt + float(rng.normal(0.0, 0.5))
        ball[f] = [{"cx": x, "cy": y, "conf": 0.88}]

    res = analyse_track(ball, 30.0, SYNTH_CORNERS)
    assert res["evidence"]["hypothesis"] == "H_a"
    assert res["events"]["bounce"] is None
    assert res["events"]["impact"] is None


def test_duplicate_frames_and_arm_swing_release_pruning() -> None:
    ball = _make_bouncing_track(t_rel=10, noise_px=0.5, seed=61, dup_at={15, 21})
    x10, y10 = ball[10][0]["cx"], ball[10][0]["cy"]
    # Prepend 3 slow arm-swing detections (< 0.4x S1 speed) right behind release
    ball[7] = [{"cx": x10 + 1.5, "cy": y10 - 6.0, "conf": 0.70}]
    ball[8] = [{"cx": x10 + 1.0, "cy": y10 - 4.0, "conf": 0.72}]
    ball[9] = [{"cx": x10 + 0.5, "cy": y10 - 2.0, "conf": 0.75}]

    res = analyse_track(ball, 30.0, SYNTH_CORNERS)
    assert res["observed"]["dup_frames"] == 2
    assert res["evidence"]["dup_frames"] == 2
    assert res["events"]["release"]["frame"] == 10
