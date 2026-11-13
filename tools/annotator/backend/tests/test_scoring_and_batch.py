"""Unit and integration tests for scoring.py, score.py, and run_batch.py."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict

import pytest

from app.calib import fit_homography, world_to_pixel
from run_batch import build_rounded_calibration, run_batch
from score import run_scoring
from scoring import (
    aggregate_scores,
    classify_pitch_z_zone,
    load_legacy_zones,
    score_clip,
)


def _make_synthetic_calibration_gt(
    confirmed_bat: bool = False,
    confirmed_bowl: bool = False,
    residual_px: float | None = None,
) -> Dict[str, Any]:
    """Build a synthetic calibration_gt where pixel space maps cleanly to pitch world coords."""
    # Map world x in [-1.525, +1.525], z in [1.22, 18.90] onto a clean trapezoid/rectangle
    points = {
        "bat_L": [300.0, 800.0],
        "bat_R": [605.0, 800.0],
        "bowl_L": [400.0, 200.0],
        "bowl_R": [505.0, 200.0],
        "bat_stump": [452.5, 800.0],
        "bowl_stump": [452.5, 200.0],
    }
    return {
        "frame": 10,
        "points": points,
        "stump_confirmed": {
            "bat_stump": confirmed_bat,
            "bowl_stump": confirmed_bowl,
        },
        "residual_px": residual_px,
    }


def test_load_legacy_zones_runtime() -> None:
    zones = load_legacy_zones()
    assert len(zones) == 4
    names = [z[2] for z in zones]
    assert names == ["YORKER", "FULL", "GOOD", "SHORT"]
    assert classify_pitch_z_zone(1.5, zones) == "YORKER"
    assert classify_pitch_z_zone(4.5, zones) == "FULL"
    assert classify_pitch_z_zone(7.0, zones) == "GOOD"
    assert classify_pitch_z_zone(10.0, zones) == "SHORT"


def test_score_clip_known_errors_and_homography() -> None:
    calib_gt = _make_synthetic_calibration_gt(
        confirmed_bat=True, confirmed_bowl=False, residual_px=1.5
    )
    fit = fit_homography(calib_gt["points"], stump_confirmed=calib_gt["stump_confirmed"])

    # Pick exact world bounce coordinates for label vs system
    # Label bounce at (x=0.0 m, z=5.0 m) -> FULL zone
    # System bounce at (x=0.3 m, z=6.4 m) -> GOOD zone
    # dx = +0.3 m, dz = +1.4 m -> ground_error = hypot(0.3, 1.4)
    lbl_bnc_px, lbl_bnc_py = world_to_pixel(fit.H, 0.0, 5.0)
    sys_bnc_px, sys_bnc_py = world_to_pixel(fit.H, 0.3, 6.4)

    label = {
        "schema_version": 1,
        "clip_id": "c_synth001",
        "status": "final",
        "split": "dev",
        "ball_colour": "red",
        "release": {"frame": 10, "x": 100.0, "y": 200.0},
        "bounce": {"frame": 25, "x": lbl_bnc_px, "y": lbl_bnc_py, "kind": "pitch"},
        "impact": {"frame": 30, "x": 450.0, "y": 700.0, "type": "pad"},
        "last_visible_frame": 34,
        "lbw": "out",
        "flags": [],
        "calibration_gt": calib_gt,
    }

    # Trajectory: frames 10..30 (21 frames), provide 14 frames (10 non-interpolated, 4 interpolated)
    # Frames 30..34 (5 frames), provide all 5 frames (all non-interpolated)
    trajectory = []
    for f in range(10, 24):
        trajectory.append(
            {"frame": f, "x": 100.0, "y": 200.0, "interpolated": f >= 20}
        )
    for f in range(30, 35):
        trajectory.append(
            {"frame": f, "x": 450.0, "y": 700.0, "interpolated": False}
        )

    results = {
        "video": {"fps": 30.0, "width": 1080, "height": 1920, "frame_count": 60},
        "events": {
            # Release: +1 frame error, (3, 4) px offset -> 5.0 px error
            "release": {"frame": 11, "x": 103.0, "y": 204.0},
            # Bounce: -2 frame error, world (0.3, 6.4), system length_m = 7.2
            "bounce": {
                "frame": 23,
                "x": sys_bnc_px,
                "y": sys_bnc_py,
                "zone": "GOOD",
                "length_m": 7.2,
            },
            # Deviation: +1 frame error, (6, 8) px offset -> 10.0 px error
            "deviation": {"frame": 31, "x": 456.0, "y": 708.0},
            "impact": None,
        },
        "trajectory": trajectory,
        "stats": {"processing_time_sec": 12.5},
    }

    scored = score_clip(label, results, expected_frame_count=60)

    assert scored["frame_count_mismatch"] is False
    assert scored["confirmed_stumps"] == 1
    assert scored["residual_px"] == pytest.approx(1.5)

    # Coverage [10, 30]: 21 frames total; frames 10..23 (14) + frame 30 (1) = 15 present, 11 non-interp
    cov_ri = scored["coverage_release_to_impact"]
    assert cov_ri["total_frames"] == 21
    assert cov_ri["present_frames"] == 15
    assert cov_ri["non_interpolated_frames"] == 11
    assert cov_ri["coverage_fraction"] == pytest.approx(15 / 21)
    assert cov_ri["non_interpolated_fraction"] == pytest.approx(11 / 21)

    # Coverage [30, 34]: 5 frames total, all 5 present and non-interp
    cov_il = scored["coverage_impact_to_last_visible"]
    assert cov_il["total_frames"] == 5
    assert cov_il["coverage_fraction"] == pytest.approx(1.0)
    assert cov_il["non_interpolated_fraction"] == pytest.approx(1.0)

    # Release
    assert scored["release_found"] is True
    assert scored["release_frame_error"] == 1
    assert scored["release_px_error"] == pytest.approx(5.0)

    # Bounce
    assert scored["bounce_found"] is True
    assert scored["bounce_frame_error"] == -2
    assert scored["bounce_pitch_x_error_m"] == pytest.approx(0.3, abs=1e-6)
    assert scored["bounce_pitch_z_error_m"] == pytest.approx(1.4, abs=1e-6)
    assert scored["bounce_ground_error_m"] == pytest.approx(math.hypot(0.3, 1.4), abs=1e-6)
    assert scored["sys_length_minus_label_z_m"] == pytest.approx(7.2 - 5.0, abs=1e-6)
    assert scored["label_zone"] == "FULL"
    assert scored["system_zone"] == "GOOD"
    assert scored["zone_match"] is False

    # Impact & deviation
    assert scored["sys_impact_present"] is False
    assert scored["deviation_present"] is True
    assert scored["deviation_frame_error"] == 1
    assert scored["deviation_px_error"] == pytest.approx(10.0)


def test_aggregate_unclear_frame_mismatch_and_no_contact() -> None:
    calib_gt = _make_synthetic_calibration_gt(
        confirmed_bat=True, confirmed_bowl=True, residual_px=2.0
    )

    # Clip 1: clear, no-contact ("none"), system emits false deviation marker
    lbl_none = {
        "clip_id": "c_none",
        "status": "final",
        "split": "dev",
        "ball_colour": "white",
        "release": {"frame": 5, "x": 100.0, "y": 100.0},
        "bounce": {"frame": 15, "x": 452.5, "y": 500.0, "kind": "pitch"},
        "impact": {"frame": None, "x": None, "y": None, "type": "none"},
        "last_visible_frame": 25,
        "flags": [],
        "calibration_gt": calib_gt,
    }
    res_none = {
        "video": {"frame_count": 40},
        "events": {
            "release": {"frame": 5, "x": 100.0, "y": 100.0},
            "bounce": {"frame": 15, "x": 452.5, "y": 500.0, "zone": "FULL", "length_m": 5.0},
            "deviation": {"frame": 20, "x": 460.0, "y": 400.0},
            "impact": None,
        },
        "trajectory": [],
        "stats": {"processing_time_sec": 10.0},
    }

    # Clip 2: flagged "unclear" -> included in release, excluded from bounce & impact
    lbl_unclear = {
        "clip_id": "c_unclear",
        "status": "final",
        "split": "final",
        "ball_colour": "white",
        "release": {"frame": 8, "x": 100.0, "y": 100.0},
        "bounce": {"frame": 18, "x": 452.5, "y": 500.0, "kind": "pitch"},
        "impact": {"frame": 24, "x": 450.0, "y": 600.0, "type": "bat"},
        "last_visible_frame": 30,
        "flags": ["unclear"],
        "calibration_gt": _make_synthetic_calibration_gt(False, False, None),
    }
    res_unclear = {
        "video": {"frame_count": 40},
        "events": {
            "release": {"frame": 10, "x": 100.0, "y": 110.0},  # +2f, 10px
            "bounce": {"frame": 28, "x": 500.0, "y": 700.0, "zone": "YORKER", "length_m": 1.0},  # huge error, must be excluded
            "deviation": {"frame": 35, "x": 500.0, "y": 700.0},
            "impact": None,
        },
        "trajectory": [],
        "stats": {"processing_time_sec": 14.0},
    }

    # Clip 3: frame count mismatch -> excluded from all scoring
    lbl_mismatch = {
        "clip_id": "c_mismatch",
        "status": "final",
        "split": "dev",
        "ball_colour": "red",
        "release": {"frame": 5, "x": 100.0, "y": 100.0},
        "bounce": {"frame": 15, "x": 452.5, "y": 500.0, "kind": "pitch"},
        "impact": {"frame": 20, "x": 450.0, "y": 600.0, "type": "bat"},
        "last_visible_frame": 25,
        "flags": [],
        "calibration_gt": calib_gt,
    }
    res_mismatch = {
        "video": {"frame_count": 99},  # expected 40
        "events": {
            "release": {"frame": 50, "x": 0.0, "y": 0.0},
            "bounce": {"frame": 50, "x": 0.0, "y": 0.0, "zone": "SHORT", "length_m": 15.0},
            "deviation": None,
            "impact": None,
        },
        "trajectory": [],
        "stats": {"processing_time_sec": 20.0},
    }

    s1 = score_clip(lbl_none, res_none, expected_frame_count=40)
    s2 = score_clip(lbl_unclear, res_unclear, expected_frame_count=40)
    s3 = score_clip(lbl_mismatch, res_mismatch, expected_frame_count=40)

    agg = aggregate_scores([s1, s2, s3], tolerances=[0, 1, 2])

    # Frame alignment: 3 total, 2 aligned, 1 mismatched
    assert agg["frame_alignment"]["n_total_labels"] == 3
    assert agg["frame_alignment"]["n_aligned"] == 2
    assert agg["frame_alignment"]["n_mismatched"] == 1
    assert agg["frame_alignment"]["mismatched_clips"][0]["clip_id"] == "c_mismatch"

    # Unclear section: 1 clip (c_unclear)
    assert len(agg["unclear_clips"]) == 1
    assert agg["unclear_clips"][0]["clip_id"] == "c_unclear"

    # Release includes BOTH c_none (err=0) and c_unclear (err=+2) -> n=2
    rel = agg["overall"]["release"]
    assert rel["n"] == 2
    assert rel["within_tolerance"]["0"] == pytest.approx(0.5)
    assert rel["within_tolerance"]["2"] == pytest.approx(1.0)

    # Bounce excludes c_unclear and c_mismatch -> only c_none (err=0) -> n=1
    bnc = agg["overall"]["bounce"]
    assert bnc["n"] == 1
    assert bnc["within_tolerance"]["0"] == pytest.approx(1.0)
    assert bnc["ground_error_m_median"] == pytest.approx(0.0, abs=1e-6)

    # Impact excludes c_unclear -> 1 clear clip (c_none) with false deviation marker
    imp = agg["overall"]["impact"]
    assert imp["n_clips"] == 1
    assert imp["n_no_contact_labelled"] == 1
    assert imp["false_marker_impact_rate"] == pytest.approx(0.0)
    assert imp["false_marker_deviation_rate"] == pytest.approx(1.0)
    assert imp["impact_type_accuracy"] == "n/a (system provides no impact type)"
    assert agg["overall"]["lbw"] == "n/a (not implemented in the system)"


def test_run_batch_dry_run_and_score_e2e(tmp_path: Path) -> None:
    labels_dir = tmp_path / "labels"
    library_dir = tmp_path / "library"
    videos_dir = library_dir / "videos"
    runs_dir = tmp_path / "runs"
    reports_dir = tmp_path / "reports"
    labels_dir.mkdir(parents=True)
    videos_dir.mkdir(parents=True)

    # Create dummy video and library.json
    vid_file = videos_dir / "c_test01.mp4"
    vid_file.write_bytes(b"fake-mp4-bytes")
    library_json = {
        "c_test01": {
            "clip_id": "c_test01",
            "display_name": "test01.mp4",
            "stored_name": "c_test01.mp4",
            "sha256": "0" * 64,
            "added_at": "2026-01-01T00:00:00Z",
            "fps": 30.0,
            "frame_count": 50,
            "width": 1080,
            "height": 1920,
        }
    }
    (library_dir / "library.json").write_text(json.dumps(library_json), encoding="utf-8")

    # Create a final label with float calibration points to verify rounding
    calib_gt = _make_synthetic_calibration_gt(True, True, 0.8)
    calib_gt["points"]["bat_L"] = [300.4, 799.6]
    rounded = build_rounded_calibration(calib_gt)
    assert rounded["bat_L"] == [300, 800]

    label_data = {
        "schema_version": 1,
        "clip_id": "c_test01",
        "status": "final",
        "split": "dev",
        "ball_colour": "white",
        "release": {"frame": 5, "x": 200.0, "y": 300.0},
        "bounce": {"frame": 15, "x": 452.5, "y": 500.0, "kind": "pitch"},
        "impact": {"frame": 22, "x": 452.5, "y": 750.0, "type": "bat"},
        "last_visible_frame": 28,
        "lbw": "not_available",
        "flags": [],
        "calibration_gt": calib_gt,
    }
    (labels_dir / "c_test01.json").write_text(json.dumps(label_data), encoding="utf-8")

    # Also add a draft label that must be ignored
    draft_label = dict(label_data, clip_id="c_draft", status="draft")
    (labels_dir / "c_draft.json").write_text(json.dumps(draft_label), encoding="utf-8")

    # 1. Test run_batch --dry-run
    info = run_batch(
        run_name="synth_run",
        dry_run=True,
        labels_dir=labels_dir,
        library_dir=library_dir,
        runs_dir=runs_dir,
    )
    assert len(info["clips"]) == 1
    assert info["clips"][0]["clip_id"] == "c_test01"
    assert info["clips"][0]["status"] == "dry_run"
    assert info["clips"][0]["calibration"]["bat_L"] == [300, 800]
    assert not (runs_dir / "synth_run").exists()

    # 2. Populate synthetic run output and run score.py end-to-end
    clip_run_dir = runs_dir / "synth_run" / "c_test01"
    clip_run_dir.mkdir(parents=True)
    synth_results = {
        "video": {"fps": 30.0, "width": 1080, "height": 1920, "frame_count": 50},
        "events": {
            "release": {"frame": 5, "x": 200.0, "y": 300.0},
            "bounce": {"frame": 16, "x": 452.5, "y": 500.0, "zone": "GOOD", "length_m": 9.5},
            "deviation": {"frame": 22, "x": 452.5, "y": 750.0},
            "impact": None,
        },
        "trajectory": [
            {"frame": f, "x": 400.0, "y": 400.0, "interpolated": False}
            for f in range(5, 29)
        ],
        "stats": {"processing_time_sec": 15.2},
    }
    (clip_run_dir / "results.json").write_text(json.dumps(synth_results), encoding="utf-8")
    (runs_dir / "synth_run" / "run_info.json").write_text(
        json.dumps(
            {
                "run_name": "synth_run",
                "utc_time": "2026-01-01T00:00:00Z",
                "git_commit": "deadbeef",
                "pipeline_or_worker_dirty": False,
                "legacy_tracker_folder": "Zone-div_V8m",
                "ball_types": ["white"],
                "clips": [{"clip_id": "c_test01", "ball_type": "white", "status": "ok", "wall_clock_sec": 15.2}],
            }
        ),
        encoding="utf-8",
    )

    md_path, csv_path, json_path = run_scoring(
        run_name="synth_run",
        labels_dir=labels_dir,
        library_dir=library_dir,
        runs_dir=runs_dir,
        reports_dir=reports_dir,
    )
    assert md_path.is_file()
    assert csv_path.is_file()
    assert json_path.is_file()

    summary = json.loads(json_path.read_text(encoding="utf-8"))
    assert summary["overall"]["release"]["within_tolerance"]["0"] == pytest.approx(1.0)
    assert summary["overall"]["bounce"]["within_tolerance"]["1"] == pytest.approx(1.0)
    assert summary["overall"]["impact"]["deviation_within_tolerance"]["0"] == pytest.approx(1.0)
    md_text = md_path.read_text(encoding="utf-8")
    assert "## 2. Headline Table (Overall)" in md_text
    assert "## 4. Worst 5 Clips per Metric" in md_text
    assert "## 5. Caveats" in md_text
