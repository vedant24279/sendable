"""Tests for release tracing, run_batch --env, and process.py TRACKER_DEBUG_DUMP hook."""

from __future__ import annotations

import csv
import importlib
import json
import math
import subprocess
import sys
import types
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest

from run_batch import parse_args as parse_batch_args
from run_batch import parse_env_vars, run_batch
from trace_release import (
    format_release_traces_csv,
    format_release_traces_md,
    run_trace_release,
    trace_clip_release,
)


def test_parse_env_vars_and_batch_args() -> None:
    parsed = parse_env_vars(["TRACKER_DEBUG_DUMP=1", "FOO=bar=baz", " EMPTY = "])
    assert parsed == {
        "TRACKER_DEBUG_DUMP": "1",
        "FOO": "bar=baz",
        "EMPTY": " ",
    }

    with pytest.raises(ValueError, match="expected KEY=VALUE"):
        parse_env_vars(["NO_EQUALS"])

    with pytest.raises(ValueError, match="empty key"):
        parse_env_vars(["=missing_key"])

    args = parse_batch_args(
        [
            "--run-name",
            "dbg_run",
            "--env",
            "TRACKER_DEBUG_DUMP=1",
            "--env",
            "TRACKER_DEBUG=1",
        ]
    )
    assert args.env == ["TRACKER_DEBUG_DUMP=1", "TRACKER_DEBUG=1"]


