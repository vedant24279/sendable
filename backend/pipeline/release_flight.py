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

K: int = FLIGHT_RUN_K
T: float = FLIGHT_RUN_T


@dataclass(frozen=True)
class _TrackPoint:
    frame: int
    x: float
    y: float
    conf: float


def _marker_x(marker: Any) -> Optional[float]:
    if marker is None:
        return None
    if isinstance(marker, Mapping):
        if "x" in marker and marker["x"] is not None:
            return float(marker["x"])
        return None
    if isinstance(marker, Sequence) and len(marker) >= 2:
        return float(marker[0])
    return None


def _crease_width_px(markers: Optional[Mapping[str, Any]]) -> Optional[float]:
    if not markers:
        return None
    bowl_l_x = _marker_x(markers.get("bowl_L"))
    bowl_r_x = _marker_x(markers.get("bowl_R"))
    if bowl_l_x is None or bowl_r_x is None:
        return None
    width = bowl_r_x - bowl_l_x
    return width if width > 0.0 else None


def _extract_candidates(
    dets: Sequence[Mapping[str, Any]],
) -> list[Tuple[float, float, float]]:
    candidates: list[Tuple[float, float, float]] = []
    for d in dets:
        cls_name = d.get("class_name")
        if cls_name is not None and cls_name != "ball":
            continue
        if "cx" in d and "cy" in d:
            cx = float(d["cx"])
            cy = float(d["cy"])
        elif "x1" in d and "y1" in d and "x2" in d and "y2" in d:
            cx = 0.5 * (float(d["x1"]) + float(d["x2"]))
            cy = 0.5 * (float(d["y1"]) + float(d["y2"]))
        else:
            continue
        conf = float(d.get("conf", 0.0))
        candidates.append((cx, cy, conf))
    return candidates


def _build_track(
    ball_by_frame: Mapping[int, Sequence[Mapping[str, Any]]],
) -> list[_TrackPoint]:
    track: list[_TrackPoint] = []
    for frame in sorted(ball_by_frame):
        candidates = _extract_candidates(ball_by_frame[frame])
        if not candidates:
            continue
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


def find_release_flight(
    ball_by_frame: Mapping[int, Sequence[Mapping[str, Any]]],
    markers: Optional[Mapping[str, Any]],
    *,
    k: int = FLIGHT_RUN_K,
    t: float = FLIGHT_RUN_T,
) -> Optional[Tuple[int, int, int]]:
    """Return ``(frame, x, y)`` for the first flight-run release, or ``None``.

    Normalises every step distance by ``bowl_R.x - bowl_L.x``. When no
    detection satisfies the incoming + ``k`` outgoing step threshold ``t``,
    returns ``None`` so the caller retains the streaming release.
    """
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    crease_w = _crease_width_px(markers)
    if crease_w is None:
        return None

    track = _build_track(ball_by_frame)
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


find_flight_release = find_release_flight
