import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import run_clip


VALID_CALIB = {
    "bat_L": [778, 434],
    "bat_R": [1083, 430],
    "bowl_L": [739, 764],
    "bowl_R": [1115, 768],
    "bat_stump": [936, 426],
    "bowl_stump": [922, 784],
}


def test_run_clip_cli_invokes_process_video_with_expected_args(tmp_path: Path):
    fake_video = tmp_path / "input.mp4"
    fake_video.write_bytes(b"fake video bytes")
    out_dir = tmp_path / "out_dir"

    mock_process = MagicMock(return_value={"schema_version": 1, "status": "ok"})

    with patch("run_clip._load_process_video", return_value=mock_process) as mock_loader:
        rc = run_clip.main(
            [
                "--video",
                str(fake_video),
                "--calibration",
                json.dumps(VALID_CALIB),
                "--ball-type",
                "red",
                "--out",
                str(out_dir),
            ]
        )

    assert rc == 0
    assert out_dir.is_dir()
    mock_loader.assert_called_once()
    mock_process.assert_called_once()

    call_kwargs = mock_process.call_args.kwargs
    assert call_kwargs["video_path"] == fake_video.resolve()
    assert call_kwargs["output_dir"] == out_dir.resolve()
    assert call_kwargs["calibration"] == VALID_CALIB
    assert call_kwargs["weights_path"].name == "redsepv2.onnx"
    assert os.environ.get("TRACKER_BALL_TYPE") == "red"
    assert Path(os.environ.get("TRACKER_LEGACY_DIR", "")).name == "Zone-div_V8m"


@pytest.mark.parametrize(
    "ball_type,expected_weights",
    [
        ("white", "whiteball.onnx"),
        ("red", "redsepv2.onnx"),
        ("pink", "pinkoct.onnx"),
    ],
)
def test_resolve_pipeline_config_ball_types(ball_type: str, expected_weights: str):
    cfg = run_clip.resolve_pipeline_config(ball_type)
    assert cfg["weights_path"].name == expected_weights
    assert cfg["legacy_dir"].name == "Zone-div_V8m"


def test_parse_calibration_arg_rejects_missing_points():
    incomplete = {"bat_L": [100, 200], "bat_R": [300, 200]}
    with pytest.raises(ValueError, match="missing required point"):
        run_clip.parse_calibration_arg(json.dumps(incomplete))
