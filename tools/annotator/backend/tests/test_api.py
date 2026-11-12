import json
import os
import shutil
import tempfile
from pathlib import Path
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app, load_manifest
import app.main as main_mod
from build_manifest import inspect_video, build_manifest_data


@pytest.fixture(scope="function")
def test_env(tmp_path, monkeypatch):
    """
    Creates an isolated test environment with:
    - a synthetic 10-frame video (64x64, 30fps) written with mp4v
    - results.json with events, trajectory, and calibration
    - isolated manifest.json, .cache, and eval/labels
    """
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    jobs_dir = repo_dir / "backend" / "_tracker_work" / "jobs"
    test_job = jobs_dir / "test_clip_01"
    test_job.mkdir(parents=True)

    # 1. Create synthetic 10-frame video (64x64) with 'mp4v'
    video_path = test_job / "input.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, 30.0, (64, 64))
    assert writer.isOpened(), "Could not open VideoWriter with mp4v codec"

    for i in range(10):
        frame = np.full((64, 64, 3), fill_value=i * 25, dtype=np.uint8)
        writer.write(frame)
    writer.release()

    # 2. Create results.json
    results_data = {
        "job_id": "test_clip_01",
        "ball_type": "red",
        "video": {
            "fps": 30.0,
            "frame_count": 10,
            "width": 64,
            "height": 64,
        },
        "events": {
            "release": {"frame": 1, "x": 10, "y": 20, "timestamp_sec": 0.033},
            "bounce": {"frame": 5, "x": 30, "y": 40, "timestamp_sec": 0.167, "zone": "GOOD"},
            "impact": None,
            "deviation": {"frame": 7, "x": 45, "y": 35, "timestamp_sec": 0.233},
        },
        "trajectory": [
            {"frame": 1, "x": 10.0, "y": 20.0, "conf": 0.9, "interpolated": False},
            {"frame": 2, "x": 15.0, "y": 25.0, "conf": 0.85, "interpolated": True},
            {"frame": 5, "x": 30.0, "y": 40.0, "conf": 0.8, "interpolated": False},
        ],
        "calibration": {
            "bat_L": [10, 50],
            "bat_R": [50, 50],
            "bat_stump": [30, 50],
            "bowl_L": [15, 10],
            "bowl_R": [45, 10],
            "bowl_stump": [30, 10],
        },
    }
    with open(test_job / "results.json", "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2)

    # 3. Directories for manifest, cache, labels
    tools_annotator = repo_dir / "tools" / "annotator"
    tools_annotator.mkdir(parents=True)
    manifest_file = tools_annotator / "manifest.json"
    cache_dir = tools_annotator / ".cache"
    labels_dir = repo_dir / "eval" / "labels"
    audit_file = labels_dir / "_audit.jsonl"

    # Set LABELS_DIR to isolated labels_dir
    monkeypatch.setenv("LABELS_DIR", str(labels_dir))

    # Build manifest
    manifest_data = build_manifest_data(jobs_dir, repo_root=repo_dir, eval_labels_dir=labels_dir)
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    # Patch main module paths
    orig_repo_root = main_mod.REPO_ROOT
    orig_manifest = main_mod.MANIFEST_PATH
    orig_cache = main_mod.CACHE_DIR

    main_mod.REPO_ROOT = repo_dir
    main_mod.MANIFEST_PATH = manifest_file
    main_mod.CACHE_DIR = cache_dir

    yield {
        "repo_dir": repo_dir,
        "jobs_dir": jobs_dir,
        "clip_id": "test_clip_01",
        "manifest_file": manifest_file,
        "labels_dir": labels_dir,
        "audit_file": audit_file,
        "cache_dir": cache_dir,
    }

    # Restore
    main_mod.REPO_ROOT = orig_repo_root
    main_mod.MANIFEST_PATH = orig_manifest
    main_mod.CACHE_DIR = orig_cache


def test_api_health():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_api_clips_list(test_env):
    client = TestClient(app)
    resp = client.get("/api/clips")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    clip = data[0]
    assert clip["clip_id"] == "test_clip_01"
    assert clip["frame_count"] == 10
    assert clip["width"] == 64
    assert clip["height"] == 64
    assert clip["fps"] == 30.0
    assert clip["ball_type"] == "red"
    assert clip["has_results"] is True
    assert clip["has_calibration"] is True
    assert clip["label_status"] == "none"
    assert clip["frame_count_mismatch"] is False


def test_api_frame_decoding_and_cache(test_env):
    client = TestClient(app)
    clip_id = test_env["clip_id"]

    # Frame 0 request decodes sequentially and caches all 10 frames
    resp = client.get(f"/api/clips/{clip_id}/frame/0")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert "public, max-age=31536000" in resp.headers.get("cache-control", "")

    # Verify frame image is decodable and matches synthetic 64x64 size
    img = cv2.imdecode(np.frombuffer(resp.content, np.uint8), cv2.IMREAD_COLOR)
    assert img is not None
    assert img.shape == (64, 64, 3)

    # Cache should have exactly 10 frame files (0.jpg..9.jpg)
    cache_dir = test_env["cache_dir"] / clip_id
    files = list(cache_dir.iterdir())
    assert len(files) == 10
    for i in range(10):
        assert (cache_dir / f"{i}.jpg").is_file()

    # Frame 9 (last frame) should succeed
    resp_last = client.get(f"/api/clips/{clip_id}/frame/9")
    assert resp_last.status_code == 200

    # Frame 10 (out of bounds) should return 404
    resp_oob = client.get(f"/api/clips/{clip_id}/frame/10")
    assert resp_oob.status_code == 404

    # Negative frame should return 404
    resp_neg = client.get(f"/api/clips/{clip_id}/frame/-1")
    assert resp_neg.status_code == 404


def test_api_prefill(test_env):
    client = TestClient(app)
    clip_id = test_env["clip_id"]

    resp = client.get(f"/api/clips/{clip_id}/prefill")
    assert resp.status_code == 200
    data = resp.json()

    assert data["clip_id"] == clip_id
    events = data["events"]
    assert events["release"]["frame"] == 1
    assert events["release"]["x"] == 10.0
    assert events["release"]["y"] == 20.0
    assert events["bounce"]["frame"] == 5
    assert events["bounce"]["zone"] == "GOOD"
    assert events["impact"] is None
    assert events["deviation"]["frame"] == 7

    # Trajectory with interpolated flag
    traj = data["trajectory"]
    assert len(traj) == 3
    assert traj[0]["interpolated"] is False
    assert traj[1]["interpolated"] is True

    # Calibration normalized list
    calib = data["calibration"]
    assert isinstance(calib, list)
    calib_names = {pt["name"] for pt in calib}
    assert "bat_L" in calib_names
    assert "bat_stump" in calib_names
    for pt in calib:
        assert isinstance(pt["x"], float)
        assert isinstance(pt["y"], float)


def test_api_label_round_trip_and_atomic_write(test_env):
    client = TestClient(app)
    clip_id = test_env["clip_id"]

    # Before saving, GET /label returns 404
    resp_initial = client.get(f"/api/clips/{clip_id}/label")
    assert resp_initial.status_code == 404

    # Invalid PUT: release.frame >= bounce.frame -> 422
    invalid_order_payload = {
        "schema_version": 1,
        "clip_id": clip_id,
        "annotator": "tester",
        "mode": "assisted",
        "status": "draft",
        "created_at": "2026-11-05T10:00:00Z",
        "updated_at": "2026-11-05T10:00:00Z",
        "release": {"frame": 6, "x": 10.0, "y": 20.0},
        "bounce": {"frame": 4, "x": 30.0, "y": 40.0},
    }
    resp_invalid = client.put(f"/api/clips/{clip_id}/label", json=invalid_order_payload)
    assert resp_invalid.status_code == 422

    # Invalid PUT: frame out of bounds (10 >= 10 frames) -> 422
    oob_payload = {
        "schema_version": 1,
        "clip_id": clip_id,
        "annotator": "tester",
        "mode": "assisted",
        "status": "draft",
        "created_at": "2026-11-05T10:00:00Z",
        "updated_at": "2026-11-05T10:00:00Z",
        "release": {"frame": 10, "x": 10.0, "y": 20.0},
        "bounce": {"frame": 12, "x": 30.0, "y": 40.0},
    }
    resp_oob = client.put(f"/api/clips/{clip_id}/label", json=oob_payload)
    assert resp_oob.status_code == 422

    # Valid PUT
    valid_payload = {
        "schema_version": 1,
        "clip_id": clip_id,
        "split": "dev",
        "annotator": "tester",
        "mode": "assisted",
        "status": "final",
        "created_at": "2026-11-05T10:00:00Z",
        "updated_at": "2026-11-05T10:00:00Z",
        "ball_colour": "red",
        "batter_hand": "right",
        "bowler_type": "pace",
        "lighting": "bright",
        "release": {"frame": 1, "x": 10.0, "y": 20.0},
        "bounce": {"frame": 4, "x": 25.0, "y": 30.0},
        "impact": {"type": "bat", "frame": 6, "x": 35.0, "y": 32.0},
        "last_visible_frame": 8,
        "lbw": None,
        "calibration_gt": {
            "points": {
                "bat_L": [15.0, 15.0],
                "bat_R": [45.0, 15.0],
                "bowl_L": [10.0, 50.0],
                "bowl_R": [50.0, 50.0],
                "bat_stump": [30.0, 13.2],
                "bowl_stump": [30.0, 53.3],
            },
            "source": "system_verified",
            "residual_px": 0.0,
            "updated_at": "2026-11-05T10:00:00Z",
        },
        "flags": ["camera_moved"],
        "notes": "Verified clean edge",
    }
    resp_put = client.put(f"/api/clips/{clip_id}/label", json=valid_payload)
    assert resp_put.status_code == 200
    assert resp_put.json()["status"] == "ok"

    # Verify atomic file creation
    label_file = test_env["labels_dir"] / f"{clip_id}.json"
    assert label_file.is_file()
    with open(label_file, "r", encoding="utf-8") as f:
        saved_disk = json.load(f)
    assert saved_disk["status"] == "final"
    assert saved_disk["annotator"] == "tester"

    # Verify audit log entry
    audit_file = test_env["audit_file"]
    assert audit_file.is_file()
    with open(audit_file, "r", encoding="utf-8") as af:
        lines = [json.loads(line) for line in af if line.strip()]
    assert len(lines) == 1
    assert lines[0]["clip_id"] == clip_id
    assert lines[0]["annotator"] == "tester"
    assert lines[0]["action"] == "save"
    assert lines[0]["status"] == "final"

    # GET /label now returns the saved label
    resp_get = client.get(f"/api/clips/{clip_id}/label")
    assert resp_get.status_code == 200
    assert resp_get.json()["clip_id"] == clip_id
    assert resp_get.json()["status"] == "final"

    # GET /clips reflects updated status "final"
    resp_clips = client.get("/api/clips")
    assert resp_clips.status_code == 200
    updated_clip = resp_clips.json()[0]
    assert updated_clip["label_status"] == "final"
    assert updated_clip["split"] == "dev"

    # PUT recomputes client residual if untrusted / differing by > 0.01
    valid_payload["calibration_gt"]["residual_px"] = 99.9
    resp_recompute = client.put(f"/api/clips/{clip_id}/label", json=valid_payload)
    assert resp_recompute.status_code == 200
    # Overwritten by backend
    assert abs(resp_recompute.json()["label"]["calibration_gt"]["residual_px"] - 0.014) < 0.01

    # Old label compatibility: draft label without calibration_gt
    old_draft = {
        "schema_version": 1,
        "clip_id": clip_id,
        "annotator": "tester",
        "mode": "blind",
        "status": "draft",
        "created_at": "2026-11-05T10:00:00Z",
        "updated_at": "2026-11-05T10:00:00Z",
        "notes": "Old draft without calibration",
    }
    resp_old = client.put(f"/api/clips/{clip_id}/label", json=old_draft)
    assert resp_old.status_code == 200
    assert resp_old.json()["label"]["calibration_gt"] is None
    resp_get_old = client.get(f"/api/clips/{clip_id}/label")
    assert resp_get_old.status_code == 200
    assert resp_get_old.json()["calibration_gt"] is None


def test_manifest_auto_build_if_missing(tmp_path, monkeypatch):
    """Verify backend builds manifest automatically if manifest.json is missing."""
    repo_dir = tmp_path / "auto_repo"
    jobs_dir = repo_dir / "backend" / "_tracker_work" / "jobs"
    test_job = jobs_dir / "auto_clip"
    test_job.mkdir(parents=True)

    video_path = test_job / "input.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, 30.0, (64, 64))
    for _ in range(5):
        writer.write(np.zeros((64, 64, 3), dtype=np.uint8))
    writer.release()

    manifest_file = repo_dir / "tools" / "annotator" / "manifest.json"
    assert not manifest_file.exists()

    orig_repo_root = main_mod.REPO_ROOT
    orig_manifest = main_mod.MANIFEST_PATH
    main_mod.REPO_ROOT = repo_dir
    main_mod.MANIFEST_PATH = manifest_file
    monkeypatch.setenv("CLIPS_ROOT", str(jobs_dir))

    try:
        manifest = load_manifest()
        assert len(manifest) == 1
        assert manifest[0]["clip_id"] == "auto_clip"
        assert manifest_file.is_file()
    finally:
        main_mod.REPO_ROOT = orig_repo_root
        main_mod.MANIFEST_PATH = orig_manifest


def test_frame_count_mismatch_detection(tmp_path):
    """
    Test that frame_count_mismatch is True when results.json video.frame_count
    or CAP_PROP_FRAME_COUNT differs from actual sequential decode.
    """
    repo_dir = tmp_path / "mismatch_repo"
    jobs_dir = repo_dir / "backend" / "_tracker_work" / "jobs"
    job = jobs_dir / "mismatch_job"
    job.mkdir(parents=True)

    video_path = job / "input.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, 30.0, (64, 64))
    for i in range(10):
        writer.write(np.zeros((64, 64, 3), dtype=np.uint8))
    writer.release()

    results_data = {
        "video": {
            "fps": 30.0,
            "frame_count": 15,
            "width": 64,
            "height": 64,
        }
    }
    with open(job / "results.json", "w", encoding="utf-8") as f:
        json.dump(results_data, f)

    manifest = build_manifest_data(jobs_dir, repo_root=repo_dir)
    assert len(manifest) == 1
    assert manifest[0]["frame_count"] == 10
    assert manifest[0]["frame_count_mismatch"] is True
