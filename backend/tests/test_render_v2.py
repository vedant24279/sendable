"""Pure-Python unit tests for render v2 time mapping and segments builder."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_LEGACY_DIR = _BACKEND_DIR / "worker" / "legacy" / "Zone-div_V8m"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
if str(_LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(_LEGACY_DIR))

from pipeline.process import (  # noqa: E402
    SPEED_B,
    build_segments,
    build_segments_v2,
    compute_seg_b_window_v2,
    map_seg_b_frame,
)


def test_speed_b_constant():
    assert SPEED_B == pytest.approx(0.35)


@pytest.mark.parametrize("n_source_frames", list(range(1, 41)))
def test_mapping_function_sum_and_duration_1_to_40_frames(n_source_frames: int):
    fps = 30.0
    seg_b_start = 7
    seg_b_end = seg_b_start + n_source_frames - 1

    total_written = 0
    for f in range(seg_b_start, seg_b_end + 1):
        out_idx, repeats, out_sec = map_seg_b_frame(f, seg_b_start, fps)
        assert out_idx == round((f - seg_b_start) / SPEED_B)
        assert repeats in (2, 3)
        assert out_sec == pytest.approx(round((f - seg_b_start) / SPEED_B) / fps)
        assert out_idx == total_written
        total_written += repeats

    expected_total = round((seg_b_end + 1 - seg_b_start) / SPEED_B)
    assert total_written == expected_total

    # Duration computed by the builder matches the sum of written frames / fps
    segs = build_segments_v2(
        total=100,
        fps=fps,
        release_f=seg_b_start + 5,
        bounce_f=None,
        impact_f=None,
        dev_f=None,
        trajectory_post=[{"frame": seg_b_end}],
    )
    assert segs["seg_b_end_sec"] == round(total_written / fps, 4)


def test_segments_v2_impact_and_trajectory_post():
    fps = 30.0
    total = 90
    release_f = 10
    bounce_f = 22
    impact_f = 27
    dev_f = 28
    traj_post = [
        {"frame": 28, "x": 100, "y": 200},
        {"frame": 31, "x": 110, "y": 210},
        {"frame": 35, "x": 120, "y": 220},
    ]

    seg_b_start, seg_b_end, contact_f = compute_seg_b_window_v2(
        total=total,
        release_f=release_f,
        bounce_f=bounce_f,
        impact_f=impact_f,
        dev_f=dev_f,
        trajectory_post=traj_post,
    )
    assert seg_b_start == 5
    assert seg_b_end == 35
    assert contact_f == 27

    segs = build_segments_v2(
        total=total,
        fps=fps,
        release_f=release_f,
        bounce_f=bounce_f,
        impact_f=impact_f,
        dev_f=dev_f,
        trajectory_post=traj_post,
    )
    assert segs["render_mode"] == "v2"
    assert segs["speed_b"] == 0.35
    assert segs["seg_a_start_sec"] == 0.0
    assert segs["seg_a_end_sec"] == 0.0
    assert segs["seg_a_release_sec"] is None
    assert segs["seg_a_bounce_sec"] is None
    assert segs["seg_a_deviation_sec"] is None

    assert segs["seg_b_start_sec"] == 0.0
    expected_b_frames = round((35 + 1 - 5) / 0.35)
    expected_b_end_sec = expected_b_frames / fps
    assert segs["seg_b_end_sec"] == round(expected_b_end_sec, 4)
    assert segs["seg_b_release_sec"] == round(round((10 - 5) / 0.35) / fps, 4)
    assert segs["seg_b_bounce_sec"] == round(round((22 - 5) / 0.35) / fps, 4)
    assert segs["seg_b_impact_sec"] == round(round((27 - 5) / 0.35) / fps, 4)
    assert segs["seg_b_deviation_sec"] == segs["seg_b_impact_sec"]
    assert segs["seg_b_post_end_sec"] == round(round((35 - 5) / 0.35) / fps, 4)

    rb_anim = 2.0 * (22 - 10) / fps
    bi_anim = 2.0 * (27 - 22) / fps
    post_anim = 2.0 * (35 - 27) / fps
    assert segs["seg_c_start_sec"] == round(expected_b_end_sec, 4)
    assert segs["seg_c_rb_end_sec"] == round(expected_b_end_sec + rb_anim, 4)
    assert segs["seg_c_bi_end_sec"] == round(
        expected_b_end_sec + rb_anim + bi_anim, 4
    )
    assert segs["seg_c_bd_end_sec"] == segs["seg_c_bi_end_sec"]
    assert segs["seg_c_post_end_sec"] == round(
        expected_b_end_sec + rb_anim + bi_anim + post_anim, 4
    )
    assert segs["seg_c_end_sec"] == round(
        expected_b_end_sec + rb_anim + bi_anim + post_anim + 1.0, 4
    )


def test_segments_v2_deviation_only():
    fps = 30.0
    total = 90
    release_f = 8
    bounce_f = 19
    dev_f = 24

    seg_b_start, seg_b_end, contact_f = compute_seg_b_window_v2(
        total=total,
        release_f=release_f,
        bounce_f=bounce_f,
        impact_f=None,
        dev_f=dev_f,
        trajectory_post=[],
    )
    assert seg_b_start == 3
    assert contact_f == 24
    assert seg_b_end == 29  # contact_f + 5

    segs = build_segments_v2(
        total=total,
        fps=fps,
        release_f=release_f,
        bounce_f=bounce_f,
        impact_f=None,
        dev_f=dev_f,
        trajectory_post=[],
    )
    assert segs["seg_b_impact_sec"] is None
    assert segs["seg_b_deviation_sec"] == round(round((24 - 3) / 0.35) / fps, 4)
    assert segs["seg_b_post_end_sec"] is None
    assert segs["seg_c_post_end_sec"] is None
    assert segs["seg_c_bi_end_sec"] == segs["seg_c_bd_end_sec"]

    expected_b_end_sec = round((29 + 1 - 3) / 0.35) / fps
    rb_anim = 2.0 * (19 - 8) / fps
    bi_anim = 2.0 * (24 - 19) / fps
    assert segs["seg_c_end_sec"] == round(
        expected_b_end_sec + rb_anim + bi_anim + 1.0, 4
    )


def test_segments_v2_no_events():
    fps = 30.0
    total = 100
    seg_b_start, seg_b_end, contact_f = compute_seg_b_window_v2(
        total=total,
        release_f=None,
        bounce_f=None,
        impact_f=None,
        dev_f=None,
        trajectory_post=[],
    )
    assert seg_b_start == 0
    assert seg_b_end == 45
    assert contact_f is None

    segs = build_segments_v2(
        total=total,
        fps=fps,
        release_f=None,
        bounce_f=None,
        impact_f=None,
        dev_f=None,
        trajectory_post=[],
    )
    assert segs["seg_b_start_sec"] == 0.0
    assert segs["seg_b_end_sec"] == round(round(46 / 0.35) / fps, 4)
    assert segs["seg_b_release_sec"] is None
    assert segs["seg_b_bounce_sec"] is None
    assert segs["seg_b_impact_sec"] is None
    assert segs["seg_b_deviation_sec"] is None
    assert segs["seg_b_post_end_sec"] is None
    assert segs["seg_c_start_sec"] is None
    assert segs["seg_c_rb_end_sec"] is None
    assert segs["seg_c_bi_end_sec"] is None
    assert segs["seg_c_bd_end_sec"] is None
    assert segs["seg_c_post_end_sec"] is None
    assert segs["seg_c_end_sec"] is None


def test_segments_v2_release_frame_2_no_offset_bug():
    fps = 30.0
    total = 80
    # release_f = 2 < 5 -> seg_b_start = max(0, 2 - 5) = 0; real lead is 2 frames, not 5.
    segs = build_segments_v2(
        total=total,
        fps=fps,
        release_f=2,
        bounce_f=14,
        impact_f=18,
        dev_f=19,
        trajectory_post=[],
    )
    # Real lead = 2 - 0 = 2 source frames -> round(2 / 0.35) = 6 output frames -> 6 / 30 = 0.2s
    assert segs["seg_b_release_sec"] == round(round(2 / 0.35) / fps, 4)
    assert segs["seg_b_release_sec"] == 0.2
    # Bounce at frame 14 -> round((14 - 0) / 0.35) = 40 output frames -> 40 / 30 = 1.3333s
    assert segs["seg_b_bounce_sec"] == round(round(14 / 0.35) / fps, 4)


def test_segments_v2_short_clip_under_60_frames():
    fps = 30.0
    total = 32  # total - 1 = 31

    # Case A: no events -> min(0 + 45, 31) = 31
    s_start, s_end, _ = compute_seg_b_window_v2(
        total=total,
        release_f=None,
        bounce_f=None,
        impact_f=None,
        dev_f=None,
        trajectory_post=[],
    )
    assert (s_start, s_end) == (0, 31)

    # Case B: bounce at 15, no contact -> min(15 + 30, 31) = 31
    s_start2, s_end2, _ = compute_seg_b_window_v2(
        total=total,
        release_f=4,
        bounce_f=15,
        impact_f=None,
        dev_f=None,
        trajectory_post=[],
    )
    assert (s_start2, s_end2) == (0, 31)

    # Case C: contact at 29 -> min(29 + 5, 31) = 31
    s_start3, s_end3, _ = compute_seg_b_window_v2(
        total=total,
        release_f=4,
        bounce_f=15,
        impact_f=29,
        dev_f=None,
        trajectory_post=[],
    )
    assert (s_start3, s_end3) == (0, 31)


def test_unset_env_legacy_path_unchanged(monkeypatch):
    monkeypatch.delenv("TRACKER_RENDER_MODE", raising=False)
    fps = 30.0
    total = 90
    segs = build_segments(
        total=total,
        fps=fps,
        release_f=10,
        bounce_f=22,
        impact_f=27,
        dev_f=28,
        trajectory_post=[{"frame": 35}],
    )
    assert "render_mode" not in segs
    assert "speed_b" not in segs
    assert "seg_b_impact_sec" not in segs
    assert "seg_b_post_end_sec" not in segs
    assert "seg_c_bi_end_sec" not in segs
    assert "seg_c_post_end_sec" not in segs

    # Legacy Segment A: starts at max(0, 10 - 30) = 0, ends at min(28 + 30, 89) = 58 -> 59 frames
    assert segs["seg_a_start_sec"] == 0.0
    assert segs["seg_a_end_sec"] == round(59 / fps, 4)
    assert segs["seg_a_release_sec"] == round(10 / fps, 4)
    assert segs["seg_a_bounce_sec"] == round(22 / fps, 4)
    assert segs["seg_a_deviation_sec"] == round(28 / fps, 4)

    # Legacy Segment B: 0.5x from frame 5 to min(28 + 5, 89) = 33 -> 29 source frames * 2 = 58 output frames
    assert segs["seg_b_start_sec"] == round(59 / fps, 4)
    assert segs["seg_b_end_sec"] == round((59 + 58) / fps, 4)
    assert segs["seg_b_release_sec"] == round(59 / fps + 5 * 2 / fps, 4)
