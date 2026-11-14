"""Post-pass-1 flight-run release detector (`TRACKER_RELEASE_MODE=flight`).

Selects the release frame from per-frame YOLO ball detections after pass 1
using the R1 "flight run" rule: the first frame along the nearest-neighbour
ball track whose incoming step (if any) and next ``K`` consecutive steps are
all at most ``T`` multiples of the bowler-end crease width.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

# Chosen from Phase 1 rule search & LOO CV on release_dump_1:
# see eval/analysis/release_rules_release_dump_1.md
# (T=0.070 matches T=0.065 and T=0.075 identically across all 14 clips).
FLIGHT_RUN_K: int = 3
FLIGHT_RUN_T: float = 0.070


@dataclass(frozen=True)
class _TrackPoint:
    frame: int
    x: float
    y: float
    conf: float


def _crease_width_px(markers: Mapping[str, Sequence[float]]) -> Optional[float]:
    bowl_l = markers.get("bowl_L")
    bowl_r = markers.get("bowl_R")
    if bowl_l is None or bowl_r is None or len(bowl_l) < 2 or len(bowl_r) < 2:
        return None
    width = float(bowl_r[0]) - float(bowl_l[0])
    return width if width > 0.0 else None


def _build_track(detections_by_frame: Mapping[int, Sequence[Mapping[str, Any]]]) -> list[_TrackPoint]:
    track: list[_TrackPoint] = []
    for frame in sorted(detections_by_frame):
        balls = [
            d for d in detections_by_frame[frame]
            if d.get("class_name") == "ball"
        ]
        if not balls:
            continue
        candidates = [
            (
                0.5 * (float(d["x1"]) + float(d["x2"])),
                0.5 * (float(d["y1"]) + float(d["y2"])),
                float(d.get("conf", 0.0)),
            )
            for d in balls
        ]
        if not track:
            cx, cy, conf = max(candidates, key=lambda c: c[2])
        else:
            prev = track[-1]
            cx, cy, conf = min(
                candidates,
                key=lambda c: (math.hypot(c[0] - prev.x, c[1] - prev.y), -c[2]),
            )
        track.append(_TrackPoint(frame=int(frame), x=cx, y=cy, conf=conf))
    return track


def find_flight_release(
    detections_by_frame: Mapping[int, Sequence[Mapping[str, Any]]],
    markers: Mapping[str, Sequence[float]],
    *,
    k: int = FLIGHT_RUN_K,
    t: float = FLIGHT_RUN_T,
) -> Optional[Tuple[int, int, int]]:
    """Return ``(frame, x, y)`` for the first flight-run release, or ``None``.

    Normalises every step distance by ``bowl_R[0] - bowl_L[0]``. When no
    detection satisfies the incoming + ``k`` outgoing step threshold ``t``,
    returns ``None`` so the caller retains the streaming release.
    """
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    crease_w = _crease_width_px(markers)
    if crease_w is None:
        return None

    track = _build_track(detections_by_frame)
    if len(track) < k + 1:
        return None

    steps = [
        math.hypot(track[i + 1].x - track[i].x, track[i + 1].y - track[i].y) / crease_w
        for i in range(len(track) - 1)
    ]
    for i in range(len(track) - k):
        incoming_ok = i == 0 or steps[i - 1] <= t
        if incoming_ok and all(steps[j] <= t for j in range(i, i + k)):
            pt = track[i]
            return int(pt.frame), int(pt.x), int(pt.y)
    return None