def test_run_batch_passes_env_and_records_in_run_info(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    labels_dir = tmp_path / "labels"
    library_dir = tmp_path / "library"
    runs_dir = tmp_path / "runs"
    labels_dir.mkdir()
    (library_dir / "videos").mkdir(parents=True)
    video_file = library_dir / "videos" / "c_env01.mp4"
    video_file.write_bytes(b"fake")

    (library_dir / "library.json").write_text(
        json.dumps(
            {
                "c_env01": {
                    "clip_id": "c_env01",
                    "display_name": "clip.mp4",
                    "stored_name": "c_env01.mp4",
                    "sha256": "0" * 64,
                    "added_at": "2026-01-01T00:00:00Z",
                    "fps": 30.0,
                    "frame_count": 30,
                    "width": 1080,
                    "height": 1920,
                }
            }
        ),
        encoding="utf-8",
    )
    (labels_dir / "c_env01.json").write_text(
        json.dumps(
            {
                "clip_id": "c_env01",
                "status": "final",
                "ball_colour": "pink",
                "calibration_gt": {
                    "points": {
                        "bat_L": [300, 800],
                        "bat_R": [600, 800],
                        "bowl_L": [400, 200],
                        "bowl_R": [500, 200],
                        "bat_stump": [450, 800],
                        "bowl_stump": [450, 200],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    seen_envs: List[Optional[Dict[str, str]]] = []

    def _fake_run(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen_envs.append(kwargs.get("env"))
        if isinstance(cmd, list) and "--out" in cmd:
            out_dir = Path(cmd[cmd.index("--out") + 1])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "results.json").write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("run_batch.subprocess.run", _fake_run)
    monkeypatch.setattr("run_batch.get_git_commit", lambda: "abc123")
    monkeypatch.setattr("run_batch.is_pipeline_or_worker_dirty", lambda: False)

    info = run_batch(
        run_name="env_run",
        extra_env={"TRACKER_DEBUG_DUMP": "1", "CUSTOM_FLAG": "yes"},
        labels_dir=labels_dir,
        library_dir=library_dir,
        runs_dir=runs_dir,
    )

    assert info["env"] == {"TRACKER_DEBUG_DUMP": "1", "CUSTOM_FLAG": "yes"}
    saved_info = json.loads((runs_dir / "env_run" / "run_info.json").read_text(encoding="utf-8"))
    assert saved_info["env"] == {"TRACKER_DEBUG_DUMP": "1", "CUSTOM_FLAG": "yes"}

    # Ensure the run_clip invocation received the env overrides
    assert any(
        isinstance(env, dict)
        and env.get("TRACKER_DEBUG_DUMP") == "1"
        and env.get("CUSTOM_FLAG") == "yes"
        for env in seen_envs
    )


def test_trace_release_synthetic_dump(tmp_path: Path) -> None:
    labels_dir = tmp_path / "labels"
    runs_dir = tmp_path / "runs"
    analysis_dir = tmp_path / "analysis"
    labels_dir.mkdir()
    clip_run_dir = runs_dir / "synth_trace" / "c_tr01"
    clip_run_dir.mkdir(parents=True)

    (labels_dir / "c_tr01.json").write_text(
        json.dumps(
            {
                "clip_id": "c_tr01",
                "status": "final",
                "ball_colour": "pink",
                "release": {"frame": 6, "x": 100.0, "y": 200.0},
            }
        ),
        encoding="utf-8",
    )
    # Also include a draft label that must be ignored
    (labels_dir / "c_draft.json").write_text(
        json.dumps({"clip_id": "c_draft", "status": "draft", "release": {"frame": 5}}),
        encoding="utf-8",
    )

    raw_dump = {
        "fps": 30.0,
        "frame_count": 15,
        "ball": {
            "2": [{"cx": 90.0, "cy": 190.0, "x1": 85, "y1": 185, "x2": 95, "y2": 195, "conf": 0.41}],
            "4": [{"cx": 95.0, "cy": 195.0, "x1": 90, "y1": 190, "x2": 100, "y2": 200, "conf": 0.55}],
            "5": [{"cx": 98.0, "cy": 199.0, "x1": 93, "y1": 194, "x2": 103, "y2": 204, "conf": 0.62}],
            "6": [
                {"cx": 100.0, "cy": 200.0, "x1": 95, "y1": 195, "x2": 105, "y2": 205, "conf": 0.78},
                {"cx": 300.0, "cy": 300.0, "x1": 295, "y1": 295, "x2": 305, "y2": 305, "conf": 0.25},
            ],
            "9": [{"cx": 120.0, "cy": 230.0, "x1": 115, "y1": 225, "x2": 125, "y2": 235, "conf": 0.85}],
        },
        "streaming_release": {"frame": 9, "x": 120, "y": 230},
        "streaming_bounce": [12, 130, 500],
    }
    (clip_run_dir / "raw_ball_detections.json").write_text(
        json.dumps(raw_dump), encoding="utf-8"
    )
    (clip_run_dir / "results.json").write_text(
        json.dumps({"events": {"release": {"frame": 2, "x": 90, "y": 190}}}),
        encoding="utf-8",
    )

    md_path, csv_path, traces = run_trace_release(
        run_name="synth_trace",
        window=4,
        labels_dir=labels_dir,
        runs_dir=runs_dir,
        analysis_dir=analysis_dir,
    )

    assert len(traces) == 1
    tr = traces[0]
    assert tr["clip_id"] == "c_tr01"
    assert tr["labelled_frame"] == 6
    assert tr["streaming_release_frame"] == 9
    assert tr["final_release_frame"] == 2
    # Strictly between 2 and 6 are frames {3, 4, 5}: 4 and 5 have detections -> 2
    assert tr["detections_between_count"] == 2

    rows_by_f = {r["frame"]: r for r in tr["rows"]}
    assert set(rows_by_f.keys()) == set(range(2, 11))
    assert rows_by_f[2]["marks"] == "O"
    assert rows_by_f[6]["marks"] == "L"
    assert rows_by_f[9]["marks"] == "S"
    assert rows_by_f[6]["n_candidates"] == 2
    # Step dist from f=5 (98, 199) to nearest candidate at f=6 (100, 200) is hypot(2, 1)
    assert rows_by_f[6]["step_dist_px"] == pytest.approx(math.hypot(2.0, 1.0), abs=1e-6)
    # Previous frame f=8 has no detection -> step_dist_px is None at f=9
    assert rows_by_f[9]["step_dist_px"] is None

    md_text = md_path.read_text(encoding="utf-8")
    assert "## Summary Table" in md_text
    assert "## Clip `c_tr01` (`pink`)" in md_text or "## Clip `c_tr01` (pink)" in md_text
    assert "| `c_tr01` | `pink` | 6 | 9 | 2 | 2 |" in md_text

    csv_rows = list(csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()))
    assert len(csv_rows) == 9
    f6_row = next(r for r in csv_rows if r["frame"] == "6")
    assert f6_row["marks"] == "L"
    assert f6_row["n_candidates"] == "2"
    assert "(300.0, 300.0, 0.250)" in f6_row["candidates"]
    assert float(f6_row["step_dist_px"]) == pytest.approx(math.hypot(2.0, 1.0), abs=0.05)


def test_process_debug_dump_hook_writes_only_when_env_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mock legacy modules & cv2 to verify TRACKER_DEBUG_DUMP behavior in process.py."""
    repo_root = Path(__file__).resolve().parents[4]
    backend_dir = repo_root / "backend"

    class _FakeCap:
        def __init__(self, n_frames: int) -> None:
            self.n_frames = n_frames
            self.pos = 0

        def isOpened(self) -> bool:
            return True

        def get(self, prop: int) -> float:
            if prop == 5:  # CAP_PROP_FPS
                return 30.0
            if prop == 7:  # CAP_PROP_FRAME_COUNT
                return float(self.n_frames)
            if prop == 3:  # CAP_PROP_FRAME_WIDTH
                return 1280.0
            if prop == 4:  # CAP_PROP_FRAME_HEIGHT
                return 720.0
            return 0.0

        def set(self, _prop: int, val: float) -> bool:
            self.pos = int(val)
            return True

        def read(self) -> tuple[bool, Any]:
            if self.pos >= self.n_frames:
                return False, None
            self.pos += 1
            return True, np.zeros((720, 1280, 3), dtype=np.uint8)

        def release(self) -> None:
            pass

    class _FakeWriter:
        def write(self, _frame: Any) -> None:
            pass

        def release(self) -> None:
            pass

    fake_cv2 = types.SimpleNamespace(
        CAP_PROP_FPS=5,
        CAP_PROP_FRAME_COUNT=7,
        CAP_PROP_FRAME_WIDTH=3,
        CAP_PROP_FRAME_HEIGHT=4,
        CAP_PROP_POS_FRAMES=1,
        FONT_HERSHEY_SIMPLEX=0,
        LINE_AA=16,
        VideoCapture=lambda _path: _FakeCap(10),
        VideoWriter=lambda *_args: _FakeWriter(),
        VideoWriter_fourcc=lambda *_args: 0,
        imwrite=lambda *_args: True,
        putText=lambda *_args: None,
        getTextSize=lambda *_args: ((40, 12), 4),
        rectangle=lambda *_args: None,
        circle=lambda *_args: None,
        ellipse=lambda *_args: None,
    )

    class _FakeRelease:
        def __init__(self, frame: int, x: int, y: int) -> None:
            self.release_frame = frame
            self.x = x
            self.y = y

    class _FakeReleaseDetector:
        def __init__(self) -> None:
            self.release: Any = None

        def update(self, dets: list[dict[str, Any]], frame_num: int) -> None:
            if frame_num == 5 and self.release is None:
                self.release = _FakeRelease(5, 900, 300)

    class _FakeBounceDetector:
        def __init__(self) -> None:
            self.bounce_point: Any = None

        def update(self, _dets: list[dict[str, Any]], frame_num: int, release_frame: Any = None) -> None:
            if frame_num == 7 and self.bounce_point is None:
                self.bounce_point = (7, 920, 500)

    class _FakeTrajectory:
        def __init__(self) -> None:
            self._pts: list[tuple[int, int, int]] = []
            self._dir_changes: list[tuple[int, int, int]] = []

        def set_bat_zone(self, **_kwargs: Any) -> None:
            pass

        def update(self, dets: list[dict[str, Any]], frame_num: int, **_kwargs: Any) -> None:
            for d in dets:
                if d.get("class_name") == "ball":
                    cx = int(0.5 * (d["x1"] + d["x2"]))
                    cy = int(0.5 * (d["y1"] + d["y2"]))
                    self._pts.append((frame_num, cx, cy))
                    break

        def draw_direction_change_markers(self, frame: Any, _f: int) -> Any:
            return frame

    class _FakeLogger:
        def __init__(self, output_dir: Path, video_fps: float = 30.0) -> None:
            self.csv_path = output_dir / "detections_fake.csv"

        def log(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def close(self) -> None:
            self.csv_path.write_text("frame\n", encoding="utf-8")

    # Pre-override streaming release sits at f=5, while earlier cluster f=1,2,3 triggers override to f=1
    per_frame_dets: Dict[int, List[Dict[str, Any]]] = {
        1: [{"class_name": "ball", "x1": 895, "y1": 215, "x2": 905, "y2": 225, "conf": 0.45}],
        2: [{"class_name": "ball", "x1": 915, "y1": 225, "x2": 925, "y2": 235, "conf": 0.50}],
        3: [{"class_name": "ball", "x1": 945, "y1": 240, "x2": 955, "y2": 250, "conf": 0.55}],
        5: [{"class_name": "ball", "x1": 895, "y1": 295, "x2": 905, "y2": 305, "conf": 0.80}],
        7: [{"class_name": "ball", "x1": 915, "y1": 495, "x2": 925, "y2": 505, "conf": 0.85}],
    }

    fake_modules = {
        "cv2": fake_cv2,
        "config": types.SimpleNamespace(GRAVITY_PX_PER_FRAME2=0.5, BOUNCE_MARKER_SIZE=10),
        "detector": types.SimpleNamespace(
            IMGSZ=1280,
            detect_objects=lambda _sess, _frm, fnum: list(per_frame_dets.get(fnum, [])),
        ),
        "filters": types.SimpleNamespace(reset_filters=lambda: None),
        "grid_utils": types.SimpleNamespace(
            compute_grid_corners=lambda _m: {},
            pixel_to_grid_cell=lambda _pt, _gc: (1, 1),
        ),
        "impact_detector": types.SimpleNamespace(
            ImpactDetector=lambda: types.SimpleNamespace(impact=None)
        ),
        "logger": types.SimpleNamespace(DetectionLogger=_FakeLogger),
        "release_detector": types.SimpleNamespace(ReleaseDetector=_FakeReleaseDetector),
        "tracker": types.SimpleNamespace(BounceDetector=_FakeBounceDetector),
        "trajectory": types.SimpleNamespace(Trajectory=_FakeTrajectory),
        "utils": types.SimpleNamespace(overlay_ball_image=lambda f, *_a, **_kw: f),
        "visualizer": types.SimpleNamespace(
            draw_detections=lambda f, *_a, **_kw: f,
            draw_release_to_bounce_parabola=lambda f, *_a, **_kw: f,
        ),
        "zones": types.SimpleNamespace(
            HALF_WIDTH=1.525,
            ZONES=[],
            build_homography=lambda _m: np.eye(3),
            draw_zones=lambda f, *_a, **_kw: f,
        ),
    }

    for mod_name, mod_obj in fake_modules.items():
        monkeypatch.setitem(sys.modules, mod_name, mod_obj)
    monkeypatch.syspath_prepend(str(backend_dir))
    sys.modules.pop("pipeline.process", None)
    process_mod = importlib.import_module("pipeline.process")

    monkeypatch.setattr(process_mod, "get_session", lambda _w: object())
    monkeypatch.setattr(
        process_mod,
        "_reencode_h264",
        lambda _tmp_v, out_v: bool(out_v.write_bytes(b"mp4") or True),
    )
    monkeypatch.setattr(process_mod, "classify_bounce", lambda _m, _pt: ("GOOD", 6.5))

    calib = {
        "bat_L": [700, 600],
        "bat_R": [1100, 600],
        "bowl_L": [750, 350],
        "bowl_R": [1050, 350],
        "bat_stump": [900, 600],
        "bowl_stump": [900, 350],
    }
    video_path = tmp_path / "in.mp4"
    video_path.write_bytes(b"video")
    weights_path = tmp_path / "w.onnx"
    weights_path.write_bytes(b"weights")

    # 1. Env var unset -> raw_ball_detections.json MUST NOT be written
    monkeypatch.delenv("TRACKER_DEBUG_DUMP", raising=False)
    out_unset = tmp_path / "out_unset"
    process_mod.process_video(video_path, out_unset, calib, weights_path)
    assert (out_unset / "results.json").is_file()
    assert not (out_unset / "raw_ball_detections.json").exists()

    # 2. Env var TRACKER_DEBUG_DUMP=1 -> raw_ball_detections.json MUST be written BEFORE override
    monkeypatch.setenv("TRACKER_DEBUG_DUMP", "1")
    out_set = tmp_path / "out_set"
    process_mod.process_video(video_path, out_set, calib, weights_path)
    dump_path = out_set / "raw_ball_detections.json"
    assert dump_path.is_file()

    dump = json.loads(dump_path.read_text(encoding="utf-8"))
    assert dump["fps"] == pytest.approx(30.0)
    assert dump["frame_count"] == 10
    # Streaming release BEFORE override is frame 5 (override moved results.json release to frame 1)
    assert dump["streaming_release"] == {"frame": 5, "x": 900, "y": 300}
    assert dump["streaming_bounce"] == [7, 920, 500]
    assert set(dump["ball"].keys()) == {"1", "2", "3", "5", "7"}
    assert dump["ball"]["1"][0]["cx"] == pytest.approx(900.0)
    assert dump["ball"]["1"][0]["cy"] == pytest.approx(220.0)
    assert dump["ball"]["1"][0]["conf"] == pytest.approx(0.45)

    res = json.loads((out_set / "results.json").read_text(encoding="utf-8"))
    assert res["events"]["release"]["frame"] == 1
