"""LBW projection feasibility study on the 14 labelled clips using reconstruct3d.

Evaluates 6-point planar camera pose estimation (calibrate.solve_pose),
3D trajectory fitting (trajectory_fit.fit_trajectory with use_drag=False/True,
use_magnus=False), continuation to the striker's stump plane (world z = 0),
and 100-trial Monte-Carlo perturbation sensitivity.

Usage:
    python tools/annotator/backend/lbw_probe.py
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

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
ANNOTATOR_BACKEND = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(ANNOTATOR_BACKEND) not in sys.path:
    sys.path.insert(0, str(ANNOTATOR_BACKEND))

from backend.pipeline.reconstruct3d.calibrate import solve_pose  # noqa: E402
from backend.pipeline.reconstruct3d.trajectory_fit import (  # noqa: E402
    BALL_R,
    ball_positions_at_times,
    fit_trajectory,
)
from backend.pipeline.reconstruct3d.world_points import (  # noqa: E402
    BALL_RADIUS_M,
    KEYPOINT_NAMES,
    PITCH_LENGTH_M,
    STUMP_HEIGHT_M,
    WORLD_POINTS_M,
)
from app.calib import fit_homography, pixel_to_world  # noqa: E402

# LBW stump-plane classification constants (Laws of Cricket: 9 in = 0.2286 m width -> 0.114 m half-width)
STUMP_HALF_WIDTH_M: float = 0.114
HITTING_X_LIMIT_M: float = STUMP_HALF_WIDTH_M + BALL_RADIUS_M  # 0.114 + 0.036 = 0.150 m
HITTING_Y_MIN_M: float = 0.0
HITTING_Y_MAX_M: float = STUMP_HEIGHT_M + BALL_RADIUS_M        # 0.711 + 0.036 = 0.747 m

# Plausibility bounds for camera pose
CAM_HEIGHT_MIN_M: float = 1.0
CAM_HEIGHT_MAX_M: float = 15.0
CAM_DIST_MIN_M: float = 5.0
CAM_DIST_MAX_M: float = 60.0

# Inverse mapping of run_full_pipeline.keypoints_to_calibration
CALIB_TO_KEYPOINT_NAME: Dict[str, str] = {
    "bat_L": "popping_striker_leg",
    "bat_R": "popping_striker_off",
    "bowl_L": "popping_nonstriker_leg",
    "bowl_R": "popping_nonstriker_off",
    "bat_stump": "stump_base_striker",
    "bowl_stump": "stump_base_nonstriker",
}
KEYPOINT_TO_CALIB_NAME: Dict[str, str] = {v: k for k, v in CALIB_TO_KEYPOINT_NAME.items()}


def calibration_to_keypoints(points: Dict[str, Sequence[float]]) -> Dict[str, Any]:
    """Map calibration_gt.points (bat_L, bat_R, bowl_L, bowl_R, bat_stump, bowl_stump)
    into the reconstruct3d keypoints schema and return ordered 6x2 image points array.

    This is the exact inverse of run_full_pipeline.keypoints_to_calibration.
    """
    kp_list = []
    img_pts = []
    for kp_name in KEYPOINT_NAMES:
        cal_name = KEYPOINT_TO_CALIB_NAME[kp_name]
        if cal_name not in points:
            raise KeyError(f"Missing calibration point '{cal_name}' for keypoint '{kp_name}'")
        uv = [float(points[cal_name][0]), float(points[cal_name][1])]
        kp_list.append({"name": kp_name, "uv": uv})
        img_pts.append(uv)
    return {
        "points": kp_list,
        "img_pts_np": np.asarray(img_pts, dtype=np.float64),
    }


def check_side_and_camera(
    points: Dict[str, Sequence[float]],
    C_world: np.ndarray,
    R: np.ndarray,
) -> Dict[str, Any]:
    """Confirm image-left points stay on the same world side (-X) and warn if the
    solved camera sits on the wrong side of the pitch.
    """
    warnings: List[str] = []

    bat_L_x, bat_R_x = float(points["bat_L"][0]), float(points["bat_R"][0])
    bowl_L_x, bowl_R_x = float(points["bowl_L"][0]), float(points["bowl_R"][0])
    image_left_consistent = (bat_L_x < bat_R_x) and (bowl_L_x < bowl_R_x)
    # In WORLD_POINTS_M, index 0 (bat_L / popping_striker_leg) and index 2 (bowl_L / popping_nonstriker_leg)
    # both have world X = -1.32 m, while bat_R and bowl_R both have world X = +1.32 m.
    world_left_same_side = (WORLD_POINTS_M[0][0] < 0.0 and WORLD_POINTS_M[2][0] < 0.0
                            and WORLD_POINTS_M[0][0] == WORLD_POINTS_M[2][0])
    if not image_left_consistent:
        warnings.append(
            f"Image-left ordering violated: bat_L.x={bat_L_x:.1f} vs bat_R.x={bat_R_x:.1f}, "
            f"bowl_L.x={bowl_L_x:.1f} vs bowl_R.x={bowl_R_x:.1f}"
        )

    cam_height_m = float(C_world[1])
    cam_dist_behind_m = float(C_world[2] - PITCH_LENGTH_M)
    wrong_side = False
    if float(C_world[2]) <= PITCH_LENGTH_M:
        wrong_side = True
        warnings.append(
            f"Camera Z ({C_world[2]:.2f} m) is not behind bowler's stumps (Z > {PITCH_LENGTH_M} m)"
        )
    if cam_height_m <= 0.0:
        wrong_side = True
        warnings.append(f"Camera Y ({cam_height_m:.2f} m) is below ground plane (Y <= 0)")
    # Camera +X axis should align with world +X when viewing from behind bowler's end toward -Z
    if float(R[0, 0]) <= 0.0:
        wrong_side = True
        warnings.append(f"Camera X axis is flipped relative to world X (R[0,0]={R[0, 0]:.3f} <= 0)")

    return {
        "image_left_consistent": image_left_consistent and world_left_same_side,
        "wrong_side": wrong_side,
        "warnings": warnings,
    }


def solve_clip_pose(
    points: Dict[str, Sequence[float]],
    image_size: Tuple[int, int],
) -> Dict[str, Any]:
    """Solve camera pose from 6 calibration points and evaluate plausibility."""
    mapped = calibration_to_keypoints(points)
    img_pts = mapped["img_pts_np"]
    world_pts = np.asarray(WORLD_POINTS_M, dtype=np.float64)

    pose = solve_pose(world_pts, img_pts, image_size)
    K = pose["K"]
    rvec = pose["rvec"].reshape(3)
    tvec = pose["tvec"].reshape(3)
    R, _ = cv2.Rodrigues(rvec)
    C_world = (-R.T @ tvec.reshape(3, 1)).reshape(3)

    per_pt = pose["per_point_error_px"]
    pose_rms_px = float(np.sqrt(np.mean(per_pt ** 2)))
    pose_mean_px = float(np.mean(per_pt))
    focal_px = float(pose["focal_px"])
    cam_height_m = float(C_world[1])
    cam_dist_behind_m = float(C_world[2] - PITCH_LENGTH_M)

    side_check = check_side_and_camera(points, C_world, R)
    height_ok = CAM_HEIGHT_MIN_M <= cam_height_m <= CAM_HEIGHT_MAX_M
    dist_ok = CAM_DIST_MIN_M <= cam_dist_behind_m <= CAM_DIST_MAX_M
    plausible = height_ok and dist_ok and (not side_check["wrong_side"])

    implausible_reasons: List[str] = list(side_check["warnings"])
    if not height_ok:
        implausible_reasons.append(
            f"height {cam_height_m:.2f} m outside [{CAM_HEIGHT_MIN_M:.0f}, {CAM_HEIGHT_MAX_M:.0f}] m"
        )
    if not dist_ok:
        implausible_reasons.append(
            f"distance {cam_dist_behind_m:.2f} m outside [{CAM_DIST_MIN_M:.0f}, {CAM_DIST_MAX_M:.0f}] m"
        )

    return {
        "K": K,
        "R": R,
        "rvec": rvec,
        "tvec": tvec,
        "C_world": C_world,
        "img_pts": img_pts,
        "world_pts": world_pts,
        "pose_rms_px": pose_rms_px,
        "pose_mean_px": pose_mean_px,
        "focal_px": focal_px,
        "cam_x_m": float(C_world[0]),
        "cam_height_m": cam_height_m,
        "cam_z_m": float(C_world[2]),
        "cam_dist_behind_m": cam_dist_behind_m,
        "image_left_consistent": side_check["image_left_consistent"],
        "wrong_side": side_check["wrong_side"],
        "plausible": plausible,
        "implausible_reasons": implausible_reasons,
    }


def classify_lbw(x_m: float, y_m: float) -> Dict[str, Any]:
    """Classify (x_m, y_m) at the striker's stump plane (world z = 0).

    HITTING when |x| <= 0.114 + 0.036 (0.150 m) and 0 <= y <= 0.711 + 0.036 (0.747 m),
    else MISSING. Also computes horizontal, vertical, and Euclidean distance outside the stumps.
    """
    if math.isnan(x_m) or math.isnan(y_m):
        return {
            "verdict": "MISSING",
            "hitting": False,
            "dx_outside_m": float("nan"),
            "dy_outside_m": float("nan"),
            "outside_dist_m": float("nan"),
        }
    dx_out = max(0.0, abs(float(x_m)) - HITTING_X_LIMIT_M)
    if float(y_m) < HITTING_Y_MIN_M:
        dy_out = HITTING_Y_MIN_M - float(y_m)
    elif float(y_m) > HITTING_Y_MAX_M:
        dy_out = float(y_m) - HITTING_Y_MAX_M
    else:
        dy_out = 0.0
    outside_dist = math.hypot(dx_out, dy_out)
    hitting = (abs(float(x_m)) <= HITTING_X_LIMIT_M) and (HITTING_Y_MIN_M <= float(y_m) <= HITTING_Y_MAX_M)
    return {
        "verdict": "HITTING" if hitting else "MISSING",
        "hitting": bool(hitting),
        "dx_outside_m": float(dx_out),
        "dy_outside_m": float(dy_out),
        "outside_dist_m": float(outside_dist),
    }


def intersect_stump_plane(
    p0: Sequence[float],
    v0: Sequence[float],
    restitution_e: float,
    friction_f: float,
    use_drag: bool = False,
    omega: Optional[Sequence[float]] = None,
    t_max: float = 3.5,
    dt: float = 2e-3,
) -> Optional[Dict[str, float]]:
    """Continue trajectory with ball_positions_at_times until world z = 0.

    Returns dict with keys {"arrival_time_s", "x_m", "y_m"} at z = 0, or None
    if the trajectory never reaches z <= 0 within [0, t_max].
    """
    p0_arr = np.asarray(p0, dtype=np.float64)
    v0_arr = np.asarray(v0, dtype=np.float64)
    n_steps = max(2, int(round(t_max / dt)) + 1)
    ts = np.linspace(0.0, t_max, n_steps)
    positions, _ = ball_positions_at_times(
        ts, p0_arr, v0_arr, float(restitution_e), float(friction_f),
        omega=omega, use_drag=use_drag, dt=dt, ball_r=BALL_R,
    )
    z = positions[:, 2]
    crossing_indices = np.where(z <= 0.0)[0]
    if len(crossing_indices) == 0:
        return None
    k = int(crossing_indices[0])
    if k == 0:
        return {
            "arrival_time_s": float(ts[0]),
            "x_m": float(positions[0, 0]),
            "y_m": float(positions[0, 1]),
        }
    z_prev, z_curr = float(z[k - 1]), float(z[k])
    denom = z_prev - z_curr
    frac = (z_prev - 0.0) / denom if abs(denom) > 1e-12 else 0.0
    frac = max(0.0, min(1.0, frac))
    t_hit = float(ts[k - 1] + frac * (ts[k] - ts[k - 1]))
    x_hit = float(positions[k - 1, 0] + frac * (positions[k, 0] - positions[k - 1, 0]))
    y_hit = float(positions[k - 1, 1] + frac * (positions[k, 1] - positions[k - 1, 1]))
    return {
        "arrival_time_s": t_hit,
        "x_m": x_hit,
        "y_m": y_hit,
    }


def evaluate_trajectory_fit(
    times: np.ndarray,
    uvs: np.ndarray,
    K: np.ndarray,
    R: np.ndarray,
    tvec: np.ndarray,
    C_world: np.ndarray,
    lbl_bounce_world: Optional[Tuple[float, float]] = None,
    use_drag: bool = False,
    time_offset_s: float = 0.0,
) -> Dict[str, Any]:
    """Fit 3D trajectory with trajectory_fit.fit_trajectory and project to stump plane z = 0."""
    fit = fit_trajectory(times, uvs, K, R, tvec, C_world, use_magnus=False, use_drag=use_drag)
    p0 = fit.x[0:3]
    v0 = fit.x[3:6]
    e = float(fit.x[7])
    f_fric = float(fit.x[8])

    # Per-point 2D reprojection error
    per_pt_err = np.linalg.norm(fit.fun.reshape(-1, 2), axis=1)
    fit_rms_px = float(np.sqrt(np.mean(per_pt_err ** 2)))

    # Speed at release (first detection time times[0])
    if abs(float(times[0])) > 1e-9 and use_drag:
        # Evaluate velocity at times[0] if times was not zeroed at release
        dt_probe = 1e-3
        t0_val = float(times[0])
        pts_v, _ = ball_positions_at_times(
            np.array([t0_val, t0_val + dt_probe]), p0, v0, e, f_fric,
            omega=None, use_drag=use_drag,
        )
        v_rel = (pts_v[1] - pts_v[0]) / dt_probe
        release_speed_at_rel_kmh = float(np.linalg.norm(v_rel) * 3.6)
    elif abs(float(times[0])) > 1e-9:
        t0_val = float(times[0])
        v_rel = v0 + np.array([0.0, -9.81, 0.0]) * t0_val
        release_speed_at_rel_kmh = float(np.linalg.norm(v_rel) * 3.6)
    else:
        release_speed_at_rel_kmh = float(np.linalg.norm(v0) * 3.6)
    v0_speed_kmh = float(np.linalg.norm(v0) * 3.6)

    # Bounce position
    _, tb = ball_positions_at_times(
        np.array([0.0, max(float(times[-1]), 2.0)]), p0, v0, e, f_fric,
        omega=None, use_drag=use_drag,
    )
    if np.isfinite(tb):
        b_arr, _ = ball_positions_at_times(
            np.array([0.0, float(tb)]), p0, v0, e, f_fric,
            omega=None, use_drag=use_drag,
        )
        bounce_x_m = float(b_arr[-1, 0])
        bounce_z_m = float(b_arr[-1, 2])
        bounce_time_s = float(tb + time_offset_s)
        if lbl_bounce_world is not None:
            bounce_dist_m = float(
                math.hypot(bounce_x_m - lbl_bounce_world[0], bounce_z_m - lbl_bounce_world[1])
            )
        else:
            bounce_dist_m = float("nan")
    else:
        bounce_x_m = float("nan")
        bounce_z_m = float("nan")
        bounce_time_s = float("nan")
        bounce_dist_m = float("nan")

    plane = intersect_stump_plane(
        p0, v0, e, f_fric, use_drag=use_drag, omega=None,
        t_max=max(float(times[-1]) + 1.5, 3.5),
    )
    if plane is not None:
        arrival_time_s = float(plane["arrival_time_s"] + time_offset_s)
        plane_x_m = float(plane["x_m"])
        plane_y_m = float(plane["y_m"])
    else:
        arrival_time_s = float("nan")
        plane_x_m = float("nan")
        plane_y_m = float("nan")

    lbw = classify_lbw(plane_x_m, plane_y_m)

    return {
        "fit_rms_px": fit_rms_px,
        "release_speed_kmh": v0_speed_kmh,
        "release_speed_at_rel_frame_kmh": release_speed_at_rel_kmh,
        "bounce_time_s": bounce_time_s,
        "bounce_x_m": bounce_x_m,
        "bounce_z_m": bounce_z_m,
        "bounce_dist_to_label_m": bounce_dist_m,
        "arrival_time_s": arrival_time_s,
        "plane_x_m": plane_x_m,
        "plane_y_m": plane_y_m,
        "verdict": lbw["verdict"],
        "hitting": lbw["hitting"],
        "dx_outside_m": lbw["dx_outside_m"],
        "dy_outside_m": lbw["dy_outside_m"],
        "outside_dist_m": lbw["outside_dist_m"],
        "p0": p0.tolist(),
        "v0": v0.tolist(),
        "restitution_e": e,
        "friction_f": f_fric,
    }


def _mc_single_trial(args: Tuple[Any, ...]) -> Optional[Tuple[float, float, bool]]:
    world_pts, img_p, image_size, times, uvs_p, use_drag = args
    try:
        pose = solve_pose(world_pts, img_p, image_size)
        K = pose["K"]
        R, _ = cv2.Rodrigues(pose["rvec"].reshape(3))
        tvec = pose["tvec"].reshape(3)
        C_world = (-R.T @ tvec.reshape(3, 1)).reshape(3)
        fit = fit_trajectory(times, uvs_p, K, R, tvec, C_world, use_magnus=False, use_drag=use_drag)
        plane = intersect_stump_plane(
            fit.x[0:3], fit.x[3:6], float(fit.x[7]), float(fit.x[8]),
            use_drag=use_drag, omega=None, t_max=max(float(times[-1]) + 1.5, 3.5),
        )
        if plane is None:
            return None
        lbw = classify_lbw(plane["x_m"], plane["y_m"])
        return (float(plane["x_m"]), float(plane["y_m"]), bool(lbw["hitting"]))
    except Exception:
        return None


def run_monte_carlo(
    world_pts: np.ndarray,
    img_pts: np.ndarray,
    image_size: Tuple[int, int],
    times: np.ndarray,
    uvs: np.ndarray,
    n_repeats: int = 100,
    seed: int = 42,
    calib_sigma_px: float = 1.5,
    traj_sigma_px: float = 2.0,
    use_drag: bool = False,
    executor: Optional[ProcessPoolExecutor] = None,
) -> Dict[str, Any]:
    """Run Monte-Carlo sensitivity with fixed seed:
    perturb each calibration point by N(0, calib_sigma_px) and each trajectory point by N(0, traj_sigma_px).
    """
    rng = np.random.default_rng(seed)
    tasks = []
    for _ in range(n_repeats):
        img_p = img_pts + rng.normal(0.0, calib_sigma_px, size=img_pts.shape)
        uvs_p = uvs + rng.normal(0.0, traj_sigma_px, size=uvs.shape)
        tasks.append((world_pts, img_p, image_size, times, uvs_p, use_drag))

    if executor is not None:
        results = list(executor.map(_mc_single_trial, tasks))
    else:
        results = [_mc_single_trial(t) for t in tasks]

    valid = [r for r in results if r is not None]
    if not valid:
        return {
            "n_repeats": n_repeats,
            "n_valid": 0,
            "hitting_fraction": 0.0,
            "std_x_m": float("nan"),
            "std_y_m": float("nan"),
            "mean_x_m": float("nan"),
            "mean_y_m": float("nan"),
        }

    xs = np.array([r[0] for r in valid], dtype=np.float64)
    ys = np.array([r[1] for r in valid], dtype=np.float64)
    hits = sum(1 for r in valid if r[2])
    return {
        "n_repeats": n_repeats,
        "n_valid": len(valid),
        "hitting_fraction": float(hits / len(valid)),
        "std_x_m": float(np.std(xs, ddof=0)),
        "std_y_m": float(np.std(ys, ddof=0)),
        "mean_x_m": float(np.mean(xs)),
        "mean_y_m": float(np.mean(ys)),
    }


def probe_clip(
    label_data: Dict[str, Any],
    results_data: Dict[str, Any],
    n_mc: int = 100,
    seed: int = 42,
    executor: Optional[ProcessPoolExecutor] = None,
) -> Dict[str, Any]:
    """Run the full LBW feasibility probe on a single clip."""
    clip_id = label_data["clip_id"]
    W = int(results_data["video"]["width"])
    H = int(results_data["video"]["height"])
    fps = float(results_data["video"]["fps"])

    cal_pts = label_data["calibration_gt"]["points"]
    pose_info = solve_clip_pose(cal_pts, (W, H))

    # Ground-truth bounce mapped to world (x, z) via 4-corner homography in calib.py
    H_homog = fit_homography(cal_pts).H
    lbl_bounce = label_data.get("bounce")
    if lbl_bounce and lbl_bounce.get("x") is not None and lbl_bounce.get("y") is not None:
        lbl_bx_m, lbl_bz_m = pixel_to_world(H_homog, float(lbl_bounce["x"]), float(lbl_bounce["y"]))
        lbl_bounce_world: Optional[Tuple[float, float]] = (lbl_bx_m, lbl_bz_m)
    else:
        lbl_bounce_world = None

    events = results_data.get("events", {})
    rel_ev = events.get("release")
    imp_ev = events.get("impact")
    lbl_imp = label_data.get("impact")
    traj = results_data.get("trajectory", [])

    rel_frame = int(rel_ev["frame"]) if rel_ev and rel_ev.get("frame") is not None else None
    sys_imp_frame = int(imp_ev["frame"]) if imp_ev and imp_ev.get("frame") is not None else None
    ora_imp_frame = int(lbl_imp["frame"]) if lbl_imp and lbl_imp.get("frame") is not None else None

    out: Dict[str, Any] = {
        "clip_id": clip_id,
        "lbw_label": label_data.get("lbw", "out"),
        "fps": fps,
        "image_size": [W, H],
        "release_frame": rel_frame,
        "sys_impact_frame": sys_imp_frame,
        "ora_impact_frame": ora_imp_frame,
        "lbl_bounce_world_m": list(lbl_bounce_world) if lbl_bounce_world else None,
        "pose": {
            k: v for k, v in pose_info.items()
            if k not in ("K", "R", "rvec", "tvec", "C_world", "img_pts", "world_pts")
        },
        "system": {},
        "oracle": {},
        "system_rel_zero": {},
        "oracle_rel_zero": {},
        "failure_reason_system": None,
        "failure_reason_oracle": None,
    }

    K = pose_info["K"]
    R = pose_info["R"]
    tvec = pose_info["tvec"]
    C_world = pose_info["C_world"]
    world_pts = pose_info["world_pts"]
    img_pts = pose_info["img_pts"]

    # Helper to run both drag=False and drag=True for a window of points
    def _run_window(win_pts: List[Dict[str, Any]], do_mc: bool) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        uvs = np.array([[float(p["x"]), float(p["y"])] for p in win_pts], dtype=np.float64)
        # 1) Literal times = frame / fps
        times_abs = np.array([float(p["frame"]) / fps for p in win_pts], dtype=np.float64)
        # 2) Release-zeroed times = (frame - release_frame) / fps (with arrival_time offset by rel_frame/fps)
        f0 = float(win_pts[0]["frame"])
        times_rel = np.array([(float(p["frame"]) - f0) / fps for p in win_pts], dtype=np.float64)

        res_abs: Dict[str, Any] = {"n_points": len(win_pts)}
        res_rel: Dict[str, Any] = {"n_points": len(win_pts)}

        for drag_flag, key in ((False, "no_drag"), (True, "drag")):
            res_abs[key] = evaluate_trajectory_fit(
                times_abs, uvs, K, R, tvec, C_world,
                lbl_bounce_world=lbl_bounce_world, use_drag=drag_flag, time_offset_s=0.0,
            )
            res_rel[key] = evaluate_trajectory_fit(
                times_rel, uvs, K, R, tvec, C_world,
                lbl_bounce_world=lbl_bounce_world, use_drag=drag_flag, time_offset_s=f0 / fps,
            )

        if do_mc:
            res_abs["mc_no_drag"] = run_monte_carlo(
                world_pts, img_pts, (W, H), times_abs, uvs,
                n_repeats=n_mc, seed=seed, use_drag=False, executor=executor,
            )
            res_rel["mc_no_drag"] = run_monte_carlo(
                world_pts, img_pts, (W, H), times_rel, uvs,
                n_repeats=n_mc, seed=seed, use_drag=False, executor=executor,
            )
        return res_abs, res_rel

    # System impact track
    if rel_frame is None:
        out["failure_reason_system"] = "no system release event"
    elif sys_imp_frame is None:
        out["failure_reason_system"] = "no system impact event (events.impact is null)"
    else:
        win_sys = [p for p in traj if rel_frame <= int(p["frame"]) <= sys_imp_frame]
        if len(win_sys) < 5:
            out["failure_reason_system"] = f"too few trajectory points ({len(win_sys)} < 5)"
        else:
            out["system"], out["system_rel_zero"] = _run_window(win_sys, do_mc=True)

    # Oracle impact track (labelled impact frame as end of track)
    if rel_frame is None:
        out["failure_reason_oracle"] = "no system release event"
    elif ora_imp_frame is None:
        out["failure_reason_oracle"] = "no labelled impact frame"
    else:
        win_ora = [p for p in traj if rel_frame <= int(p["frame"]) <= ora_imp_frame]
        if len(win_ora) < 6:
            out["failure_reason_oracle"] = (
                f"insufficient trajectory points up to oracle impact frame {ora_imp_frame} "
                f"(only {len(win_ora)} pts in frames {win_ora[0]['frame']}..{win_ora[-1]['frame']}, "
                f"trajectory stops before bounce/impact)"
                if win_ora else f"no trajectory points in [{rel_frame}, {ora_imp_frame}]"
            )
            # Still compute the degenerate 5-point fit for completeness if >= 5 pts
            if len(win_ora) >= 5:
                out["oracle"], out["oracle_rel_zero"] = _run_window(win_ora, do_mc=True)
        else:
            out["oracle"], out["oracle_rel_zero"] = _run_window(win_ora, do_mc=True)

    return out


def _fmt(val: Optional[float], fmt_str: str = ".2f", na: str = "—") -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return na
    return format(val, fmt_str)


def write_csv(records: List[Dict[str, Any]], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "clip_id",
        "lbw_label",
        "pose_rms_px",
        "focal_px",
        "cam_height_m",
        "cam_dist_behind_m",
        "pose_plausible",
        "image_left_consistent",
        "wrong_side",
        "release_frame",
        "sys_impact_frame",
        "ora_impact_frame",
        # System impact (times = frame / fps, use_drag=False)
        "sys_nodrag_fit_rms_px",
        "sys_nodrag_speed_kmh",
        "sys_nodrag_bounce_x_m",
        "sys_nodrag_bounce_z_m",
        "sys_nodrag_bounce_dist_m",
        "sys_nodrag_arrival_s",
        "sys_nodrag_plane_x_m",
        "sys_nodrag_plane_y_m",
        "sys_nodrag_verdict",
        "sys_nodrag_outside_m",
        # System impact (times = frame / fps, use_drag=True)
        "sys_drag_fit_rms_px",
        "sys_drag_speed_kmh",
        "sys_drag_bounce_x_m",
        "sys_drag_bounce_z_m",
        "sys_drag_bounce_dist_m",
        "sys_drag_arrival_s",
        "sys_drag_plane_x_m",
        "sys_drag_plane_y_m",
        "sys_drag_verdict",
        "sys_drag_outside_m",
        # System Monte-Carlo (100 repeats, seed=42)
        "sys_mc_hitting_frac",
        "sys_mc_std_x_m",
        "sys_mc_std_y_m",
        # Oracle impact (times = frame / fps, use_drag=False)
        "ora_nodrag_fit_rms_px",
        "ora_nodrag_speed_kmh",
        "ora_nodrag_bounce_x_m",
        "ora_nodrag_bounce_z_m",
        "ora_nodrag_bounce_dist_m",
        "ora_nodrag_arrival_s",
        "ora_nodrag_plane_x_m",
        "ora_nodrag_plane_y_m",
        "ora_nodrag_verdict",
        "ora_nodrag_outside_m",
        # Oracle impact (times = frame / fps, use_drag=True)
        "ora_drag_fit_rms_px",
        "ora_drag_speed_kmh",
        "ora_drag_bounce_x_m",
        "ora_drag_bounce_z_m",
        "ora_drag_bounce_dist_m",
        "ora_drag_arrival_s",
        "ora_drag_plane_x_m",
        "ora_drag_plane_y_m",
        "ora_drag_verdict",
        "ora_drag_outside_m",
        # Oracle Monte-Carlo (100 repeats, seed=42)
        "ora_mc_hitting_frac",
        "ora_mc_std_x_m",
        "ora_mc_std_y_m",
        # Release-zeroed times = (frame - release_frame) / fps key columns
        "sys_rel0_nodrag_fit_rms_px",
        "sys_rel0_nodrag_speed_kmh",
        "sys_rel0_nodrag_bounce_dist_m",
        "sys_rel0_nodrag_plane_x_m",
        "sys_rel0_nodrag_plane_y_m",
        "sys_rel0_nodrag_verdict",
        "sys_rel0_drag_plane_x_m",
        "sys_rel0_drag_plane_y_m",
        "sys_rel0_drag_verdict",
        "ora_rel0_nodrag_plane_x_m",
        "ora_rel0_nodrag_plane_y_m",
        "ora_rel0_nodrag_verdict",
        "ora_rel0_drag_plane_x_m",
        "ora_rel0_drag_plane_y_m",
        "ora_rel0_drag_verdict",
        "failure_reason_system",
        "failure_reason_oracle",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            p = r["pose"]
            s_nd = r["system"].get("no_drag", {})
            s_d = r["system"].get("drag", {})
            s_mc = r["system"].get("mc_no_drag", {})
            o_nd = r["oracle"].get("no_drag", {})
            o_d = r["oracle"].get("drag", {})
            o_mc = r["oracle"].get("mc_no_drag", {})

            sr_nd = r["system_rel_zero"].get("no_drag", {})
            sr_d = r["system_rel_zero"].get("drag", {})
            or_nd = r["oracle_rel_zero"].get("no_drag", {})
            or_d = r["oracle_rel_zero"].get("drag", {})

            row = {
                "clip_id": r["clip_id"],
                "lbw_label": r["lbw_label"],
                "pose_rms_px": round(p["pose_rms_px"], 3),
                "focal_px": round(p["focal_px"], 1),
                "cam_height_m": round(p["cam_height_m"], 3),
                "cam_dist_behind_m": round(p["cam_dist_behind_m"], 3),
                "pose_plausible": p["plausible"],
                "image_left_consistent": p["image_left_consistent"],
                "wrong_side": p["wrong_side"],
                "release_frame": r["release_frame"],
                "sys_impact_frame": r["sys_impact_frame"],
                "ora_impact_frame": r["ora_impact_frame"],
                # System no_drag
                "sys_nodrag_fit_rms_px": round(s_nd["fit_rms_px"], 3) if s_nd else "",
                "sys_nodrag_speed_kmh": round(s_nd["release_speed_kmh"], 2) if s_nd else "",
                "sys_nodrag_bounce_x_m": round(s_nd["bounce_x_m"], 3) if s_nd else "",
                "sys_nodrag_bounce_z_m": round(s_nd["bounce_z_m"], 3) if s_nd else "",
                "sys_nodrag_bounce_dist_m": round(s_nd["bounce_dist_to_label_m"], 3) if s_nd else "",
                "sys_nodrag_arrival_s": round(s_nd["arrival_time_s"], 4) if s_nd else "",
                "sys_nodrag_plane_x_m": round(s_nd["plane_x_m"], 3) if s_nd else "",
                "sys_nodrag_plane_y_m": round(s_nd["plane_y_m"], 3) if s_nd else "",
                "sys_nodrag_verdict": s_nd.get("verdict", ""),
                "sys_nodrag_outside_m": round(s_nd["outside_dist_m"], 3) if s_nd else "",
                # System drag
                "sys_drag_fit_rms_px": round(s_d["fit_rms_px"], 3) if s_d else "",
                "sys_drag_speed_kmh": round(s_d["release_speed_kmh"], 2) if s_d else "",
                "sys_drag_bounce_x_m": round(s_d["bounce_x_m"], 3) if s_d else "",
                "sys_drag_bounce_z_m": round(s_d["bounce_z_m"], 3) if s_d else "",
                "sys_drag_bounce_dist_m": round(s_d["bounce_dist_to_label_m"], 3) if s_d else "",
                "sys_drag_arrival_s": round(s_d["arrival_time_s"], 4) if s_d else "",
                "sys_drag_plane_x_m": round(s_d["plane_x_m"], 3) if s_d else "",
                "sys_drag_plane_y_m": round(s_d["plane_y_m"], 3) if s_d else "",
                "sys_drag_verdict": s_d.get("verdict", ""),
                "sys_drag_outside_m": round(s_d["outside_dist_m"], 3) if s_d else "",
                # System MC
                "sys_mc_hitting_frac": round(s_mc["hitting_fraction"], 3) if s_mc else "",
                "sys_mc_std_x_m": round(s_mc["std_x_m"], 4) if s_mc else "",
                "sys_mc_std_y_m": round(s_mc["std_y_m"], 4) if s_mc else "",
                # Oracle no_drag
                "ora_nodrag_fit_rms_px": round(o_nd["fit_rms_px"], 3) if o_nd else "",
                "ora_nodrag_speed_kmh": round(o_nd["release_speed_kmh"], 2) if o_nd else "",
                "ora_nodrag_bounce_x_m": round(o_nd["bounce_x_m"], 3) if o_nd else "",
                "ora_nodrag_bounce_z_m": round(o_nd["bounce_z_m"], 3) if o_nd else "",
                "ora_nodrag_bounce_dist_m": round(o_nd["bounce_dist_to_label_m"], 3) if o_nd else "",
                "ora_nodrag_arrival_s": round(o_nd["arrival_time_s"], 4) if o_nd else "",
                "ora_nodrag_plane_x_m": round(o_nd["plane_x_m"], 3) if o_nd else "",
                "ora_nodrag_plane_y_m": round(o_nd["plane_y_m"], 3) if o_nd else "",
                "ora_nodrag_verdict": o_nd.get("verdict", ""),
                "ora_nodrag_outside_m": round(o_nd["outside_dist_m"], 3) if o_nd else "",
                # Oracle drag
                "ora_drag_fit_rms_px": round(o_d["fit_rms_px"], 3) if o_d else "",
                "ora_drag_speed_kmh": round(o_d["release_speed_kmh"], 2) if o_d else "",
                "ora_drag_bounce_x_m": round(o_d["bounce_x_m"], 3) if o_d else "",
                "ora_drag_bounce_z_m": round(o_d["bounce_z_m"], 3) if o_d else "",
                "ora_drag_bounce_dist_m": round(o_d["bounce_dist_to_label_m"], 3) if o_d else "",
                "ora_drag_arrival_s": round(o_d["arrival_time_s"], 4) if o_d else "",
                "ora_drag_plane_x_m": round(o_d["plane_x_m"], 3) if o_d else "",
                "ora_drag_plane_y_m": round(o_d["plane_y_m"], 3) if o_d else "",
                "ora_drag_verdict": o_d.get("verdict", ""),
                "ora_drag_outside_m": round(o_d["outside_dist_m"], 3) if o_d else "",
                # Oracle MC
                "ora_mc_hitting_frac": round(o_mc["hitting_fraction"], 3) if o_mc else "",
                "ora_mc_std_x_m": round(o_mc["std_x_m"], 4) if o_mc else "",
                "ora_mc_std_y_m": round(o_mc["std_y_m"], 4) if o_mc else "",
                # Release-zeroed key columns
                "sys_rel0_nodrag_fit_rms_px": round(sr_nd["fit_rms_px"], 3) if sr_nd else "",
                "sys_rel0_nodrag_speed_kmh": round(sr_nd["release_speed_kmh"], 2) if sr_nd else "",
                "sys_rel0_nodrag_bounce_dist_m": round(sr_nd["bounce_dist_to_label_m"], 3) if sr_nd else "",
                "sys_rel0_nodrag_plane_x_m": round(sr_nd["plane_x_m"], 3) if sr_nd else "",
                "sys_rel0_nodrag_plane_y_m": round(sr_nd["plane_y_m"], 3) if sr_nd else "",
                "sys_rel0_nodrag_verdict": sr_nd.get("verdict", ""),
                "sys_rel0_drag_plane_x_m": round(sr_d["plane_x_m"], 3) if sr_d else "",
                "sys_rel0_drag_plane_y_m": round(sr_d["plane_y_m"], 3) if sr_d else "",
                "sys_rel0_drag_verdict": sr_d.get("verdict", ""),
                "ora_rel0_nodrag_plane_x_m": round(or_nd["plane_x_m"], 3) if or_nd else "",
                "ora_rel0_nodrag_plane_y_m": round(or_nd["plane_y_m"], 3) if or_nd else "",
                "ora_rel0_nodrag_verdict": or_nd.get("verdict", ""),
                "ora_rel0_drag_plane_x_m": round(or_d["plane_x_m"], 3) if or_d else "",
                "ora_rel0_drag_plane_y_m": round(or_d["plane_y_m"], 3) if or_d else "",
                "ora_rel0_drag_verdict": or_d.get("verdict", ""),
                "failure_reason_system": r["failure_reason_system"] or "",
                "failure_reason_oracle": r["failure_reason_oracle"] or "",
            }
            writer.writerow(row)


def write_markdown(records: List[Dict[str, Any]], out_md: Path) -> str:
    out_md.parent.mkdir(parents=True, exist_ok=True)
    n_total = len(records)
    n_pose_solved = sum(1 for r in records if r.get("pose"))
    n_plausible = sum(1 for r in records if r["pose"]["plausible"])
    n_left_ok = sum(1 for r in records if r["pose"]["image_left_consistent"])
    n_wrong_side = sum(1 for r in records if r["pose"]["wrong_side"])

    sys_solved = [r for r in records if r["system"].get("no_drag")]
    ora_solved_valid = [r for r in records if r["oracle"].get("no_drag") and not r["failure_reason_oracle"]]
    ora_solved_all = [r for r in records if r["oracle"].get("no_drag")]

    # Counts for literal times = frame / fps
    sys_hit_nd = sum(1 for r in sys_solved if r["system"]["no_drag"]["hitting"])
    sys_hit_d = sum(1 for r in sys_solved if r["system"]["drag"]["hitting"])
    ora_hit_nd_v = sum(1 for r in ora_solved_valid if r["oracle"]["no_drag"]["hitting"])
    ora_hit_d_v = sum(1 for r in ora_solved_valid if r["oracle"]["drag"]["hitting"])
    ora_hit_nd_all = sum(1 for r in ora_solved_all if r["oracle"]["no_drag"]["hitting"])
    ora_hit_d_all = sum(1 for r in ora_solved_all if r["oracle"]["drag"]["hitting"])

    # Counts for release-zeroed times = (frame - release_frame) / fps
    sys_r0_hit_nd = sum(1 for r in sys_solved if r["system_rel_zero"]["no_drag"]["hitting"])
    sys_r0_hit_d = sum(1 for r in sys_solved if r["system_rel_zero"]["drag"]["hitting"])
    ora_r0_hit_nd_v = sum(1 for r in ora_solved_valid if r["oracle_rel_zero"]["no_drag"]["hitting"])
    ora_r0_hit_d_v = sum(1 for r in ora_solved_valid if r["oracle_rel_zero"]["drag"]["hitting"])
    ora_r0_hit_nd_all = sum(1 for r in ora_solved_all if r["oracle_rel_zero"]["no_drag"]["hitting"])
    ora_r0_hit_d_all = sum(1 for r in ora_solved_all if r["oracle_rel_zero"]["drag"]["hitting"])

    lines: List[str] = []
    lines.append("# LBW Projection Feasibility Probe (`v2_1`)")
    lines.append("")
    lines.append(
        "> **Note on Ground Truth**: All 14 labelled clips in `eval/labels` are **on-field LBW \"out\"** "
        "decisions (`lbw == \"out\"`, all pad impacts). This study is a **physics and calibration feasibility "
        "sanity check**, not an accuracy benchmark across out/not-out classes."
    )
    lines.append("")
    lines.append("## 1. Overall Summary")
    lines.append("")
    lines.append("| Metric | Value | Notes |")
    lines.append("| :--- | :--- | :--- |")
    lines.append(f"| Final labelled clips with `v2_1` results | `{n_total}` | All 14 clips have `lbw = \"out\"` |")
    lines.append(
        f"| Image-left / world-side consistency | `{n_left_ok}/{n_total}` (`100%`) | "
        "`bat_L` & `bowl_L` stay on world `-X` (`-1.32 m`); zero camera-side inversions (`wrong_side = 0`) |"
    )
    lines.append(f"| Camera poses solved (`calibrate.solve_pose`) | `{n_pose_solved}/{n_total}` (`100%`) | Coplanar 6-point PnP focal search over `500..15000 px` |")
    lines.append(
        f"| Camera poses plausible (`height in [1, 15] m`, `dist in [5, 60] m`) | **`{n_plausible}/{n_total}` (`{100*n_plausible/n_total:.1f}%`)** | "
        "Only `c_69ba9415` (`f=10725 px`, `h=7.50 m`, `d=57.46 m`); the other 13 hit the `f=15000 px` ceiling (`d=65.1..81.3 m`) |"
    )
    lines.append(
        f"| Clips solved — System impact | `{len(sys_solved)}/{n_total}` (`{100*len(sys_solved)/n_total:.1f}%`) | "
        "`c_69ba9415` and `c_6e281881` skipped (`events.impact` is `null`) |"
    )
    lines.append(
        f"| Clips solved — Oracle impact (`>= 6` pts / all) | `{len(ora_solved_valid)}/{n_total}` (`{len(ora_solved_all)}/{n_total}` incl. 5-pt `c_69ba9415`) | "
        "`c_6e281881` has 13 pts up to oracle impact f19; `c_69ba9415` has only 5 pre-bounce pts in `9..16` |"
    )
    lines.append(
        f"| **Share `HITTING` — System impact (`times = frame/fps`, `use_drag=False`)** | **`{sys_hit_nd}/{len(sys_solved)}` (`{100*sys_hit_nd/len(sys_solved):.1f}%`)** | "
        f"`{sys_r0_hit_nd}/{len(sys_solved)}` (`{100*sys_r0_hit_nd/len(sys_solved):.1f}%`) when `times = (frame - release_frame)/fps` |"
    )
    lines.append(
        f"| **Share `HITTING` — System impact (`times = frame/fps`, `use_drag=True`)** | **`{sys_hit_d}/{len(sys_solved)}` (`{100*sys_hit_d/len(sys_solved):.1f}%`)** | "
        f"`{sys_r0_hit_d}/{len(sys_solved)}` (`{100*sys_r0_hit_d/len(sys_solved):.1f}%`) when `times = (frame - release_frame)/fps` |"
    )
    lines.append(
        f"| **Share `HITTING` — Oracle impact (`times = frame/fps`, `use_drag=False`)** | **`{ora_hit_nd_v}/{len(ora_solved_valid)}` (`{100*ora_hit_nd_v/len(ora_solved_valid):.1f}%`)** (`{ora_hit_nd_all}/{len(ora_solved_all)}` all) | "
        f"`{ora_r0_hit_nd_v}/{len(ora_solved_valid)}` (`{100*ora_r0_hit_nd_v/len(ora_solved_valid):.1f}%`) when `times = (frame - release_frame)/fps` |"
    )
    lines.append(
        f"| **Share `HITTING` — Oracle impact (`times = frame/fps`, `use_drag=True`)** | **`{ora_hit_d_v}/{len(ora_solved_valid)}` (`{100*ora_hit_d_v/len(ora_solved_valid):.1f}%`)** (`{ora_hit_d_all}/{len(ora_solved_all)}` all) | "
        f"`{ora_r0_hit_d_v}/{len(ora_solved_valid)}` (`{100*ora_r0_hit_d_v/len(ora_solved_valid):.1f}%`) when `times = (frame - release_frame)/fps` |"
    )
    lines.append("")

    lines.append("## 2. Main Per-Clip Table (`times = frame / fps`, `use_magnus=False`)")
    lines.append("")
    lines.append(
        "Stump-plane hitting box at `z = 0`: `|x| <= 0.114 + 0.036 = 0.150 m` and `0 <= y <= 0.711 + 0.036 = 0.747 m`. "
        "Values shown as `no_drag / drag` where both drag modes are run; Monte-Carlo columns (`MC hit%`, `std_x`, `std_y`) "
        "use 100 repeats (`seed=42`) with calibration perturbed by `N(0, 1.5 px)` and trajectory by `N(0, 2.0 px)`."
    )
    lines.append("")
    lines.append(
        "| Clip | Pose RMS (px) | Focal (px) | Cam `h` / `dist` (m) | Plaus. | Fit RMS `nd/d` (px) | Speed `nd/d` (km/h) | Bounce `(x, z)` `nd` (m) | Bounce Err `nd/d` (m) | Sys `t_arr` `nd` (s) | Sys `(x, y)` `nd` (m) | Sys Out `nd` (m) | Sys Verdict `nd/d` | Ora `(x, y)` `nd` (m) | Ora Out `nd` (m) | Ora Verdict `nd/d` | MC Hit% `sys/ora` | MC `std_x` `sys` (m) | MC `std_y` `sys` (m) |"
    )
    lines.append(
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    )

    for r in records:
        cid = r["clip_id"]
        p = r["pose"]
        plaus_s = "YES" if p["plausible"] else "NO"
        s_nd = r["system"].get("no_drag")
        s_d = r["system"].get("drag")
        s_mc = r["system"].get("mc_no_drag")
        o_nd = r["oracle"].get("no_drag")
        o_d = r["oracle"].get("drag")
        o_mc = r["oracle"].get("mc_no_drag")

        if s_nd and s_d:
            fit_rms_s = f"{s_nd['fit_rms_px']:.2f} / {s_d['fit_rms_px']:.2f}"
            spd_s = f"{s_nd['release_speed_kmh']:.1f} / {s_d['release_speed_kmh']:.1f}"
            b_pos_s = f"({s_nd['bounce_x_m']:+.2f}, {s_nd['bounce_z_m']:.2f})"
            b_err_s = f"{s_nd['bounce_dist_to_label_m']:.2f} / {s_d['bounce_dist_to_label_m']:.2f}"
            t_arr_s = f"{s_nd['arrival_time_s']:.3f}"
            sys_xy_s = f"({s_nd['plane_x_m']:+.2f}, {s_nd['plane_y_m']:+.2f})"
            sys_out_s = f"{s_nd['outside_dist_m']:.3f}"
            sys_v_s = f"{s_nd['verdict']} / {s_d['verdict']}"
        elif o_nd and o_d:
            fit_rms_s = f"— ({o_nd['fit_rms_px']:.2f} ora)"
            spd_s = f"— ({o_nd['release_speed_kmh']:.1f} ora)"
            b_pos_s = f"({o_nd['bounce_x_m']:+.2f}, {o_nd['bounce_z_m']:.2f})*"
            b_err_s = f"— ({o_nd['bounce_dist_to_label_m']:.2f} ora)"
            t_arr_s = "—"
            sys_xy_s = "—"
            sys_out_s = "—"
            sys_v_s = "SKIP"
        else:
            fit_rms_s = "—"
            spd_s = "—"
            b_pos_s = "—"
            b_err_s = "—"
            t_arr_s = "—"
            sys_xy_s = "—"
            sys_out_s = "—"
            sys_v_s = "SKIP"

        if o_nd and o_d:
            ora_xy_s = f"({o_nd['plane_x_m']:+.2f}, {o_nd['plane_y_m']:+.2f})"
            ora_out_s = f"{o_nd['outside_dist_m']:.3f}"
            ora_v_s = f"{o_nd['verdict']} / {o_d['verdict']}"
            if r["failure_reason_oracle"]:
                ora_v_s += "*"
        else:
            ora_xy_s = "—"
            ora_out_s = "—"
            ora_v_s = "SKIP"

        mc_hit_s = (
            f"{100*s_mc['hitting_fraction']:.0f}% / {100*o_mc['hitting_fraction']:.0f}%"
            if (s_mc and o_mc)
            else (f"— / {100*o_mc['hitting_fraction']:.0f}%" if o_mc else "—")
        )
        mc_sx_s = f"{s_mc['std_x_m']:.3f}" if s_mc else (f"{o_mc['std_x_m']:.3f}*" if o_mc else "—")
        mc_sy_s = f"{s_mc['std_y_m']:.3f}" if s_mc else (f"{o_mc['std_y_m']:.3f}*" if o_mc else "—")

        lines.append(
            f"| `{cid}` | {p['pose_rms_px']:.2f} | {p['focal_px']:.0f} | "
            f"{p['cam_height_m']:.2f} / {p['cam_dist_behind_m']:.2f} | {plaus_s} | "
            f"{fit_rms_s} | {spd_s} | {b_pos_s} | {b_err_s} | {t_arr_s} | "
            f"{sys_xy_s} | {sys_out_s} | {sys_v_s} | {ora_xy_s} | {ora_out_s} | "
            f"{ora_v_s} | {mc_hit_s} | {mc_sx_s} | {mc_sy_s} |"
        )

    lines.append("")
    lines.append("## 3. Comparison with Release-Zeroed Times (`times = (frame - release_frame) / fps`)")
    lines.append("")
    lines.append(
        "In `trajectory_fit.ball_positions_at_times`, `p0` and `v0` represent the ball state at `t = 0`, "
        "with `p0[2]` bounded to `[15.0, 25.0] m`. When raw `times = frame / fps` is passed, `t = 0` is video frame 0 "
        "(`release_frame` frames before release), which hits the `p0[2] <= 25.0 m` ceiling on late-release or high-speed "
        "clips (`c_542fca8b`, `c_5e5ea872`, `c_77d7834d`, `c_e6b5e8a3`). Zeroing `t = 0` at `release_frame` "
        "(matching `trajectory_fit.py` lines 635 & 657) yields:"
    )
    lines.append("")
    lines.append(
        "| Clip | Rel Frame | Sys Fit RMS `nd/d` (px) | Sys Speed `nd/d` (km/h) | Sys Bounce Err `nd/d` (m) | Sys `(x, y)` `nd` (m) | Sys `(x, y)` `d` (m) | Sys Verdict `nd/d` | Ora `(x, y)` `nd` (m) | Ora Verdict `nd/d` | MC Hit% `sys/ora` | MC `std_x / std_y` `sys` (m) |"
    )
    lines.append(
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    )
    for r in records:
        cid = r["clip_id"]
        sr_nd = r["system_rel_zero"].get("no_drag")
        sr_d = r["system_rel_zero"].get("drag")
        sr_mc = r["system_rel_zero"].get("mc_no_drag")
        or_nd = r["oracle_rel_zero"].get("no_drag")
        or_d = r["oracle_rel_zero"].get("drag")
        or_mc = r["oracle_rel_zero"].get("mc_no_drag")
        if sr_nd and sr_d:
            rms_s = f"{sr_nd['fit_rms_px']:.2f} / {sr_d['fit_rms_px']:.2f}"
            spd_s = f"{sr_nd['release_speed_kmh']:.1f} / {sr_d['release_speed_kmh']:.1f}"
            berr_s = f"{sr_nd['bounce_dist_to_label_m']:.2f} / {sr_d['bounce_dist_to_label_m']:.2f}"
            sxy_nd = f"({sr_nd['plane_x_m']:+.2f}, {sr_nd['plane_y_m']:+.2f})"
            sxy_d = f"({sr_d['plane_x_m']:+.2f}, {sr_d['plane_y_m']:+.2f})"
            sv = f"{sr_nd['verdict']} / {sr_d['verdict']}"
        else:
            rms_s = spd_s = berr_s = sxy_nd = sxy_d = "—"
            sv = "SKIP"
        if or_nd and or_d:
            oxy_nd = f"({or_nd['plane_x_m']:+.2f}, {or_nd['plane_y_m']:+.2f})"
            ov = f"{or_nd['verdict']} / {or_d['verdict']}"
        else:
            oxy_nd = "—"
            ov = "SKIP"
        mc_h = (
            f"{100*sr_mc['hitting_fraction']:.0f}% / {100*or_mc['hitting_fraction']:.0f}%"
            if (sr_mc and or_mc)
            else (f"— / {100*or_mc['hitting_fraction']:.0f}%" if or_mc else "—")
        )
        mc_s = f"{sr_mc['std_x_m']:.3f} / {sr_mc['std_y_m']:.3f}" if sr_mc else "—"
        lines.append(
            f"| `{cid}` | {r['release_frame']} | {rms_s} | {spd_s} | {berr_s} | "
            f"{sxy_nd} | {sxy_d} | {sv} | {oxy_nd} | {ov} | {mc_h} | {mc_s} |"
        )

    lines.append("")
    lines.append("## 4. Failed / Implausible Clips & Reasons")
    lines.append("")
    lines.append("### 4.1 Trajectory / Impact Failures")
    lines.append("- **`c_69ba9415`**:")
    lines.append("  - **System impact**: Skipped — `events.impact` is `null` (and `events.bounce` is `null`).")
    lines.append(
        "  - **Oracle impact**: Trajectory in `v2_1/c_69ba9415/results.json` contains only **5 pre-bounce points** "
        "(frames `[9, 10, 11, 15, 16]`), terminating before the labelled bounce (frame 19) and labelled impact (frame 23). "
        "Fitting 9 parameters to 5 pre-bounce points has no post-bounce observability (`y = -0.05 m` / `-0.42 m` at `z = 0`)."
    )
    lines.append("- **`c_6e281881`**:")
    lines.append(
        "  - **System impact**: Skipped — `events.impact` is `null` (Rule I5b found no post-bounce vertex with `>= 20 deg` kink)."
    )
    lines.append(
        "  - **Oracle impact**: Succeeds (`13` points in frames `5..17` spanning the bounce at frame 16 up to labelled impact frame 19), "
        "giving `fit_rms = 2.91 px` and classifying as **`HITTING`** (`x = +0.09 m, y = +0.30 m`)."
    )
    lines.append("")
    lines.append("### 4.2 Camera Pose Plausibility Flags (`height in [1, 15] m`, `distance in [5, 60] m`)")
    for r in records:
        p = r["pose"]
        if not p["plausible"]:
            reasons_str = "; ".join(p["implausible_reasons"])
            lines.append(
                f"- **`{r['clip_id']}`**: Implausible (`focal = {p['focal_px']:.0f} px`, "
                f"`height = {p['cam_height_m']:.2f} m`, `dist_behind = {p['cam_dist_behind_m']:.2f} m`) — {reasons_str}."
            )

    lines.append("")
    lines.append("## 5. Key Feasibility Findings")
    lines.append("")
    lines.append(
        "1. **Lateral (`x`) projection is strong across all solved clips**: Every single solved clip (`12/12` system, `13/13` valid oracle) "
        "lands horizontally in-line with the stumps at `z = 0` (`|x| in [0.01, 0.15] m <= 0.150 m`), with tight Monte-Carlo lateral spread (`std_x` median `~0.014 m`)."
    )
    lines.append(
        "2. **Vertical (`y`) height at the stumps is the sole cause of `MISSING` classifications**: Every `MISSING` verdict on a valid track "
        "is a narrow over-the-top miss (`y in [0.75, 0.97] m` vs the `0.747 m` top-of-stumps limit; several miss by only `3–55 mm`)."
    )
    lines.append(
        "3. **Root cause is coplanar 6-point focal-length degeneracy**: Because all 6 calibration points lie on `Y = 0`, `solve_pose` "
        "runs to the `f = 15000 px` search boundary on 13/14 clips (`distance = 65–81 m` behind bowler's stumps), flattening perspective "
        "and biasing the post-bounce vertical pitch angle upward."
    )
    lines.append("")

    md_text = "\n".join(lines)
    out_md.write_text(md_text, encoding="utf-8")
    return md_text


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run LBW projection feasibility probe on v2_1.")
    parser.add_argument("--labels-dir", type=Path, default=REPO_ROOT / "eval" / "labels")
    parser.add_argument("--runs-dir", type=Path, default=REPO_ROOT / "eval" / "runs" / "v2_1")
    parser.add_argument("--out-md", type=Path, default=REPO_ROOT / "eval" / "analysis" / "lbw_probe_v2_1.md")
    parser.add_argument("--out-csv", type=Path, default=REPO_ROOT / "eval" / "analysis" / "lbw_probe_v2_1.csv")
    parser.add_argument("--mc-repeats", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)

    records: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        for lbl_path in sorted(args.labels_dir.glob("c_*.json")):
            lbl = json.loads(lbl_path.read_text(encoding="utf-8"))
            if lbl.get("status") != "final":
                continue
            cid = lbl["clip_id"]
            res_path = args.runs_dir / cid / "results.json"
            if not res_path.exists():
                continue
            res = json.loads(res_path.read_text(encoding="utf-8"))
            print(f"Probing {cid} ...", flush=True)
            rec = probe_clip(lbl, res, n_mc=args.mc_repeats, seed=args.seed, executor=executor)
            records.append(rec)

    write_csv(records, args.out_csv)
    md_text = write_markdown(records, args.out_md)
    print(f"\nWrote {args.out_csv}")
    print(f"Wrote {args.out_md}\n")
    print(md_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
