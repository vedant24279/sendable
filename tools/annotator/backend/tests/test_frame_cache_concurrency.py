"""Tests for thread-safe single-decode frame caching and catalog locking."""
from __future__ import annotations

import concurrent.futures
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from app import library, main as app_main


def _write_test_video(path: Path, n_frames: int = 8) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, 30.0, (64, 64))
    try:
        for i in range(n_frames):
            frame = np.full((64, 64, 3), fill_value=i * 25, dtype=np.uint8)
            writer.write(frame)
    finally:
        writer.release()


def test_ensure_clip_cached_serializes_concurrent_decodes(tmp_path, monkeypatch) -> None:
    video_path = tmp_path / "clip.mp4"
    _write_test_video(video_path, n_frames=8)
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(app_main, "CACHE_DIR", cache_dir)

    open_calls = 0
    open_lock = threading.Lock()
    real_capture = cv2.VideoCapture

    def counted_capture(src: str):
        nonlocal open_calls
        with open_lock:
            open_calls += 1
        time.sleep(0.05)  # widen window so parallel requests overlap
        return real_capture(src)

    monkeypatch.setattr(app_main.cv2, "VideoCapture", counted_capture)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        counts = list(
            pool.map(
                lambda _: app_main.ensure_clip_cached(
                    "c_race_test", video_path, expected_frame_count=8
                ),
                range(8),
            )
        )

    assert counts == [8] * 8
    assert open_calls == 1
    for i in range(8):
        jpg = cache_dir / "c_race_test" / f"{i}.jpg"
        assert jpg.is_file() and jpg.stat().st_size > 0
        decoded = cv2.imread(str(jpg))
        assert decoded is not None and decoded.shape == (64, 64, 3)


def test_library_catalog_concurrent_saves_do_not_collide(tmp_path) -> None:
    lib_dir = tmp_path / "lib"

    def save_worker(idx: int) -> None:
        library.save_library_catalog({f"c_{idx}": {"clip_id": f"c_{idx}"}}, lib_dir)
        loaded = library.load_library_catalog(lib_dir)
        assert isinstance(loaded, dict)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(save_worker, range(24)))
