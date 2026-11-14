"""Unit tests for trace_impact.py, impact_rules.py, and eval_impact_rules.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from eval_impact_rules import evaluate_impact_run, load_impact_clip_inputs
from impact_rules import (
    rule_i1_direction_change,
    rule_i2_max_turn,
    rule_i3_speed_drop,
    rule_i4_last_seen,
)
from trace_impact import run_trace_impact


def _calib(bowl_w: float = 540.0, bat_stump_y: float = 480.0) -> Dict[str, Any]:
    return {
        "bowl_L": [700.0, 960.0],
        "bowl_R": [700.0 + bowl_w, 960.0],
        "bat_L": [715.0, 505.0],
        "bat_R": [1175.0, 505.0],
        "bowl_stump": [700.0 + bowl_w / 2.0, 995.0],
        "bat_stump": [950.0, bat_stump_y],
    }


def _det(cx: float, cy: float, conf: float = 0.8, size: float = 14.0) -> Dict[str, Any]:
    half = size / 2.0
    return {
        "cx": cx,
        "cy": cy,
        "x1": cx - half,
        "y1": cy - half,
        "x2": cx + half,
        "y2": cy + half,
        "conf": conf,
    }


def test_i1_and_i2_detect_pad_deflection_vertex() -> None:
    # Bounce at f15, rising up-left through f17->f18->f19, then turns right at f19->f20 (~45 deg turn).
    dump = {
        "fps": 30.0,
        "frame_count": 30,
        "streaming_bounce": [15, 1011, 608],
        "ball": {
            "15": [_det(1011.0, 608.0)],
            "16": [_det(998.0, 566.0)],
            "17": [_det(986.0, 526.0)],
            "18": [_det(975.0, 488.0)],
            "19": [_det(964.0, 446.0)],  # turn vertex
            "20": [_det(992.0, 412.0)],  # deflected right (dx=+28, dy=-34 -> +39.5 deg vs -104 deg)
            "21": [_det(1030.0, 402.0)],
        },
    }
    pts = _calib()
    assert rule_i1_direction_change(dump, pts, theta_deg=20.0) == (19, 964.0, 446.0)
    assert rule_i1_direction_change(dump, pts, theta_deg=45.0) == (19, 964.0, 446.0)
    assert rule_i2_max_turn(dump, pts) == (19, 964.0, 446.0)


def test_i3_detects_speed_drop_and_vertical_sign_flip() -> None:
    # Vertical step changes sign at f18->f19 (dy=-40) -> f19->f20 (dy=+15).
    dump_flip = {
        "streaming_bounce": [15, 1000, 600],
        "ball": {
            "15": [_det(1000.0, 600.0)],
            "17": [_det(990.0, 520.0)],
            "18": [_det(980.0, 480.0)],
            "19": [_det(970.0, 440.0)],
            "20": [_det(975.0, 455.0)],
        },
    }
    assert rule_i3_speed_drop(dump_flip, _calib()) == (19, 970.0, 440.0)

    # Pure speed drop (no dy sign flip): 40px/f then drops to 10px/f (<= 0.5 * 40).
    dump_slow = {
        "streaming_bounce": [15, 1000, 600],
        "ball": {
            "15": [_det(1000.0, 600.0)],
            "16": [_det(1000.0, 560.0)],
            "17": [_det(1000.0, 520.0)],
            "18": [_det(1000.0, 480.0)],
            "19": [_det(1000.0, 470.0)],
        },
    }
    assert rule_i3_speed_drop(dump_slow, _calib()) == (18, 1000.0, 480.0)


def test_i4_last_seen_scales_by_crease_width_and_respects_window() -> None:
    # bowl_w = 270 -> half of 540, so max_dy_px = 45 around bat_stump_y = 480 -> [435, 525].
    # f17 (cy=500) is inside; f18 (cy=420, 60px away) is outside; f32 is outside bounce+14.
    dump = {
        "streaming_bounce": [15, 1000, 600],
        "ball": {
            "15": [_det(1000.0, 600.0)],
            "16": [_det(990.0, 520.0)],
            "17": [_det(980.0, 500.0)],
            "18": [_det(970.0, 420.0)],
            "32": [_det(960.0, 480.0)],
        },
    }
    pts = _calib(bowl_w=270.0, bat_stump_y=480.0)
    assert rule_i4_last_seen(dump, pts, plus_one=True) == (18, 980.0, 500.0)
    assert rule_i4_last_seen(dump, pts, plus_one=False) == (17, 980.0, 500.0)


def test_rules_return_none_without_streaming_bounce() -> None:
    dump = {
        "streaming_bounce": None,
        "ball": {"15": [_det(950.0, 480.0)], "16": [_det(955.0, 470.0)]},
    }
    pts = _calib()
    assert rule_i1_direction_change(dump, pts, theta_deg=20.0) is None
    assert rule_i2_max_turn(dump, pts) is None
    assert rule_i3_speed_drop(dump, pts) is None
    assert rule_i4_last_seen(dump, pts, plus_one=True) is None


def test_trace_impact_and_eval_impact_rules_synthetic_run(tmp_path: Path) -> None:
    labels_dir = tmp_path / "labels"
    runs_dir = tmp_path / "runs"
    analysis_dir = tmp_path / "analysis"
    labels_dir.mkdir()
    run_dir = runs_dir / "synth_impact"
    run_dir.mkdir(parents=True)

    # One non-contact clip must be ignored.
    (labels_dir / "c_none.json").write_text(
        json.dumps(
            {
                "clip_id": "c_none",
                "status": "final",
                "calibration_gt": {"points": _calib()},
                "impact": {"type": "none", "frame": None, "x": None, "y": None},
            }
        ),
        encoding="utf-8",
    )

    for idx in range(3):
        cid = f"c_imp{idx}"
        imp_f = 18 + idx
        (labels_dir / f"{cid}.json").write_text(
            json.dumps(
                {
                    "clip_id": cid,
                    "status": "final",
                    "ball_colour": "pink",
                    "calibration_gt": {"points": _calib()},
                    "bounce": {"frame": 14, "x": 1000.0, "y": 610.0},
                    "impact": {"type": "pad", "frame": imp_f, "x": 965.0, "y": 460.0},
                }
            ),
            encoding="utf-8",
        )
        c_dir = run_dir / cid
        c_dir.mkdir()
        ball: Dict[str, List[Dict[str, Any]]] = {}
        for f in range(14, imp_f + 1):
            step_n = f - 14
            ball[str(f)] = [_det(1000.0 - 8.0 * step_n, 610.0 - 38.0 * step_n)]
        # Deflect right after impact
        last_x = 1000.0 - 8.0 * (imp_f - 14)
        last_y = 610.0 - 38.0 * (imp_f - 14)
        ball[str(imp_f + 1)] = [_det(last_x + 35.0, last_y - 10.0)]
        ball[str(imp_f + 2)] = [_det(last_x + 70.0, last_y - 15.0)]

        (c_dir / "raw_ball_detections.json").write_text(
            json.dumps(
                {
                    "fps": 30.0,
                    "frame_count": 40,
                    "streaming_bounce": [14, 1000, 610],
                    "ball": ball,
                }
            ),
            encoding="utf-8",
        )
        (c_dir / "results.json").write_text(
            json.dumps(
                {"events": {"deviation": {"frame": imp_f + 2, "x": 1000, "y": 440}}}
            ),
            encoding="utf-8",
        )

    md_trace, csv_trace, traces = run_trace_impact(
        run_name="synth_impact",
        before=4,
        after=4,
        labels_dir=labels_dir,
        runs_dir=runs_dir,
        analysis_dir=analysis_dir,
    )
    assert len(traces) == 3
    assert md_trace.is_file() and csv_trace.is_file()
    assert "## Summary Table" in md_trace.read_text(encoding="utf-8")

    clips = load_impact_clip_inputs(run_dir=run_dir, labels_dir=labels_dir)
    assert [c.clip_id for c in clips] == ["c_imp0", "c_imp1", "c_imp2"]

    eval_md = evaluate_impact_run(
        run_name="synth_impact",
        labels_dir=labels_dir,
        runs_dir=runs_dir,
        analysis_dir=analysis_dir,
    )
    assert eval_md.is_file()
    report_txt = eval_md.read_text(encoding="utf-8")
    assert "## Ranked Rules (In-Sample)" in report_txt
    assert "## Leave-One-Out Cross-Validation (LOO)" in report_txt
    assert "3/3 (100.0% of 3)" in report_txt
