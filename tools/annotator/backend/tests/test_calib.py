import json
import math
from pathlib import Path
import pytest
import numpy as np

from app.calib import (
    fit_homography,
    pixel_to_world,
    world_to_pixel,
    pitch_grid_segments,
    classify_source,
    validate_calibration_geometry,
)
from app.calib_constants import CALIB_WARN_PX, WORLD_CALIB_POINTS


@pytest.fixture
def golden_fixture():
    fixture_path = (
        Path(__file__).resolve().parent.parent.parent / "fixtures" / "calibration_golden.json"
    )
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_golden_fixture_parity(golden_fixture):
    pts = golden_fixture["points"]
    res = fit_homography(pts)

    # 1. Residual parity
    assert abs(res.residual_px - golden_fixture["expected_residual_px"]) < 1e-3

    # 2. Homography matrix parity
    exp_H = np.array(golden_fixture["expected_H"], dtype=np.float64)
    exp_H_inv = np.array(golden_fixture["expected_H_inv"], dtype=np.float64)

    assert np.max(np.abs(res.H - exp_H)) < 1e-6
    assert np.max(np.abs(res.H_inv - exp_H_inv)) < 1e-6

    # 3. Pixel -> World parity
    for item in golden_fixture["test_pixels"]:
        px, py = item["pixel"]
        wX, wZ = pixel_to_world(res.H, px, py)
        assert abs(wX - item["expected_world"][0]) < 1e-6
        assert abs(wZ - item["expected_world"][1]) < 1e-6

    # 4. World -> Pixel parity
    for item in golden_fixture["test_world"]:
        wX, wZ = item["world"]
        px, py = world_to_pixel(res.H, wX, wZ)
        assert abs(px - item["expected_pixel"][0]) < 1e-3
        assert abs(py - item["expected_pixel"][1]) < 1e-3


def test_nudge_bat_stump_by_6px():
    # Perfectly aligned calibration
    pts = {
        "bat_L": [778.0, 434.0],
        "bat_R": [1083.0, 430.0],
        "bowl_L": [739.0, 764.0],
        "bowl_R": [1115.0, 768.0],
        "bat_stump": [0.0, 0.0],
        "bowl_stump": [0.0, 0.0],
    }
    initial = fit_homography(pts)
    perf_bat = world_to_pixel(initial.H, 0.0, 0.0)
    perf_bowl = world_to_pixel(initial.H, 0.0, 20.12)

    pts["bat_stump"] = [perf_bat[0], perf_bat[1]]
    pts["bowl_stump"] = [perf_bowl[0], perf_bowl[1]]

    zero_res = fit_homography(pts)
    assert zero_res.residual_px < 1e-6

    # Nudge bat_stump by 6px
    pts["bat_stump"] = [perf_bat[0] + 6.0, perf_bat[1]]
    shifted = fit_homography(pts)

    assert shifted.residual_px > CALIB_WARN_PX
    assert abs(shifted.residual_px - math.sqrt(18.0)) < 1e-3


def test_classify_source():
    pts = {
        "bat_L": [778.0, 434.0],
        "bat_R": [1083.0, 430.0],
        "bowl_L": [739.0, 764.0],
        "bowl_R": [1115.0, 768.0],
        "bat_stump": [936.0, 426.0],
        "bowl_stump": [922.0, 784.0],
    }

    assert classify_source(pts, None) == "manual"
    assert classify_source(pts, {}) == "manual"

    # Exact system points
    sys_ver = {k: list(v) for k, v in pts.items()}
    assert classify_source(pts, sys_ver) == "system_verified"

    # Within 0.05 px
    sys_ver["bat_L"][0] += 0.03
    assert classify_source(pts, sys_ver) == "system_verified"

    # Exceeding 0.05 px
    sys_adj = {k: list(v) for k, v in pts.items()}
    sys_adj["bat_L"][0] += 0.06
    assert classify_source(pts, sys_adj) == "system_adjusted"


def test_validate_calibration_geometry():
    valid = {
        "bat_L": [778.0, 434.0],
        "bat_R": [1083.0, 430.0],
        "bowl_L": [739.0, 764.0],
        "bowl_R": [1115.0, 768.0],
        "bat_stump": [936.0, 426.0],
        "bowl_stump": [922.0, 784.0],
    }

    assert validate_calibration_geometry(valid, 1920, 1080) == []

    # Missing point
    missing = dict(valid)
    del missing["bowl_stump"]
    assert len(validate_calibration_geometry(missing, 1920, 1080)) > 0

    # Out of bounds
    oob = dict(valid)
    oob["bat_L"] = [-1.0, 434.0]
    assert any("out of bounds" in e for e in validate_calibration_geometry(oob, 1920, 1080))

    # Horizontal order bat_L.x >= bat_R.x
    bad_order = dict(valid)
    bad_order["bat_L"] = [1100.0, 434.0]
    assert any("strictly less than" in e for e in validate_calibration_geometry(bad_order, 1920, 1080))

    # Stump outside crease range
    bad_stump = dict(valid)
    bad_stump["bat_stump"] = [700.0, 426.0]
    assert any("must be between" in e for e in validate_calibration_geometry(bad_stump, 1920, 1080))

    # Non-convex quad
    non_convex = dict(valid)
    non_convex["bowl_L"] = [1150.0, 764.0]
    non_convex["bowl_R"] = [720.0, 768.0]
    assert any("convex" in e for e in validate_calibration_geometry(non_convex, 1920, 1080))

    # Area too small (< 2% frame area)
    tiny = {
        "bat_L": [100.0, 100.0],
        "bat_R": [110.0, 100.0],
        "bowl_R": [110.0, 110.0],
        "bowl_L": [100.0, 110.0],
        "bat_stump": [105.0, 100.0],
        "bowl_stump": [105.0, 110.0],
    }
    assert any("must be > 2%" in e for e in validate_calibration_geometry(tiny, 1920, 1080))


def test_pitch_grid_segments(golden_fixture):
    pts = golden_fixture["points"]
    res = fit_homography(pts)
    segs = pitch_grid_segments(res.H, spacing_m=1.0)

    assert len(segs) > 20
    for p1, p2 in segs:
        assert len(p1) == 2 and len(p2) == 2
        assert all(math.isfinite(c) for c in p1)
        assert all(math.isfinite(c) for c in p2)
