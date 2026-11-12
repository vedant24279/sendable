"""
FastAPI Backend for Cricket Delivery Annotator.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure tools/annotator/backend is on sys.path
_current_dir = Path(__file__).resolve().parent
_backend_dir = _current_dir.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

import cv2
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.schema import Label, validate_label
from app.calib import fit_homography
from app.library import (
    get_library_dir,
    process_video_upload,
    get_library_recents,
    get_all_library_entries,
    touch_library_clip_opened,
    hide_library_clip,
    find_library_clip_video,
)


def get_repo_root() -> Path:
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "backend").is_dir() and (current / "tools").is_dir():
            return current
        current = current.parent
    return Path.cwd().resolve()


REPO_ROOT = get_repo_root()
MANIFEST_PATH = REPO_ROOT / "tools" / "annotator" / "manifest.json"
CACHE_DIR = REPO_ROOT / "tools" / "annotator" / ".cache"
DEFAULT_CLIPS_ROOT = REPO_ROOT / "backend" / "_tracker_work" / "jobs"


def get_labels_dir() -> Path:
    """Return configured labels directory from LABELS_DIR env or default to eval/labels."""
    env_dir = os.getenv("LABELS_DIR")
    if env_dir:
        p = Path(env_dir)
        return p if p.is_absolute() else (REPO_ROOT / p)
    return REPO_ROOT / "eval" / "labels"


app = FastAPI(title="Cricket Delivery Annotator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_manifest() -> List[Dict[str, Any]]:
    """Loads manifest.json; if missing, builds it automatically on startup."""
    if not MANIFEST_PATH.is_file():
        try:
            backend_dir = REPO_ROOT / "tools" / "annotator" / "backend"
            if str(backend_dir) not in sys.path:
                sys.path.insert(0, str(backend_dir))
            from build_manifest import build_manifest_data

            clips_root = Path(os.getenv("CLIPS_ROOT", str(DEFAULT_CLIPS_ROOT)))
            if not clips_root.is_absolute():
                clips_root = REPO_ROOT / clips_root
            data = build_manifest_data(
                clips_root, repo_root=REPO_ROOT, eval_labels_dir=get_labels_dir()
            )
            MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return data
        except Exception as e:
            print(f"Error auto-building manifest: {e}", file=sys.stderr)
            return []

    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {MANIFEST_PATH}: {e}", file=sys.stderr)
    return []


@app.on_event("startup")
def startup_event() -> None:
    load_manifest()


def resolve_clip(clip_id: str) -> Optional[Tuple[Path, Dict[str, Any]]]:
    """
    Resolve video file path and clip metadata for a clip_id from either the
    user library or the debug/job manifest.
    """
    # 1. Check user library first
    lib_match = find_library_clip_video(clip_id)
    if lib_match is not None:
        video_path, entry = lib_match
        status, split = get_current_label_state(clip_id)
        has_gt = False
        label_file = get_labels_dir() / f"{clip_id}.json"
        if label_file.is_file():
            try:
                with open(label_file, "r", encoding="utf-8") as lf:
                    has_gt = bool(json.load(lf).get("calibration_gt"))
            except Exception:
                pass

        meta: Dict[str, Any] = {
            "clip_id": entry["clip_id"],
            "display_name": entry.get("display_name", clip_id),
            "pool": "library",
            "fps": entry["fps"],
            "frame_count": entry["frame_count"],
            "width": entry["width"],
            "height": entry["height"],
            "warnings": entry.get("warnings", []),
            "added_at": entry.get("added_at"),
            "last_opened_at": entry.get("last_opened_at"),
            "size_bytes": entry.get("size_bytes"),
            "ball_type": None,
            "has_results": False,
            "has_calibration": False,
            "system_residual_px": None,
            "has_gt_calibration": has_gt,
            "label_status": status,
            "split": split,
            "path": str(video_path),
        }
        return video_path, meta

    # 2. Check manifest for job / debug clips
    manifest = load_manifest()
    for item in manifest:
        if item.get("clip_id") == clip_id:
            rel_path = item["path"]
            video_path = REPO_ROOT / rel_path
            status, split = get_current_label_state(clip_id)
            meta = dict(item)
            meta["pool"] = "debug"
            if "display_name" not in meta:
                meta["display_name"] = clip_id
            meta["label_status"] = status
            if split is not None:
                meta["split"] = split
            return video_path, meta

    return None


def get_clip_entry(clip_id: str) -> Optional[Dict[str, Any]]:
    resolved = resolve_clip(clip_id)
    if resolved is not None:
        return resolved[1]
    return None


def get_current_label_state(clip_id: str) -> tuple[str, Optional[str]]:
    labels_dir = get_labels_dir()
    label_file = labels_dir / f"{clip_id}.json"
    if label_file.is_file():
        try:
            with open(label_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("status", "draft"), data.get("split")
        except Exception:
            pass
    return "none", None


def ensure_clip_cached(
    clip_id: str, video_path: Path, expected_frame_count: Optional[int] = None
) -> int:
    """
    Sequentially decode and disk-cache every frame as JPEG (quality 92).
    Returns total decoded frame count. Only stores {n}.jpg files in the folder.
    """
    clip_cache_dir = CACHE_DIR / clip_id
    clip_cache_dir.mkdir(parents=True, exist_ok=True)

    # Check if already cached (only JPEG frames)
    existing_jpgs = list(clip_cache_dir.glob("*.jpg"))
    if expected_frame_count is not None and len(existing_jpgs) == expected_frame_count:
        return len(existing_jpgs)
    elif expected_frame_count is None and len(existing_jpgs) > 0:
        return len(existing_jpgs)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise HTTPException(
            status_code=500,
            detail=f"Cannot open video for clip {clip_id}: {video_path}",
        )

    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_file = clip_cache_dir / f"{idx}.jpg"
        cv2.imwrite(
            str(frame_file),
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), 92],
        )
        idx += 1
    cap.release()

    return idx


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/clips")
def list_clips() -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []

    # 1. Library clips (pool "library")
    lib_entries = get_all_library_entries()
    labels_dir = get_labels_dir()
    for entry in lib_entries:
        clip_id = entry["clip_id"]
        status, split = get_current_label_state(clip_id)
        has_gt = False
        label_file = labels_dir / f"{clip_id}.json"
        if label_file.is_file():
            try:
                with open(label_file, "r", encoding="utf-8") as lf:
                    has_gt = bool(json.load(lf).get("calibration_gt"))
            except Exception:
                pass

        result.append(
            {
                "clip_id": clip_id,
                "display_name": entry.get("display_name", clip_id),
                "pool": "library",
                "fps": entry["fps"],
                "frame_count": entry["frame_count"],
                "width": entry["width"],
                "height": entry["height"],
                "warnings": entry.get("warnings", []),
                "added_at": entry.get("added_at"),
                "last_opened_at": entry.get("last_opened_at"),
                "size_bytes": entry.get("size_bytes"),
                "ball_type": None,
                "has_results": False,
                "has_calibration": False,
                "system_residual_px": None,
                "has_gt_calibration": has_gt,
                "label_status": status,
                "split": split,
            }
        )

    # 2. Debug clips from manifest (pool "debug")
    manifest = load_manifest()
    for item in manifest:
        clip_copy = dict(item)
        clip_id = clip_copy["clip_id"]
        status, split = get_current_label_state(clip_id)
        clip_copy["pool"] = "debug"
        if "display_name" not in clip_copy:
            clip_copy["display_name"] = clip_id
        clip_copy["label_status"] = status
        if split is not None:
            clip_copy["split"] = split
        result.append(clip_copy)

    return result


@app.post("/api/library/upload")
async def upload_library_video(request: Request, name: str = "") -> Dict[str, Any]:
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Missing 'name' query parameter")

    status, entry = await process_video_upload(request.stream(), name.strip())
    return {"status": status, "entry": entry}


@app.get("/api/library/recents")
def list_library_recents(limit: int = 20) -> List[Dict[str, Any]]:
    entries = get_library_recents(limit=limit)
    result: List[Dict[str, Any]] = []
    labels_dir = get_labels_dir()

    for e in entries:
        e_copy = dict(e)
        clip_id = e["clip_id"]
        status, split = get_current_label_state(clip_id)
        e_copy["label_status"] = status
        if split is not None:
            e_copy["split"] = split
        has_gt = False
        label_file = labels_dir / f"{clip_id}.json"
        if label_file.is_file():
            try:
                with open(label_file, "r", encoding="utf-8") as lf:
                    has_gt = bool(json.load(lf).get("calibration_gt"))
            except Exception:
                pass
        e_copy["has_gt_calibration"] = has_gt
        result.append(e_copy)

    return result


@app.get("/api/library")
def list_library_all() -> List[Dict[str, Any]]:
    entries = get_all_library_entries()
    result: List[Dict[str, Any]] = []
    labels_dir = get_labels_dir()

    for e in entries:
        e_copy = dict(e)
        clip_id = e["clip_id"]
        status, split = get_current_label_state(clip_id)
        e_copy["label_status"] = status
        if split is not None:
            e_copy["split"] = split
        has_gt = False
        label_file = labels_dir / f"{clip_id}.json"
        if label_file.is_file():
            try:
                with open(label_file, "r", encoding="utf-8") as lf:
                    has_gt = bool(json.load(lf).get("calibration_gt"))
            except Exception:
                pass
        e_copy["has_gt_calibration"] = has_gt
        result.append(e_copy)

    return result


@app.get("/api/library/info")
def get_library_info() -> Dict[str, Any]:
    folder = get_library_dir()
    entries = get_all_library_entries()
    return {
        "folder": str(folder),
        "count": len(entries),
    }


@app.post("/api/library/{clip_id}/opened")
def open_library_clip(clip_id: str) -> Dict[str, Any]:
    entry = touch_library_clip_opened(clip_id)
    if not entry:
        return {"status": "ok"}
    return {"status": "ok", "entry": entry}


@app.post("/api/library/{clip_id}/hide")
def hide_clip(clip_id: str) -> Dict[str, Any]:
    ok = hide_library_clip(clip_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Clip not found in library: {clip_id}")
    return {"status": "ok"}


@app.get("/api/clips/{clip_id}/frame/{n}")
def get_frame(clip_id: str, n: int) -> Response:
    resolved = resolve_clip(clip_id)
    if not resolved:
        raise HTTPException(status_code=404, detail=f"Clip not found: {clip_id}")

    video_path, clip = resolved
    if not video_path.is_file():
        raise HTTPException(
            status_code=404, detail=f"Video file missing for clip: {clip_id}"
        )

    total_frames = ensure_clip_cached(
        clip_id, video_path, expected_frame_count=clip.get("frame_count")
    )

    if n < 0 or n >= total_frames:
        raise HTTPException(
            status_code=404,
            detail=f"Frame index {n} out of bounds [0, {total_frames - 1}]",
        )

    frame_file = CACHE_DIR / clip_id / f"{n}.jpg"
    if not frame_file.is_file():
        raise HTTPException(
            status_code=404, detail=f"Frame {n} not found on disk cache."
        )

    with open(frame_file, "rb") as f:
        data = f.read()

    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/api/clips/{clip_id}/prefill")
def get_prefill(clip_id: str) -> Dict[str, Any]:
    resolved = resolve_clip(clip_id)
    if not resolved:
        raise HTTPException(status_code=404, detail=f"Clip not found: {clip_id}")

    video_path, clip = resolved
    # For library clips or clips without results.json: prefill returns empty events, empty trajectory, calibration null
    empty_prefill = {
        "clip_id": clip_id,
        "events": {
            "release": None,
            "bounce": None,
            "impact": None,
            "deviation": None,
        },
        "trajectory": [],
        "calibration": None,
    }

    if clip.get("pool") == "library":
        return empty_prefill

    job_dir = video_path.parent
    results_json = job_dir / "results.json"

    if not results_json.is_file():
        return empty_prefill

    with open(results_json, "r", encoding="utf-8") as f:
        res = json.load(f)

    # Normalise events (all nullable)
    ev_raw = res.get("events") or {}

    def norm_event(name: str) -> Optional[Dict[str, Any]]:
        e = ev_raw.get(name)
        if not e or not isinstance(e, dict):
            return None
        res_e: Dict[str, Any] = {
            "frame": e.get("frame"),
            "x": float(e["x"]) if e.get("x") is not None else None,
            "y": float(e["y"]) if e.get("y") is not None else None,
        }
        if "timestamp_sec" in e:
            res_e["timestamp_sec"] = e["timestamp_sec"]
        if "type" in e:
            res_e["type"] = e["type"]
        if "zone" in e:
            res_e["zone"] = e["zone"]
        if "length_m" in e:
            res_e["length_m"] = e["length_m"]
        if "grid_cell" in e:
            res_e["grid_cell"] = e["grid_cell"]
        return res_e

    events = {
        "release": norm_event("release"),
        "bounce": norm_event("bounce"),
        "impact": norm_event("impact"),
        "deviation": norm_event("deviation"),
    }

    # Normalise trajectory
    raw_traj = res.get("trajectory") or []
    trajectory: List[Dict[str, Any]] = []
    for pt in raw_traj:
        if isinstance(pt, dict) and "frame" in pt and "x" in pt and "y" in pt:
            trajectory.append(
                {
                    "frame": int(pt["frame"]),
                    "x": float(pt["x"]),
                    "y": float(pt["y"]),
                    "conf": float(pt["conf"]) if pt.get("conf") is not None else None,
                    "interpolated": bool(pt.get("interpolated", False)),
                }
            )

    # Normalise calibration into list of named points {name, x, y}
    raw_calib = res.get("calibration") or {}
    calibration: List[Dict[str, Any]] = []
    if isinstance(raw_calib, dict):
        for name, coords in raw_calib.items():
            if (
                isinstance(coords, (list, tuple))
                and len(coords) == 2
                and coords[0] is not None
                and coords[1] is not None
            ):
                calibration.append(
                    {
                        "name": str(name),
                        "x": float(coords[0]),
                        "y": float(coords[1]),
                    }
                )

    return {
        "clip_id": clip_id,
        "events": events,
        "trajectory": trajectory,
        "calibration": calibration,
    }


@app.get("/api/clips/{clip_id}/label")
def get_label(clip_id: str) -> Dict[str, Any]:
    labels_dir = get_labels_dir()
    label_file = labels_dir / f"{clip_id}.json"
    if not label_file.is_file():
        raise HTTPException(
            status_code=404, detail=f"Label not found for clip: {clip_id}"
        )

    try:
        with open(label_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read label: {e}")


@app.put("/api/clips/{clip_id}/label")
async def save_label(clip_id: str, request: Request) -> Dict[str, Any]:
    clip = get_clip_entry(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail=f"Clip not found: {clip_id}")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid JSON payload")

    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object")

    if body.get("clip_id") != clip_id:
        raise HTTPException(
            status_code=422,
            detail=f"clip_id in payload ('{body.get('clip_id')}') does not match URL ('{clip_id}')",
        )

    frame_count = clip["frame_count"]
    width = clip["width"]
    height = clip["height"]

    # Recompute calibration residual_px on every PUT (never trust client value)
    calib_gt = body.get("calibration_gt")
    if calib_gt and isinstance(calib_gt, dict) and "points" in calib_gt:
        pts = calib_gt.get("points")
        if isinstance(pts, dict):
            try:
                stump_conf = calib_gt.get("stump_confirmed") or {
                    "bat_stump": False,
                    "bowl_stump": False,
                }
                fit_res = fit_homography(pts, stump_confirmed=stump_conf)
                computed_res = fit_res.residual_px
                client_res = calib_gt.get("residual_px")
                if computed_res is None:
                    calib_gt["residual_px"] = None
                elif client_res is None or abs(float(client_res) - float(computed_res)) > 0.01:
                    calib_gt["residual_px"] = float(computed_res)
            except Exception:
                pass

    try:
        label = validate_label(
            body,
            frame_count=frame_count,
            width=width,
            height=height,
        )
    except (ValidationError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Atomic write to <labels_dir>/<clip_id>.json
    labels_dir = get_labels_dir()
    labels_dir.mkdir(parents=True, exist_ok=True)
    target_path = labels_dir / f"{clip_id}.json"
    tmp_path = labels_dir / f".{clip_id}.json.tmp"

    label_data = label.model_dump()
    with open(tmp_path, "w", encoding="utf-8") as tf:
        json.dump(label_data, tf, indent=2)

    os.replace(tmp_path, target_path)

    # Append to audit log in configured labels_dir
    audit_file = labels_dir / "_audit.jsonl"
    audit_entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "clip_id": clip_id,
        "annotator": label.annotator,
        "action": "save",
        "status": label.status,
    }
    with open(audit_file, "a", encoding="utf-8") as af:
        af.write(json.dumps(audit_entry) + "\n")

    return {"status": "ok", "label": label_data}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8765, reload=True)
