import pytest
from filename_meta import parse_filename_meta


@pytest.mark.parametrize(
    "filename, expected_decision, expected_colour",
    [
        # Required test cases from specification
        ("ind_vs_aus_lbw_out.mp4", "out", None),
        ("Over 12.3 NOT OUT.mov", "not_out", None),
        ("clip-17-notout.mp4", "not_out", None),
        ("outstanding_catch.mp4", None, None),
        ("bowled_out_red.mp4", "out", "red"),
        ("about.mp4", None, None),
        # Additional separator, casing, conflict, and ball colour cases
        ("Clips1_out.mp4", "out", None),
        ("match.2.not-out.WHITE.mkv", "not_out", "white"),
        ("DayNight_PINK_not_out.webm", "not_out", "pink"),
        ("not_out_or_out.mp4", None, None),
        ("out_vs_notout.mov", None, None),
        ("red_lbw_01.mp4", None, "red"),
        ("redball_shout_out.avi", "out", None),
        ("pink.ball-delivery_04.m4v", None, "pink"),
    ],
)
def test_parse_filename_meta(filename, expected_decision, expected_colour):
    res = parse_filename_meta(filename)
    assert res["reference_decision"] == expected_decision
    assert res["ball_colour_hint"] == expected_colour
    assert res["source_group"] is None
