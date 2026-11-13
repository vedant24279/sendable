"""Unit and integration tests for scoring.py, score.py, and run_batch.py."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Dict

import pytest

from app.calib import fit_homography, pixel_to_world, world_to_pixel
from run_batch import build_rounded_calibration, run_batch
from score import main as score_main
from score import run_scoring
from scoring import (
    aggregate_scores,
    classify_pitch_z_zone,
    format_markdown_report,
    format_per_clip_csv,
    load_ball_detections_csv,
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
    assert "## Conventions" in md_text
    assert "## 2. Headline Table (Overall)" in md_text
    assert "## 4. Worst 5 Clips per Metric" in md_text
    assert "## 5. Caveats" in md_text


def test_centre_vs_centre_marker_offset_approx_no_centre_and_zones(tmp_path: Path) -> None:
    zones = load_legacy_zones()
    calib_gt = _make_synthetic_calibration_gt(True, True, 0.5)
    H = fit_homography(calib_gt["points"], calib_gt["stump_confirmed"]).H

    # Label bounce at world (0.10, 7.0) -> GOOD ([4.0, 8.0))
    lx, lz = 0.10, 7.0
    lbl_px = world_to_pixel(H, lx, lz)
    assert lbl_px is not None
    lbl_x, lbl_y = lbl_px

    # Exact centre at world (0.25, 3.5) -> FULL ([2.0, 4.0))
    # While as-reported marker is further down on screen (+10 px in y -> marker y = cy + 10)
    cx1, cz1 = 0.25, 3.5
    c1_px = world_to_pixel(H, cx1, cz1)
    assert c1_px is not None
    c1_x, c1_y = c1_px
    marker1_x, marker1_y = c1_x + 2.0, c1_y + 10.0  # box height = 20 -> marker dy depends on lbl_y

    # Write synthetic pipeline detections CSV with section headers
    csv_path = tmp_path / "detections_synth.csv"
    csv_path.write_text(
        "\n".join(
            [
                "--- BALL DETECTIONS ---",
                "frame,timestamp_sec,event_type,class,conf,x1,y1,x2,y2,cx,cy,width,height,grid_row,grid_col",
                f"15,0.5,detection,ball,0.8,440,590,460,610,{c1_x},{c1_y},20,20,60,10",
                "",
                "--- BAT DETECTIONS ---",
                "frame,timestamp_sec,event_type,class,conf,x1,y1,x2,y2,cx,cy,width,height,grid_row,grid_col",
                "15,0.5,detection,bat,0.9,400,700,450,780,425,740,50,80,,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    dets = load_ball_detections_csv(csv_path)
    assert dets[15]["height"] == pytest.approx(20.0)
    assert dets[15]["y2"] == pytest.approx(610.0)
    assert dets[15]["cy"] == pytest.approx(c1_y)

    label_base = {
        "schema_version": 1,
        "clip_id": "c_exact",
        "status": "final",
        "split": "dev",
        "ball_colour": "pink",
        "release": {"frame": 5, "x": lbl_x, "y": lbl_y},
        "bounce": {"frame": 15, "x": lbl_x, "y": lbl_y, "kind": "pitch"},
        "impact": {"frame": 22, "x": lbl_x, "y": lbl_y, "type": "none"},
        "last_visible_frame": 25,
        "flags": [],
        "calibration_gt": calib_gt,
    }

    # Case 1: "exact" (non-interpolated at bounce frame 15; marker zone says GOOD while recomputed says YORKER)
    res_exact = {
        "video": {"fps": 30.0, "width": 1080, "height": 1920, "frame_count": 30},
        "events": {
            "release": {"frame": 5, "x": lbl_x, "y": lbl_y},
            "bounce": {"frame": 15, "x": marker1_x, "y": marker1_y, "zone": "GOOD", "length_m": 6.5},
            "deviation": None,
            "impact": None,
        },
        "trajectory": [
            {"frame": 14, "x": c1_x - 5.0, "y": c1_y - 5.0, "interpolated": False},
            {"frame": 15, "x": c1_x, "y": c1_y, "interpolated": False},
        ],
        "stats": {"processing_time_sec": 5.0},
    }
    sc_exact = score_clip(
        label_base,
        res_exact,
        expected_frame_count=30,
        zones=zones,
        detections_by_frame=dets,
    )
    expected_c_wx, expected_c_wz = pixel_to_world(H, c1_x, c1_y)
    assert expected_c_wx is not None and expected_c_wz is not None
    expected_lbl_wx, expected_lbl_wz = pixel_to_world(H, lbl_x, lbl_y)
    assert expected_lbl_wx is not None and expected_lbl_wz is not None

    assert sc_exact["bounce_centre_status"] == "exact"
    assert sc_exact["bounce_centre_frame"] == 15
    assert sc_exact["bounce_centre_dx"] == pytest.approx(c1_x - lbl_x, abs=1e-6)
    assert sc_exact["bounce_centre_dy"] == pytest.approx(c1_y - lbl_y, abs=1e-6)
    assert sc_exact["bounce_centre_px_error"] == pytest.approx(math.hypot(c1_x - lbl_x, c1_y - lbl_y), abs=1e-6)
    assert sc_exact["bounce_centre_pitch_x_error_m"] == pytest.approx(expected_c_wx - expected_lbl_wx, abs=1e-6)
    assert sc_exact["bounce_centre_pitch_z_error_m"] == pytest.approx(expected_c_wz - expected_lbl_wz, abs=1e-6)
    assert sc_exact["bounce_centre_ground_error_m"] == pytest.approx(
        math.hypot(expected_c_wx - expected_lbl_wx, expected_c_wz - expected_lbl_wz), abs=1e-6
    )
    assert sc_exact["label_zone"] == "GOOD"
    assert sc_exact["system_zone"] == "GOOD"
    assert sc_exact["zone_match"] is True
    assert sc_exact["system_zone_recomputed"] == classify_pitch_z_zone(expected_c_wz, zones) == "FULL"
    assert sc_exact["zone_match_recomputed"] is False

    assert sc_exact["bounce_marker_dx"] == pytest.approx(marker1_x - lbl_x, abs=1e-6)
    assert sc_exact["bounce_marker_dy"] == pytest.approx(marker1_y - lbl_y, abs=1e-6)
    assert sc_exact["bounce_det_box_height_px"] == pytest.approx(20.0)
    assert sc_exact["bounce_marker_dy_over_box_height"] == pytest.approx((marker1_y - lbl_y) / 20.0, abs=1e-6)

    # Case 2: "approx" (frame 15 is interpolated=True, frame 16 is non-interpolated -> picks 16)
    res_approx = {
        "video": {"fps": 30.0, "width": 1080, "height": 1920, "frame_count": 30},
        "events": {
            "release": {"frame": 5, "x": lbl_x, "y": lbl_y},
            "bounce": {"frame": 15, "x": lbl_x, "y": lbl_y + 10.0, "zone": "YORKER", "length_m": 6.5},
            "deviation": None,
            "impact": None,
        },
        "trajectory": [
            {"frame": 15, "x": 999.0, "y": 999.0, "interpolated": True},
            {"frame": 16, "x": lbl_x + 4.0, "y": lbl_y - 3.0, "interpolated": False},
        ],
        "stats": {"processing_time_sec": 4.0},
    }
    sc_approx = score_clip(
        dict(label_base, clip_id="c_approx"),
        res_approx,
        expected_frame_count=30,
        zones=zones,
        detections_by_frame=dets,
    )
    assert sc_approx["bounce_centre_status"] == "approx"
    assert sc_approx["bounce_centre_frame"] == 16
    assert sc_approx["bounce_centre_dx"] == pytest.approx(4.0, abs=1e-6)
    assert sc_approx["bounce_centre_dy"] == pytest.approx(-3.0, abs=1e-6)
    assert sc_approx["bounce_centre_px_error"] == pytest.approx(5.0, abs=1e-6)
    assert sc_approx["bounce_marker_dy"] == pytest.approx(10.0, abs=1e-6)
    assert sc_approx["bounce_marker_dy_over_box_height"] == pytest.approx(0.5, abs=1e-6)
    assert sc_approx["system_zone"] == "YORKER"
    assert sc_approx["zone_match"] is False
    assert sc_approx["system_zone_recomputed"] == "GOOD"
    assert sc_approx["zone_match_recomputed"] is True

    # Case 3: "no_centre" (only frame 15 interpolated and frame 17 non-interpolated outside +-1)
    res_none = {
        "video": {"fps": 30.0, "width": 1080, "height": 1920, "frame_count": 30},
        "events": {
            "release": {"frame": 5, "x": lbl_x, "y": lbl_y},
            "bounce": {"frame": 15, "x": lbl_x + 2.0, "y": lbl_y + 8.0, "zone": "GOOD", "length_m": 6.5},
            "deviation": None,
            "impact": None,
        },
        "trajectory": [
            {"frame": 15, "x": 999.0, "y": 999.0, "interpolated": True},
            {"frame": 17, "x": lbl_x, "y": lbl_y, "interpolated": False},
        ],
        "stats": {"processing_time_sec": 3.0},
    }
    sc_none = score_clip(
        dict(label_base, clip_id="c_nocentre"),
        res_none,
        expected_frame_count=30,
        zones=zones,
        detections_by_frame=dets,
    )
    assert sc_none["bounce_centre_status"] == "no_centre"
    assert sc_none["bounce_centre_x"] is None
    assert sc_none["bounce_centre_dx"] is None
    assert sc_none["system_zone_recomputed"] is None
    assert sc_none["zone_match_recomputed"] is None

    summary = aggregate_scores([sc_exact, sc_approx, sc_none], zones=zones)
    ov_cc = summary["overall"]["bounce_centre_vs_centre"]
    assert ov_cc["n_found"] == 3
    assert ov_cc["n_exact"] == 1
    assert ov_cc["n_approx"] == 1
    assert ov_cc["n_no_centre"] == 1
    assert ov_cc["n"] == 2
    assert ov_cc["dx_mean"] == pytest.approx(((c1_x - lbl_x) + 4.0) / 2.0, abs=1e-6)
    assert ov_cc["dy_mean"] == pytest.approx(((c1_y - lbl_y) - 3.0) / 2.0, abs=1e-6)
    # Recomputed zone agrees on c_approx only (1/2 = 0.5); as-reported agrees on c_exact & c_nocentre (2/3)
    assert ov_cc["zone_agreement_rate"] == pytest.approx(0.5, abs=1e-6)
    assert summary["overall"]["bounce"]["zone_agreement_rate"] == pytest.approx(2.0 / 3.0, abs=1e-6)

    zc_rec = summary["zone_confusion_recomputed"]
    assert zc_rec["n"] == 2
    assert zc_rec["agreement_count"] == 1
    assert zc_rec["matrix"]["GOOD"]["GOOD"] == 1
    assert zc_rec["matrix"]["GOOD"]["FULL"] == 1

    ov_mo = summary["overall"]["bounce_marker_offset"]
    assert ov_mo["n"] == 3
    assert ov_mo["n_with_box_height"] == 3
    expected_dy_ratios = sorted(
        [(marker1_y - lbl_y) / 20.0, 10.0 / 20.0, 8.0 / 20.0]
    )
    assert ov_mo["dy_over_box_height_median"] == pytest.approx(expected_dy_ratios[1], abs=1e-6)

    csv_text = format_per_clip_csv([sc_exact, sc_approx, sc_none])
    rows = list(csv.DictReader(csv_text.splitlines()))
    assert len(rows) == 3
    assert rows[0]["bounce_centre_status"] == "exact"
    assert rows[1]["bounce_centre_status"] == "approx"
    assert rows[2]["bounce_centre_status"] == "no_centre"
    assert float(rows[1]["bounce_marker_dy_over_box_height"]) == pytest.approx(0.5, abs=1e-6)
    assert rows[0]["system_zone_recomputed"] == "FULL"


def test_score_cli_out_name_and_detections_csv(tmp_path: Path) -> None:
    labels_dir = tmp_path / "labels"
    library_dir = tmp_path / "library"
    runs_dir = tmp_path / "runs"
    reports_dir = tmp_path / "reports"
    labels_dir.mkdir()
    library_dir.mkdir()
    clip_run_dir = runs_dir / "orig_run" / "c_cli01"
    clip_run_dir.mkdir(parents=True)

    (library_dir / "library.json").write_text(
        json.dumps({"c_cli01": {"clip_id": "c_cli01", "frame_count": 30}}),
        encoding="utf-8",
    )
    calib_gt = _make_synthetic_calibration_gt(True, True, 0.5)
    H = fit_homography(calib_gt["points"], calib_gt["stump_confirmed"]).H
    bx, by = world_to_pixel(H, 0.0, 6.0)
    (labels_dir / "c_cli01.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "clip_id": "c_cli01",
                "status": "final",
                "split": "final",
                "ball_colour": "red",
                "release": {"frame": 5, "x": bx, "y": by},
                "bounce": {"frame": 15, "x": bx, "y": by, "kind": "pitch"},
                "impact": {"frame": 20, "x": bx, "y": by, "type": "none"},
                "last_visible_frame": 25,
                "flags": [],
                "calibration_gt": calib_gt,
            }
        ),
        encoding="utf-8",
    )
    (clip_run_dir / "detections_20261113_000000.csv").write_text(
        f"--- BALL DETECTIONS ---\nframe,height,y2,cy\n15,16,{by + 8.0},{by}\n",
        encoding="utf-8",
    )
    (clip_run_dir / "results.json").write_text(
        json.dumps(
            {
                "video": {"frame_count": 30},
                "outputs": {"csv_url": "detections_20261113_000000.csv"},
                "events": {
                    "release": {"frame": 5, "x": bx, "y": by},
                    "bounce": {"frame": 15, "x": bx, "y": by + 8.0, "zone": "GOOD", "length_m": 6.0},
                    "deviation": None,
                    "impact": None,
                },
                "trajectory": [{"frame": 15, "x": bx, "y": by, "interpolated": False}],
                "stats": {"processing_time_sec": 2.5},
            }
        ),
        encoding="utf-8",
    )
    (runs_dir / "orig_run" / "run_info.json").write_text(
        json.dumps({"run_name": "orig_run", "clips": [{"clip_id": "c_cli01"}]}),
        encoding="utf-8",
    )

    rc = score_main(
        [
            "--run",
            "orig_run",
            "--out-name",
            "orig_run_v2",
            "--labels-dir",
            str(labels_dir),
            "--library-dir",
            str(library_dir),
            "--runs-dir",
            str(runs_dir),
            "--reports-dir",
            str(reports_dir),
        ]
    )
    assert rc == 0
    assert (reports_dir / "orig_run_v2.md").is_file()
    assert (reports_dir / "orig_run_v2_per_clip.csv").is_file()
    assert (reports_dir / "orig_run_v2_summary.json").is_file()
    assert not (reports_dir / "orig_run.md").exists()

    summary = json.loads((reports_dir / "orig_run_v2_summary.json").read_text(encoding="utf-8"))
    assert summary["overall"]["bounce_marker_offset"]["dy_median"] == pytest.approx(8.0, abs=1e-6)
    assert summary["overall"]["bounce_marker_offset"]["dy_over_box_height_median"] == pytest.approx(0.5, abs=1e-6)
    assert summary["overall"]["bounce_centre_vs_centre"]["dx_median"] == pytest.approx(0.0, abs=1e-6)
    assert summary["overall"]["bounce_centre_vs_centre"]["dy_median"] == pytest.approx(0.0, abs=1e-6)
