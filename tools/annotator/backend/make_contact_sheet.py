#!/usr/bin/env python3
"""
Generates contact sheets for cricket delivery clips listed in manifest.json.
Layout: 3 columns x 5 rows = 15 clips per sheet (1800x1200 px).
Each cell: [frame 0 thumbnail 384x216 | ball crop 216x216]
           [24 px caption strip below: "clip_id | ball_type or N/A | frame_count | results yes/no"]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np


def find_repo_root() -> Path:
    """Locate the root of the repository containing backend/ and tools/."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "backend").is_dir() and (current / "tools").is_dir():
            return current
        current = current.parent
    return Path.cwd().resolve()


def decode_clip_frames(
    video_path: Path,
    target_bounce_frame: Optional[int],
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Sequentially decodes video frames without seeking to extract:
    1. Frame 0
    2. Frame target_bounce_frame (if target_bounce_frame is specified)
    """
    if not video_path.is_file():
        return None, None

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None, None

    frame0: Optional[np.ndarray] = None
    bounce_frame: Optional[np.ndarray] = None
    current_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if current_idx == 0:
            frame0 = frame.copy()

        if target_bounce_frame is not None and current_idx == target_bounce_frame:
            bounce_frame = frame.copy()
            break

        current_idx += 1
        # If no bounce frame was requested, stop immediately after frame 0
        if target_bounce_frame is None and current_idx > 0:
            break

    cap.release()
    return frame0, bounce_frame


def build_cell(clip: Dict[str, Any], repo_root: Path) -> np.ndarray:
    """
    Constructs a 600x240 px cell for a single clip:
    - Upper (600x216): [frame 0 thumbnail 384x216 | ball crop 216x216]
    - Lower (600x24): caption strip
    """
    clip_id = clip.get("clip_id", "unknown")
    clip_path = clip.get("path", "")
    video_path = Path(clip_path)
    if not video_path.is_absolute():
        video_path = repo_root / video_path

    # Check results.json for bounce event
    results_path = video_path.parent / "results.json"
    bounce_data: Optional[Dict[str, Any]] = None

    if results_path.is_file():
        try:
            with open(results_path, "r", encoding="utf-8") as rf:
                rdata = json.load(rf)
                events = rdata.get("events") or {}
                b = events.get("bounce")
                if (
                    isinstance(b, dict)
                    and b.get("frame") is not None
                    and b.get("x") is not None
                    and b.get("y") is not None
                ):
                    bounce_data = b
        except Exception:
            bounce_data = None

    target_frame = int(bounce_data["frame"]) if bounce_data is not None else None

    # Sequential frame decode (no seeking)
    frame0, bounce_frame = decode_clip_frames(video_path, target_frame)

    # 1. Frame 0 thumbnail (384x216)
    if frame0 is not None:
        thumb = cv2.resize(frame0, (384, 216), interpolation=cv2.INTER_AREA)
    else:
        thumb = np.zeros((216, 384, 3), dtype=np.uint8)
        cv2.putText(
            thumb,
            "no video",
            (140, 115),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (150, 150, 150),
            1,
            cv2.LINE_AA,
        )

    # 2. Ball crop (216x216)
    ball_crop: np.ndarray
    if bounce_frame is not None and bounce_data is not None:
        fh, fw = bounce_frame.shape[:2]
        cx = int(round(float(bounce_data["x"])))
        cy = int(round(float(bounce_data["y"])))

        # 64x64 window centered on (cx, cy)
        x1 = cx - 32
        y1 = cy - 32
        x2 = x1 + 64
        y2 = y1 + 64

        # Clamp within image bounds
        if x1 < 0:
            x1 = 0
            x2 = min(fw, 64)
        if x2 > fw:
            x2 = fw
            x1 = max(0, fw - 64)
        if y1 < 0:
            y1 = 0
            y2 = min(fh, 64)
        if y2 > fh:
            y2 = fh
            y1 = max(0, fh - 64)

        crop = bounce_frame[y1:y2, x1:x2]
        if crop.size > 0:
            # Resize with nearest-neighbour
            ball_crop = cv2.resize(crop, (216, 216), interpolation=cv2.INTER_NEAREST)
        else:
            ball_crop = np.full((216, 216, 3), 70, dtype=np.uint8)
            cv2.putText(
                ball_crop,
                "no bounce",
                (55, 115),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (190, 190, 190),
                1,
                cv2.LINE_AA,
            )
    else:
        # Grey placeholder with text "no bounce"
        ball_crop = np.full((216, 216, 3), 70, dtype=np.uint8)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.55
        thickness = 1
        text = "no bounce"
        (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
        tx = (216 - tw) // 2
        ty = (216 + th) // 2
        cv2.putText(
            ball_crop,
            text,
            (tx, ty),
            font,
            font_scale,
            (190, 190, 190),
            thickness,
            cv2.LINE_AA,
        )

    # Upper strip: 384 + 216 = 600 width, 216 height
    upper = np.hstack([thumb, ball_crop])

    # 3. Caption strip (600x24)
    # Format: "clip_id | ball_type or N/A | frame_count | results yes/no"
    ball_type_str = clip.get("ball_type") or "N/A"
    frame_count_str = str(clip.get("frame_count", 0))
    results_str = "results yes" if clip.get("has_results") else "results no"
    caption_text = f"{clip_id} | {ball_type_str} | {frame_count_str} | {results_str}"

    caption_strip = np.full((24, 600, 3), (25, 25, 30), dtype=np.uint8)
    cv2.putText(
        caption_strip,
        caption_text,
        (10, 16),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (220, 220, 220),
        1,
        cv2.LINE_AA,
    )

    # Complete 600x240 cell
    cell = np.vstack([upper, caption_strip])
    return cell


def generate_contact_sheets(
    manifest_path: Path,
    output_dir: Path,
    repo_root: Optional[Path] = None,
) -> Tuple[int, float]:
    """
    Builds contact sheets (1800x1200 px, 3 cols x 5 rows = 15 clips per sheet).
    Returns (num_sheets, total_time_seconds).
    """
    t0 = time.time()

    if repo_root is None:
        repo_root = find_repo_root()

    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        clips: List[Dict[str, Any]] = json.load(f)

    # Sort clips by clip_id
    sorted_clips = sorted(clips, key=lambda c: str(c.get("clip_id", "")))

    output_dir.mkdir(parents=True, exist_ok=True)

    total_clips = len(sorted_clips)
    clips_per_sheet = 15
    num_sheets = math.ceil(total_clips / clips_per_sheet) if total_clips > 0 else 0

    for s_idx in range(num_sheets):
        sheet_clips = sorted_clips[s_idx * clips_per_sheet : (s_idx + 1) * clips_per_sheet]
        sheet = np.zeros((1200, 1800, 3), dtype=np.uint8)

        for i, clip in enumerate(sheet_clips):
            row = i // 3
            col = i % 3
            cell = build_cell(clip, repo_root)

            y1 = row * 240
            y2 = y1 + 240
            x1 = col * 600
            x2 = x1 + 600

            sheet[y1:y2, x1:x2] = cell

        out_name = f"sheet_{s_idx + 1:02d}.jpg"
        out_file = output_dir / out_name
        cv2.imwrite(str(out_file), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])

    elapsed = time.time() - t0
    return num_sheets, elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate annotator contact sheets")
    parser.add_argument(
        "--manifest",
        type=str,
        default="tools/annotator/manifest.json",
        help="Path to manifest.json (default: tools/annotator/manifest.json)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="tools/annotator/contact_sheets",
        help="Directory to save contact sheet JPEGs (default: tools/annotator/contact_sheets)",
    )
    args = parser.parse_args()

    repo_root = find_repo_root()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = repo_root / manifest_path

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    num_sheets, elapsed = generate_contact_sheets(manifest_path, output_dir, repo_root)
    print(f"Generated {num_sheets} contact sheet(s) in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
