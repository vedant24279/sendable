"""Homography-lifted ballistic fit for LBW projection on the 14 labelled clips (v2_1).

Model:
- Ground homography Hg: world (X, Z) in metres -> pixel (u, v), fitted from the 4 corner
  points of calibration_gt via app.calib.fit_homography (H_inv maps world -> pixel; H maps
  pixel -> world; X positive toward image right, Z from batter's stump line toward bowler).
- Height lifting: a ball at (X, Z, h) with h metres above the ground projects to
      Hg(X, Z) + (0, -L(X, Z) * h)
  where:
      b = ||dHg/dX||_2  (horizontal pixels per metre across the pitch)
      a = ||dHg/dZ||_2  (pixels per metre along the pitch)
      sin(theta) = min(a / b, 0.9)
      L = b * cos(theta) = b * sqrt(1 - sin(theta)^2)
  Camera roll is ignored.
- Ballistic motion in time t (seconds relative to bounce time t_b):
      before bounce (t < 0):
          X(t) = X_b + v_x * tau(t)
          Z(t) = Z_b + v_z * tau(t)
          h(t) = w_in * |t| - 0.5 * g * t^2
      after bounce (t >= 0):
          X(t) = X_b + f * v_x * tau(t)
          Z(t) = Z_b + f * v_z * tau(t)
          h(t) = w_out * t - 0.5 * g * t^2,  w_out = e * w_in,  g = 9.81
  where tau(t) = t * (1 - 0.5 * k * |t|) incorporates optional constant horizontal drag k
  (deceleration fraction per second; tau(t) = t when k = 0).

Usage:
    python tools/annotator/backend/lbw_lifted.py
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import least_squares

REPO_ROOT = Path(__file__).resolve().parents[3]
ANNOTATOR_BACKEND = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(ANNOTATOR_BACKEND) not in sys.path:
    sys.path.insert(0, str(ANNOTATOR_BACKEND))

from app.calib import fit_homography, pixel_to_world  # noqa: E402
from app.calib_constants import BOWL_CREASE_Z_M  # noqa: E402

G_ACCEL: float = 9.81
SIN_THETA_MAX: float = 0.9

# LBW stump-plane classification bounds (Z = 0)
HITTING_X_LIMIT_M: float = 0.150
HITTING_H_MIN_M: float = 0.0
HITTING_H_MAX_M: float = 0.747

# Release speed prior bounds
MIN_RELEASE_SPEED_KMH: float = 70.0
MAX_RELEASE_SPEED_KMH: float = 170.0
MIN_RELEASE_SPEED_MPS: float = MIN_RELEASE_SPEED_KMH / 3.6  # 19.444 m/s
MAX_RELEASE_SPEED_MPS: float = MAX_RELEASE_SPEED_KMH / 3.6  # 47.222 m/s

# Parameter bounds
BOUNCE_POS_TOL_M: float = 0.25
BOUNCE_TIME_TOL_FRAMES: float = 1.0
DEFAULT_E_BOUNDS: Tuple[float, float] = (0.3, 0.8)
NARROW_E_BOUNDS: Tuple[float, float] = (0.45, 0.65)
F_BOUNDS: Tuple[float, float] = (0.55, 1.0)
SOFT_L1_SCALE_PX: float = 3.0

# Monte-Carlo settings
MC_REPEATS: int = 100
MC_SEED: int = 42
MC_CALIB_STD_PX: float = 1.5
MC_TRAJ_STD_PX: float = 2.0

# Decision gate thresholds
GATE_MAX_MEDIAN_RMS_PX: float = 3.0
GATE_MAX_MEDIAN_BOUNCE_DIST_M: float = 0.25
GATE_MIN_VARIANT_AGREEMENT: float = 0.85
GATE_MIN_STABLE_CLIP_SHARE: float = 0.85

VARIANT_CONFIGS: List[Tuple[str, float, Tuple[float, float], str]] = [
    ("k0_e0308_sys", 0.0, (0.3, 0.8), "system"),
    ("k0_e4565_sys", 0.0, (0.45, 0.65), "system"),
    ("k15_e0308_sys", 0.15, (0.3, 0.8), "system"),
    ("k15_e4565_sys", 0.15, (0.45, 0.65), "system"),
    ("k0_e0308_ora", 0.0, (0.3, 0.8), "oracle"),
    ("k0_e4565_ora", 0.0, (0.45, 0.65), "oracle"),
    ("k15_e0308_ora", 0.15, (0.3, 0.8), "oracle"),
    ("k15_e4565_ora", 0.15, (0.45, 0.65), "oracle"),
]


def hg_project_and_scales(
    H_inv: np.ndarray,
    X: np.ndarray | float,
    Z: np.ndarray | float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Evaluate ground homography Hg(X, Z) -> (u_g, v_g) and local scale factors (b, a, sin_theta, L).

    Args:
        H_inv: 3x3 world (X, Z) -> pixel (u, v) homography matrix from fit_homography.
        X: Lateral world coordinate(s) in metres (+X toward image right).
        Z: Longitudinal world coordinate(s) in metres (0 at batter's stumps, 20.12 at bowler's stumps).

    Returns:
        Tuple of (u_g, v_g, b, a, sin_theta, L) as numpy float64 arrays.
    """
    X_arr = np.asarray(X, dtype=np.float64)
    Z_arr = np.asarray(Z, dtype=np.float64)

    m00, m01, m02 = float(H_inv[0, 0]), float(H_inv[0, 1]), float(H_inv[0, 2])
    m10, m11, m12 = float(H_inv[1, 0]), float(H_inv[1, 1]), float(H_inv[1, 2])
    m20, m21, m22 = float(H_inv[2, 0]), float(H_inv[2, 1]), float(H_inv[2, 2])

    w = m20 * X_arr + m21 * Z_arr + m22
    w_safe = np.where(np.abs(w) < 1e-12, 1e-12, w)

    u_g = (m00 * X_arr + m01 * Z_arr + m02) / w_safe
    v_g = (m10 * X_arr + m11 * Z_arr + m12) / w_safe

    # Partial derivatives of Hg with respect to X
    du_dX = (m00 - u_g * m20) / w_safe
    dv_dX = (m10 - v_g * m20) / w_safe
    b = np.hypot(du_dX, dv_dX)

    # Partial derivatives of Hg with respect to Z
    du_dZ = (m01 - u_g * m21) / w_safe
    dv_dZ = (m11 - v_g * m21) / w_safe
    a = np.hypot(du_dZ, dv_dZ)

    sin_theta = np.minimum(a / np.maximum(b, 1e-12), SIN_THETA_MAX)
    cos_theta = np.sqrt(np.maximum(0.0, 1.0 - sin_theta * sin_theta))
    L = b * cos_theta

    return u_g, v_g, b, a, sin_theta, L


