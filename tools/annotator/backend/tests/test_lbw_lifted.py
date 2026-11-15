"""Unit tests for homography-lifted ballistic LBW fit (lbw_lifted.py)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from app.calib import fit_homography, world_to_pixel
from lbw_lifted import (
    G_ACCEL,
    compute_post_bounce_rise_angle_deg,
    compute_release_speed_kmh,
    continue_to_stump_plane,
    evaluate_ballistic_world,
    fit_lifted_ballistic,
    hg_project_and_scales,
    project_ballistic_track,
    project_lifted_point,
)


def _sample_calib_points() -> dict[str, list[float]]:
    """Load calibration_gt points from c_13f43606 (or construct a realistic broadcast homography)."""
    lbl_path = Path(__file__).resolve().parents[4] / "eval" / "labels" / "c_13f43606.json"
    if lbl_path.is_file():
        data = json.loads(lbl_path.read_text(encoding="utf-8"))
        return data["calibration_gt"]["points"]
    return {
        "bat_L": [718.1, 548.3],
        "bat_R": [1213.5, 547.7],
        "bowl_L": [685.8, 959.4],
        "bowl_R": [1261.7, 957.0],
        "bat_stump": [965.6, 523.3],
        "bowl_stump": [974.4, 991.1],
    }


def test_hg_project_and_scales_matches_finite_differences():
    """Verify analytic Jacobian norms b = ||dHg/dX|| and a = ||dHg/dZ|| and L = b * cos(theta)."""
    pts = _sample_calib_points()
    fit_h = fit_homography(pts)
    H, H_inv = fit_h.H, fit_h.H_inv

    X_test, Z_test = 0.15, 6.20
    u_g, v_g, b, a, sin_theta, L = hg_project_and_scales(H_inv, X_test, Z_test)

    u_ref, v_ref = world_to_pixel(H, X_test, Z_test, H_inv=H_inv)
    assert math.isclose(float(u_g), u_ref, abs_tol=1e-9)
    assert math.isclose(float(v_g), v_ref, abs_tol=1e-9)

    eps = 1e-6
    u_x1, v_x1 = world_to_pixel(H, X_test + eps, Z_test, H_inv=H_inv)
    u_x0, v_x0 = world_to_pixel(H, X_test - eps, Z_test, H_inv=H_inv)
    b_fd = math.hypot((u_x1 - u_x0) / (2.0 * eps), (v_x1 - v_x0) / (2.0 * eps))

    u_z1, v_z1 = world_to_pixel(H, X_test, Z_test + eps, H_inv=H_inv)
    u_z0, v_z0 = world_to_pixel(H, X_test, Z_test - eps, H_inv=H_inv)
    a_fd = math.hypot((u_z1 - u_z0) / (2.0 * eps), (v_z1 - v_z0) / (2.0 * eps))

    assert math.isclose(float(b), b_fd, rel_tol=1e-6)
    assert math.isclose(float(a), a_fd, rel_tol=1e-6)

    expected_sin = min(a_fd / b_fd, 0.9)
    expected_L = b_fd * math.sqrt(1.0 - expected_sin * expected_sin)
    assert math.isclose(float(sin_theta), expected_sin, rel_tol=1e-6)
    assert math.isclose(float(L), expected_L, rel_tol=1e-6)

    # Verify height lifting shifts vertical pixel coordinate by -L * h
    h_val = 0.65
    u_lifted, v_lifted = project_lifted_point(H_inv, X_test, Z_test, h_val)
    assert math.isclose(float(u_lifted), float(u_g), abs_tol=1e-9)
    assert math.isclose(float(v_lifted), float(v_g) - float(L) * h_val, abs_tol=1e-9)


def test_stump_continuation_and_verdict_margins():
    """Verify post-bounce continuation to Z = 0, rise angle, and HITTING/MISSING margins."""
    # Ball bounces at t_b = 0.50 s, (X_b, Z_b) = (0.04, 6.00) m
    # v_x = -0.25 m/s, v_z = -30.0 m/s, w_in = 7.0 m/s, e = 0.55, f = 0.80
    # After bounce: vx_out = -0.20 m/s, vz_out = -24.0 m/s, w_out = 3.85 m/s
    # Time to Z = 0: t_s = 6.00 / 24.0 = 0.25 s
    # X_s = 0.04 + (-0.20) * 0.25 = -0.010 m
    # h_s = 3.85 * 0.25 - 0.5 * 9.81 * 0.0625 = 0.9625 - 0.3065625 = 0.6559375 m
    params = [0.50, 0.04, 6.00, -0.25, -30.0, 7.0, 0.55, 0.80]
    stump = continue_to_stump_plane(params, drag_k=0.0)

    assert math.isclose(stump["arrival_time_rel_s"], 0.25, abs_tol=1e-9)
    assert math.isclose(stump["arrival_time_s"], 0.75, abs_tol=1e-9)
    assert math.isclose(stump["X_s"], -0.010, abs_tol=1e-9)
    assert math.isclose(stump["h_s"], 0.6559375, abs_tol=1e-7)
    assert stump["verdict"] == "HITTING"
    assert stump["margin_m"] == 0.0
    # Nearest boundary is top of stumps: 0.747 - 0.6559375 = 0.0910625 m
    assert math.isclose(stump["signed_margin_m"], -(0.747 - 0.6559375), abs_tol=1e-6)

    # Rise angle: atan2(3.85, 0.80 * hypot(-0.25, -30.0))
    expected_angle = math.degrees(math.atan2(3.85, 0.80 * math.hypot(-0.25, -30.0)))
    assert math.isclose(compute_post_bounce_rise_angle_deg(params), expected_angle, abs_tol=1e-7)

    # Over-the-top miss: increase e to 0.70 -> w_out = 4.90 -> h_s = 4.90*0.25 - 0.3065625 = 0.9184375 m
    params_high = [0.50, 0.04, 6.00, -0.25, -30.0, 7.0, 0.70, 0.80]
    stump_high = continue_to_stump_plane(params_high, drag_k=0.0)
    assert stump_high["verdict"] == "MISSING"
    assert math.isclose(stump_high["margin_m"], 0.9184375 - 0.747, abs_tol=1e-6)


def test_synthetic_recovery_with_1_5px_noise():
    """Synthetic recovery test:
    Generate a ball track from the model with known parameters, project it through a known
    ground homography, add 1.5 px noise; recover X_s and h_s within 0.05 m and the bounce
    position within 0.1 m.
    """
    calib_pts = {
        "bat_L": [660.0, 520.0],
        "bat_R": [1260.0, 520.0],
        "bowl_L": [520.0, 960.0],
        "bowl_R": [1400.0, 960.0],
        "bat_stump": [960.0, 495.0],
        "bowl_stump": [960.0, 990.0],
    }
    fit_h = fit_homography(calib_pts)
    H, H_inv = fit_h.H, fit_h.H_inv

    fps = 30.0
    # Known physical parameters:
    # Bounce at frame 14 (t_b = 14 / 30 = 0.4667 s), X_b = -0.05 m, Z_b = 5.50 m
    true_params = [14.0 / fps, -0.05, 5.50, 2.80, -35.0, 7.50, 0.55, 0.80]
    true_stump = continue_to_stump_plane(true_params, drag_k=0.0)

    # Generate frames 3..19 (release to pad impact)
    frames = np.arange(3, 20, dtype=np.float64)
    t_frames = frames / fps
    u_clean, v_clean = project_ballistic_track(t_frames, true_params, H_inv, drag_k=0.0)

    rng = np.random.default_rng(42)
    u_noisy = u_clean + rng.normal(0.0, 1.5, size=len(t_frames))
    v_noisy = v_clean + rng.normal(0.0, 1.5, size=len(t_frames))

    bnc_idx = int(np.where(frames == 14)[0][0])
    bounce_center_uv = (float(u_noisy[bnc_idx]), float(v_noisy[bnc_idx]))

    fit_res = fit_lifted_ballistic(
        frame_times_s=t_frames,
        u_obs=u_noisy,
        v_obs=v_noisy,
        H=H,
        H_inv=H_inv,
        t_b_init_s=14.0 / fps,
        bounce_center_uv=bounce_center_uv,
        fps=fps,
        drag_k=0.0,
    )

    err_Xs = abs(fit_res["X_s"] - true_stump["X_s"])
    err_hs = abs(fit_res["h_s"] - true_stump["h_s"])
    err_bounce = math.hypot(fit_res["X_b"] - true_params[1], fit_res["Z_b"] - true_params[2])

    assert err_Xs <= 0.05, f"|X_s - X_s_true| = {err_Xs:.4f} m > 0.05 m"
    assert err_hs <= 0.05, f"|h_s - h_s_true| = {err_hs:.4f} m > 0.05 m"
    assert err_bounce <= 0.10, f"bounce position error = {err_bounce:.4f} m > 0.10 m"
