#!/usr/bin/env python3
"""
Scans CLIPS_ROOT (default backend/_tracker_work/jobs), sequentially decodes input.mp4
with OpenCV to obtain actual frame counts, detects any frame_count_mismatch, and writes
manifest.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import cv2

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.calib import fit_homography


def find_repo_root() -> Path:
    """Locate the root of the repository containing backend/ and tools/."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "backend").is_dir() and (current / "tools").is_dir():
            return current
        current = current.parent
    # Fallback to current working directory
    return Path.cwd().resolve()


def get_labels_dir(repo_root: Optional[Path] = None) -> Path:
    """Return configured labels directory from LABELS_DIR env or default to eval/labels."""
    if repo_root is None:
        repo_root = find_repo_root()
    env_dir = os.getenv("LABELS_DIR")
    if env_dir:
        p = Path(env_dir)
        return p if p.is_absolute() else (repo_root / p)
    return repo_root / "eval" / "labels"


def inspect_video(video_path: Path) -> tuple[int, int, float, int, int]:
    """
    Open video and sequentially decode every frame to find true decoded frame count.
    Returns: (decoded_count, cap_prop_count, fps, width, height)
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file: {video_path}")

    cap_prop_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)

    decoded_count = 0
    while True:
        ret, _ = cap.read()
        if not ret:
            break
        decoded_count += 1
    cap.release()

    return decoded_count, cap_prop_count, fps, width, height


def build_manifest_data(
    clips_root: Path,
    repo_root: Optional[Path] = None,
    eval_labels_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    if repo_root is None:
        repo_root = find_repo_root()
    if eval_labels_dir is None:
        eval_labels_dir = get_labels_dir(repo_root)

    manifest: List[Dict[str, Any]] = []

    if not clips_root.is_dir():
        print(f"Warning: clips_root does not exist: {clips_root}", file=sys.stderr)
        return manifest

    job_dirs = sorted([p for p in clips_root.iterdir() if p.is_dir()])

    for job_dir in job_dirs:
        clip_id = job_dir.name
        input_video = job_dir / "input.mp4"
        if not input_video.is_file():
            continue

        results_json = job_dir / "results.json"
        has_results = results_json.is_file()
        error_json = job_dir / "error.json"
        has_error = error_json.is_file()

        ball_type: Optional[str] = None
        has_calibration = False
        system_residual_px: Optional[float] = None
        res_frame_count: Optional[int] = None

        if has_results:
            try:
                with open(results_json, "r", encoding="utf-8") as rf:
                    res_data = json.load(rf)
                    ball_type = res_data.get("ball_type")
                    calib_dict = res_data.get("calibration")
                    has_calibration = bool(calib_dict)
                    if has_calibration and isinstance(calib_dict, dict):
                        try:
                            fit_res = fit_homography(calib_dict)
                            system_residual_px = round(float(fit_res.residual_px), 4)
                        except Exception:
                            pass
                    res_video = res_data.get("video", {})
                    res_frame_count = res_video.get("frame_count")
            except Exception as e:
                print(f"Error reading {results_json}: {e}", file=sys.stderr)

        decoded_count, cap_prop_count, fps, width, height = inspect_video(input_video)

        mismatch = False
        if decoded_count != cap_prop_count:
            mismatch = True
        if res_frame_count is not None and decoded_count != res_frame_count:
            mismatch = True

        # Check existing label in configured eval_labels_dir
        label_file = eval_labels_dir / f"{clip_id}.json"
        label_status = "none"
        split = None
        has_gt_calibration = False
        if label_file.is_file():
            try:
                with open(label_file, "r", encoding="utf-8") as lf:
                    ldata = json.load(lf)
                    label_status = ldata.get("status", "draft")
                    split = ldata.get("split")
                    has_gt_calibration = bool(ldata.get("calibration_gt"))
            except Exception:
                pass

        try:
            rel_path = input_video.relative_to(repo_root).as_posix()
        except ValueError:
            rel_path = input_video.as_posix()

        entry: Dict[str, Any] = {
            "clip_id": clip_id,
            "path": rel_path,
            "fps": fps,
            "frame_count": decoded_count,
            "width": width,
            "height": height,
            "ball_type": ball_type,
            "has_results": has_results,
            "has_calibration": has_calibration,
            "system_residual_px": system_residual_px,
            "has_gt_calibration": has_gt_calibration,
            "label_status": label_status,
            "split": split,
            "frame_count_mismatch": mismatch,
            "has_error": has_error,
        }
        manifest.append(entry)

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build annotator clips manifest")
    parser.add_argument(
        "--clips-root",
        type=str,
        default=os.getenv("CLIPS_ROOT", "backend/_tracker_work/jobs"),
        help="Root directory containing clip jobs (default: env CLIPS_ROOT or backend/_tracker_work/jobs)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="tools/annotator/manifest.json",
        help="Path to output manifest.json (default: tools/annotator/manifest.json)",
    )
    args = parser.parse_args()

    repo_root = find_repo_root()
    clips_root = Path(args.clips_root)
    if not clips_root.is_absolute():
        clips_root = repo_root / clips_root

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = repo_root / output_path

    print(f"Scanning clips from: {clips_root}")
    manifest = build_manifest_data(clips_root, repo_root=repo_root)
    print(f"Processed {len(manifest)} clips.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Manifest written to: {output_path}")


if __name__ == "__main__":
    main()
