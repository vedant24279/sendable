import pytest
from pydantic import ValidationError

from app.schema import (
    Label,
    Point,
    ImpactPoint,
    get_consistency_warnings,
    validate_label,
)


def base_valid_dict() -> dict:
    return {
        "schema_version": 1,
        "clip_id": "test_clip_1",
        "split": "dev",
        "annotator": "alice",
        "mode": "assisted",
        "status": "final",
        "created_at": "2026-11-05T10:00:00Z",
        "updated_at": "2026-11-05T10:00:00Z",
        "ball_colour": "white",
        "batter_hand": "right",
        "bowler_type": "pace",
        "lighting": "bright",
        "release": {"frame": 2, "x": 100.0, "y": 200.0},
        "bounce": {"frame": 12, "x": 150.0, "y": 250.0},
        "impact": {"type": "bat", "frame": 18, "x": 180.0, "y": 220.0},
        "last_visible_frame": 25,
        "lbw": None,
        "calibration_gt": {
            "points": {
                "bat_L": [150.0, 100.0],
                "bat_R": [350.0, 100.0],
                "bowl_L": [100.0, 400.0],
                "bowl_R": [400.0, 400.0],
                "bat_stump": [250.0, 86.5],
                "bowl_stump": [250.0, 432.2],
            },
            "source": "system_verified",
            "residual_px": 0.0,
            "updated_at": "2026-11-05T10:00:00Z",
        },
        "flags": ["bad_calibration"],
        "notes": "Good delivery",
    }


def test_schema_valid_final():
    data = base_valid_dict()
    label = validate_label(data, frame_count=30, width=500, height=500)
    assert label.status == "final"
    assert label.schema_version == 1
    assert label.release.frame == 2
    assert label.bounce.frame == 12
    assert label.impact.frame == 18
    assert label.last_visible_frame == 25


def test_schema_valid_draft_partial():
    data = {
        "schema_version": 1,
        "clip_id": "test_clip_draft",
        "annotator": "bob",
        "mode": "blind",
        "status": "draft",
        "created_at": "2026-11-05T10:00:00Z",
        "updated_at": "2026-11-05T10:00:00Z",
    }
    label = validate_label(data)
    assert label.status == "draft"
    assert label.release is None
    assert label.bounce is None
    assert label.impact is None
    assert label.ball_colour is None


def test_schema_version_must_be_1():
    data = base_valid_dict()
    data["schema_version"] = 2
    with pytest.raises((ValidationError, ValueError)):
        validate_label(data)


def test_schema_release_before_bounce_rule():
    data = base_valid_dict()
    data["release"] = {"frame": 15, "x": 100.0, "y": 200.0}
    data["bounce"] = {"frame": 10, "x": 150.0, "y": 250.0}
    with pytest.raises((ValidationError, ValueError), match="strictly less than bounce.frame"):
        validate_label(data)

    # Equal frame numbers also invalid
    data["release"] = {"frame": 12, "x": 100.0, "y": 200.0}
    data["bounce"] = {"frame": 12, "x": 150.0, "y": 250.0}
    with pytest.raises((ValidationError, ValueError), match="strictly less than bounce.frame"):
        validate_label(data)


def test_schema_bounce_before_or_equal_impact():
    data = base_valid_dict()
    data["bounce"] = {"frame": 20, "x": 150.0, "y": 250.0}
    data["impact"] = {"type": "bat", "frame": 18, "x": 180.0, "y": 220.0}
    with pytest.raises((ValidationError, ValueError), match="bounce.frame .* <= impact.frame"):
        validate_label(data)

    # Equal is allowed
    data["impact"] = {"type": "bat", "frame": 20, "x": 180.0, "y": 220.0}
    label = validate_label(data)
    assert label.bounce.frame == label.impact.frame


def test_schema_impact_before_or_equal_last_visible():
    data = base_valid_dict()
    data["impact"] = {"type": "bat", "frame": 28, "x": 180.0, "y": 220.0}
    data["last_visible_frame"] = 25
    with pytest.raises((ValidationError, ValueError), match="impact.frame .* <= last_visible_frame"):
        validate_label(data)


def test_schema_impact_type_none_requires_null_coords():
    data = base_valid_dict()
    data["impact"] = {"type": "none", "frame": None, "x": None, "y": None}
    label = validate_label(data)
    assert label.impact.type == "none"
    assert label.impact.frame is None

    # Invalid: frame given when type is none
    data["impact"] = {"type": "none", "frame": 18, "x": None, "y": None}
    with pytest.raises((ValidationError, ValueError)):
        validate_label(data)

    # Invalid: x, y given when type is none
    data["impact"] = {"type": "none", "frame": None, "x": 100.0, "y": 200.0}
    with pytest.raises((ValidationError, ValueError)):
        validate_label(data)


