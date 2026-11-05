import json
from pathlib import Path
import cv2
import numpy as np
import pytest

from make_contact_sheet import generate_contact_sheets


def test_generate_contact_sheet_synthetic(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    job_dir = repo_dir / "backend" / "_tracker_work" / "jobs" / "synthetic_01"
    job_dir.mkdir(parents=True)

    # 1. Create synthetic video with 'mp4v'
    video_path = job_dir / "input.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, 30.0, (64, 64))
    assert writer.isOpened(), "Could not open VideoWriter with mp4v codec"

    for i in range(10):
        frame = np.full((64, 64, 3), fill_value=i * 20, dtype=np.uint8)
        # Draw a small marker to simulate a ball
        cv2.circle(frame, (32, 32), 4, (0, 0, 255), -1)
        writer.write(frame)
    writer.release()

    # 2. Create results.json with bounce event
    results_path = job_dir / "results.json"
    results_data = {
        "job_id": "synthetic_01",
        "ball_type": "white",
        "video": {
            "fps": 30.0,
            "frame_count": 10,
            "width": 64,
            "height": 64,
        },
        "events": {
            "release": {"frame": 1, "x": 10, "y": 20},
            "bounce": {"frame": 4, "x": 32, "y": 32},
            "impact": None,
        },
    }
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results_data, f)

    # 3. Create manifest.json with this clip and a clip with no bounce
    manifest_path = repo_dir / "tools" / "annotator" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_data = [
        {
            "clip_id": "synthetic_01",
            "path": "backend/_tracker_work/jobs/synthetic_01/input.mp4",
            "fps": 30.0,
            "frame_count": 10,
            "width": 64,
            "height": 64,
            "ball_type": "white",
            "has_results": True,
            "has_calibration": False,
            "label_status": "none",
            "split": None,
            "frame_count_mismatch": False,
            "has_error": False,
        },
        {
            "clip_id": "synthetic_02_nobounce",
            "path": "backend/_tracker_work/jobs/synthetic_01/input.mp4",
            "fps": 30.0,
            "frame_count": 10,
            "width": 64,
            "height": 64,
            "ball_type": None,
            "has_results": False,
            "has_calibration": False,
            "label_status": "none",
            "split": None,
            "frame_count_mismatch": False,
            "has_error": False,
        },
    ]
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f)

    output_dir = repo_dir / "tools" / "annotator" / "contact_sheets"

    # 4. Generate contact sheet
    num_sheets, elapsed = generate_contact_sheets(manifest_path, output_dir, repo_root=repo_dir)

    assert num_sheets == 1
    assert elapsed >= 0

    sheet_01 = output_dir / "sheet_01.jpg"
    assert sheet_01.is_file()

    img = cv2.imread(str(sheet_01))
    assert img is not None, "Failed to read generated contact sheet image"
    h, w, c = img.shape
    assert (w, h) == (1800, 1200), f"Expected 1800x1200, got {w}x{h}"
    assert c == 3
