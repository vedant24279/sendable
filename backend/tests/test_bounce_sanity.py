"""Unit tests for the flagged TRACKER_BOUNCE_SANITY rule."""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_LEGACY_DIR = _BACKEND_DIR / "worker" / "legacy" / "Zone-div_V8m"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
if str(_LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(_LEGACY_DIR))

from pipeline.process import BOUNCE_SANITY_MIN_OFFSET, apply_bounce_sanity  # noqa: E402


def _ball_det(cx: int, cy: int, conf: float = 0.9) -> list[dict]:
    return [{
        "class_name": "ball",
        "x1": cx - 5,
        "y1": cy - 5,
        "x2": cx + 5,
        "y2": cy + 5,
        "conf": conf,
    }]


def test_discards_bounce_at_release_plus_2_and_finds_next():
    release_f = 4
    # Spurious early bounce at frame 6 (release + 2), plus real bounce at frame 13
    # (detected using only frames >= release + 6 == 10).
    dets_by_frame = {
        4: _ball_det(500, 300),
        5: _ball_det(500, 340),
        6: _ball_det(500, 380),   # spurious bounce vertex at release + 2
        7: _ball_det(500, 340),
        8: _ball_det(500, 360),
        10: _ball_det(500, 420),
        12: _ball_det(500, 460),
        13: _ball_det(500, 510),  # real bounce vertex (>= release + 6)
        14: _ball_det(500, 470),
    }
    spurious_bounce = (6, 500, 385)

    res = apply_bounce_sanity(dets_by_frame, release_f, spurious_bounce)

    assert res is not None
    assert res[0] == 13
    assert res[0] >= release_f + BOUNCE_SANITY_MIN_OFFSET


def test_discards_bounce_at_release_plus_2_and_returns_none_when_no_later_bounce():
    release_f = 4
    # Only a spurious early bounce at frame 6; post-frame-10 detections move strictly down.
    dets_by_frame = {
        5: _ball_det(500, 340),
        6: _ball_det(500, 380),
        7: _ball_det(500, 340),
        10: _ball_det(500, 400),
        11: _ball_det(500, 420),
        12: _ball_det(500, 440),
    }
    spurious_bounce = (6, 500, 385)

    res = apply_bounce_sanity(dets_by_frame, release_f, spurious_bounce)

    assert res is None


def test_keeps_bounce_at_release_plus_6():
    release_f = 4
    valid_bounce = (10, 500, 505)

    res = apply_bounce_sanity({}, release_f, valid_bounce)

    assert res == valid_bounce


def test_passthrough_when_release_or_bounce_missing():
    assert apply_bounce_sanity({}, 4, None) is None
    assert apply_bounce_sanity({}, None, (6, 500, 385)) == (6, 500, 385)