def test_schema_lbw_only_allowed_with_pad():
    data = base_valid_dict()
    data["impact"] = {"type": "pad", "frame": 18, "x": 180.0, "y": 220.0}
    data["lbw"] = "out"
    label = validate_label(data)
    assert label.lbw == "out"

    # All valid lbw decisions
    for dec in [
        "out",
        "not_out_pitched_leg",
        "not_out_impact_outside",
        "not_out_missing",
        "umpires_call",
        "not_out_unspecified",
        "not_available",
    ]:
        data["lbw"] = dec
        assert validate_label(data).lbw == dec

    # Invalid: impact is bat but lbw is set
    data["impact"]["type"] = "bat"
    with pytest.raises((ValidationError, ValueError), match="lbw may be non-null only when impact.type == 'pad'"):
        validate_label(data)

    # Invalid: impact is stumps but lbw is set
    data["impact"]["type"] = "stumps"
    with pytest.raises((ValidationError, ValueError), match="lbw may be non-null only when impact.type == 'pad'"):
        validate_label(data)

    # Invalid: impact is none but lbw is set
    data["impact"] = {"type": "none", "frame": None, "x": None, "y": None}
    with pytest.raises((ValidationError, ValueError), match="lbw may be non-null only when impact.type == 'pad'"):
        validate_label(data)


def test_schema_final_status_mandatory_fields():
    # Missing release
    data = base_valid_dict()
    data["release"] = None
    with pytest.raises((ValidationError, ValueError), match="release is required"):
        validate_label(data)

    # Missing bounce
    data = base_valid_dict()
    data["bounce"] = None
    with pytest.raises((ValidationError, ValueError), match="bounce is required"):
        validate_label(data)

    # Missing impact
    data = base_valid_dict()
    data["impact"] = None
    with pytest.raises((ValidationError, ValueError), match="impact is required"):
        validate_label(data)

    # Missing last_visible_frame
    data = base_valid_dict()
    data["last_visible_frame"] = None
    with pytest.raises((ValidationError, ValueError), match="last_visible_frame is required"):
        validate_label(data)

    # Missing ball_colour
    data = base_valid_dict()
    data["ball_colour"] = None
    with pytest.raises((ValidationError, ValueError), match="ball_colour is required"):
        validate_label(data)

    # Missing batter_hand
    data = base_valid_dict()
    data["batter_hand"] = None
    with pytest.raises((ValidationError, ValueError), match="batter_hand is required"):
        validate_label(data)

    # Missing annotator
    data = base_valid_dict()
    data["annotator"] = ""
    with pytest.raises((ValidationError, ValueError), match="annotator is required"):
        validate_label(data)

    # Missing calibration_gt
    data = base_valid_dict()
    data["calibration_gt"] = None
    with pytest.raises((ValidationError, ValueError), match="calibration_gt is required"):
        validate_label(data)

    # split=None is ALLOWED for status 'final'
    data = base_valid_dict()
    data["split"] = None
    valid_no_split = validate_label(data)
    assert valid_no_split.status == "final"
    assert valid_no_split.split is None

    # Missing bowler_type
    data = base_valid_dict()
    data["bowler_type"] = None
    with pytest.raises((ValidationError, ValueError), match="bowler_type is required"):
        validate_label(data)

    # Missing lighting
    data = base_valid_dict()
    data["lighting"] = None
    with pytest.raises((ValidationError, ValueError), match="lighting is required"):
        validate_label(data)

    # Missing lbw when impact.type == 'pad'
    data = base_valid_dict()
    data["impact"]["type"] = "pad"
    data["lbw"] = None
    with pytest.raises((ValidationError, ValueError), match="lbw is required for status 'final' when impact.type is 'pad'"):
        validate_label(data)

    # Valid when lbw is supplied for pad impact
    data["lbw"] = "out"
    valid_pad = validate_label(data)
    assert valid_pad.lbw == "out"


def test_schema_calibration_rules():
    # Residual > CALIB_ERROR_PX (12.0) without bad_calibration flag raises error
    data = base_valid_dict()
    data["calibration_gt"]["residual_px"] = 14.5
    data["flags"] = []
    with pytest.raises((ValidationError, ValueError), match="exceeds CALIB_ERROR_PX"):
        validate_label(data)

    # Residual > CALIB_ERROR_PX (12.0) with bad_calibration flag is valid
    data["flags"] = ["bad_calibration"]
    valid_flagged = validate_label(data)
    assert valid_flagged.calibration_gt.residual_px == 14.5
    assert "bad_calibration" in valid_flagged.flags

    # Non-convex quad
    data = base_valid_dict()
    data["calibration_gt"]["points"]["bowl_L"] = [450.0, 400.0]
    data["calibration_gt"]["points"]["bowl_R"] = [50.0, 400.0]  # inverted
    with pytest.raises((ValidationError, ValueError), match="strictly convex"):
        validate_label(data, width=500, height=500)

    # Area < 2% of frame area (500*500*0.02 = 5000 px^2)
    data = base_valid_dict()
    data["calibration_gt"]["points"] = {
        "bat_L": [10.0, 10.0],
        "bat_R": [20.0, 10.0],
        "bowl_R": [20.0, 20.0],
        "bowl_L": [10.0, 20.0],
        "bat_stump": [15.0, 10.0],
        "bowl_stump": [15.0, 20.0],
    }
    with pytest.raises((ValidationError, ValueError), match="must be > 2%"):
        validate_label(data, width=500, height=500)

    # Horizontal order violation bat_L.x >= bat_R.x
    data = base_valid_dict()
    data["calibration_gt"]["points"]["bat_L"] = [360.0, 100.0]
    with pytest.raises((ValidationError, ValueError), match="strictly less than"):
        validate_label(data, width=500, height=500)


