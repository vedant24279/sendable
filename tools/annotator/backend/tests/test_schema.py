import pytest
from pydantic import ValidationError

from app.schema import Label, Point, ImpactPoint, validate_label


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
    for dec in ["out", "not_out_pitched_leg", "not_out_impact_outside", "not_out_missing", "umpires_call"]:
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
