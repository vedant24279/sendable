"""Line-only LBW prediction from a single broadcast camera.

The single TV camera (about 8 degrees elevation, 65-80 m away) cannot separate
ball height from distance along the pitch, so the height of the ball at the
stumps is NOT recoverable. The lateral (across-pitch) position is robust, so
this module evaluates only the LINE of the delivery:

* where the ball pitched (lateral position of the bounce centre on the ground),
* where it hit the pad (lateral position of the impact pixel on the ground),
* where it would have crossed the stump line (lateral extrapolation).

Geometry: exact 4-point ground homography from the four crease corners using
the Laws of Cricket dimensions (stumps 20.12 m apart, popping creases 1.22 m in
front of the stumps, half width 1.32 m). World frame: X positive toward image
right, Z measured from the batter's stump line toward the bowler.

Pure numpy; no imports from the rest of the pipeline.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

# ── Constants ───────────────────────────────────────────────────────────────
# TO BE CONFIRMED BY THE USER. The whole off/leg sign logic depends only on this
# constant: True means that, for a right-handed batter, the off side is the left
# of the image (X < 0 in the world frame). For a left-hander it is mirrored.
OFF_SIDE_IS_IMAGE_LEFT_FOR_RIGHT_HANDER: bool = True

HALF_WIDTH_M: float = 1.32
BAT_CREASE_Z_M: float = 1.22
BOWL_CREASE_Z_M: float = 18.90

STUMP_HALF_WIDTH_M: float = 0.1143
BALL_RADIUS_M: float = 0.036
UMPIRES_CALL_LIMIT_M: float = STUMP_HALF_WIDTH_M + BALL_RADIUS_M

RELEASE_Z_M: float = 19.5           # release assumed this far from the stump line
POST_BOUNCE_SPEED_FACTOR: float = 0.85
POST_BOUNCE_SPEED_SIGMA_FRAC: float = 0.10   # of vz_pre

IMPACT_Z_M: float = 1.0             # pad to stump line distance (assumed)
IMPACT_Z_SIGMA_M: float = 0.6
PIXEL_SIGMA_PX: float = 2.5         # lateral pixel uncertainty of the impact point
# Dimensionless sigma of dX/dZ used when fewer than 3 points allow a slope fit
# (the slope is then forced to 0 and slope_flag is set).
SLOPE_FLAG_SIGMA_RATIO: float = 0.05
# Provisional model uncertainty on X_s (metres): the line model and the lifted-ballistic
# probe disagree by about 10 cm RMS on X_s, so each carries about 7 cm. To be calibrated
# once not-out clips exist. Added in quadrature to the statistical sigma.
MODEL_SIGMA_M: float = 0.07
STUMP_HEIGHT_M: float = 0.711

_CORNER_KEYS: Tuple[str, ...] = ("bat_L", "bat_R", "bowl_L", "bowl_R")
_WORLD_CORNERS: Dict[str, Tuple[float, float]] = {
    "bat_L": (-HALF_WIDTH_M, BAT_CREASE_Z_M),
    "bat_R": (+HALF_WIDTH_M, BAT_CREASE_Z_M),
    "bowl_L": (-HALF_WIDTH_M, BOWL_CREASE_Z_M),
    "bowl_R": (+HALF_WIDTH_M, BOWL_CREASE_Z_M),
}

NOTES: List[str] = [
    "line only: height not evaluated (single camera)",
    "impact type not classified (pad assumed)",
]


# ── Geometry ────────────────────────────────────────────────────────────────
def fit_ground_homography(corners: Mapping[str, Sequence[float]]) -> Tuple[np.ndarray, np.ndarray]:
    """Exact 4-point homography from the crease corners.

    Returns (H, H_inv): H maps pixel (u, v) -> world (X, Z); H_inv the reverse.
    Raises ValueError when a corner is missing or the configuration is degenerate.
    """
    missing = [k for k in _CORNER_KEYS if k not in corners]
    if missing:
        raise ValueError(f"missing corner points: {missing}")
    A = np.zeros((8, 8), dtype=np.float64)
    b = np.zeros(8, dtype=np.float64)
    for i, key in enumerate(_CORNER_KEYS):
        u, v = float(corners[key][0]), float(corners[key][1])
        X, Z = _WORLD_CORNERS[key]
        A[2 * i] = [u, v, 1.0, 0.0, 0.0, 0.0, -X * u, -X * v]
        b[2 * i] = X
        A[2 * i + 1] = [0.0, 0.0, 0.0, u, v, 1.0, -Z * u, -Z * v]
        b[2 * i + 1] = Z
    try:
        sol = np.linalg.solve(A, b)
    except np.linalg.LinAlgError as exc:
        raise ValueError(f"degenerate corner configuration: {exc}") from exc
    H = np.array(
        [[sol[0], sol[1], sol[2]], [sol[3], sol[4], sol[5]], [sol[6], sol[7], 1.0]],
        dtype=np.float64,
    )
    H_inv = np.linalg.inv(H)
    H_inv = H_inv / H_inv[2, 2]
    return H, H_inv


def pixel_to_ground(H: np.ndarray, u: float, v: float) -> Tuple[float, float]:
    """Map an image pixel to ground (X, Z) in metres."""
    w = H[2, 0] * u + H[2, 1] * v + H[2, 2]
    if abs(w) < 1e-12:
        raise ValueError("pixel maps to infinity")
    return (
        float((H[0, 0] * u + H[0, 1] * v + H[0, 2]) / w),
        float((H[1, 0] * u + H[1, 1] * v + H[1, 2]) / w),
    )


def pixels_per_metre_across(H_inv: np.ndarray, X: float, Z: float) -> float:
    """b = ||dHg/dX|| at ground point (X, Z): horizontal pixels per metre across the pitch."""
    w = H_inv[2, 0] * X + H_inv[2, 1] * Z + H_inv[2, 2]
    u = (H_inv[0, 0] * X + H_inv[0, 1] * Z + H_inv[0, 2]) / w
    v = (H_inv[1, 0] * X + H_inv[1, 1] * Z + H_inv[1, 2]) / w
    du = (H_inv[0, 0] - u * H_inv[2, 0]) / w
    dv = (H_inv[1, 0] - v * H_inv[2, 0]) / w
    return float(math.hypot(du, dv))


def ground_to_pixel(H_inv: np.ndarray, X: float, Z: float) -> Optional[List[int]]:
    """Map ground (X, Z) in metres to an integer image pixel [u, v]; None when it cannot be projected."""
    w = H_inv[2, 0] * X + H_inv[2, 1] * Z + H_inv[2, 2]
    if abs(w) < 1e-12:
        return None
    u = (H_inv[0, 0] * X + H_inv[0, 1] * Z + H_inv[0, 2]) / w
    v = (H_inv[1, 0] * X + H_inv[1, 1] * Z + H_inv[1, 2]) / w
    if not (math.isfinite(u) and math.isfinite(v)):
        return None
    return [int(round(u)), int(round(v))]


def _pixels_block(
    H_inv: np.ndarray,
    X_b: float,
    Z_b: float,
    X_i: float,
    X_s: float,
    sigma: float,
    b_px: float,
) -> Dict[str, Any]:
    """Integer image pixels of the LBW graphic points, all through the ground homography.

    stump_top_offset_px uses the across-pitch scale at the stump base (the ground homography
    carries no vertical information), matching how process.py sizes stumps in pixels.
    """
    half_track = PIXEL_SIGMA_PX / b_px
    b0 = pixels_per_metre_across(H_inv, 0.0, 0.0)
    return {
        "stump_base_left": ground_to_pixel(H_inv, -STUMP_HALF_WIDTH_M, 0.0),
        "stump_base_right": ground_to_pixel(H_inv, +STUMP_HALF_WIDTH_M, 0.0),
        "stump_top_offset_px": int(round(STUMP_HEIGHT_M * b0)) if math.isfinite(b0) else None,
        "pitching": ground_to_pixel(H_inv, X_b, Z_b),
        "impact_ground": ground_to_pixel(H_inv, X_i, IMPACT_Z_M),
        "wickets_centre": ground_to_pixel(H_inv, X_s, 0.0),
        "wickets_left": ground_to_pixel(H_inv, X_s - sigma, 0.0),
        "wickets_right": ground_to_pixel(H_inv, X_s + sigma, 0.0),
        "impact_left": ground_to_pixel(H_inv, X_i - half_track, IMPACT_Z_M),
        "impact_right": ground_to_pixel(H_inv, X_i + half_track, IMPACT_Z_M),
    }


# ── Sides and verdicts ──────────────────────────────────────────────────────
def _off_sign(batter_hand: Optional[str]) -> Optional[int]:
    """Sign of X on the off side (-1 image left, +1 image right); None when the hand is unknown.

    This is the ONLY place that uses OFF_SIDE_IS_IMAGE_LEFT_FOR_RIGHT_HANDER.
    """
    if batter_hand not in ("right", "left"):
        return None
    right_hander_off = -1 if OFF_SIDE_IS_IMAGE_LEFT_FOR_RIGHT_HANDER else +1
    return right_hander_off if batter_hand == "right" else -right_hander_off


def side(X: float, batter_hand: Optional[str]) -> Optional[str]:
    """'off', 'leg' or 'centre' (|X| <= stump half width); None when batter_hand is None."""
    sign = _off_sign(batter_hand)
    if sign is None:
        return None
    if abs(X) <= STUMP_HALF_WIDTH_M:
        return "centre"
    return "off" if (X > 0) == (sign > 0) else "leg"


def _pitching_verdict(X: float, batter_hand: Optional[str]) -> str:
    if abs(X) <= STUMP_HALF_WIDTH_M:
        return "in_line"
    s = side(X, batter_hand)
    if s is None:
        return "outside_side_unknown"
    return "outside_leg" if s == "leg" else "outside_off"


def _impact_verdict(X: float, batter_hand: Optional[str]) -> str:
    ax = abs(X)
    if ax <= STUMP_HALF_WIDTH_M:
        return "in_line"
    if ax <= UMPIRES_CALL_LIMIT_M:
        return "umpires_call"
    s = side(X, batter_hand)
    if s is None:
        return "outside_side_unknown"
    return "outside_leg" if s == "leg" else "outside_off"


def _wickets_verdict(X: float) -> str:
    ax = abs(X)
    if ax <= STUMP_HALF_WIDTH_M:
        return "HITTING"
    if ax <= UMPIRES_CALL_LIMIT_M:
        return "UMPIRES_CALL"
    return "MISSING"


# ── Lateral slope ───────────────────────────────────────────────────────────
def _fit_lateral_slope(frames: Sequence[int], xs: Sequence[float]) -> Tuple[float, float, bool]:
    """Least-squares X = a + vx * frame. Returns (vx m/frame, standard error, slope_flag).

    With fewer than 3 points the slope is 0, the standard error is 0 and the flag is True.
    """
    n = len(frames)
    if n < 3:
        return 0.0, 0.0, True
    f = np.asarray(frames, dtype=np.float64)
    x = np.asarray(xs, dtype=np.float64)
    fc = f - f.mean()
    sxx = float(np.sum(fc * fc))
    if sxx <= 0.0:
        return 0.0, 0.0, True
    vx = float(np.sum(fc * (x - x.mean())) / sxx)
    resid = x - (x.mean() + vx * fc)
    s2 = float(np.sum(resid * resid) / (n - 2))
    return vx, math.sqrt(s2 / sxx), False


def _event_ok(ev: Optional[Mapping[str, Any]], need_xy: bool) -> bool:
    if not ev or ev.get("frame") is None:
        return False
    return (not need_xy) or (ev.get("x") is not None and ev.get("y") is not None)


# ── Public API ──────────────────────────────────────────────────────────────
def compute_lbw_line(
    corners: Mapping[str, Sequence[float]],
    fps: float,
    release: Optional[Mapping[str, Any]],
    bounce_centre: Optional[Mapping[str, Any]],
    impact: Optional[Mapping[str, Any]],
    trajectory: Sequence[Mapping[str, Any]],
    trajectory_post: Optional[Sequence[Mapping[str, Any]]],
    batter_hand: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Line-only LBW prediction. See the module docstring.

    Args:
        corners: calibration pixels with bat_L, bat_R, bowl_L, bowl_R.
        fps: video frame rate (kept for the caller's context; the model works per frame).
        release: events.release dict (needs "frame").
        bounce_centre: events.bounce dict (needs "frame"; "x"/"y" is the fallback pixel when
            the trajectory has no point at the bounce frame). The bounce CENTRE pixel is the
            trajectory point at the bounce frame.
        impact: events.impact dict (needs "frame", "x", "y").
        trajectory: results.json trajectory points {"frame", "x", "y"}.
        trajectory_post: post-impact points (not used by the line model).
        batter_hand: "right", "left" or None.

    Returns:
        The lbw dict, or None when there is no impact event or when the delivery timing cannot
        be established (no release/bounce, bounce not after release, or bounce not in front of
        the assumed release distance).
    """
    if not _event_ok(impact, need_xy=True):
        return None
    if not _event_ok(release, need_xy=False) or not _event_ok(bounce_centre, need_xy=False):
        return None
    hand = batter_hand if batter_hand in ("right", "left") else None

    H, H_inv = fit_ground_homography(corners)

    rel_f = int(release["frame"])
    bnc_f = int(bounce_centre["frame"])
    imp_f = int(impact["frame"])
    if bnc_f <= rel_f:
        return None

    # 1. Pitching: bounce centre pixel -> ground.
    by_frame = {int(p["frame"]): p for p in trajectory if p.get("frame") is not None}
    if bnc_f in by_frame:
        bu, bv = float(by_frame[bnc_f]["x"]), float(by_frame[bnc_f]["y"])
    elif bounce_centre.get("x") is not None and bounce_centre.get("y") is not None:
        bu, bv = float(bounce_centre["x"]), float(bounce_centre["y"])
    else:
        return None
    X_b, Z_b = pixel_to_ground(H, bu, bv)

    vz_pre = (RELEASE_Z_M - Z_b) / (bnc_f - rel_f)
    if vz_pre <= 0.0:
        return None
    vz = POST_BOUNCE_SPEED_FACTOR * vz_pre
    sigma_vz = POST_BOUNCE_SPEED_SIGMA_FRAC * vz_pre

    # 2. Impact: only the lateral position is valid.
    X_i, _z_unused = pixel_to_ground(H, float(impact["x"]), float(impact["y"]))

    # 3. Lateral slope from the bounce frame to the impact frame.
    seg = sorted(
        (f, p) for f, p in by_frame.items() if bnc_f <= f <= imp_f
    )
    frames = [f for f, _ in seg]
    xs = [pixel_to_ground(H, float(p["x"]), float(p["y"]))[0] for _, p in seg]
    vx, se_vx, slope_flag = _fit_lateral_slope(frames, xs)

    ratio = vx / vz
    X_s = X_i + ratio * IMPACT_Z_M

    # 4. Uncertainty (metres).
    if slope_flag:
        sigma_ratio = SLOPE_FLAG_SIGMA_RATIO
    else:
        sigma_ratio = math.sqrt((se_vx / vz) ** 2 + (ratio * sigma_vz / vz) ** 2)
    b_px = pixels_per_metre_across(H_inv, X_i, IMPACT_Z_M)
    sigma_stat = math.sqrt(
        (PIXEL_SIGMA_PX / b_px) ** 2
        + (IMPACT_Z_SIGMA_M * abs(ratio)) ** 2
        + (IMPACT_Z_M * sigma_ratio) ** 2
    )
    sigma = math.sqrt(sigma_stat ** 2 + MODEL_SIGMA_M ** 2)

    # 5-6. Sides and verdicts.
    p_verdict = _pitching_verdict(X_b, hand)
    i_verdict = _impact_verdict(X_i, hand)
    w_verdict = _wickets_verdict(X_s)
    margin = abs(X_s) - STUMP_HALF_WIDTH_M
    stable = bool(abs(margin) > 2.0 * sigma)

    stable_miss = w_verdict == "MISSING" and stable
    if (
        p_verdict == "outside_leg"
        or i_verdict.startswith("outside")
        or stable_miss
    ):
        overall = "NOT_OUT_LINE"
    elif i_verdict == "umpires_call" or w_verdict == "UMPIRES_CALL":
        overall = "UMPIRES_CALL"
    else:
        overall = "OUT_LINE"

    notes = list(NOTES)
    if hand is None:
        notes.append("batter_hand unknown: pitching/impact side not evaluated")
    if slope_flag:
        notes.append("fewer than 3 points between bounce and impact: lateral slope set to 0")

    return {
        "mode": "line",
        "batter_hand": hand,
        "pitching": {
            "x": round(X_b, 4),
            "z": round(Z_b, 4),
            "side": side(X_b, hand),
            "verdict": p_verdict,
        },
        "impact": {
            "x": round(X_i, 4),
            "side": side(X_i, hand),
            "verdict": i_verdict,
        },
        "wickets": {
            "x": round(X_s, 4),
            "sigma": round(sigma, 4),
            "sigma_stat": round(sigma_stat, 4),
            "verdict": w_verdict,
            "margin_m": round(margin, 4),
            "stable": stable,
        },
        "height": None,
        "overall": overall,
        "notes": notes,
        "slope_flag": bool(slope_flag),
        "pixels": _pixels_block(H_inv, X_b, Z_b, X_i, X_s, sigma, b_px),
    }


def lbw_block(results: Mapping[str, Any], env: Mapping[str, str]) -> Optional[Dict[str, Any]]:
    """The results.json "lbw" block, or None.

    Active only when env TRACKER_LBW_MODE == "line"; the batter hand comes from
    TRACKER_BATTER_HAND ("right" / "left"; anything else is None). Returns None
    when the mode is off, the calibration is incomplete, or compute_lbw_line returns None.
    """
    if env.get("TRACKER_LBW_MODE", "").strip().lower() != "line":
        return None
    hand = env.get("TRACKER_BATTER_HAND", "").strip().lower() or None
    events = results.get("events") or {}
    try:
        return compute_lbw_line(
            corners=results.get("calibration") or {},
            fps=float((results.get("video") or {}).get("fps") or 0.0),
            release=events.get("release"),
            bounce_centre=events.get("bounce"),
            impact=events.get("impact"),
            trajectory=results.get("trajectory") or [],
            trajectory_post=results.get("trajectory_post"),
            batter_hand=hand,
        )
    except ValueError:
        return None