def test_old_label_compatibility_without_calibration():
    # Existing label without calibration_gt loads as draft without issues
    old_label = {
        "schema_version": 1,
        "clip_id": "legacy_clip_01",
        "split": "dev",
        "annotator": "bob",
        "mode": "blind",
        "status": "draft",
        "created_at": "2026-11-01T10:00:00Z",
        "updated_at": "2026-11-01T10:00:00Z",
        "notes": "Legacy draft",
    }
    label = validate_label(old_label)
    assert label.status == "draft"
    assert label.calibration_gt is None


def test_schema_bounds_validation():
    data = base_valid_dict()
    # Frame out of bounds [0, 29]
    data["last_visible_frame"] = 30
    with pytest.raises((ValidationError, ValueError), match="out of bounds"):
        validate_label(data, frame_count=30, width=500, height=500)

    # Negative frame
    data = base_valid_dict()
    data["release"]["frame"] = -1
    with pytest.raises((ValidationError, ValueError), match="out of bounds"):
        validate_label(data, frame_count=30, width=500, height=500)

    # X out of bounds
    data = base_valid_dict()
    data["release"]["x"] = 501.0
    with pytest.raises((ValidationError, ValueError), match="x coordinate .* out of bounds"):
        validate_label(data, frame_count=30, width=500, height=500)

    # Y out of bounds
    data = base_valid_dict()
    data["bounce"]["y"] = -0.5
    with pytest.raises((ValidationError, ValueError), match="y coordinate .* out of bounds"):
        validate_label(data, frame_count=30, width=500, height=500)


def test_schema_stump_confirmed_defaults_and_null_residual():
    data = base_valid_dict()
    # Remove stump_confirmed and set residual_px to None (unconfirmed stumps)
    del data["flags"]  # no bad_calibration flag
    data["calibration_gt"]["residual_px"] = None
    if "stump_confirmed" in data["calibration_gt"]:
        del data["calibration_gt"]["stump_confirmed"]

    label = validate_label(data, frame_count=30, width=500, height=500)
    assert label.status == "final"
    assert label.calibration_gt.stump_confirmed.bat_stump is False
    assert label.calibration_gt.stump_confirmed.bowl_stump is False
    assert label.calibration_gt.residual_px is None


def test_schema_stump_confirmed_partial_and_both():
    data = base_valid_dict()
    data["calibration_gt"]["stump_confirmed"] = {"bat_stump": True, "bowl_stump": False}
    data["calibration_gt"]["residual_px"] = 2.5
    label = validate_label(data, frame_count=30, width=500, height=500)
    assert label.calibration_gt.stump_confirmed.bat_stump is True
    assert label.calibration_gt.stump_confirmed.bowl_stump is False
    assert label.calibration_gt.residual_px == 2.5


def test_schema_reference_decision_and_source_group():
    data = base_valid_dict()
    data["reference_decision"] = "out"
    data["source_group"] = "ind_vs_aus_2025"
    label = validate_label(data)
    assert label.reference_decision == "out"
    assert label.source_group == "ind_vs_aus_2025"

    data["reference_decision"] = "invalid_val"
    with pytest.raises(ValidationError):
        validate_label(data)


def test_consistency_warnings():
    # 1. reference_decision "out" + impact.type "pad" + lbw not in ("out", "not_available")
    data = base_valid_dict()
    data["reference_decision"] = "out"
    data["impact"] = {"type": "pad", "frame": 18, "x": 180.0, "y": 220.0}
    data["lbw"] = "not_out_missing"
    label = validate_label(data)
    warnings = get_consistency_warnings(label)
    assert len(warnings) == 1
    assert warnings[0]["severity"] == "warning"
    assert warnings[0]["message"] == "File name says out but lbw is not out"

    # Allowed when lbw is "out" or "not_available"
    for ok_lbw in ("out", "not_available"):
        data["lbw"] = ok_lbw
        assert get_consistency_warnings(validate_label(data)) == []

    # 2. reference_decision "not_out" + lbw "out"
    data = base_valid_dict()
    data["reference_decision"] = "not_out"
    data["impact"] = {"type": "pad", "frame": 18, "x": 180.0, "y": 220.0}
    data["lbw"] = "out"
    warnings = get_consistency_warnings(validate_label(data))
    assert len(warnings) == 1
    assert warnings[0]["message"] == "File name says not out but lbw is out"

    # 3. reference_decision "out" + impact.type "none"
    data = base_valid_dict()
    data["reference_decision"] = "out"
    data["impact"] = {"type": "none", "frame": None, "x": None, "y": None}
    data["lbw"] = None
    warnings = get_consistency_warnings(validate_label(data))
    assert len(warnings) == 1
    assert warnings[0]["message"] == "Out delivery with no contact: check the label"

