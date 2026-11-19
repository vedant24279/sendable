"""Unit tests for tools.annotator.backend.eval_track_engine."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

TOOLS_BACKEND = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_BACKEND.parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(TOOLS_BACKEND) not in sys.path:
    sys.path.insert(0, str(TOOLS_BACKEND))
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from eval_track_engine import (  # noqa: E402
    deleted_window_frames,
    filter_ball_by_frame,
    run_offline_evaluation,
)


def test_deleted_window_and_filter() -> None:
    drop3 = deleted_window_frames(20, 3)
    assert drop3 == {19, 20, 21}
    assert deleted_window_frames(20, 0) == set()
    ball = {"18": [{"cx": 1, "cy": 2}], "19": [{"cx": 2, "cy": 3}], "22": [{"cx": 5, "cy": 6}]}
    filtered = filter_ball_by_frame(ball, drop3)
    assert set(filtered.keys()) == {18, 22}


def test_run_offline_evaluation_temp_dirs(tmp_path: Path) -> None:
    labels_dir = tmp_path / "labels"
    runs_dir = tmp_path / "runs"
    reports_dir = tmp_path / "reports"
    analysis_dir = tmp_path / "analysis"
    lib_dir = tmp_path / "library"
    for d in (labels_dir, runs_dir, reports_dir, analysis_dir, lib_dir):
        d.mkdir(parents=True)

    corners = {
        "bat_L": [770.0, 448.0],
        "bat_R": [1130.0, 448.0],
        "bowl_L": [735.0, 750.0],
        "bowl_R": [1185.0, 750.0],
        "bat_stump": [950.0, 430.0],
        "bowl_stump": [960.0, 775.0],
    }
    lbl: Dict[str, Any] = {
        "schema_version": 1,
        "clip_id": "c_synth01",
        "status": "final",
        "ball_colour": "pink",
        "batter_hand": "right",
        "release": {"frame": 5, "x": 960.0, "y": 300.0},
        "bounce": {"frame": 16, "x": 950.0, "y": 560.0},
        "impact": {"frame": 22, "x": 942.0, "y": 430.0, "type": "pad"},
        "last_visible_frame": 28,
        "calibration_gt": {"points": corners, "stump_confirmed": {"bat_stump": True, "bowl_stump": True}},
        "flags": [],
    }
    (labels_dir / "c_synth01.json").write_text(json.dumps(lbl), encoding="utf-8")

    # Synthetic bouncing + pad-impact detections
    ball: Dict[str, Any] = {}
    for f in range(5, 29):
        if f <= 16:
            dt = f - 16
            x, y = 950.0 - 1.0 * dt, 560.0 + 18.0 * dt + 0.5 * dt * dt
        elif f <= 22:
            dt = f - 16
            x, y = 950.0 - 1.2 * dt, 560.0 - 18.0 * dt + 0.3 * dt * dt
        else:
            dt = f - 22
            x, y = 942.8 + 14.0 * dt, 462.8 - 8.0 * dt
        ball[str(f)] = [{"cx": x, "cy": y, "conf": 0.85}]

    dump_clip = runs_dir / "dump_all_1" / "c_synth01"
    dump_clip.mkdir(parents=True)
    (dump_clip / "raw_ball_detections.json").write_text(
        json.dumps({"fps": 30.0, "frame_count": 30, "ball": ball}), encoding="utf-8"
    )
    (dump_clip / "results.json").write_text(
        json.dumps({
            "ball_type": "pink",
            "video": {"fps": 30.0, "frame_count": 30},
            "calibration": corners,
        }),
        encoding="utf-8",
    )

    import os
    old_lib = os.environ.get("ANNOTATOR_LIBRARY_DIR")
    os.environ["ANNOTATOR_LIBRARY_DIR"] = str(lib_dir)
    try:
        summary = run_offline_evaluation(
            labels_dir=labels_dir,
            runs_dir=runs_dir,
            reports_dir=reports_dir,
            analysis_dir=analysis_dir,
        )
    finally:
        if old_lib is None:
            os.environ.pop("ANNOTATOR_LIBRARY_DIR", None)
        else:
            os.environ["ANNOTATOR_LIBRARY_DIR"] = old_lib

    assert summary["n_clips"] == 1
    assert (runs_dir / "track_1" / "c_synth01" / "results.json").is_file()
    assert (reports_dir / "track_1.md").is_file()
    assert Path(summary["analysis_md"]).is_file()
