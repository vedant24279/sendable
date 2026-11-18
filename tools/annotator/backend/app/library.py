"""
Library management for the Cricket Delivery Annotator.

Manages video files outside the repository in ANNOTATOR_LIBRARY_DIR
(default: <home>/CricketAnnotator/library), with videos in videos/
and metadata cataloged in library.json.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import cv2
from fastapi import HTTPException

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}
_CATALOG_LOCK = threading.RLock()


def get_library_dir() -> Path:
    """Return library root path from ANNOTATOR_LIBRARY_DIR or default to <home>/CricketAnnotator/library."""
    env_dir = os.getenv("ANNOTATOR_LIBRARY_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    return (Path.home() / "CricketAnnotator" / "library").resolve()


def get_max_upload_bytes() -> int:
    """Maximum allowed upload size in bytes (default 2048 MB)."""
    mb_str = os.getenv("ANNOTATOR_MAX_UPLOAD_MB", "2048")
    try:
        mb = int(mb_str)
    except ValueError:
        mb = 2048
    return mb * 1024 * 1024


def init_library_dirs(library_dir: Optional[Path] = None) -> Tuple[Path, Path, Path]:
    """Ensure library root and videos/ directory exist; return (library_dir, videos_dir, library_json)."""
    if library_dir is None:
        library_dir = get_library_dir()
    videos_dir = library_dir / "videos"
    library_json = library_dir / "library.json"

    library_dir.mkdir(parents=True, exist_ok=True)
    videos_dir.mkdir(parents=True, exist_ok=True)
    return library_dir, videos_dir, library_json


def load_library_catalog(library_dir: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Load library.json as a dict mapping clip_id -> entry dict."""
    with _CATALOG_LOCK:
        lib_dir, _, catalog_file = init_library_dirs(library_dir)
        if not catalog_file.is_file():
            return {}

        try:
            with open(catalog_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                if isinstance(data, list):
                    # Normalize list of entries into dict keyed by clip_id
                    return {item["clip_id"]: item for item in data if isinstance(item, dict) and "clip_id" in item}
        except Exception as e:
            print(f"Error loading {catalog_file}: {e}", file=sys.stderr)
        return {}


def save_library_catalog(
    catalog: Dict[str, Dict[str, Any]], library_dir: Optional[Path] = None
) -> None:
    """Atomically write library.json using a temp file."""
    with _CATALOG_LOCK:
        lib_dir, _, catalog_file = init_library_dirs(library_dir)
        tmp_file = lib_dir / f".library.json.tmp.{uuid.uuid4().hex}"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(catalog, f, indent=2)
            for attempt in range(5):
                try:
                    os.replace(tmp_file, catalog_file)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.02 * (attempt + 1))
        except Exception:
            if tmp_file.is_file():
                try:
                    tmp_file.unlink()
                except OSError:
                    pass
            raise


def generate_clip_id(sha256_hash: str, existing_catalog: Dict[str, Dict[str, Any]]) -> str:
    """
    Generate clip_id: "c_" + first 8 hex chars of sha256.
    If 8 chars collide with a different hash, use 12 chars.
    """
    prefix8 = f"c_{sha256_hash[:8]}"
    if prefix8 in existing_catalog:
        existing = existing_catalog[prefix8]
        if existing.get("sha256") != sha256_hash:
            return f"c_{sha256_hash[:12]}"
        return prefix8
    return prefix8


def compute_video_warnings(fps: float, height: int, frame_count: int) -> List[str]:
    """
    Warnings:
    - low_fps: fps < 25
    - low_res: height < 720
    - short: frame_count < 20
    - long: frame_count > 300
    """
    warnings: List[str] = []
    if fps < 25.0:
        warnings.append("low_fps")
    if height < 720:
        warnings.append("low_res")
    if frame_count < 20:
        warnings.append("short")
    elif frame_count > 300:
        warnings.append("long")
    return warnings


