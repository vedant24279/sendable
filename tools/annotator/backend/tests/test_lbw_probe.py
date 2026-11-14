"""Unit tests for lbw_probe.py:
- plane-intersection and LBW classification helpers
- calibration-to-keypoints inverse mapping and camera-side checks
- Monte-Carlo helper determinism and spread with a fixed seed
- synthetic 3D round trip: generate trajectory with ball_positions_at_times,
  project through a known pose, recover focal length within 1% and (x, y) at z=0 within 5 cm.
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
import pytest

from backend.pipeline.reconstruct3d.calibrate import solve_pose
from backend.pipeline.reconstruct3d.run_full_pipeline import keypoints_to_calibration
from backend.pipeline.reconstruct3d.trajectory_fit import (
    G,
    ball_positions_at_times,
    fit_trajectory,
    project_world,
)
from backend.pipeline.reconstruct3d.world_points import WORLD_POINTS_M
from lbw_probe import (
    HITTING_X_LIMIT_M,
    HITTING_Y_MAX_M,
    calibration_to_keypoints,
    check_side_and_camera,
    classify_lbw,
    evaluate_trajectory_fit,
    intersect_stump_plane,
    run_monte_carlo,
    write_csv,
    write_markdown,
)


def _make_known_camera_pose(
    f_true: float = 3510.0,
    image_size: tuple[int, int] = (1920, 1080),
    C_true: tuple[float, float, float] = (0.0, 6.0, 50.0),
    target: tuple[float, float, float] = (0.0, 0.5, 10.0),
):
    W, H = image_size
    K = np.array(
        [[f_true, 0.0, W / 2.0], [0.0, f_true, H / 2.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    C_arr = np.asarray(C_true, dtype=np.float64)
    tgt_arr = np.asarray(target, dtype=np.float64)
    z_cam = (tgt_arr - C_arr) / np.linalg.norm(tgt_arr - C_arr)
    up_world = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    x_cam = np.cross(z_cam, up_world)
    x_cam /= np.linalg.norm(x_cam)
    y_cam = np.cross(z_cam, x_cam)
    R = np.vstack([x_cam, y_cam, z_cam])
    tvec = -R @ C_arr
    rvec, _ = cv2.Rodrigues(R)
    return K, R, rvec, tvec, C_arr


def test_calibration_to_keypoints_is_exact_inverse() -> None:
    cal = {
        "bat_L": [715.2, 508.2],
        "bat_R": [1178.6, 506.7],
        "bowl_L": [684.1, 963.1],
        "bowl_R": [1225.6, 961.2],
        "bat_stump": [948.9, 480.2],
        "bowl_stump": [955.3, 999.5],
    }
    kp_data = calibration_to_keypoints(cal)
    round_trip = keypoints_to_calibration(kp_data)
    for key, val in cal.items():
        assert round_trip[key] == pytest.approx(val)


def test_check_side_and_camera_warns_on_wrong_side() -> None:
    cal = {
        "bat_L": [715.0, 508.0],
        "bat_R": [1179.0, 507.0],
        "bowl_L": [684.0, 963.0],
        "bowl_R": [1226.0, 961.0],
        "bat_stump": [949.0, 480.0],
        "bowl_stump": [955.0, 1000.0],
    }
    _, R_good, _, _, C_good = _make_known_camera_pose()
    ok_res = check_side_and_camera(cal, C_good, R_good)
    assert ok_res["image_left_consistent"] is True
    assert ok_res["wrong_side"] is False
    assert ok_res["warnings"] == []

    # Camera on wrong side of pitch (behind striker's end, Z < 0)
    C_bad = np.array([0.0, 5.0, -10.0])
    bad_res = check_side_and_camera(cal, C_bad, R_good)
    assert bad_res["wrong_side"] is True
    assert any("not behind bowler's stumps" in w for w in bad_res["warnings"])


def test_classify_lbw_boundaries_and_outside_distance() -> None:
    assert HITTING_X_LIMIT_M == pytest.approx(0.114 + 0.036)
    assert HITTING_Y_MAX_M == pytest.approx(0.711 + 0.036)

    # Dead centre
    c0 = classify_lbw(0.0, 0.40)
    assert c0["hitting"] is True
    assert c0["verdict"] == "HITTING"
    assert c0["outside_dist_m"] == pytest.approx(0.0)

    # Exact boundary corners -> HITTING
    assert classify_lbw(0.150, 0.747)["hitting"] is True
    assert classify_lbw(-0.150, 0.0)["hitting"] is True

    # Slightly over top of stumps only
    c_high = classify_lbw(0.05, 0.797)
    assert c_high["hitting"] is False
    assert c_high["verdict"] == "MISSING"
    assert c_high["dx_outside_m"] == pytest.approx(0.0)
    assert c_high["dy_outside_m"] == pytest.approx(0.05)
    assert c_high["outside_dist_m"] == pytest.approx(0.05)

    # Slightly wide outside off/leg only
    c_wide = classify_lbw(-0.200, 0.50)
    assert c_wide["hitting"] is False
    assert c_wide["dx_outside_m"] == pytest.approx(0.05)
    assert c_wide["dy_outside_m"] == pytest.approx(0.0)
    assert c_wide["outside_dist_m"] == pytest.approx(0.05)

    # Both wide (3 cm) and high (4 cm) -> 5 cm outside
    c_both = classify_lbw(0.180, 0.787)
    assert c_both["hitting"] is False
    assert c_both["outside_dist_m"] == pytest.approx(0.05)


def test_intersect_stump_plane_matches_closed_form_and_handles_no_crossing() -> None:
    p0 = np.array([0.18, 2.0, 18.9], dtype=np.float64)
    v0 = np.array([-0.12, -2.4, -34.0], dtype=np.float64)
    e = 0.45
    f = 0.72

    res = intersect_stump_plane(p0, v0, e, f, use_drag=False)
    assert res is not None

    # Verify against analytical post-bounce solution
    _, tb = ball_positions_at_times(np.array([0.0, 1.0]), p0, v0, e, f, use_drag=False)
    p_b = p0 + v0 * tb + 0.5 * G * tb ** 2
    v_b = v0 + G * tb
    v_after = np.array([v_b[0] * f, -v_b[1] * e, v_b[2] * f])
    dt_after = -p_b[2] / v_after[2]
    t_exact = tb + dt_after
    p_exact = p_b + v_after * dt_after + 0.5 * G * dt_after ** 2

    assert res["arrival_time_s"] == pytest.approx(t_exact, abs=1e-4)
    assert res["x_m"] == pytest.approx(p_exact[0], abs=1e-4)
    assert res["y_m"] == pytest.approx(p_exact[1], abs=1e-4)

    # Trajectory moving away from striker (+Z) never crosses z=0
    res_none = intersect_stump_plane(p0, np.array([0.0, 0.0, +10.0]), e, f, use_drag=False, t_max=1.0)
    assert res_none is None


def test_synthetic_round_trip_pose_and_plane_recovery() -> None:
    """Generate a trajectory with ball_positions_at_times, project it through a known pose,
    and recover the pose (focal within 1%) and (x, y) at the stump plane within 5 cm.
    """
    world_pts = np.asarray(WORLD_POINTS_M, dtype=np.float64)
    image_size = (1920, 1080)
    f_true = 3510.0
    K_true, R_true, rvec_true, t_true, _ = _make_known_camera_pose(
        f_true=f_true, image_size=image_size
    )

    # Project the 6 calibration world points into image pixels
    img_pts, _ = cv2.projectPoints(world_pts, rvec_true, t_true, K_true, None)
    img_pts = img_pts.reshape(-1, 2)

    # Recover camera pose via solve_pose
    pose_rec = solve_pose(world_pts, img_pts, image_size)
    f_rec = float(pose_rec["focal_px"])
    rel_focal_err = abs(f_rec - f_true) / f_true
    assert rel_focal_err <= 0.01, f"Recovered focal {f_rec} differs from {f_true} by {rel_focal_err:.4%}"

    K_rec = pose_rec["K"]
    R_rec, _ = cv2.Rodrigues(pose_rec["rvec"].reshape(3))
    t_rec = pose_rec["tvec"].reshape(3)
    C_rec = (-R_rec.T @ t_rec.reshape(3, 1)).reshape(3)

    # Generate synthetic delivery trajectory with ball_positions_at_times
    p0_true = np.array([0.20, 2.00, 18.90], dtype=np.float64)
    v0_true = np.array([-0.15, -2.50, -33.00], dtype=np.float64)
    e_true = 0.45
    f_fric_true = 0.72
    fps = 30.0
    times = np.arange(0, 16, dtype=np.float64) / fps

    pos_true, _ = ball_positions_at_times(
        times, p0_true, v0_true, e_true, f_fric_true, use_drag=False
    )
    uvs = np.array([project_world(P, K_true, R_true, t_true) for P in pos_true], dtype=np.float64)

    plane_true = intersect_stump_plane(p0_true, v0_true, e_true, f_fric_true, use_drag=False)
    assert plane_true is not None

    eval_rec = evaluate_trajectory_fit(
        times, uvs, K_rec, R_rec, t_rec, C_rec, use_drag=False
    )
    assert abs(eval_rec["plane_x_m"] - plane_true["x_m"]) <= 0.05
    assert abs(eval_rec["plane_y_m"] - plane_true["y_m"]) <= 0.05
    assert eval_rec["hitting"] is True


def test_monte_carlo_helper_fixed_seed_reproducibility(tmp_path: Path) -> None:
    world_pts = np.asarray(WORLD_POINTS_M, dtype=np.float64)
    image_size = (1920, 1080)
    K_true, R_true, rvec_true, t_true, _ = _make_known_camera_pose(
        f_true=3500.0, image_size=image_size
    )
    img_pts, _ = cv2.projectPoints(world_pts, rvec_true, t_true, K_true, None)
    img_pts = img_pts.reshape(-1, 2)

    p0_true = np.array([0.10, 2.00, 18.90], dtype=np.float64)
    v0_true = np.array([-0.10, -2.50, -33.00], dtype=np.float64)
    times = np.arange(0, 16, dtype=np.float64) / 30.0
    pos_true, _ = ball_positions_at_times(times, p0_true, v0_true, 0.45, 0.72, use_drag=False)
    uvs = np.array([project_world(P, K_true, R_true, t_true) for P in pos_true], dtype=np.float64)

    mc1 = run_monte_carlo(
        world_pts, img_pts, image_size, times, uvs,
        n_repeats=6, seed=12345, calib_sigma_px=1.5, traj_sigma_px=2.0, use_drag=False,
    )
    mc2 = run_monte_carlo(
        world_pts, img_pts, image_size, times, uvs,
        n_repeats=6, seed=12345, calib_sigma_px=1.5, traj_sigma_px=2.0, use_drag=False,
    )
    assert mc1["n_valid"] == 6
    assert mc1["hitting_fraction"] == pytest.approx(mc2["hitting_fraction"])
    assert mc1["std_x_m"] == pytest.approx(mc2["std_x_m"])
    assert mc1["std_y_m"] == pytest.approx(mc2["std_y_m"])
    assert mc1["std_x_m"] > 0.0
    assert mc1["std_y_m"] > 0.0
