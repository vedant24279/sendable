"""Unit tests for backend.pipeline.impact_vertex."""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from pipeline.impact_vertex import (
    POST_IMPACT_MAX_MISSING_FRAMES,
    POST_IMPACT_MAX_STEP_W,
    SPEED_RATIO,
    STUMP_DX_MAX,
    STUMP_DY_ABOVE_MAX,
    STUMP_DY_BELOW_MAX,
    THETA,
    UP,
    find_impact_vertex,
    find_post_impact_points,
)


def _markers(width: float = 400.0) -> Dict[str, tuple[float, float]]:
    return {
        "bat_L": (760.0, 500.0),
        "bat_R": (1160.0, 500.0),
        "bowl_L": (760.0, 950.0),
        "bowl_R": (760.0 + width, 950.0),
        "bat_stump": (960.0, 480.0),
        "bowl_stump": (960.0, 960.0),
    }


def _det(
    cx: float,
    cy: float,
    conf: float = 0.85,
    class_name: str = "ball",
) -> Dict[str, Any]:
    return {
        "class_name": class_name,
        "x1": cx - 8.0,
        "y1": cy - 8.0,
        "x2": cx + 8.0,
        "y2": cy + 8.0,
        "conf": conf,
    }


def test_default_constants_match_phase1b_selection() -> None:
    assert UP == pytest.approx(0.01)
    assert THETA == pytest.approx(30.0)
    assert SPEED_RATIO == pytest.approx(0.6)
    assert STUMP_DX_MAX == pytest.approx(0.30)
    assert STUMP_DY_ABOVE_MAX == pytest.approx(0.35)
    assert STUMP_DY_BELOW_MAX == pytest.approx(0.05)
    assert POST_IMPACT_MAX_MISSING_FRAMES == 3
    assert POST_IMPACT_MAX_STEP_W == pytest.approx(0.25)


def test_straight_passthrough_track_with_no_turn_returns_none() -> None:
    # Ball rises steadily after bounce (frame 10) with constant velocity (dx=2, dy=-15)
    # and no deflection or speed drop -> returns None.
    dets: Dict[int, List[Dict[str, Any]]] = {
        8: [_det(946.0, 510.0)],
        9: [_det(948.0, 530.0)],
        10: [_det(950.0, 550.0)],  # bounce
        11: [_det(952.0, 535.0)],
        12: [_det(954.0, 520.0)],
        13: [_det(956.0, 505.0)],
        14: [_det(958.0, 490.0)],
        15: [_det(960.0, 475.0)],
        16: [_det(962.0, 460.0)],
        17: [_det(964.0, 445.0)],
    }
    assert find_impact_vertex(dets, _markers(400.0), bounce_frame=10) is None


def test_descending_bounce_rising_to_vertex_returns_vertex() -> None:
    # Descending to bounce at f12, rising to pad vertex at f16 (inside bat_stump gate),
    # then deflecting down-right at f17..f19.
    dets: Dict[int, List[Dict[str, Any]]] = {
        10: [_det(950.0, 490.0)],
        11: [_det(952.0, 520.0)],
        12: [_det(954.0, 555.0)],  # bounce (big turn here, but frame <= bounce_frame)
        13: [_det(955.0, 525.0)],
        14: [_det(956.0, 495.0)],
        15: [_det(958.0, 465.0)],
        16: [_det(960.0, 440.0)],  # ascending vertex at pad
        17: [_det(980.0, 452.0)],  # deflected off pad
        18: [_det(1000.0, 466.0)],
        19: [_det(1020.0, 482.0)],
    }
    res = find_impact_vertex(dets, _markers(400.0), bounce_frame=12)
    assert res == {"frame": 16, "x": 960, "y": 440}


def test_track_ending_behind_stumps_with_no_outgoing_steps_returns_none() -> None:
    # Ball rises after bounce and track ends at f15 (or has only 1 outgoing step)
    # without the 2 outgoing steps required to establish a vertex -> returns None.
    dets_no_outgoing: Dict[int, List[Dict[str, Any]]] = {
        10: [_det(950.0, 500.0)],
        11: [_det(952.0, 530.0)],
        12: [_det(954.0, 560.0)],  # bounce
        13: [_det(956.0, 520.0)],
        14: [_det(958.0, 480.0)],
        15: [_det(960.0, 440.0)],  # last detection, no outgoing steps
    }
    assert find_impact_vertex(dets_no_outgoing, _markers(400.0), bounce_frame=12) is None

    # Even if one point exists after f15 (f16), f15 has only 1 outgoing step and
    # if incoming up to f14 had no deflection, still None.
    dets_one_outgoing = dict(dets_no_outgoing)
    dets_one_outgoing[16] = [_det(962.0, 400.0)]
    assert find_impact_vertex(dets_one_outgoing, _markers(400.0), bounce_frame=12) is None


def test_detection_gap_right_after_bounce_still_finds_vertex() -> None:
    # Frame 13 (immediately after bounce at f12) and frame 17 (immediately after
    # vertex at f16) are missing; per-frame step normalization still finds f16.
    dets: Dict[int, List[Dict[str, Any]]] = {
        10: [_det(950.0, 490.0)],
        11: [_det(952.0, 525.0)],
        12: [_det(954.0, 560.0)],  # bounce
        # frame 13 missing!
        14: [_det(956.0, 500.0)],
        15: [_det(958.0, 470.0)],
        16: [_det(960.0, 442.0)],  # vertex
        # frame 17 missing!
        18: [_det(992.0, 462.0)],
        19: [_det(1010.0, 475.0)],
    }
    res = find_impact_vertex(dets, _markers(400.0), bounce_frame=12)
    assert res == {"frame": 16, "x": 960, "y": 442}


def test_post_impact_track_stops_at_gap_and_large_step() -> None:
    markers = _markers(400.0)  # W = 400 -> 0.25 * W = 100 px
    # Impact at frame 16.
    # Frames 17, 18 present; frames 19, 20, 21 missing (gap of 3 missing frames <= 3) -> f22 kept!
    # Frames 23, 24, 25, 26 missing (gap of 4 missing frames > 3) -> f27 and beyond stopped!
    dets_gap: Dict[int, List[Dict[str, Any]]] = {
        16: [_det(960.0, 440.0, conf=0.9)],
        17: [_det(975.0, 448.0, conf=0.81234)],
        18: [_det(990.0, 456.0, conf=0.75)],
        # 19, 20, 21 missing (3 missing frames -> allowed)
        22: [_det(1030.0, 476.0, conf=0.70)],
        # 23, 24, 25, 26 missing (4 missing frames -> stops before 27)
        27: [_det(1060.0, 490.0, conf=0.88)],
        28: [_det(1070.0, 495.0, conf=0.85)],
    }
    pts = find_post_impact_points(dets_gap, markers, impact_frame=16)
    assert [p["frame"] for p in pts] == [17, 18, 22]
    assert pts[0] == {"frame": 17, "x": 975, "y": 448, "conf": 0.8123}

    # Also stops when step distance > 0.25 * W (100 px), even with 0 missing frames:
    dets_jump: Dict[int, List[Dict[str, Any]]] = {
        16: [_det(960.0, 440.0, conf=0.9)],
        17: [_det(980.0, 450.0, conf=0.85)],
        18: [_det(1120.0, 450.0, conf=0.90)],  # step = 140 px > 100 px -> stop!
        19: [_det(1130.0, 455.0, conf=0.85)],
    }
    pts_jump = find_post_impact_points(dets_jump, markers, impact_frame=16)
    assert [p["frame"] for p in pts_jump] == [17]
