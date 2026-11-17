"""Synthetic unit tests for piecewise Huber kink fits and gap robustness."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pytest

from kink_events import (
    compute_recall_metrics,
    delete_frames_from_dump,
    deleted_window_frames,
    fit_bounce_kink,
    fit_impact_kink,
    run_evaluation,
)
from release_rules import TrackPoint


def _synthetic_delivery(
    *,
    rel_f: int = 2,
    bnc_t: float = 14.3,
    imp_t: float = 23.6,
    last_f: int = 32,
    noise_sigma: float = 1.5,
    seed: int = 7,
) -> Tuple[Dict[int, TrackPoint], Tuple[float, float], Tuple[float, float]]:
    """Build a synthetic 3-piece delivery track matching the kinematic model.

    - Pre-bounce: x linear, y quadratic downward (+y) with gravity
    - Post-bounce (t in (bnc_t, imp_t)): x linear, y quadratic upward (-y) with gravity
    - Outgoing (t > imp_t): deflected linear x, linear y
    """
    rng = np.random.default_rng(seed)

    # Exact bounce point (x_b, y_b) at t = bnc_t
    xb, yb = 950.0, 520.0
    # Pre-bounce: vx_pre = 3.0, vy(bnc_t) = +32 px/f, a_pre = +1.4 px/f^2
    def pre_pos(t: float) -> Tuple[float, float]:
        dt = t - bnc_t
        return xb + 3.0 * dt, yb + 32.0 * dt + 0.7 * dt * dt

    # Post-bounce: vx_post = 3.5, vy(bnc_t+) = -22 px/f, a_post = +0.9 px/f^2
    def post_pos(t: float) -> Tuple[float, float]:
        dt = t - bnc_t
        return xb + 3.5 * dt, yb - 22.0 * dt + 0.45 * dt * dt

    xi, yi = post_pos(imp_t)

    # Outgoing post-impact: strong deflection in x (-24 px/f), slower upward y (-8 px/f)
    def out_pos(t: float) -> Tuple[float, float]:
        dt = t - imp_t
        return xi - 24.0 * dt, yi - 8.0 * dt

    pts: Dict[int, TrackPoint] = {}
    for f in range(rel_f, last_f + 1):
        if f < bnc_t:
            x, y = pre_pos(float(f))
        elif f < imp_t:
            x, y = post_pos(float(f))
        else:
            x, y = out_pos(float(f))
        nx = float(x + rng.normal(0.0, noise_sigma)) if noise_sigma > 0 else x
        ny = float(y + rng.normal(0.0, noise_sigma)) if noise_sigma > 0 else y
        pts[f] = TrackPoint(frame=f, x=nx, y=ny, conf=0.9)

    return pts, (xb, yb), (xi, yi)


def test_noiseless_recovers_subframe_kinks() -> None:
    bnc_t, imp_t = 14.3, 23.6
    pts, (xb, yb), (xi, yi) = _synthetic_delivery(bnc_t=bnc_t, imp_t=imp_t, noise_sigma=0.0)

    bf = fit_bounce_kink(pts, 2, round(bnc_t), round(imp_t), 32)
    assert bf is not None
    assert abs(bf["t"] - bnc_t) <= 0.1
    assert math.hypot(bf["x"] - xb, bf["y"] - yb) <= 3.0

    imf = fit_impact_kink(pts, round(bnc_t), round(imp_t))
    assert imf is not None
    assert abs(imf["t"] - imp_t) <= 0.1
    assert math.hypot(imf["x"] - xi, imf["y"] - yi) <= 3.0


def test_noisy_1_5px_recovers_bounce_and_impact_with_and_without_gaps() -> None:
    bnc_t, imp_t = 14.2, 24.4
    pts, (xb, yb), (xi, yi) = _synthetic_delivery(
        rel_f=2, bnc_t=bnc_t, imp_t=imp_t, last_f=34, noise_sigma=1.5, seed=42
    )

    for k in (0, 2, 3, 5):
        drop_b = deleted_window_frames(round(bnc_t), k)
        reduced_b = {f: pt for f, pt in pts.items() if f not in drop_b}
        bf = fit_bounce_kink(reduced_b, 2, round(bnc_t), round(imp_t), 34)
        assert bf is not None, f"bounce fit failed for k={k}"
        assert abs(bf["t"] - bnc_t) <= 0.6, f"k={k} dt={bf['t'] - bnc_t}"
        assert math.hypot(bf["x"] - xb, bf["y"] - yb) <= 15.0

        drop_i = deleted_window_frames(round(imp_t), k)
        reduced_i = {f: pt for f, pt in pts.items() if f not in drop_i}
        imf = fit_impact_kink(reduced_i, round(bnc_t), round(imp_t))
        assert imf is not None, f"impact fit failed for k={k}"
        assert abs(imf["t"] - imp_t) <= 0.6, f"k={k} dt={imf['t'] - imp_t}"
        assert math.hypot(imf["x"] - xi, imf["y"] - yi) <= 15.0


def test_huber_resists_single_detection_outlier() -> None:
    bnc_t, imp_t = 14.0, 24.0
    pts, (xb, yb), _ = _synthetic_delivery(bnc_t=bnc_t, imp_t=imp_t, noise_sigma=0.5, seed=11)
    # Inject an 80 px false positive outlier in the pre-bounce segment.
    pts[8] = TrackPoint(frame=8, x=pts[8].x + 80.0, y=pts[8].y - 80.0, conf=0.5)
    bf = fit_bounce_kink(pts, 2, 14, 24, 32)
    assert bf is not None
    assert abs(bf["t"] - bnc_t) <= 0.25
    assert math.hypot(bf["x"] - xb, bf["y"] - yb) <= 5.0


def test_recall_and_end_to_end_temp_dirs(tmp_path: Path) -> None:
    pts, (xb, yb), (xi, yi) = _synthetic_delivery(
        rel_f=2, bnc_t=14.0, imp_t=24.0, last_f=32, noise_sigma=1.0, seed=5
    )
    # Introduce a 2-frame gap near bounce (13, 14) and a 1-frame gap post-impact (27).
    for f in (13, 14, 27):
        pts.pop(f)
    rec = compute_recall_metrics(pts, 2, 14, 24, 32)
    assert rec["tot_overall"] == 31
    assert rec["det_overall"] == 28
    assert rec["gap_overall"] == 2
    assert rec["gap_bnc_win"] == 2
    assert rec["gap_imp_win"] == 1

    labels_dir = tmp_path / "labels"
    runs_dir = tmp_path / "runs"
    clip_dir = runs_dir / "test_run" / "c_synth01"
    labels_dir.mkdir(parents=True)
    clip_dir.mkdir(parents=True)

    (labels_dir / "c_synth01.json").write_text(
        json.dumps(
            {
                "clip_id": "c_synth01",
                "status": "final",
                "ball_colour": "red",
                "calibration_gt": {
                    "points": {
                        "bat_L": [880, 300],
                        "bat_R": [1040, 300],
                        "bowl_L": [700, 900],
                        "bowl_R": [1240, 900],
                        "bat_stump": [960, 300],
                        "bowl_stump": [960, 900],
                    }
                },
                "release": {"frame": 2, "x": pts[2].x, "y": pts[2].y},
                "bounce": {"frame": 14, "x": xb, "y": yb},
                "impact": {"type": "pad", "frame": 24, "x": xi, "y": yi},
                "last_visible_frame": 32,
            }
        ),
        encoding="utf-8",
    )
    raw_ball = {
        str(f): [{"cx": pt.x, "cy": pt.y, "conf": pt.conf}] for f, pt in pts.items()
    }
    (clip_dir / "raw_ball_detections.json").write_text(
        json.dumps({"fps": 30.0, "frame_count": 35, "ball": raw_ball, "streaming_bounce": [15, xb, yb]}),
        encoding="utf-8",
    )
    (clip_dir / "results.json").write_text(
        json.dumps(
            {
                "events": {
                    "release": {"frame": 2, "x": pts[2].x, "y": pts[2].y},
                    "bounce": {"frame": 15, "x": pts[15].x, "y": pts[15].y},
                    "impact": {"frame": 24, "x": pts[24].x, "y": pts[24].y},
                },
                "trajectory": [{"frame": f, "x": pt.x, "y": pt.y, "interpolated": False} for f, pt in pts.items()],
            }
        ),
        encoding="utf-8",
    )

    # delete_frames_from_dump drops frames cleanly
    edited = delete_frames_from_dump(
        json.loads((clip_dir / "raw_ball_detections.json").read_text(encoding="utf-8")),
        [24, 25],
    )
    assert "24" not in edited["ball"] and "25" not in edited["ball"]

    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"
    run_evaluation(
        run_name="test_run",
        labels_dir=labels_dir,
        runs_dir=runs_dir,
        out_md=out_md,
        out_csv=out_csv,
    )
    assert out_md.is_file() and out_csv.is_file()
    md_text = out_md.read_text(encoding="utf-8")
    assert "Kink Events & Detection Recall Report" in md_text
    assert "c_synth01" in md_text