def inspect_video_file(video_path: Path) -> Tuple[float, int, int, int, List[str]]:
    """
    Open video and sequentially decode frames with OpenCV to verify integrity and frame count.
    Returns: (fps, frame_count, width, height, warnings)
    Raises ValueError if video cannot be opened or decoded frame count == 0.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path.name}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    decoded_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        decoded_count += 1
        if decoded_count == 1:
            if width <= 0 or height <= 0:
                h, w = frame.shape[:2]
                width = w
                height = h
    cap.release()

    if decoded_count == 0:
        raise ValueError("Corrupt or empty video: 0 frames decoded")

    warnings = compute_video_warnings(fps=fps, height=height, frame_count=decoded_count)
    return fps, decoded_count, width, height, warnings


async def process_video_upload(
    stream: AsyncIterator[bytes],
    original_name: str,
    library_dir: Optional[Path] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Stream upload bytes into a temp file while computing SHA256 and enforcing max size.
    Returns (status, entry) where status is 'added' or 'duplicate'.
    """
    # 1. Validate extension from original filename
    base_name = Path(original_name).name  # Prevent directory traversal
    ext = Path(base_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported video extension: '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    lib_dir, videos_dir, _ = init_library_dirs(library_dir)
    max_bytes = get_max_upload_bytes()

    # 2. Stream to a temp file in the library folder
    temp_file = lib_dir / f".upload_{uuid.uuid4().hex}.tmp"
    hasher = hashlib.sha256()
    total_bytes = 0

    try:
        with open(temp_file, "wb") as f:
            async for chunk in stream:
                if not chunk:
                    continue
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Upload size exceeds maximum allowed ({max_bytes // (1024 * 1024)} MB)",
                    )
                hasher.update(chunk)
                f.write(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="Empty upload body")

        sha256_hash = hasher.hexdigest()
        catalog = load_library_catalog(lib_dir)

        # 3. Check for duplicate hash
        for existing_id, entry in catalog.items():
            if entry.get("sha256") == sha256_hash:
                # Duplicate found: clean up temp file, un-hide, update last_opened_at
                try:
                    temp_file.unlink()
                except OSError:
                    pass

                now_iso = datetime.now(timezone.utc).isoformat()
                entry["hidden"] = False
                entry["last_opened_at"] = now_iso
                catalog[existing_id] = entry
                save_library_catalog(catalog, lib_dir)
                return "duplicate", entry

        # 4. New clip: generate ID and destination path
        clip_id = generate_clip_id(sha256_hash, catalog)
        target_video_file = videos_dir / f"{clip_id}{ext}"

        # Move temp file to final destination
        shutil.move(str(temp_file), str(target_video_file))

        # 5. Decode sequentially with OpenCV
        try:
            fps, frame_count, width, height, warnings = inspect_video_file(target_video_file)
        except Exception as e:
            # Delete corrupt video file from videos/
            if target_video_file.is_file():
                try:
                    target_video_file.unlink()
                except OSError:
                    pass
            raise HTTPException(
                status_code=422,
                detail=f"Video validation failed: {str(e)}",
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        entry: Dict[str, Any] = {
            "clip_id": clip_id,
            "display_name": base_name,
            "sha256": sha256_hash,
            "size_bytes": total_bytes,
            "added_at": now_iso,
            "last_opened_at": now_iso,
            "hidden": False,
            "fps": fps,
            "frame_count": frame_count,
            "width": width,
            "height": height,
            "warnings": warnings,
        }

        catalog[clip_id] = entry
        save_library_catalog(catalog, lib_dir)
        return "added", entry

    except Exception:
        # Guarantee removal of temp file on any failure path
        if temp_file.is_file():
            try:
                temp_file.unlink()
            except OSError:
                pass
        raise


def get_library_recents(limit: int = 20, library_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Return non-hidden entries sorted by last_opened_at desc (added_at when never opened).
    """
    catalog = load_library_catalog(library_dir)
    non_hidden = [entry for entry in catalog.values() if not entry.get("hidden", False)]

    def sort_key(e: Dict[str, Any]) -> str:
        return e.get("last_opened_at") or e.get("added_at") or ""

    sorted_entries = sorted(non_hidden, key=sort_key, reverse=True)
    return sorted_entries[:limit]


def get_all_library_entries(library_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Return all non-hidden entries."""
    catalog = load_library_catalog(library_dir)
    return [entry for entry in catalog.values() if not entry.get("hidden", False)]


def touch_library_clip_opened(clip_id: str, library_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Set last_opened_at = now() for given clip_id."""
    catalog = load_library_catalog(library_dir)
    if clip_id not in catalog:
        return None
    entry = catalog[clip_id]
    entry["last_opened_at"] = datetime.now(timezone.utc).isoformat()
    catalog[clip_id] = entry
    save_library_catalog(catalog, library_dir)
    return entry


def hide_library_clip(clip_id: str, library_dir: Optional[Path] = None) -> bool:
    """Set hidden = True for given clip_id. Returns True if found, False otherwise."""
    catalog = load_library_catalog(library_dir)
    if clip_id not in catalog:
        return False
    catalog[clip_id]["hidden"] = True
    save_library_catalog(catalog, library_dir)
    return True


def find_library_clip_video(clip_id: str, library_dir: Optional[Path] = None) -> Optional[Tuple[Path, Dict[str, Any]]]:
    """
    Locate video file in library for given clip_id.
    Returns (video_path, entry) or None.
    """
    catalog = load_library_catalog(library_dir)
    if clip_id not in catalog:
        return None
    entry = catalog[clip_id]
    lib_dir, videos_dir, _ = init_library_dirs(library_dir)

    # Search for videos/<clip_id><ext>
    for ext in ALLOWED_EXTENSIONS:
        candidate = videos_dir / f"{clip_id}{ext}"
        if candidate.is_file():
            return candidate, entry

    return None
