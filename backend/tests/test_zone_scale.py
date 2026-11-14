"""Unit tests for backend/pipeline/zone_scale.py."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_LEGACY_DIR = _BACKEND_DIR / "worker" / "legacy" / "Zone-div_V8m"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
if str(_LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(_LEGACY_DIR))

import zones as _zones_mod  # noqa: E402
from pipeline import zone_scale  # noqa: E402
from pipeline import zones_classify  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_legacy_after_test():
    zone_scale.apply("legacy")
    yield
    zone_scale.apply("legacy")


def test_apply_laws_then_legacy_restores_constants_bit_for_bit():
    orig_zones_id = id(_zones_mod.ZONES)
    orig_world_id = id(_zones_mod.WORLD_COORDS)
    assert id(zones_classify.ZONES) == orig_zones_id

    orig_hw = _zones_mod.HALF_WIDTH
    orig_bat_y = _zones_mod.BAT_CREASE_Y
    orig_bowl_y = _zones_mod.BOWL_CREASE_Y
    orig_stump_y = _zones_mod.BOWL_STUMP_Y
    orig_world = copy.deepcopy(_zones_mod.WORLD_COORDS)
    orig_zones = copy.deepcopy(_zones_mod.ZONES)

    assert orig_bowl_y == 20.90
    assert orig_stump_y == pytest.approx(22.12)
    assert orig_stump_y == 20.90 + 1.22

    # Switch to laws
    mode = zone_scale.apply("laws")
    assert mode == "laws"
    assert id(_zones_mod.ZONES) == orig_zones_id
    assert id(zones_classify.ZONES) == orig_zones_id
    assert id(_zones_mod.WORLD_COORDS) == orig_world_id

    assert _zones_mod.BOWL_CREASE_Y == 18.90
    assert _zones_mod.BOWL_STUMP_Y == 20.12
    assert _zones_mod.WORLD_COORDS["bowl_L"] == (-1.32, 18.90)
    assert _zones_mod.WORLD_COORDS["bowl_R"] == (1.32, 18.90)
    assert _zones_mod.WORLD_COORDS["bowl_stump"] == (0.0, 20.12)
    assert _zones_mod.ZONES[-1][0] == 8.0
    assert _zones_mod.ZONES[-1][1] == 18.90
    assert _zones_mod.ZONES[-1][3] == "SHORT"
    assert zones_classify.ZONES[-1][1] == 18.90

    # Switch back to legacy and verify bit-for-bit restoration
    mode_back = zone_scale.apply("legacy")
    assert mode_back == "legacy"
    assert id(_zones_mod.ZONES) == orig_zones_id
    assert id(zones_classify.ZONES) == orig_zones_id
    assert id(_zones_mod.WORLD_COORDS) == orig_world_id

    assert _zones_mod.HALF_WIDTH == orig_hw
    assert _zones_mod.BAT_CREASE_Y == orig_bat_y
    assert _zones_mod.BOWL_CREASE_Y == orig_bowl_y
    assert _zones_mod.BOWL_STUMP_Y == orig_stump_y
    assert _zones_mod.WORLD_COORDS == orig_world
    assert _zones_mod.ZONES == orig_zones


def _build_synthetic_true_homography() -> np.ndarray:
    """Build a realistic perspective world->pixel homography for a 1920x1080 frame."""
    src_world = np.array(
        [
            [-1.32, 1.22],
            [+1.32, 1.22],
            [-1.32, 18.90],
            [+1.32, 18.90],
        ],
        dtype=np.float32,
    )
    dst_px = np.array(
        [
            [720.0, 500.0],
            [1200.0, 500.0],
            [680.0, 960.0],
            [1240.0, 960.0],
        ],
        dtype=np.float32,
    )
    H, _ = cv2.findHomography(src_world, dst_px, method=0)
    assert H is not None
    return H


def _project(H: np.ndarray, wx: float, wy: float) -> tuple[float, float]:
    pt = np.array([[[wx, wy]]], dtype=np.float32)
    px = cv2.perspectiveTransform(pt, H).reshape(2)
    return float(px[0]), float(px[1])


def test_derived_stumps_equal_exact_projection():
    H_true = _build_synthetic_true_homography()
    exact_bat_stump = _project(H_true, 0.0, 0.0)
    exact_bowl_stump = _project(H_true, 0.0, 20.12)

    # Perturb the clicked stumps significantly (simulating human click noise)
    noisy_markers = {
        "bat_L": _project(H_true, -1.32, 1.22),
        "bat_R": _project(H_true, +1.32, 1.22),
        "bowl_L": _project(H_true, -1.32, 18.90),
        "bowl_R": _project(H_true, +1.32, 18.90),
        "bat_stump": (exact_bat_stump[0] + 15.0, exact_bat_stump[1] - 12.0),
        "bowl_stump": (exact_bowl_stump[0] - 22.0, exact_bowl_stump[1] + 35.0),
    }

    # In legacy mode, markers are returned unchanged
    legacy_m = zone_scale.markers_for_zones(noisy_markers, "legacy")
    assert legacy_m == noisy_markers

    # In laws mode, stumps equal the exact 4-corner projection
    laws_m = zone_scale.markers_for_zones(noisy_markers, "laws")
    assert laws_m["bat_stump"][0] == pytest.approx(exact_bat_stump[0], abs=1e-3)
    assert laws_m["bat_stump"][1] == pytest.approx(exact_bat_stump[1], abs=1e-3)
    assert laws_m["bowl_stump"][0] == pytest.approx(exact_bowl_stump[0], abs=1e-3)
    assert laws_m["bowl_stump"][1] == pytest.approx(exact_bowl_stump[1], abs=1e-3)


def test_classify_bounce_synthetic_pitch_laws_vs_legacy():
    H_true = _build_synthetic_true_homography()
    markers = {
        "bat_L": _project(H_true, -1.32, 1.22),
        "bat_R": _project(H_true, +1.32, 1.22),
        "bowl_L": _project(H_true, -1.32, 18.90),
        "bowl_R": _project(H_true, +1.32, 18.90),
        "bat_stump": _project(H_true, 0.0, 0.0),
        "bowl_stump": _project(H_true, 0.0, 20.12),
    }

    samples = [
        (0.0, 1.50, "YORKER"),
        (0.2, 4.25, "FULL"),
        (-0.1, 6.80, "GOOD"),
        (0.0, 10.50, "SHORT"),
    ]

    # 1. Laws mode: returns exact zone and length_m within 2 cm (0.02 m)
    zone_scale.apply("laws")
    laws_markers = zone_scale.markers_for_zones(markers, "laws")
    laws_results = []
    for wx, wy, expected_zone in samples:
        bpx = _project(H_true, wx, wy)
        zone, length_m = zones_classify.classify_bounce(laws_markers, bpx)
        assert zone == expected_zone
        assert length_m is not None
        assert abs(length_m - wy) <= 0.02
        laws_results.append((zone, length_m))

    # Beyond bowler popping crease (18.95 m >= 18.90 m) is outside SHORT in laws mode
    beyond_px = _project(H_true, 0.0, 18.95)
    z_out, _ = zones_classify.classify_bounce(laws_markers, beyond_px)
    assert z_out is None

    # 2. Legacy mode: stretches (wy - 1.22) by ~19.68 / 17.68 (~1.113x)
    zone_scale.apply("legacy")
    legacy_markers = zone_scale.markers_for_zones(markers, "legacy")
    for (wx, wy, _), (_, laws_len) in zip(samples, laws_results):
        bpx = _project(H_true, wx, wy)
        leg_zone, leg_len = zones_classify.classify_bounce(legacy_markers, bpx)
        assert leg_zone is not None
        assert leg_len is not None
        # For wy > 1.22, legacy length_m is systematically larger than true wy
        assert leg_len > laws_len
