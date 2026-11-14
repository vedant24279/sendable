"""Unit tests for release_rules.py and eval_release_rules.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from eval_release_rules import evaluate_run, load_clip_inputs
from release_rules import (
    build_track,
    get_bowler_crease_width_px,
    rule_r0_streaming,
    rule_r1_flight_run,
    rule_r2_apex,
    rule_r3_deceleration,
    rule_r4_filtered_flight_run,
)


def _calib(width: float = 100.0) -> Dict[str, Any]:
    return {
        "bowl_L": [100.0, 200.0],
        "bowl_R": [100.0 + width, 200.0],
        "bat_L": [50.0, 500.0],
        "bat_R": [250.0, 500.0],
        "bowl_mid": [100.0 + width / 2.0, 200.0],
        "bat_mid": [150.0, 500.0],
    }


def _det(cx: float, cy: float, conf: float = 0.8) -> Dict[str, float]:
    return {
        "cx": cx,
        "cy": cy,
        "x1": cx - 5.0,
        "y1": cy - 5.0,
        "x2": cx + 5.0,
        "y2": cy + 5.0,
        "conf": conf,
    }


def test_build_track_selects_highest_conf_then_nearest() -> None:
    dump = {
        "ball": {
            "2": [_det(200.0, 200.0, 0.9), _det(112.0, 102.0, 0.4)],
            "0": [_det(10.0, 10.0, 0.5), _det(100.0, 100.0, 0.9)],
            "1": [_det(105.0, 101.0, 0.6), _det(300.0, 300.0, 0.95)],
        }
    }
    track = build_track(dump)
    assert [(p.frame, p.x, p.y) for p in track] == [
        (0, 100.0, 100.0),
        (1, 105.0, 101.0),
        (2, 112.0, 102.0),
    ]


def test_bowler_crease_width_px_validation() -> None:
    assert get_bowler_crease_width_px(_calib(120.0)) == pytest.approx(120.0)
    with pytest.raises(ValueError):
        get_bowler_crease_width_px({"bowl_L": [100.0, 200.0], "bowl_R": [100.0, 200.0]})


def test_rule_r0_streaming() -> None:
    dump = {"streaming_release": {"frame": 4, "x": 111.5, "y": 222.5}, "ball": {}}
    assert rule_r0_streaming(dump, _calib()) == (4, 111.5, 222.5)
    assert rule_r0_streaming({"streaming_release": None}, _calib()) is None


def test_rule_r1_flight_run_swing_then_steady_flight() -> None:
    # Crease width = 100. Swing steps: 80px (0.80), 60px (0.60).
    # Then steady steps starting at frame 3: 5px (0.05), 5px (0.05), 5px (0.05).
    dump = {
        "ball": {
            "0": [_det(100.0, 300.0)],
            "1": [_det(180.0, 300.0)],
            "2": [_det(240.0, 300.0)],
            "3": [_det(245.0, 300.0)],
            "4": [_det(250.0, 300.0)],
            "5": [_det(255.0, 300.0)],
            "6": [_det(260.0, 300.0)],
        }
    }
    # At frame 2, incoming step is 0.60 (> 0.065), so it is rejected.
    # At frame 3, incoming step is 0.05 <= 0.065 and next 3 steps are 0.05 <= 0.065.
    assert rule_r1_flight_run(dump, _calib(100.0), k=3, t=0.065) == (3, 245.0, 300.0)


def test_rule_r1_first_detection_qualifies_on_following_steps_only() -> None:
    dump = {
        "ball": {
            "5": [_det(100.0, 100.0)],
            "6": [_det(104.0, 100.0)],
            "7": [_det(108.0, 100.0)],
            "8": [_det(112.0, 100.0)],
        }
    }
    assert rule_r1_flight_run(dump, _calib(100.0), k=3, t=0.055) == (5, 100.0, 100.0)


def test_rule_r1_fallback_to_first_detection() -> None:
    dump = {
        "ball": {
            "2": [_det(100.0, 100.0)],
            "3": [_det(150.0, 100.0)],
            "4": [_det(200.0, 100.0)],
        }
    }
    assert rule_r1_flight_run(dump, _calib(100.0), k=2, t=0.045) == (2, 100.0, 100.0)


def test_rule_r2_apex_picks_min_cy_with_increasing_cy_after() -> None:
    # Arm rises to apex at frame 4 (cy=80), then drops (cy=95, 115, 140),
    # and a later detection at frame 20 (outside +8 frames) has smaller cy=50 which must be ignored.
    dump = {
        "ball": {
            "1": [_det(100.0, 120.0)],
            "2": [_det(110.0, 100.0)],
            "4": [_det(120.0, 80.0)],
            "5": [_det(125.0, 95.0)],
            "6": [_det(130.0, 115.0)],
            "7": [_det(135.0, 140.0)],
            "20": [_det(150.0, 50.0)],
        }
    }
    assert rule_r2_apex(dump, _calib()) == (4, 120.0, 80.0)


def test_rule_r3_deceleration() -> None:
    # Crease width = 100.
    # f0->f1 step = 60 (0.60 >= 0.07), f1->f2 step = 10 (0.10 <= 0.4 * 0.60 = 0.24).
    dump = {
        "ball": {
            "0": [_det(100.0, 100.0)],
            "1": [_det(160.0, 100.0)],
            "2": [_det(170.0, 100.0)],
            "3": [_det(180.0, 100.0)],
        }
    }
    assert rule_r3_deceleration(dump, _calib(100.0)) == (2, 170.0, 100.0)


def test_rule_r4_rejects_isolated_outlier_before_r1() -> None:
    # f0 is isolated (> 0.15 away from f1), wait: end points only have 1 neighbour!
    # Put an isolated interior false detection at f1 (dist to f0 = 30px = 0.30 > 0.15,
    # dist to f2 = 28px = 0.28 > 0.15), while f0->f2 is steady flight (4px) once f1 is removed.
    dump = {
        "ball": {
            "0": [_det(100.0, 100.0)],
            "1": [_det(130.0, 100.0)],
            "2": [_det(104.0, 100.0)],
            "3": [_det(108.0, 100.0)],
            "4": [_det(112.0, 100.0)],
        }
    }
    # Without filtering, R1 hits f0->f1 jump (0.30) and lands on f3/fallback.
    # With R4 filtering out f1, track becomes [f0(100), f2(104), f3(108), f4(112)] -> hits f0.
    assert rule_r4_filtered_flight_run(dump, _calib(100.0), k=3, t=0.055) == (
        0,
        100.0,
        100.0,
    )


def _write_synthetic_clip(
    labels_dir: Path,
    run_dir: Path,
    clip_id: str,
    label_frame: int,
    swing_frames: int,
) -> None:
    label_payload = {
        "clip_id": clip_id,
        "status": "final",
        "ball_colour": "pink",
        "calibration_gt": {"points": _calib(100.0)},
        "release": {"frame": label_frame, "x": 200.0, "y": 100.0},
    }
    (labels_dir / f"{clip_id}.json").write_text(
        json.dumps(label_payload), encoding="utf-8"
    )

    ball: Dict[str, List[Dict[str, float]]] = {}
    x = 100.0
    for f in range(swing_frames):
        ball[str(f)] = [_det(x, 120.0 - f * 5.0)]
        x += 30.0  # 0.30 normalized swing step
    for offset in range(6):
        f = label_frame + offset
        ball[str(f)] = [_det(x, 100.0 + offset * 4.0)]
        x += 5.0  # 0.05 normalized flight step

    clip_run_dir = run_dir / clip_id
    clip_run_dir.mkdir(parents=True, exist_ok=True)
    dump_payload = {
        "fps": 60.0,
        "frame_count": 30,
        "ball": ball,
        "streaming_release": {"frame": 0, "x": 100.0, "y": 120.0},
        "streaming_bounce": None,
    }
    (clip_run_dir / "raw_ball_detections.json").write_text(
        json.dumps(dump_payload), encoding="utf-8"
    )


def test_eval_release_rules_and_loo_report(tmp_path: Path) -> None:
    labels_dir = tmp_path / "labels"
    runs_dir = tmp_path / "runs"
    analysis_dir = tmp_path / "analysis"
    labels_dir.mkdir()
    run_dir = runs_dir / "synth_run"
    run_dir.mkdir(parents=True)

    # Draft label must be ignored.
    (labels_dir / "c_draft.json").write_text(
        json.dumps({"clip_id": "c_draft", "status": "draft"}), encoding="utf-8"
    )

    for idx in range(4):
        _write_synthetic_clip(
            labels_dir=labels_dir,
            run_dir=run_dir,
            clip_id=f"c_000{idx}",
            label_frame=3 + idx,
            swing_frames=3 + idx,
        )

    loaded = load_clip_inputs(run_dir=run_dir, labels_dir=labels_dir)
    assert [c.clip_id for c in loaded] == ["c_0000", "c_0001", "c_0002", "c_0003"]

    report_path = evaluate_run(
        run_name="synth_run",
        labels_dir=labels_dir,
        runs_dir=runs_dir,
        analysis_dir=analysis_dir,
    )
    assert report_path.is_file()
    text = report_path.read_text(encoding="utf-8")
    assert "## Ranked Rules (In-Sample)" in text
    assert "## Leave-One-Out Cross-Validation (LOO)" in text
    assert "## Per-Clip Signed Errors (`rule - label`) — Best 3 Rules" in text
    assert "| R1(K=2,T=0.055) |" in text or "4/4" in text
