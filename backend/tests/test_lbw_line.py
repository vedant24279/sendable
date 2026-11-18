"""Tests for the line-only LBW prediction (backend/pipeline/lbw_line.py)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from backend.pipeline import lbw_line  # noqa: E402
from backend.pipeline.lbw_line import (  # noqa: E402
    STUMP_HALF_WIDTH_M,
    compute_lbw_line,
    fit_ground_homography,
    lbw_block,
    side,
)

# A broadcast-like camera: corner pixels of the four creases.
CORNERS = {
    "bat_L": [660.0, 520.0],
    "bat_R": [1260.0, 520.0],
    "bowl_L": [520.0, 960.0],
    "bowl_R": [1400.0, 960.0],
}
REL_F, BNC_F, IMP_F = 4, 14, 18


def _ground_to_pixel(H_inv, X, Z):
    w = H_inv[2, 0] * X + H_inv[2, 1] * Z + H_inv[2, 2]
    return (
        (H_inv[0, 0] * X + H_inv[0, 1] * Z + H_inv[0, 2]) / w,
        (H_inv[1, 0] * X + H_inv[1, 1] * Z + H_inv[1, 2]) / w,
    )


def _geometry():
    """(Z_b, post-bounce vz per frame) so the pad is exactly IMPACT_Z_M from the stump line."""
    n_pre, n_post = BNC_F - REL_F, IMP_F - BNC_F
    k = lbw_line.POST_BOUNCE_SPEED_FACTOR
    z_b = (lbw_line.IMPACT_Z_M + k * n_post / n_pre * lbw_line.RELEASE_Z_M) / (1.0 + k * n_post / n_pre)
    vz = k * (lbw_line.RELEASE_Z_M - z_b) / n_pre
    return z_b, vz


def _synthetic(x_b: float, vx: float):
    """Track consistent with the model: pre-bounce speed vz_pre, post-bounce 0.85 vz_pre,
    and the pad exactly IMPACT_Z_M (1.0 m) from the stump line at the impact frame.

    Returns (kwargs for compute_lbw_line, true X_s).
    """
    n_post = IMP_F - BNC_F
    z_b, vz = _geometry()
    _, H_inv = fit_ground_homography(CORNERS)

    traj = []
    for f in range(BNC_F, IMP_F + 1):
        X = x_b + vx * (f - BNC_F)
        Z = z_b - vz * (f - BNC_F)
        u, v = _ground_to_pixel(H_inv, X, Z)
        traj.append({"frame": f, "x": int(round(u)), "y": int(round(v))})
    imp = traj[-1]
    true_xs = (x_b + vx * n_post) + vx * lbw_line.IMPACT_Z_M / vz
    kwargs = dict(
        corners=CORNERS,
        fps=30.0,
        release={"frame": REL_F},
        bounce_centre={"frame": BNC_F, "x": traj[0]["x"], "y": traj[0]["y"]},
        impact={"frame": IMP_F, "x": imp["x"], "y": imp["y"]},
        trajectory=traj,
        trajectory_post=[],
        batter_hand="right",
    )
    return kwargs, true_xs


def test_recovers_xs_within_3cm_and_verdicts_in_line():
    # Drifting toward the stumps from slightly off the line: all three points in line.
    kwargs, true_xs = _synthetic(x_b=0.05, vx=-0.01)
    out = compute_lbw_line(**kwargs)
    assert out is not None and out["mode"] == "line" and out["height"] is None
    assert abs(out["wickets"]["x"] - true_xs) <= 0.03
    assert out["pitching"]["verdict"] == "in_line"
    assert out["impact"]["verdict"] == "in_line"
    assert out["wickets"]["verdict"] == "HITTING"
    assert out["wickets"]["margin_m"] < 0
    assert out["overall"] == "OUT_LINE"
    assert out["slope_flag"] is False


def test_recovers_xs_with_lateral_slope_and_stable_miss():
    # Clear lateral slope that takes the ball well outside the stumps by the stump line.
    kwargs, true_xs = _synthetic(x_b=0.10, vx=0.06)
    out = compute_lbw_line(**kwargs)
    assert abs(out["wickets"]["x"] - true_xs) <= 0.03
    assert out["wickets"]["verdict"] == "MISSING"
    assert out["wickets"]["stable"] is True
    assert out["overall"] == "NOT_OUT_LINE"


def test_umpires_call_band():
    # Choose the slope so that the true X_s sits inside the umpire's-call band (0.1143, 0.1503].
    _, vz = _geometry()
    n_post = IMP_F - BNC_F
    # X_s = vx * n_post + vx / vz * IMPACT_Z_M = 0.13
    vx = 0.13 / (n_post + lbw_line.IMPACT_Z_M / vz)
    kwargs, true_xs = _synthetic(x_b=0.0, vx=vx)
    out = compute_lbw_line(**kwargs)
    assert true_xs == pytest.approx(0.13, abs=1e-9)
    assert out["wickets"]["verdict"] == "UMPIRES_CALL"
    assert out["impact"]["verdict"] == "in_line"
    assert out["overall"] == "UMPIRES_CALL"


def test_no_impact_returns_none():
    kwargs, _ = _synthetic(0.0, 0.0)
    kwargs["impact"] = None
    assert compute_lbw_line(**kwargs) is None


def test_fewer_than_three_points_sets_flag_and_zero_slope():
    kwargs, _ = _synthetic(0.05, 0.02)
    kwargs["trajectory"] = kwargs["trajectory"][:1] + kwargs["trajectory"][-1:]  # 2 points
    out = compute_lbw_line(**kwargs)
    assert out["slope_flag"] is True
    # slope 0: X_s equals the impact lateral position
    assert out["wickets"]["x"] == pytest.approx(out["impact"]["x"], abs=1e-9)


def test_bounce_not_after_release_returns_none():
    kwargs, _ = _synthetic(0.0, 0.0)
    kwargs["release"] = {"frame": BNC_F}
    assert compute_lbw_line(**kwargs) is None


def test_side_sign_depends_only_on_constant(monkeypatch):
    far = 0.5
    # Default constant: off side is image left (X < 0) for a right-hander.
    assert lbw_line.OFF_SIDE_IS_IMAGE_LEFT_FOR_RIGHT_HANDER is True
    assert side(-far, "right") == "off"
    assert side(+far, "right") == "leg"
    assert side(-far, "left") == "leg"
    assert side(+far, "left") == "off"
    assert side(STUMP_HALF_WIDTH_M, "right") == "centre"
    assert side(-STUMP_HALF_WIDTH_M, "left") == "centre"
    assert side(far, None) is None

    monkeypatch.setattr(lbw_line, "OFF_SIDE_IS_IMAGE_LEFT_FOR_RIGHT_HANDER", False)
    assert side(-far, "right") == "leg"
    assert side(+far, "right") == "off"
    assert side(-far, "left") == "off"
    assert side(+far, "left") == "leg"


def test_pitching_outside_leg_depends_on_constant_and_hand(monkeypatch):
    # Pitch 0.4 m to image right; make the impact and slope in line so only pitching matters.
    kwargs, _ = _synthetic(x_b=0.40, vx=-0.10)
    right = compute_lbw_line(**kwargs)  # right-hander: image right = leg side
    assert right["pitching"]["verdict"] == "outside_leg"
    assert right["overall"] == "NOT_OUT_LINE"

    kwargs["batter_hand"] = "left"      # left-hander: image right = off side
    left = compute_lbw_line(**kwargs)
    assert left["pitching"]["verdict"] == "outside_off"
    assert left["pitching"]["side"] == "off"

    monkeypatch.setattr(lbw_line, "OFF_SIDE_IS_IMAGE_LEFT_FOR_RIGHT_HANDER", False)
    kwargs["batter_hand"] = "right"
    flipped = compute_lbw_line(**kwargs)
    assert flipped["pitching"]["verdict"] == "outside_off"


def test_unknown_hand_has_no_side_and_does_not_apply_leg_rule():
    kwargs, _ = _synthetic(x_b=0.40, vx=-0.10)
    kwargs["batter_hand"] = None
    out = compute_lbw_line(**kwargs)
    assert out["batter_hand"] is None
    assert out["pitching"]["side"] is None and out["impact"]["side"] is None
    assert out["pitching"]["verdict"] == "outside_side_unknown"


def _results_from(kwargs):
    return {
        "calibration": kwargs["corners"],
        "video": {"fps": kwargs["fps"]},
        "events": {
            "release": kwargs["release"],
            "bounce": kwargs["bounce_centre"],
            "impact": kwargs["impact"],
        },
        "trajectory": kwargs["trajectory"],
        "trajectory_post": [],
    }


def test_block_absent_unless_mode_is_line():
    kwargs, _ = _synthetic(0.05, -0.01)
    results = _results_from(kwargs)
    assert lbw_block(results, {}) is None
    assert lbw_block(results, {"TRACKER_LBW_MODE": ""}) is None
    assert lbw_block(results, {"TRACKER_LBW_MODE": "off", "TRACKER_BATTER_HAND": "right"}) is None
    # Mimic process.py: the key is only added when the block is not None.
    res = dict(results)
    blk = lbw_block(res, {})
    if blk is not None:
        res["lbw"] = blk
    assert "lbw" not in res

    on = lbw_block(results, {"TRACKER_LBW_MODE": "line", "TRACKER_BATTER_HAND": "right"})
    assert on is not None and on["batter_hand"] == "right"
    unknown = lbw_block(results, {"TRACKER_LBW_MODE": "line"})
    assert unknown["batter_hand"] is None


def test_block_none_without_impact():
    kwargs, _ = _synthetic(0.05, -0.01)
    results = _results_from(kwargs)
    results["events"]["impact"] = None
    assert lbw_block(results, {"TRACKER_LBW_MODE": "line", "TRACKER_BATTER_HAND": "right"}) is None


def test_output_is_json_serialisable():
    import json

    kwargs, _ = _synthetic(0.05, -0.01)
    out = compute_lbw_line(**kwargs)
    json.dumps(out)
    assert out["wickets"]["stable"] in (True, False)
    assert isinstance(out["notes"], list) and len(out["notes"]) >= 2


def test_sigma_includes_model_term_in_quadrature():
    kwargs, _ = _synthetic(0.05, -0.01)
    w = compute_lbw_line(**kwargs)["wickets"]
    assert lbw_line.MODEL_SIGMA_M == pytest.approx(0.07)
    assert w["sigma_stat"] < w["sigma"]
    assert w["sigma"] == pytest.approx(
        math.sqrt(w["sigma_stat"] ** 2 + lbw_line.MODEL_SIGMA_M ** 2), abs=2e-4
    )
    # stable keeps using the combined sigma
    assert w["stable"] == (abs(w["margin_m"]) > 2.0 * w["sigma"])


def test_ground_to_pixel_known_points():
    _, H_inv = fit_ground_homography(CORNERS)
    # The four crease corners project back exactly onto their pixels.
    assert lbw_line.ground_to_pixel(H_inv, -1.32, 1.22) == [660, 520]
    assert lbw_line.ground_to_pixel(H_inv, +1.32, 1.22) == [1260, 520]
    assert lbw_line.ground_to_pixel(H_inv, -1.32, 18.90) == [520, 960]
    assert lbw_line.ground_to_pixel(H_inv, +1.32, 18.90) == [1400, 960]
    # A synthetic interior point matches the reference projection.
    u, v = _ground_to_pixel(H_inv, 0.3, 5.0)
    assert lbw_line.ground_to_pixel(H_inv, 0.3, 5.0) == [int(round(u)), int(round(v))]


def test_pixels_block_matches_homography():
    kwargs, _ = _synthetic(0.05, -0.01)
    out = compute_lbw_line(**kwargs)
    px = out["pixels"]
    _, H_inv = fit_ground_homography(CORNERS)

    def proj(X, Z):
        u, v = _ground_to_pixel(H_inv, X, Z)
        return [int(round(u)), int(round(v))]

    X_b, Z_b = out["pitching"]["x"], out["pitching"]["z"]
    X_i, X_s, s = out["impact"]["x"], out["wickets"]["x"], out["wickets"]["sigma"]
    assert px["stump_base_left"] == proj(-STUMP_HALF_WIDTH_M, 0.0)
    assert px["stump_base_right"] == proj(+STUMP_HALF_WIDTH_M, 0.0)
    for key, (X, Z) in {
        "pitching": (X_b, Z_b),
        "impact_ground": (X_i, lbw_line.IMPACT_Z_M),
        "wickets_centre": (X_s, 0.0),
        "wickets_left": (X_s - s, 0.0),
        "wickets_right": (X_s + s, 0.0),
    }.items():
        got, exp = px[key], proj(X, Z)
        assert abs(got[0] - exp[0]) <= 1 and abs(got[1] - exp[1]) <= 1, key  # inputs rounded to 4 dp
    b0 = lbw_line.pixels_per_metre_across(H_inv, 0.0, 0.0)
    assert px["stump_top_offset_px"] == int(round(0.711 * b0))
    # impact ribbon is +-PIXEL_SIGMA_PX wide around the impact point: 5 px across.
    width = math.hypot(px["impact_right"][0] - px["impact_left"][0],
                       px["impact_right"][1] - px["impact_left"][1])
    assert width == pytest.approx(2 * lbw_line.PIXEL_SIGMA_PX, abs=1.5)
    assert all(isinstance(c, int) for k, v in px.items() if isinstance(v, list) for c in v)