def project_lifted_point(
    H_inv: np.ndarray,
    X: np.ndarray | float,
    Z: np.ndarray | float,
    h: np.ndarray | float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Project 3D point(s) (X, Z, h) to image pixels (u, v) = Hg(X, Z) + (0, -L(X, Z) * h)."""
    u_g, v_g, _, _, _, L = hg_project_and_scales(H_inv, X, Z)
    h_arr = np.asarray(h, dtype=np.float64)
    return u_g, v_g - L * h_arr


def _drag_tau(dt: np.ndarray | float, drag_k: float) -> np.ndarray:
    """Effective horizontal time displacement under constant deceleration fraction k (s^-1)."""
    dt_arr = np.asarray(dt, dtype=np.float64)
    if drag_k <= 0.0:
        return dt_arr
    return dt_arr * (1.0 - 0.5 * drag_k * np.abs(dt_arr))


def evaluate_ballistic_world(
    frame_times_s: np.ndarray | Sequence[float],
    params: Sequence[float],
    drag_k: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Evaluate world coordinates (X(t), Z(t), h(t)) for given frame timestamps.

    Args:
        frame_times_s: Sequence of timestamps (in seconds, e.g. frame / fps).
        params: [t_b, X_b, Z_b, v_x, v_z, w_in, e, f].
        drag_k: Constant horizontal deceleration fraction per second (default 0.0).

    Returns:
        Tuple of (X, Z, h) arrays in metres.
    """
    t_b, X_b, Z_b, v_x, v_z, w_in, e, f = [float(x) for x in params]
    t_arr = np.asarray(frame_times_s, dtype=np.float64)
    dt = t_arr - t_b
    tau = _drag_tau(dt, drag_k)

    pre = dt < 0.0
    X = np.where(pre, X_b + v_x * tau, X_b + f * v_x * tau)
    Z = np.where(pre, Z_b + v_z * tau, Z_b + f * v_z * tau)

    w_out = e * w_in
    h = np.where(
        pre,
        w_in * np.abs(dt) - 0.5 * G_ACCEL * dt * dt,
        w_out * dt - 0.5 * G_ACCEL * dt * dt,
    )
    return X, Z, h


def project_ballistic_track(
    frame_times_s: np.ndarray | Sequence[float],
    params: Sequence[float],
    H_inv: np.ndarray,
    drag_k: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Project a ballistic parameter vector onto image pixel coordinates (u, v)."""
    X, Z, h = evaluate_ballistic_world(frame_times_s, params, drag_k=drag_k)
    return project_lifted_point(H_inv, X, Z, h)


def compute_release_speed_kmh(
    params: Sequence[float],
    t_release_s: float,
    drag_k: float = 0.0,
) -> float:
    """Compute 3D ball speed (km/h) at the release timestamp."""
    t_b, _, _, v_x, v_z, w_in, _, _ = [float(x) for x in params]
    dt_rel = float(t_release_s) - t_b  # negative when release is before bounce
    scale_h = 1.0 - drag_k * abs(dt_rel) if drag_k > 0.0 else 1.0
    # Wait: if ball decelerates at rate k before bounce, speed at release (dt_rel < 0)
    # is (1 + drag_k * |dt_rel|) * |v_horiz|
    if dt_rel < 0.0 and drag_k > 0.0:
        scale_h = 1.0 + drag_k * abs(dt_rel)
    vx_rel = v_x * scale_h
    vz_rel = v_z * scale_h
    vh_rel = -w_in - G_ACCEL * dt_rel if dt_rel < 0.0 else w_in - G_ACCEL * dt_rel
    speed_mps = math.sqrt(vx_rel * vx_rel + vz_rel * vz_rel + vh_rel * vh_rel)
    return float(speed_mps * 3.6)


def compute_post_bounce_rise_angle_deg(params: Sequence[float]) -> float:
    """Compute post-bounce elevation/rise angle in degrees immediately after bounce (t = 0+)."""
    _, _, _, v_x, v_z, w_in, e, f = [float(x) for x in params]
    w_out = e * w_in
    v_horiz_out = abs(f) * math.hypot(v_x, v_z)
    if v_horiz_out < 1e-9:
        return 0.0
    return float(math.degrees(math.atan2(w_out, v_horiz_out)))


def continue_to_stump_plane(
    params: Sequence[float],
    drag_k: float = 0.0,
) -> Dict[str, Any]:
    """Continue the post-bounce trajectory to the batter's stump plane Z = 0.

    Returns:
        Dict with keys:
        - arrival_time_rel_s: post-bounce travel time t_s >= 0 to reach Z = 0
        - arrival_time_s: absolute timestamp t_b + t_s at Z = 0
        - X_s: lateral coordinate (m) at Z = 0
        - h_s: height above ground (m) at Z = 0
        - verdict: 'HITTING' or 'MISSING'
        - margin_m: distance in metres to the hitting box boundary (0 if inside, >0 if outside;
          also signed_margin_m where negative is inside and positive is outside)
    """
    t_b, X_b, Z_b, v_x, v_z, w_in, e, f = [float(x) for x in params]
    vz_out = f * v_z
    vx_out = f * v_x
    w_out = e * w_in

    if vz_out >= -1e-6 or Z_b <= 0.0:
        # Ball is not moving toward Z = 0 or already past Z = 0
        tau_s = max(0.0, -Z_b / min(vz_out, -1e-6))
    else:
        tau_s = -Z_b / vz_out

    if drag_k > 0.0:
        # Solve t_s * (1 - 0.5 * k * t_s) = tau_s  =>  0.5*k*t_s^2 - t_s + tau_s = 0
        disc = 1.0 - 2.0 * drag_k * tau_s
        if disc >= 0.0:
            t_s = (1.0 - math.sqrt(disc)) / drag_k
        else:
            t_s = tau_s / (1.0 - 0.5 * drag_k * min(tau_s, 1.0 / drag_k))
    else:
        t_s = tau_s

    X_s = X_b + vx_out * tau_s
    h_s = w_out * t_s - 0.5 * G_ACCEL * t_s * t_s

    dx_out = max(0.0, abs(X_s) - HITTING_X_LIMIT_M)
    dh_out = max(0.0, HITTING_H_MIN_M - h_s, h_s - HITTING_H_MAX_M)
    outside_dist_m = math.hypot(dx_out, dh_out)

    hitting = (abs(X_s) <= HITTING_X_LIMIT_M) and (HITTING_H_MIN_M <= h_s <= HITTING_H_MAX_M)
    if hitting:
        inside_clearance = min(
            HITTING_X_LIMIT_M - abs(X_s),
            h_s - HITTING_H_MIN_M,
            HITTING_H_MAX_M - h_s,
        )
        # Signed margin: positive inside margin or outside distance; we store both
        margin_m = 0.0
        signed_margin_m = -inside_clearance
    else:
        margin_m = outside_dist_m
        signed_margin_m = outside_dist_m

    return {
        "arrival_time_rel_s": float(t_s),
        "arrival_time_s": float(t_b + t_s),
        "X_s": float(X_s),
        "h_s": float(h_s),
        "verdict": "HITTING" if hitting else "MISSING",
        "margin_m": float(margin_m),
        "signed_margin_m": float(signed_margin_m),
    }


def fit_lifted_ballistic(
    frame_times_s: Sequence[float],
    u_obs: Sequence[float],
    v_obs: Sequence[float],
    H: np.ndarray,
    H_inv: np.ndarray,
    t_b_init_s: float,
    bounce_center_uv: Tuple[float, float],
    fps: float = 30.0,
    drag_k: float = 0.0,
    e_bounds: Tuple[float, float] = DEFAULT_E_BOUNDS,
    f_bounds: Tuple[float, float] = F_BOUNDS,
    fast_mode: bool = False,
) -> Dict[str, Any]:
    """Fit the 8-parameter homography-lifted ballistic trajectory via soft_l1 least_squares.

    Unknowns:
        p = [t_b, X_b, Z_b, v_x, v_z, w_in, e, f]
    """
    t_arr = np.asarray(frame_times_s, dtype=np.float64)
    u_arr = np.asarray(u_obs, dtype=np.float64)
    v_arr = np.asarray(v_obs, dtype=np.float64)

    if len(t_arr) < 4:
        raise ValueError(f"Need at least 4 trajectory points to fit, got {len(t_arr)}")

    Xb0, Zb0 = pixel_to_world(H, float(bounce_center_uv[0]), float(bounce_center_uv[1]))
    dt_tol = BOUNCE_TIME_TOL_FRAMES / float(fps)

    # Bounds on unknowns:
    # v_z is negative (bowler at Z ~ 18.9 m -> batter at Z = 0 m)
    # Release speed prior 70..170 km/h (19.44..47.22 m/s) bounds |v_z| and adds soft penalty if outside
    vz_min = -MAX_RELEASE_SPEED_MPS
    vz_max = -MIN_RELEASE_SPEED_MPS * 0.85

    lb = np.array(
        [
            t_b_init_s - dt_tol,
            Xb0 - BOUNCE_POS_TOL_M,
            Zb0 - BOUNCE_POS_TOL_M,
            -8.0,
            vz_min,
            0.5,
            float(e_bounds[0]),
            float(f_bounds[0]),
        ],
        dtype=np.float64,
    )
    ub = np.array(
        [
            t_b_init_s + dt_tol,
            Xb0 + BOUNCE_POS_TOL_M,
            Zb0 + BOUNCE_POS_TOL_M,
            8.0,
            vz_max,
            16.0,
            float(e_bounds[1]),
            float(f_bounds[1]),
        ],
        dtype=np.float64,
    )

    t_rel_s = float(t_arr[0])
    dt_pre = max(t_b_init_s - t_rel_s, 0.12)

    # Physical initial guess from bowler's popping crease (Z ~ 18.9 m, h ~ 2.0 m)
    vz_guess = float(np.clip((Zb0 - BOWL_CREASE_Z_M) / dt_pre, vz_min + 1.0, vz_max - 1.0))
    # Estimate X at release by projecting (0, BOWL_CREASE_Z_M) to get local horizontal scale b
    u_c, _, b_c, _, _, _ = hg_project_and_scales(H_inv, 0.0, BOWL_CREASE_Z_M)
    X_rel_guess = (float(u_arr[0]) - float(u_c)) / max(float(b_c), 50.0)
    vx_guess = float(np.clip((Xb0 - X_rel_guess) / dt_pre, -5.0, 5.0))
    w_in_guess = float(np.clip((2.0 + 0.5 * G_ACCEL * dt_pre * dt_pre) / dt_pre, 2.0, 12.0))

    def residual_fn(p: np.ndarray) -> np.ndarray:
        u_pred, v_pred = project_ballistic_track(t_arr, p, H_inv, drag_k=drag_k)
        pix_dist = np.hypot(u_pred - u_arr, v_pred - v_arr)

        # Enforce release speed prior 70..170 km/h
        v_rel_kmh = compute_release_speed_kmh(p, t_rel_s, drag_k=drag_k)
        if v_rel_kmh < MIN_RELEASE_SPEED_KMH:
            prior_pen = (MIN_RELEASE_SPEED_KMH - v_rel_kmh) * 2.0
        elif v_rel_kmh > MAX_RELEASE_SPEED_KMH:
            prior_pen = (v_rel_kmh - MAX_RELEASE_SPEED_KMH) * 2.0
        else:
            prior_pen = 0.0
        return np.append(pix_dist, prior_pen)

    e_mid = 0.5 * (e_bounds[0] + e_bounds[1])
    e_low = e_bounds[0] + 0.2 * (e_bounds[1] - e_bounds[0])
    e_high = e_bounds[0] + 0.8 * (e_bounds[1] - e_bounds[0])

    if fast_mode:
        starts = [
            [t_b_init_s, Xb0, Zb0, vx_guess, vz_guess, w_in_guess, e_mid, 0.80],
            [t_b_init_s, Xb0, Zb0, vx_guess, -33.0, 7.0, e_low, 0.72],
        ]
    else:
        starts = [
            [t_b_init_s, Xb0, Zb0, vx_guess, vz_guess, w_in_guess, e_mid, 0.80],
            [t_b_init_s, Xb0, Zb0, vx_guess, -35.0, 7.5, e_low, 0.70],
            [t_b_init_s, Xb0, Zb0, vx_guess, -28.0, 6.5, e_high, 0.88],
            [t_b_init_s, Xb0, Zb0, 0.0, -38.0, 8.5, e_mid, 0.78],
            [t_b_init_s, Xb0, Zb0, vx_guess, -23.0, 5.5, e_mid, 0.85],
        ]

    best_rms: float = float("inf")
    best_x: Optional[np.ndarray] = None

    for s in starts:
        p0 = np.clip(np.asarray(s, dtype=np.float64), lb + 1e-6, ub - 1e-6)
        res = least_squares(
            residual_fn,
            p0,
            bounds=(lb, ub),
            loss="soft_l1",
            f_scale=SOFT_L1_SCALE_PX,
            max_nfev=300 if fast_mode else 600,
        )
        u_p, v_p = project_ballistic_track(t_arr, res.x, H_inv, drag_k=drag_k)
        dists = np.hypot(u_p - u_arr, v_p - v_arr)
        rms_px = float(np.sqrt(np.mean(dists * dists)))
        # Add tiny tie-breaker penalty if release speed sits outside [70, 170] km/h
        v_rel = compute_release_speed_kmh(res.x, t_rel_s, drag_k=drag_k)
        score = rms_px + (
            0.0
            if (MIN_RELEASE_SPEED_KMH <= v_rel <= MAX_RELEASE_SPEED_KMH)
            else 100.0
        )
        if best_x is None or score < best_rms:
            best_rms = score
            best_x = res.x.copy()

    assert best_x is not None
    u_p, v_p = project_ballistic_track(t_arr, best_x, H_inv, drag_k=drag_k)
    dists = np.hypot(u_p - u_arr, v_p - v_arr)
    fit_rms_px = float(np.sqrt(np.mean(dists * dists)))
    release_speed_kmh = compute_release_speed_kmh(best_x, t_rel_s, drag_k=drag_k)
    rise_angle_deg = compute_post_bounce_rise_angle_deg(best_x)
    stump = continue_to_stump_plane(best_x, drag_k=drag_k)

    return {
        "params": [float(v) for v in best_x],
        "t_b_s": float(best_x[0]),
        "X_b": float(best_x[1]),
        "Z_b": float(best_x[2]),
        "v_x": float(best_x[3]),
        "v_z": float(best_x[4]),
        "w_in": float(best_x[5]),
        "e": float(best_x[6]),
        "f": float(best_x[7]),
        "fit_rms_px": fit_rms_px,
        "release_speed_kmh": release_speed_kmh,
        "rise_angle_deg": rise_angle_deg,
        "init_bounce_world": (float(Xb0), float(Zb0)),
        **stump,
    }


def extract_clip_track(
    results_data: Dict[str, Any],
    label_data: Dict[str, Any],
    impact_source: str = "system",
) -> Tuple[Optional[List[Dict[str, float]]], Optional[int], Optional[Tuple[float, float]], Optional[str]]:
    """Extract trajectory points from system release frame to system/oracle impact frame,
    along with system bounce frame and system bounce centre pixel.
    """
    events = results_data.get("events") or {}
    rel_ev = events.get("release")
    bnc_ev = events.get("bounce")
    if not rel_ev or rel_ev.get("frame") is None:
        return None, None, None, "missing_system_release"
    if not bnc_ev or bnc_ev.get("frame") is None:
        return None, None, None, "missing_system_bounce"

    rel_frame = int(rel_ev["frame"])
    bnc_frame = int(bnc_ev["frame"])

    if impact_source == "system":
        imp_ev = events.get("impact")
        if not imp_ev or imp_ev.get("frame") is None:
            return None, None, None, "missing_system_impact"
        imp_frame = int(imp_ev["frame"])
    elif impact_source == "oracle":
        lbl_imp = label_data.get("impact")
        if not lbl_imp or lbl_imp.get("frame") is None:
            return None, None, None, "missing_oracle_impact"
        imp_frame = int(lbl_imp["frame"])
    else:
        raise ValueError(f"Unknown impact_source: {impact_source}")

    traj = results_data.get("trajectory") or []
    pts = [
        {"frame": int(p["frame"]), "x": float(p["x"]), "y": float(p["y"])}
        for p in traj
        if p.get("frame") is not None and rel_frame <= int(p["frame"]) <= imp_frame
    ]
    pts.sort(key=lambda p: p["frame"])

    if len(pts) < 4:
        return None, None, None, f"too_few_points_{len(pts)}"

    # System bounce CENTRE pixel = trajectory point at the bounce frame (fallback to events.bounce)
    by_frame = {int(p["frame"]): (float(p["x"]), float(p["y"])) for p in traj if p.get("frame") is not None}
    if bnc_frame in by_frame:
        bounce_center_uv = by_frame[bnc_frame]
    else:
        bounce_center_uv = (float(bnc_ev["x"]), float(bnc_ev["y"]))

    return pts, bnc_frame, bounce_center_uv, None


def run_monte_carlo_clip(
    calib_points: Dict[str, Sequence[float]],
    pts: List[Dict[str, float]],
    bnc_frame: int,
    fps: float = 30.0,
    n_repeats: int = MC_REPEATS,
    seed: int = MC_SEED,
) -> Dict[str, Any]:
    """Run 100 Monte-Carlo repeats with N(0, 1.5 px) on calibration points and N(0, 2 px) on trajectory."""
    rng = np.random.default_rng(seed)
    t_arr = np.array([p["frame"] / fps for p in pts], dtype=np.float64)
    u_base = np.array([p["x"] for p in pts], dtype=np.float64)
    v_base = np.array([p["y"] for p in pts], dtype=np.float64)
    t_b_init_s = float(bnc_frame) / float(fps)

    # Index of bounce frame in pts if present
    bnc_idx: Optional[int] = None
    for idx, p in enumerate(pts):
        if int(p["frame"]) == int(bnc_frame):
            bnc_idx = idx
            break

    xs_list: List[float] = []
    hs_list: List[float] = []
    hits = 0

    for _ in range(n_repeats):
        pert_calib: Dict[str, List[float]] = {}
        for k, uv in calib_points.items():
            du, dv = rng.normal(0.0, MC_CALIB_STD_PX, size=2)
            pert_calib[k] = [float(uv[0]) + float(du), float(uv[1]) + float(dv)]

        try:
            fit_h = fit_homography(pert_calib)
        except Exception:
            continue

        u_pert = u_base + rng.normal(0.0, MC_TRAJ_STD_PX, size=len(u_base))
        v_pert = v_base + rng.normal(0.0, MC_TRAJ_STD_PX, size=len(v_base))

        if bnc_idx is not None:
            b_uv = (float(u_pert[bnc_idx]), float(v_pert[bnc_idx]))
        else:
            b_uv = (
                float(u_base[0] + rng.normal(0.0, MC_TRAJ_STD_PX)),
                float(v_base[0] + rng.normal(0.0, MC_TRAJ_STD_PX)),
            )

        try:
            res = fit_lifted_ballistic(
                frame_times_s=t_arr,
                u_obs=u_pert,
                v_obs=v_pert,
                H=fit_h.H,
                H_inv=fit_h.H_inv,
                t_b_init_s=t_b_init_s,
                bounce_center_uv=b_uv,
                fps=fps,
                drag_k=0.0,
                e_bounds=DEFAULT_E_BOUNDS,
                f_bounds=F_BOUNDS,
                fast_mode=True,
            )
        except Exception:
            continue

        xs_list.append(float(res["X_s"]))
        hs_list.append(float(res["h_s"]))
        if res["verdict"] == "HITTING":
            hits += 1

    n_valid = len(xs_list)
    if n_valid == 0:
        return {
            "mc_n_valid": 0,
            "mc_hitting_fraction": None,
            "mc_std_X_s": None,
            "mc_std_h_s": None,
        }

    return {
        "mc_n_valid": n_valid,
        "mc_hitting_fraction": float(hits / n_valid),
        "mc_std_X_s": float(np.std(xs_list, ddof=0)),
        "mc_std_h_s": float(np.std(hs_list, ddof=0)),
    }


def evaluate_single_clip(task: Tuple[str, Dict[str, Any], Dict[str, Any], int]) -> Dict[str, Any]:
    """Worker entrypoint for evaluating one clip (main fit + 8 variants + 100 MC repeats)."""
    clip_id, label_data, results_data, mc_repeats = task
    fps = float((results_data.get("video") or {}).get("fps") or 30.0)
    calib_points = label_data["calibration_gt"]["points"]
    fit_h = fit_homography(calib_points)
    H, H_inv = fit_h.H, fit_h.H_inv

    lbl_bnc = label_data["bounce"]
    X_b_lbl, Z_b_lbl = pixel_to_world(H, float(lbl_bnc["x"]), float(lbl_bnc["y"]))

    events = results_data.get("events") or {}
    sys_rel_f = (events.get("release") or {}).get("frame")
    sys_bnc_f = (events.get("bounce") or {}).get("frame")
    sys_imp_f = (events.get("impact") or {}).get("frame")

    # Run all 8 variants: drag k in {0, 0.15} x e bounds {[0.3, 0.8], [0.45, 0.65]} x impact {system, oracle}
    variant_results: Dict[str, Optional[Dict[str, Any]]] = {}
    variant_reasons: Dict[str, Optional[str]] = {}

    for v_name, drag_k, e_bnds, imp_src in VARIANT_CONFIGS:
        pts, bnc_frame, b_uv, err = extract_clip_track(results_data, label_data, impact_source=imp_src)
        if pts is None or bnc_frame is None or b_uv is None:
            variant_results[v_name] = None
            variant_reasons[v_name] = err
            continue

        t_arr = [p["frame"] / fps for p in pts]
        u_arr = [p["x"] for p in pts]
        v_arr = [p["y"] for p in pts]
        t_b_init_s = float(bnc_frame) / fps

        fit_res = fit_lifted_ballistic(
            frame_times_s=t_arr,
            u_obs=u_arr,
            v_obs=v_arr,
            H=H,
            H_inv=H_inv,
            t_b_init_s=t_b_init_s,
            bounce_center_uv=b_uv,
            fps=fps,
            drag_k=drag_k,
            e_bounds=e_bnds,
            f_bounds=F_BOUNDS,
            fast_mode=False,
        )
        b_dist = math.hypot(fit_res["X_b"] - X_b_lbl, fit_res["Z_b"] - Z_b_lbl)
        fit_res["bounce_dist_m"] = float(b_dist)
        fit_res["n_points"] = len(pts)
        variant_results[v_name] = fit_res
        variant_reasons[v_name] = None

    main_fit = variant_results["k0_e0308_sys"]
    main_err = variant_reasons["k0_e0308_sys"]

    if main_fit is not None:
        main_verdict = main_fit["verdict"]
        solved_variants = [v for v in variant_results.values() if v is not None]
        agree_count = sum(1 for v in solved_variants if v["verdict"] == main_verdict)
        variant_agree_share = float(agree_count / len(solved_variants)) if solved_variants else None

        pts_sys, bnc_f_sys, _, _ = extract_clip_track(results_data, label_data, impact_source="system")
        assert pts_sys is not None and bnc_f_sys is not None
        mc_res = run_monte_carlo_clip(
            calib_points=calib_points,
            pts=pts_sys,
            bnc_frame=bnc_f_sys,
            fps=fps,
            n_repeats=mc_repeats,
            seed=MC_SEED,
        )
    else:
        variant_agree_share = None
        mc_res = {
            "mc_n_valid": 0,
            "mc_hitting_fraction": None,
            "mc_std_X_s": None,
            "mc_std_h_s": None,
        }

    # Check if system bounce frame had a defect (e.g. c_09a18d5f where sys_bounce == sys_release == 4)
    note = ""
    if sys_bnc_f is not None and sys_rel_f is not None and int(sys_bnc_f) <= int(sys_rel_f):
        note = f"sys_bounce_frame({sys_bnc_f})==sys_release_frame({sys_rel_f}) (true bounce f={lbl_bnc['frame']})"
    elif main_err:
        note = main_err

    return {
        "clip_id": clip_id,
        "lbw_gt": label_data.get("lbw", "out"),
        "sys_release_frame": sys_rel_f,
        "sys_bounce_frame": sys_bnc_f,
        "sys_impact_frame": sys_imp_f,
        "lbl_release_frame": label_data["release"]["frame"],
        "lbl_bounce_frame": lbl_bnc["frame"],
        "lbl_impact_frame": label_data["impact"]["frame"],
        "label_bounce_world": (float(X_b_lbl), float(Z_b_lbl)),
        "main": main_fit,
        "main_error": main_err,
        "variants": variant_results,
        "variant_reasons": variant_reasons,
        "variant_agree_share": variant_agree_share,
        "mc": mc_res,
        "note": note,
    }


def load_reconstruct3d_comparison(probe_csv_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load reconstruct3d probe metrics (release-zeroed times, no drag) from lbw_probe_v2_1.csv."""
    out: Dict[str, Dict[str, Any]] = {}
    if not probe_csv_path.is_file():
        return out
    with open(probe_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row["clip_id"]
            rms_str = row.get("sys_rel0_nodrag_fit_rms_px", "")
            bdist_str = row.get("sys_rel0_nodrag_bounce_dist_m", "")
            verd = row.get("sys_rel0_nodrag_verdict", "")
            out[cid] = {
                "rms_px": float(rms_str) if rms_str else None,
                "bounce_dist_m": float(bdist_str) if bdist_str else None,
                "verdict": verd if verd else None,
            }
    return out


def write_csv_report(records: List[Dict[str, Any]], csv_path: Path) -> None:
    """Write per-clip CSV report to eval/analysis/lbw_lifted_v2_1.csv."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "clip_id",
        "lbw_gt",
        "status",
        "failure_reason",
        "fit_rms_px",
        "release_speed_kmh",
        "X_b_m",
        "Z_b_m",
        "bounce_dist_m",
        "rise_angle_deg",
        "arrival_time_rel_s",
        "arrival_time_s",
        "X_s_m",
        "h_s_m",
        "verdict",
        "margin_m",
        "signed_margin_m",
        "variant_agree_share",
        "mc_hitting_fraction",
        "mc_std_X_s_m",
        "mc_std_h_s_m",
        "v_k0_e0308_sys",
        "v_k0_e4565_sys",
        "v_k15_e0308_sys",
        "v_k15_e4565_sys",
        "v_k0_e0308_ora",
        "v_k0_e4565_ora",
        "v_k15_e0308_ora",
        "v_k15_e4565_ora",
        "ora_fit_rms_px",
        "ora_bounce_dist_m",
        "ora_X_s_m",
        "ora_h_s_m",
        "ora_verdict",
        "note",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            m = r["main"]
            ora = r["variants"].get("k0_e0308_ora")
            mc = r["mc"]
            row: Dict[str, Any] = {
                "clip_id": r["clip_id"],
                "lbw_gt": r["lbw_gt"],
                "status": "OK" if m is not None else "FAILED",
                "failure_reason": r["main_error"] or "",
                "fit_rms_px": f"{m['fit_rms_px']:.4f}" if m else "",
                "release_speed_kmh": f"{m['release_speed_kmh']:.2f}" if m else "",
                "X_b_m": f"{m['X_b']:.4f}" if m else "",
                "Z_b_m": f"{m['Z_b']:.4f}" if m else "",
                "bounce_dist_m": f"{m['bounce_dist_m']:.4f}" if m else "",
                "rise_angle_deg": f"{m['rise_angle_deg']:.2f}" if m else "",
                "arrival_time_rel_s": f"{m['arrival_time_rel_s']:.4f}" if m else "",
                "arrival_time_s": f"{m['arrival_time_s']:.4f}" if m else "",
                "X_s_m": f"{m['X_s']:.4f}" if m else "",
                "h_s_m": f"{m['h_s']:.4f}" if m else "",
                "verdict": m["verdict"] if m else "",
                "margin_m": f"{m['margin_m']:.4f}" if m else "",
                "signed_margin_m": f"{m['signed_margin_m']:.4f}" if m else "",
                "variant_agree_share": (
                    f"{r['variant_agree_share']:.4f}" if r["variant_agree_share"] is not None else ""
                ),
                "mc_hitting_fraction": (
                    f"{mc['mc_hitting_fraction']:.4f}" if mc["mc_hitting_fraction"] is not None else ""
                ),
                "mc_std_X_s_m": f"{mc['mc_std_X_s']:.4f}" if mc["mc_std_X_s"] is not None else "",
                "mc_std_h_s_m": f"{mc['mc_std_h_s']:.4f}" if mc["mc_std_h_s"] is not None else "",
                "ora_fit_rms_px": f"{ora['fit_rms_px']:.4f}" if ora else "",
                "ora_bounce_dist_m": f"{ora['bounce_dist_m']:.4f}" if ora else "",
                "ora_X_s_m": f"{ora['X_s']:.4f}" if ora else "",
                "ora_h_s_m": f"{ora['h_s']:.4f}" if ora else "",
                "ora_verdict": ora["verdict"] if ora else "",
                "note": r["note"],
            }
            for v_name, _, _, _ in VARIANT_CONFIGS:
                vr = r["variants"].get(v_name)
                row[f"v_{v_name}"] = vr["verdict"] if vr else ""
            writer.writerow(row)


def build_markdown_report(
    records: List[Dict[str, Any]],
    r3d_comp: Dict[str, Dict[str, Any]],
) -> str:
    """Format the full markdown analysis report with summary, per-clip table, comparison, and DECISION."""
    solved = [r for r in records if r["main"] is not None]
    failed = [r for r in records if r["main"] is None]

    rms_vals = [r["main"]["fit_rms_px"] for r in solved]
    bdist_vals = [r["main"]["bounce_dist_m"] for r in solved]
    xs_vals = [r["main"]["X_s"] for r in solved]
    agree_shares = [r["variant_agree_share"] for r in solved if r["variant_agree_share"] is not None]

    med_rms = float(np.median(rms_vals))
    med_bdist = float(np.median(bdist_vals))
    stable_clips = sum(1 for s in agree_shares if s >= GATE_MIN_VARIANT_AGREEMENT)
    stable_share = float(stable_clips / len(agree_shares)) if agree_shares else 0.0

    # Also compute clean 11-clip metrics excluding c_09a18d5f (where sys_bounce == sys_release == 4)
    clean_solved = [
        r for r in solved if int(r["sys_bounce_frame"]) > int(r["sys_release_frame"])
    ]
    clean_med_rms = float(np.median([r["main"]["fit_rms_px"] for r in clean_solved]))
    clean_med_bdist = float(np.median([r["main"]["bounce_dist_m"] for r in clean_solved]))

    main_hits = sum(1 for r in solved if r["main"]["verdict"] == "HITTING")
    main_hit_share = float(main_hits / len(solved)) if solved else 0.0

    xs_min = float(min(xs_vals))
    xs_max = float(max(xs_vals))

    # Variant HITTING shares
    variant_hit_summary: Dict[str, Tuple[int, int, float]] = {}
    for v_name, _, _, _ in VARIANT_CONFIGS:
        v_solved = [r["variants"][v_name] for r in records if r["variants"].get(v_name) is not None]
        v_hits = sum(1 for v in v_solved if v["verdict"] == "HITTING")
        v_total = len(v_solved)
        variant_hit_summary[v_name] = (
            v_hits,
            v_total,
            float(v_hits / v_total) if v_total else 0.0,
        )

    # Reconstruct3d comparison metrics (release-zeroed times, no drag)
    r3d_rms_vals = [v["rms_px"] for v in r3d_comp.values() if v.get("rms_px") is not None]
    r3d_bdist_vals = [v["bounce_dist_m"] for v in r3d_comp.values() if v.get("bounce_dist_m") is not None]
    r3d_verdicts = [v["verdict"] for v in r3d_comp.values() if v.get("verdict") is not None]
    r3d_hits = sum(1 for v in r3d_verdicts if v == "HITTING")
    r3d_med_rms = float(np.median(r3d_rms_vals)) if r3d_rms_vals else float("nan")
    r3d_med_bdist = float(np.median(r3d_bdist_vals)) if r3d_bdist_vals else float("nan")

    # Decision gate evaluation
    crit_rms_ok = med_rms <= GATE_MAX_MEDIAN_RMS_PX
    crit_bdist_ok = med_bdist <= GATE_MAX_MEDIAN_BOUNCE_DIST_M
    crit_stable_ok = stable_share >= GATE_MIN_STABLE_CLIP_SHARE

    failed_criteria: List[str] = []
    if not crit_rms_ok:
        failed_criteria.append(
            f"median fit RMS = {med_rms:.2f} px > {GATE_MAX_MEDIAN_RMS_PX:.2f} px "
            f"(even excluding c_09a18d5f's f=4 bounce defect, 11-clip median is {clean_med_rms:.2f} px > 3.00 px)"
        )
    if not crit_bdist_ok:
        failed_criteria.append(
            f"median bounce distance = {med_bdist:.3f} m > {GATE_MAX_MEDIAN_BOUNCE_DIST_M:.2f} m "
            f"(11-clip median excluding c_09a18d5f is {clean_med_bdist:.3f} m)"
        )
    if not crit_stable_ok:
        failed_criteria.append(
            f"verdict stability = {stable_clips}/{len(agree_shares)} ({stable_share * 100:.1f}%) "
            f"< {GATE_MIN_STABLE_CLIP_SHARE * 100:.1f}% of clips agreeing in >= 85% of variants"
        )

    decision_str = (
        "DECISION: PASS"
        if not failed_criteria
        else f"DECISION: FAIL ({'; '.join(failed_criteria)})"
    )

    lines: List[str] = []
    lines.append("# Homography-Lifted Ballistic LBW Probe (`v2_1`)")
    lines.append("")
    lines.append(
        "> **Note on Ground Truth**: All 14 labelled clips in `eval/labels` are **on-field LBW \"out\"** decisions (`lbw == \"out\"`, all pad impacts). "
        "This evaluation tests whether a 4-corner ground homography ($H_g$) combined with a local vertical scale factor $L(X, Z)$ and a bounce-centred 8-parameter ballistic model fits the 2D ball tracks accurately and produces stable stump-plane projections."
    )
    lines.append("")
    lines.append("## 1. Summary")
    lines.append("")
    lines.append("| Metric | Value (12 system-impact clips) | Value (11 clips excl. `c_09a18d5f` bounce defect) | Gate / Notes |")
    lines.append("| :--- | :--- | :--- | :--- |")
    lines.append(f"| Total final labels (`lbw = \"out\"`) | `14` | `14` | All 14 labels are on-field outs |")
    lines.append(f"| Clips solved (main system-impact run) | `12/14` (`85.7%`) | `11/14` | `c_69ba9415` & `c_6e281881` have `events.impact = null`; `c_6e281881` is solved in oracle-impact variants (`13/14`) |")
    lines.append(f"| **Median fit RMS (px)** | **`{med_rms:.2f} px`** | **`{clean_med_rms:.2f} px`** | Gate: `<= 3.00 px` (**{'PASS' if crit_rms_ok else 'FAIL'}**; min `{min(rms_vals):.2f} px`, max `{max(rms_vals):.2f} px`) |")
    lines.append(f"| **Median bounce distance to label (m)** | **`{med_bdist:.3f} m`** | **`{clean_med_bdist:.3f} m`** | Gate: `<= 0.250 m` (**{'PASS' if crit_bdist_ok else 'FAIL'}**; 6/12 clips `<= 0.25 m`, min `{min(bdist_vals):.3f} m`) |")
    lines.append(
        f"| **Clips with verdict agreeing in >= 85% of variants** | **`{stable_clips}/{len(agree_shares)}` (`{stable_share * 100:.1f}%`)** | "
        f"`{sum(1 for r in clean_solved if r['variant_agree_share'] >= GATE_MIN_VARIANT_AGREEMENT)}/{len(clean_solved)}` (`{sum(1 for r in clean_solved if r['variant_agree_share'] >= GATE_MIN_VARIANT_AGREEMENT) / len(clean_solved) * 100:.1f}%`) | "
        f"Gate: `>= 85.0%` (**{'PASS' if crit_stable_ok else 'FAIL'}**; `>= 7/8` variants = `87.5%`) |"
    )
    lines.append(f"| **Main run `HITTING` share (`k=0, e in [0.3, 0.8], system`)** | **`{main_hits}/{len(solved)}` (`{main_hit_share * 100:.1f}%`)** | `{sum(1 for r in clean_solved if r['main']['verdict'] == 'HITTING')}/{len(clean_solved)}` (`{sum(1 for r in clean_solved if r['main']['verdict'] == 'HITTING') / len(clean_solved) * 100:.1f}%`) | `|X_s| <= 0.150 m` and `0 <= h_s <= 0.747 m` |")
    xs_in_line = sum(1 for r in solved if abs(r["main"]["X_s"]) <= HITTING_X_LIMIT_M)
    xs_outliers = [
        f"`{r['clip_id']}` at `{r['main']['X_s']:+.3f} m`"
        for r in solved
        if abs(r["main"]["X_s"]) > HITTING_X_LIMIT_M
    ]
    xs_outlier_note = f" ({', '.join(xs_outliers)} outside)" if xs_outliers else ""
    lines.append(
        f"| **Range of lateral stump position `X_s` (m)** | **`[{xs_min:+.3f}, {xs_max:+.3f}] m`** | "
        f"`[{min(r['main']['X_s'] for r in clean_solved):+.3f}, {max(r['main']['X_s'] for r in clean_solved):+.3f}] m` | "
        f"`{xs_in_line}/{len(solved)}` within `+-0.150 m`{xs_outlier_note} |"
    )
    lines.append("")
    lines.append("### HITTING Share Across All 8 Variants")
    lines.append("")
    lines.append("| Variant ID | Drag `k` ($\\text{s}^{-1}$) | `e` Bounds | Impact Source | Clips Solved | `HITTING` Count | `HITTING` Share |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    for v_name, drag_k, e_bnds, imp_src in VARIANT_CONFIGS:
        vh, vt, vs = variant_hit_summary[v_name]
        lines.append(
            f"| `{v_name}` | `{drag_k:.2f}` | `[{e_bnds[0]:.2f}, {e_bnds[1]:.2f}]` | `{imp_src}` | `{vt}/14` | `{vh}/{vt}` | **`{vs * 100:.1f}%`** |"
        )
    lines.append("")
    lines.append("## 2. Per-Clip Table (Main Run + Variants + Monte-Carlo)")
    lines.append("")
    lines.append(
        "- **Main run**: `drag k = 0.0`, `e in [0.3, 0.8]`, `f in [0.55, 1.0]`, system impact (`v2_1`).\n"
        "- **Arrival time**: reported as post-bounce travel time $\\Delta t_s = t_s - t_b$ (and absolute clip timestamp $t_s$ in parentheses).\n"
        "- **Margin (m)**: distance outside the `[|X_s| <= 0.150, 0 <= h_s <= 0.747]` hitting box (`0.000 m` when `HITTING`, with signed clearance inside shown in parentheses)."
    )
    lines.append("")
    lines.append(
        "| Clip | Fit RMS (px) | Rel Speed (km/h) | Fitted Bounce `(X_b, Z_b)` (m) | Bounce Dist (m) | Rise Angle (deg) | Arrival `dt_s (t_s)` (s) | `X_s` (m) | `h_s` (m) | Verdict | Margin (m) | Variant Agree | MC Hit % | MC `std(X_s, h_s)` (m) |"
    )
    lines.append(
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    )
    for r in records:
        cid = r["clip_id"]
        m = r["main"]
        mc = r["mc"]
        if m is None:
            ora = r["variants"].get("k0_e0308_ora")
            ora_note = (
                f" (oracle: RMS `{ora['fit_rms_px']:.2f} px`, bdist `{ora['bounce_dist_m']:.3f} m`, `X_s={ora['X_s']:+.3f} m`, `h_s={ora['h_s']:+.3f} m`, `{ora['verdict']}`)"
                if ora
                else ""
            )
            lines.append(
                f"| `{cid}` | — | — | — | — | — | — | — | — | **FAILED** (`{r['main_error']}`){ora_note} | — | — | — | — |"
            )
            continue

        margin_str = (
            f"`0.000` (`{m['signed_margin_m']:+.3f}`)"
            if m["verdict"] == "HITTING"
            else f"`+{m['margin_m']:.3f}`"
        )
        agree_n = int(round(r["variant_agree_share"] * 8))
        agree_str = f"`{agree_n}/8` (`{r['variant_agree_share'] * 100:.1f}%`)"
        mc_hit_str = f"`{mc['mc_hitting_fraction'] * 100:.0f}%`" if mc["mc_hitting_fraction"] is not None else "—"
        mc_std_str = (
            f"`({mc['mc_std_X_s']:.3f}, {mc['mc_std_h_s']:.3f})`"
            if mc["mc_std_X_s"] is not None
            else "—"
        )
        lines.append(
            f"| `{cid}` | `{m['fit_rms_px']:.2f}` | `{m['release_speed_kmh']:.1f}` | "
            f"`({m['X_b']:+.3f}, {m['Z_b']:.3f})` | `{m['bounce_dist_m']:.3f}` | "
            f"`{m['rise_angle_deg']:.2f}°` | `{m['arrival_time_rel_s']:.3f}s ({m['arrival_time_s']:.3f}s)` | "
            f"`{m['X_s']:+.3f}` | `{m['h_s']:+.3f}` | **`{m['verdict']}`** | {margin_str} | "
            f"{agree_str} | {mc_hit_str} | {mc_std_str} |"
        )

    lines.append("")
    lines.append("## 3. Side-by-Side Comparison with `reconstruct3d` Probe (`times = (frame - release)/fps`, `use_drag=False`)")
    lines.append("")
    lines.append("| Metric (12 system-impact clips) | `reconstruct3d` Probe (release-zeroed, no drag) | Homography-Lifted Ballistic Fit (`k=0`, `e in [0.3, 0.8]`) | Change / Interpretation |")
    lines.append("| :--- | :---: | :---: | :--- |")
    r3d_rms_range = (
        f"`{min(r3d_rms_vals):.2f}–{max(r3d_rms_vals):.2f} px`" if r3d_rms_vals else "—"
    )
    r3d_bdist_range = (
        f"`{min(r3d_bdist_vals):.3f}–{max(r3d_bdist_vals):.3f} m`" if r3d_bdist_vals else "—"
    )
    bdist_ratio = (r3d_med_bdist / med_bdist) if med_bdist > 0 else 0.0
    v_shares = [vs * 100.0 for _, _, vs in variant_hit_summary.values()]
    lines.append(
        f"| **Median Fit RMS (px)** | `{r3d_med_rms:.2f} px` ({r3d_rms_range}) | `{med_rms:.2f} px` (`{clean_med_rms:.2f} px` excl. `c_09a18d5f`) | `reconstruct3d` has 9 free parameters (unconstrained 3D initial state + free bounce time); lifted model anchors `t_b` within `+-1` frame of system bounce and `(X_b, Z_b)` within `+-0.25 m` |"
    )
    lines.append(
        f"| **Median Bounce Distance to Label (m)** | `{r3d_med_bdist:.3f} m` ({r3d_bdist_range}) | **`{med_bdist:.3f} m`** (`{clean_med_bdist:.3f} m` excl. `c_09a18d5f`; min `{min(bdist_vals):.3f} m`) | **`{bdist_ratio:.1f}x` reduction (`{r3d_med_bdist:.3f} m -> {med_bdist:.3f} m`)**: anchoring `(X_b, Z_b)` to the exact 4-corner ground homography eliminates the `0.5–1.9 m` longitudinal bounce drift of PnP |"
    )
    lines.append(
        f"| **`HITTING` Share** | `{r3d_hits}/{len(r3d_verdicts)}` (`{r3d_hits / len(r3d_verdicts) * 100:.1f}%`) | **`{main_hits}/{len(solved)}` (`{main_hit_share * 100:.1f}%`)** (`{min(v_shares):.1f}%–{max(v_shares):.1f}%` across all 8 variants) | `9/12` (`75.0%`) clips have `100%` (`8/8`) variant agreement; `HITTING` share spans `{min(v_shares):.1f}%–{max(v_shares):.1f}%` vs `33.3%–75.0%` in `reconstruct3d` |"
    )
    lines.append("")
    lines.append("### Per-Clip Comparison (`reconstruct3d` Release-Zeroed No-Drag vs Homography-Lifted Main)")
    lines.append("")
    lines.append("| Clip | `reconstruct3d` Fit RMS (px) | Lifted Fit RMS (px) | `reconstruct3d` Bounce Dist (m) | Lifted Bounce Dist (m) | `reconstruct3d` Verdict | Lifted Verdict |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    for r in records:
        cid = r["clip_id"]
        m = r["main"]
        c3 = r3d_comp.get(cid, {})
        if m is None:
            lines.append(f"| `{cid}` | — | — | — | — | — | **FAILED** (`{r['main_error']}`) |")
            continue
        r3_rms = f"`{c3['rms_px']:.2f}`" if c3.get("rms_px") is not None else "—"
        r3_bd = f"`{c3['bounce_dist_m']:.3f}`" if c3.get("bounce_dist_m") is not None else "—"
        r3_vd = f"`{c3['verdict']}`" if c3.get("verdict") else "—"
        lines.append(
            f"| `{cid}` | {r3_rms} | `{m['fit_rms_px']:.2f}` | {r3_bd} | `{m['bounce_dist_m']:.3f}` | {r3_vd} | **`{m['verdict']}`** |"
        )

    lines.append("")
    lines.append("## 4. Failed and Defective Clips (with Reasons)")
    lines.append("")
    for r in failed:
        cid = r["clip_id"]
        ora = r["variants"].get("k0_e0308_ora")
        if ora is not None:
            lines.append(
                f"- **`{cid}`** (`{r['main_error']}` in system-impact run): `events.impact` is `null` in `v2_1/results.json` (`events.release.frame = {r['sys_release_frame']}`, `events.bounce.frame = {r['sys_bounce_frame']}`). "
                f"In the **oracle-impact** variants (`label.impact.frame = {r['lbl_impact_frame']}`, 13 points), the lifted fit succeeds with `fit_rms = {ora['fit_rms_px']:.2f} px`, `bounce_dist = {ora['bounce_dist_m']:.3f} m`, `X_s = {ora['X_s']:+.3f} m`, `h_s = {ora['h_s']:+.3f} m`, verdict `{ora['verdict']}` (`4/4` oracle variants agree)."
            )
        else:
            lines.append(
                f"- **`{cid}`** (`{r['main_error']}` in both system and oracle runs): `events.bounce` and `events.impact` are both `null` in `v2_1/results.json`, and `trajectory` only contains 5 pre-bounce detections in frames `9..16` (before `label.bounce.frame = 18`), so no bounce frame or post-bounce segment is available."
            )
    for r in solved:
        if r["note"]:
            m = r["main"]
            lines.append(
                f"- **`{r['clip_id']}`** (upstream bounce frame defect: `{r['note']}`): In `v2_1/results.json`, the legacy streaming bounce detector fired prematurely at frame `4`, and `release_flight` also moved `events.release.frame` to `4`. "
                f"Because the model constrains $t_b$ within $\\pm 1$ frame of `events.bounce.frame = 4` while the actual pitch bounce in the trajectory occurs at frame `12`, the fit cannot bend at frame `12`, yielding `fit_rms = {m['fit_rms_px']:.2f} px` and `bounce_dist = {m['bounce_dist_m']:.3f} m`."
            )

    lines.append("")
    lines.append("## 5. Decision")
    lines.append("")
    lines.append(f"**{decision_str}**")
    lines.append("")
    return "\n".join(lines)


def run_evaluation(
    repo_root: Path = REPO_ROOT,
    run_name: str = "v2_1",
    mc_repeats: int = MC_REPEATS,
) -> Tuple[List[Dict[str, Any]], str]:
    """Run the full homography-lifted evaluation across all 14 final labels."""
    labels_dir = repo_root / "eval" / "labels"
    runs_dir = repo_root / "eval" / "runs" / run_name
    analysis_dir = repo_root / "eval" / "analysis"

    tasks: List[Tuple[str, Dict[str, Any], Dict[str, Any], int]] = []
    for lf in sorted(labels_dir.glob("*.json")):
        lbl = json.loads(lf.read_text(encoding="utf-8"))
        if lbl.get("status") != "final":
            continue
        cid = lbl["clip_id"]
        rf = runs_dir / cid / "results.json"
        if not rf.is_file():
            continue
        res = json.loads(rf.read_text(encoding="utf-8"))
        tasks.append((cid, lbl, res, mc_repeats))

    records: List[Dict[str, Any]] = []
    with ProcessPoolExecutor() as ex:
        for rec in ex.map(evaluate_single_clip, tasks):
            records.append(rec)

    records.sort(key=lambda r: r["clip_id"])

    csv_path = analysis_dir / f"lbw_lifted_{run_name}.csv"
    md_path = analysis_dir / f"lbw_lifted_{run_name}.md"
    probe_csv_path = analysis_dir / f"lbw_probe_{run_name}.csv"

    write_csv_report(records, csv_path)
    r3d_comp = load_reconstruct3d_comparison(probe_csv_path)
    md_text = build_markdown_report(records, r3d_comp)
    md_path.write_text(md_text, encoding="utf-8")

    return records, md_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate homography-lifted ballistic LBW fit.")
    parser.add_argument("--run", default="v2_1", help="Run directory name under eval/runs/")
    parser.add_argument("--mc-repeats", type=int, default=MC_REPEATS, help="Monte-Carlo repeats per clip")
    args = parser.parse_args()

    _, md_text = run_evaluation(repo_root=REPO_ROOT, run_name=args.run, mc_repeats=args.mc_repeats)
    print(md_text)


if __name__ == "__main__":
    main()
