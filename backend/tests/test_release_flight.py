"""Unit tests for backend.pipeline.release_flight."""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from pipeline.release_flight import (
    FLIGHT_RUN_K,
    FLIGHT_RUN_T,
    find_flight_release,
)


def _markers(width: float = 500.0) -> Dict[str, tuple[float, float]]:
    return {
        "bat_L": (700.0, 500.0),
        "bat_R": (1200.0, 500.0),
        "bowl_L": (700.0, 950.0),
        "bowl_R": (700.0 + width, 950.0),
    }


def _det(
    cx: float,
    cy: float,
    conf: float = 0.8,
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


def test_default_constants_match_phase1_selection() -> None:
    assert FLIGHT_RUN_K == 3
    assert FLIGHT_RUN_T == pytest.approx(0.070)


def test_swing_then_flight_picks_release_after_arm_swing() -> None:
    # Crease width = 500 -> T = 35 px.
    # f0->f1: 80px (0.16), f1->f2: 60px (0.12), f2->f3: 55px (0.11),
    # f3->f4: 15px (0.03), f4->f5: 20px (0.04), f5->f6: 25px (0.05), f6->f7: 30px (0.06).
    # At f3: incoming is 0.11 (> 0.070), rejected.
    # At f4: incoming is 0.03 <= 0.070, outgoing 3 steps [0.04, 0.05, 0.06] <= 0.070 -> release = f4.
    detections = {
        0: [_det(800.0, 670.0), _det(900.0, 400.0, conf=0.95, class_name="bat")],
        1: [_det(800.0, 590.0)],
        2: [_det(800.0, 530.0)],
        3: [_det(800.0, 475.0)],
        4: [_det(800.0, 460.0)],
        5: [_det(800.0, 480.0)],
        6: [_det(800.0, 505.0)],
        7: [_det(800.0, 535.0)],
    }
    assert find_flight_release(detections, _markers(500.0)) == (4, 800, 460)


def test_first_detection_qualifies_on_three_following_steps() -> None:
    detections = {
        2: [_det(776.0, 456.0)],
        3: [_det(784.0, 462.0)],
        4: [_det(786.0, 464.0)],
        5: [_det(795.0, 470.0)],
    }
    assert find_flight_release(detections, _markers(376.0)) == (2, 776, 456)


def test_multi_candidate_nearest_neighbour_ignores_distractor() -> None:
    detections = {
        0: [_det(800.0, 600.0, conf=0.9), _det(200.0, 200.0, conf=0.4)],
        1: [_det(800.0, 520.0, conf=0.8)],
        2: [_det(800.0, 505.0, conf=0.7), _det(1400.0, 500.0, conf=0.95)],
        3: [_det(800.0, 490.0, conf=0.7)],
        4: [_det(800.0, 475.0, conf=0.7)],
        5: [_det(800.0, 460.0, conf=0.7)],
    }
    assert find_flight_release(detections, _markers(500.0)) == (2, 800, 505)


def test_returns_none_when_no_detection_qualifies() -> None:
    # All normalized steps are >= 0.10 (> 0.070) -> return None to keep streaming release.
    detections: Dict[int, List[Dict[str, Any]]] = {
        f: [_det(800.0, 300.0 + f * 60.0)] for f in range(6)
    }
    assert find_flight_release(detections, _markers(500.0)) is None


def test_returns_none_on_short_track_or_bad_markers() -> None:
    short = {0: [_det(800.0, 400.0)], 1: [_det(810.0, 405.0)], 2: [_det(820.0, 410.0)]}
    assert find_flight_release(short, _markers(500.0)) is None
    valid = {f: [_det(800.0 + f * 5.0, 400.0)] for f in range(5)}
    assert find_flight_release(valid, {"bowl_L": (700.0, 950.0), "bowl_R": (700.0, 950.0)}) is None
    assert find_flight_release(valid, {"bowl_L": (700.0, 950.0)}) is None
