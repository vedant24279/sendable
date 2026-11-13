import json
import os
import shutil
import tempfile
from pathlib import Path
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.library import (
    load_library_catalog,
    init_library_dirs,
    get_library_dir,
)


@pytest.fixture
def temp_dirs(monkeypatch):
    """Provide isolated temp folders for LABELS_DIR and ANNOTATOR_LIBRARY_DIR."""
    labels_tmp = tempfile.mkdtemp(prefix="test_annotator_labels_")
    lib_tmp = tempfile.mkdtemp(prefix="test_annotator_library_")

    monkeypatch.setenv("LABELS_DIR", labels_tmp)
    monkeypatch.setenv("ANNOTATOR_LIBRARY_DIR", lib_tmp)

    yield {
        "labels_dir": Path(labels_tmp),
        "library_dir": Path(lib_tmp),
    }

    shutil.rmtree(labels_tmp, ignore_errors=True)
    shutil.rmtree(lib_tmp, ignore_errors=True)


def create_synthetic_video_bytes(
    num_frames: int = 25,
    width: int = 720,
    height: int = 720,
    fps: float = 30.0,
    color_offset: int = 0,
) -> bytes:
    """Create a temporary mp4 video file and return its raw bytes."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(tmp_path), fourcc, fps, (width, height))
    for i in range(num_frames):
        frame = np.full((height, width, 3), (i * 10 + color_offset) % 255, dtype=np.uint8)
        out.write(frame)
    out.release()

    with open(tmp_path, "rb") as f:
        data = f.read()

    try:
        tmp_path.unlink()
    except OSError:
        pass

    return data


def test_library_upload_add_success(temp_dirs):
    client = TestClient(app)
    video_bytes = create_synthetic_video_bytes(num_frames=30, width=1280, height=720, fps=30.0)

    # 1. Upload valid video
    resp = client.post(
        "/api/library/upload?name=my_match_delivery.mp4",
        content=video_bytes,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "added"
    entry = data["entry"]
    clip_id = entry["clip_id"]
    assert clip_id.startswith("c_")
    assert entry["display_name"] == "my_match_delivery.mp4"
    assert entry["frame_count"] == 30
    assert entry["width"] == 1280
    assert entry["height"] == 720
    assert entry["warnings"] == []
    assert entry["hidden"] is False

    # Check file exists on disk under videos/<clip_id>.mp4
    video_on_disk = temp_dirs["library_dir"] / "videos" / f"{clip_id}.mp4"
    assert video_on_disk.is_file()

    # Check client filename was NEVER used in disk path
    assert not (temp_dirs["library_dir"] / "videos" / "my_match_delivery.mp4").exists()

    # Check GET /api/library/info
    info_resp = client.get("/api/library/info")
    assert info_resp.status_code == 200
    assert info_resp.json()["count"] == 1

    # Check GET /api/clips contains the new library clip
    clips_resp = client.get("/api/clips")
    assert clips_resp.status_code == 200
    lib_clips = [c for c in clips_resp.json() if c.get("pool") == "library"]
    assert len(lib_clips) == 1
    assert lib_clips[0]["clip_id"] == clip_id
    assert lib_clips[0]["display_name"] == "my_match_delivery.mp4"


def test_library_upload_duplicate(temp_dirs):
    client = TestClient(app)
    video_bytes = create_synthetic_video_bytes(num_frames=25, color_offset=42)

    # First upload
    resp1 = client.post("/api/library/upload?name=delivery_1.mp4", content=video_bytes)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "added"
    clip_id = resp1.json()["entry"]["clip_id"]

    # Hide the clip
    hide_resp = client.post(f"/api/library/{clip_id}/hide")
    assert hide_resp.status_code == 200

    # Upload same video again under a different name
    resp2 = client.post("/api/library/upload?name=delivery_copy.mp4", content=video_bytes)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "duplicate"
    # Clip should be un-hidden
    assert data2["entry"]["hidden"] is False
    assert data2["entry"]["clip_id"] == clip_id


def test_library_upload_unsupported_extension(temp_dirs):
    client = TestClient(app)
    resp = client.post("/api/library/upload?name=document.txt", content=b"hello text")
    assert resp.status_code == 415
    assert "Unsupported video extension" in resp.json()["detail"]


def test_library_upload_empty_body(temp_dirs):
    client = TestClient(app)
    resp = client.post("/api/library/upload?name=empty.mp4", content=b"")
    assert resp.status_code == 400
    assert "Empty upload body" in resp.json()["detail"]


def test_library_upload_too_large(temp_dirs, monkeypatch):
    monkeypatch.setenv("ANNOTATOR_MAX_UPLOAD_MB", "1")
    client = TestClient(app)

    # Send 1.2 MB dummy bytes
    big_data = b"0" * (1024 * 1024 + 200 * 1024)
    resp = client.post("/api/library/upload?name=big.mp4", content=big_data)
    assert resp.status_code == 413
    assert "exceeds maximum allowed" in resp.json()["detail"]


def test_library_upload_corrupt_file_leaves_no_leftovers(temp_dirs):
    client = TestClient(app)
    # Corrupt data with .mp4 extension
    corrupt_data = b"GARBAGE_NOT_A_VALID_VIDEO_HEADER_1234567890" * 100

    resp = client.post("/api/library/upload?name=corrupt.mp4", content=corrupt_data)
    assert resp.status_code == 422
    assert "Video validation failed" in resp.json()["detail"]

    # Verify no temp files or leftover video files remain in library
    lib_dir = temp_dirs["library_dir"]
    videos_dir = lib_dir / "videos"
    remaining_videos = list(videos_dir.iterdir())
    assert remaining_videos == []

    temp_files = [f for f in lib_dir.iterdir() if f.name.startswith(".upload_")]
    assert temp_files == []


def test_library_path_traversal_safe(temp_dirs):
    client = TestClient(app)
    video_bytes = create_synthetic_video_bytes(num_frames=20)

    # Name containing relative path traversal
    resp = client.post("/api/library/upload?name=..%2F..%2Fescaped.mp4", content=video_bytes)
    assert resp.status_code == 200
    entry = resp.json()["entry"]
    assert entry["display_name"] == "escaped.mp4"

    # Make sure nothing escaped outside videos/
    parent_escaped = temp_dirs["library_dir"].parent / "escaped.mp4"
    assert not parent_escaped.exists()


def test_library_recents_ordering_and_opened(temp_dirs):
    client = TestClient(app)
    vid1 = create_synthetic_video_bytes(num_frames=20, color_offset=10)
    vid2 = create_synthetic_video_bytes(num_frames=20, color_offset=20)
    vid3 = create_synthetic_video_bytes(num_frames=20, color_offset=30)

    r1 = client.post("/api/library/upload?name=clip1.mp4", content=vid1).json()["entry"]
    r2 = client.post("/api/library/upload?name=clip2.mp4", content=vid2).json()["entry"]
    r3 = client.post("/api/library/upload?name=clip3.mp4", content=vid3).json()["entry"]

    # Initial recents order should be clip3, clip2, clip1 (most recently added)
    recents = client.get("/api/library/recents").json()
    assert [c["clip_id"] for c in recents] == [r3["clip_id"], r2["clip_id"], r1["clip_id"]]

    # Now open clip1
    open_resp = client.post(f"/api/library/{r1['clip_id']}/opened")
    assert open_resp.status_code == 200

    # Recents should now be clip1, clip3, clip2
    recents_after = client.get("/api/library/recents").json()
    assert recents_after[0]["clip_id"] == r1["clip_id"]
    assert recents_after[1]["clip_id"] == r3["clip_id"]
    assert recents_after[2]["clip_id"] == r2["clip_id"]


def test_library_hide_and_readd_unhides(temp_dirs):
    client = TestClient(app)
    video_bytes = create_synthetic_video_bytes(num_frames=25)

    add_resp = client.post("/api/library/upload?name=test_hide.mp4", content=video_bytes)
    clip_id = add_resp.json()["entry"]["clip_id"]

    # Hide clip
    assert client.post(f"/api/library/{clip_id}/hide").status_code == 200

    # Should not appear in recents or /library
    recents = client.get("/api/library/recents").json()
    assert not any(c["clip_id"] == clip_id for c in recents)

    all_lib = client.get("/api/library").json()
    assert not any(c["clip_id"] == clip_id for c in all_lib)

    # Re-upload same video -> unhides and sets status duplicate
    re_resp = client.post("/api/library/upload?name=test_hide.mp4", content=video_bytes)
    assert re_resp.status_code == 200
    assert re_resp.json()["status"] == "duplicate"
    assert re_resp.json()["entry"]["hidden"] is False

    # Appears in recents again
    recents2 = client.get("/api/library/recents").json()
    assert any(c["clip_id"] == clip_id for c in recents2)


def test_library_catalog_survives_reload(temp_dirs):
    client = TestClient(app)
    video_bytes = create_synthetic_video_bytes(num_frames=25)

    add_resp = client.post("/api/library/upload?name=persistent.mp4", content=video_bytes)
    clip_id = add_resp.json()["entry"]["clip_id"]

    # Direct catalog reload from disk
    catalog = load_library_catalog(temp_dirs["library_dir"])
    assert clip_id in catalog
    assert catalog[clip_id]["display_name"] == "persistent.mp4"
    assert catalog[clip_id]["frame_count"] == 25


def test_library_clip_prefill_and_frame_endpoints(temp_dirs):
    client = TestClient(app)
    video_bytes = create_synthetic_video_bytes(num_frames=25, width=640, height=480, fps=20.0)

    add_resp = client.post("/api/library/upload?name=low_fps.mp4", content=video_bytes)
    entry = add_resp.json()["entry"]
    clip_id = entry["clip_id"]
    # Check warning low_fps (<25) and low_res (height <720)
    assert "low_fps" in entry["warnings"]
    assert "low_res" in entry["warnings"]

    # Frame retrieval: frame 0
    frame_resp = client.get(f"/api/clips/{clip_id}/frame/0")
    assert frame_resp.status_code == 200
    assert frame_resp.headers["content-type"] == "image/jpeg"
    assert len(frame_resp.content) > 0

    # Out of bounds frame
    oob_resp = client.get(f"/api/clips/{clip_id}/frame/999")
    assert oob_resp.status_code == 404

    # Prefill: for library clip, returns empty events, trajectory: [], calibration: null (not an error!)
    prefill_resp = client.get(f"/api/clips/{clip_id}/prefill")
    assert prefill_resp.status_code == 200
    prefill_data = prefill_resp.json()
    assert prefill_data["clip_id"] == clip_id
    assert prefill_data["events"] == {"release": None, "bounce": None, "impact": None, "deviation": None}
    assert prefill_data["trajectory"] == []
    assert prefill_data["calibration"] is None


def test_library_upload_parses_filename_meta_and_patch(temp_dirs):
    client = TestClient(app)
    video_bytes = create_synthetic_video_bytes(num_frames=25, color_offset=77)

    resp = client.post(
        "/api/library/upload?name=bowled_out_red.mp4",
        content=video_bytes,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 200
    entry = resp.json()["entry"]
    clip_id = entry["clip_id"]
    assert entry["reference_decision"] == "out"
    assert entry["ball_colour_hint"] == "red"
    assert entry["source_group"] is None

    # PATCH valid fields
    patch_resp = client.patch(
        f"/api/library/{clip_id}",
        json={
            "reference_decision": "not_out",
            "ball_colour_hint": "white",
            "source_group": "ind_vs_aus",
        },
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()["entry"]
    assert patched["reference_decision"] == "not_out"
    assert patched["ball_colour_hint"] == "white"
    assert patched["source_group"] == "ind_vs_aus"

    # Persistence check
    catalog = load_library_catalog(temp_dirs["library_dir"])
    assert catalog[clip_id]["reference_decision"] == "not_out"
    assert catalog[clip_id]["ball_colour_hint"] == "white"
    assert catalog[clip_id]["source_group"] == "ind_vs_aus"

    # PATCH partial clear (set reference_decision to null, leave others unchanged)
    patch_clear = client.patch(
        f"/api/library/{clip_id}",
        json={"reference_decision": None},
    )
    assert patch_clear.status_code == 200
    assert patch_clear.json()["entry"]["reference_decision"] is None
    assert patch_clear.json()["entry"]["ball_colour_hint"] == "white"

    # Invalid value -> 422
    bad_patch = client.patch(
        f"/api/library/{clip_id}",
        json={"reference_decision": "maybe"},
    )
    assert bad_patch.status_code == 422

    # Unknown field -> 422
    extra_patch = client.patch(
        f"/api/library/{clip_id}",
        json={"unknown_field": 123},
    )
    assert extra_patch.status_code == 422

    # Missing clip -> 404
    missing_patch = client.patch(
        "/api/library/c_doesnotexist",
        json={"reference_decision": "out"},
    )
    assert missing_patch.status_code == 404


def test_put_label_enforces_reference_decision_from_library(temp_dirs):
    client = TestClient(app)
    video_bytes = create_synthetic_video_bytes(num_frames=30, color_offset=99)

    resp = client.post(
        "/api/library/upload?name=ind_vs_aus_lbw_out.mp4",
        content=video_bytes,
    )
    clip_id = resp.json()["entry"]["clip_id"]

    # Client attempts to send wrong reference_decision ("not_out"); backend must overwrite from library entry ("out")
    payload = {
        "schema_version": 1,
        "clip_id": clip_id,
        "annotator": "tester",
        "mode": "blind",
        "status": "draft",
        "created_at": "2026-11-13T10:00:00Z",
        "updated_at": "2026-11-13T10:00:00Z",
        "reference_decision": "not_out",
        "impact": {"type": "pad", "frame": 15, "x": 100.0, "y": 100.0},
        "lbw": "not_out_missing",
    }
    put_resp = client.put(f"/api/clips/{clip_id}/label", json=payload)
    assert put_resp.status_code == 200
    body = put_resp.json()
    assert body["label"]["reference_decision"] == "out"
    assert len(body["warnings"]) == 1
    assert body["warnings"][0]["message"] == "File name says out but lbw is not out"

