"""Candidate release detection rules evaluated on raw pass-1 ball dumps."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

R1_K_VALUES: Tuple[int, ...] = (2, 3, 4)
R1_T_VALUES: Tuple[float, ...] = (0.045, 0.055, 0.065, 0.075)
R3_PREV_MIN_NORM: float = 0.07
R3_RATIO_MAX: float = 0.4
R4_ISOLATED_NORM: float = 0.15
R2_MAX_OFFSET_FRAMES: int = 8
R2_MIN_FOLLOWING_INCREASE: int = 2


@dataclass(frozen=True)
class TrackPoint:
    """One selected ball candidate on a frame."""

    frame: int
    x: float
    y: float
    conf: float

    def as_tuple(self) -> Tuple[int, float, float]:
        return (self.frame, self.x, self.y)


def _safe_int(val: Any) -> Optional[int]:
    if val is None or isinstance(val, bool):
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _safe_float(val: Any) -> Optional[float]:
    if val is None or isinstance(val, bool):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def get_bowler_crease_width_px(calib_points: Dict[str, Any]) -> float:
    """Return bowler-end crease width in px (bowl_R.x - bowl_L.x)."""
    bowl_l = calib_points.get("bowl_L")
    bowl_r = calib_points.get("bowl_R")
    if (
        not isinstance(bowl_l, (list, tuple))
        or not isinstance(bowl_r, (list, tuple))
        or len(bowl_l) < 2
        or len(bowl_r) < 2
    ):
        raise ValueError("calibration points must contain bowl_L and bowl_R [x, y]")
    width = float(bowl_r[0]) - float(bowl_l[0])
    if width <= 0.0:
        raise ValueError(f"Non-positive bowler crease width: {width}")
    return width


def build_track(raw_dump: Dict[str, Any]) -> List[TrackPoint]:
    """Build a 1-candidate-per-frame track sorted by frame.

    Picks the highest-confidence candidate on the first frame with detections,
    and on each subsequent frame picks the candidate nearest in Euclidean distance
    to the previously chosen point (breaking ties by higher confidence).
    """
    raw_ball = raw_dump.get("ball") or {}
    if not isinstance(raw_ball, dict):
        return []

    parsed_frames: List[Tuple[int, List[Tuple[float, float, float]]]] = []
    for raw_f, raw_cands in raw_ball.items():
        f_idx = _safe_int(raw_f)
        if f_idx is None or not isinstance(raw_cands, list):
            continue
        cands: List[Tuple[float, float, float]] = []
        for c in raw_cands:
            if not isinstance(c, dict):
                continue
            cx = _safe_float(c.get("cx"))
            cy = _safe_float(c.get("cy"))
            conf = _safe_float(c.get("conf"))
            if cx is None or cy is None:
                continue
            cands.append((cx, cy, conf if conf is not None else 0.0))
        if cands:
            parsed_frames.append((f_idx, cands))

    parsed_frames.sort(key=lambda item: item[0])
    if not parsed_frames:
        return []

    track: List[TrackPoint] = []
    first_f, first_cands = parsed_frames[0]
    best_first = max(first_cands, key=lambda c: c[2])
    track.append(TrackPoint(first_f, best_first[0], best_first[1], best_first[2]))

    for f_idx, cands in parsed_frames[1:]:
        prev = track[-1]
        best = min(
            cands,
            key=lambda c: (math.hypot(c[0] - prev.x, c[1] - prev.y), -c[2]),
        )
        track.append(TrackPoint(f_idx, best[0], best[1], best[2]))

    return track


def _normalised_steps(track: Sequence[TrackPoint], crease_width_px: float) -> List[Optional[float]]:
    """Return normalised incoming step distances aligned with `track` (index 0 is None)."""
    steps: List[Optional[float]] = [None]
    for i in range(1, len(track)):
        dist = math.hypot(track[i].x - track[i - 1].x, track[i].y - track[i - 1].y)
        steps.append(dist / crease_width_px)
    return steps


def rule_r0_streaming(
    raw_dump: Dict[str, Any],
    calib_points: Dict[str, Any],
) -> Optional[Tuple[int, float, float]]:
    """R0: baseline streaming_release recorded in raw_ball_detections.json."""
    _ = calib_points
    sr = raw_dump.get("streaming_release")
    if not isinstance(sr, dict):
        return None
    f_idx = _safe_int(sr.get("frame"))
    x = _safe_float(sr.get("x"))
    y = _safe_float(sr.get("y"))
    if f_idx is None or x is None or y is None:
        return None
    return (f_idx, x, y)


def _apply_r1_on_track(
    track: Sequence[TrackPoint],
    crease_width_px: float,
    *,
    k: int,
    t: float,
) -> Optional[Tuple[int, float, float]]:
    if not track:
        return None
    steps = _normalised_steps(track, crease_width_px)
    n = len(track)
    for i in range(n):
        if i + k >= n:
            continue
        if i > 0:
            inc = steps[i]
            if inc is None or inc > t:
                continue
        if all((steps[i + m] is not None and steps[i + m] <= t) for m in range(1, k + 1)):
            return track[i].as_tuple()
    return track[0].as_tuple()


def rule_r1_flight_run(
    raw_dump: Dict[str, Any],
    calib_points: Dict[str, Any],
    *,
    k: int,
    t: float,
) -> Optional[Tuple[int, float, float]]:
    """R1: first detection with incoming <= T (if any) and next K steps <= T."""
    track = build_track(raw_dump)
    if not track:
        return None
    crease_w = get_bowler_crease_width_px(calib_points)
    return _apply_r1_on_track(track, crease_w, k=k, t=t)


def rule_r2_apex(
    raw_dump: Dict[str, Any],
    calib_points: Dict[str, Any],
) -> Optional[Tuple[int, float, float]]:
    """R2: min cy within first +8 frames where cy increases over >= 2 following detections."""
    _ = calib_points
    track = build_track(raw_dump)
    if not track:
        return None
    f_limit = track[0].frame + R2_MAX_OFFSET_FRAMES
    best_pt: Optional[TrackPoint] = None
    n = len(track)
    for i in range(n):
        pt = track[i]
        if pt.frame > f_limit:
            break
        if i + R2_MIN_FOLLOWING_INCREASE >= n:
            continue
        strictly_increasing = all(
            track[i + m].y > track[i + m - 1].y
            for m in range(1, R2_MIN_FOLLOWING_INCREASE + 1)
        )
        if not strictly_increasing:
            continue
        if best_pt is None or pt.y < best_pt.y:
            best_pt = pt
    return best_pt.as_tuple() if best_pt is not None else track[0].as_tuple()


def rule_r3_deceleration(
    raw_dump: Dict[str, Any],
    calib_points: Dict[str, Any],
) -> Optional[Tuple[int, float, float]]:
    """R3: first detection whose incoming step <= 0.4 * prev_step with prev_step >= 0.07."""
    track = build_track(raw_dump)
    if not track:
        return None
    crease_w = get_bowler_crease_width_px(calib_points)
    steps = _normalised_steps(track, crease_w)
    for i in range(2, len(track)):
        prev_step = steps[i - 1]
        curr_step = steps[i]
        if prev_step is None or curr_step is None:
            continue
        if prev_step >= R3_PREV_MIN_NORM and curr_step <= R3_RATIO_MAX * prev_step:
            return track[i].as_tuple()
    return track[0].as_tuple()


def rule_r4_filtered_flight_run(
    raw_dump: Dict[str, Any],
    calib_points: Dict[str, Any],
    *,
    k: int,
    t: float,
) -> Optional[Tuple[int, float, float]]:
    """R4: drop isolated points (both neighbour steps > 0.15 normalised), then apply R1."""
    track = build_track(raw_dump)
    if not track:
        return None
    crease_w = get_bowler_crease_width_px(calib_points)
    steps = _normalised_steps(track, crease_w)
    n = len(track)
    filtered: List[TrackPoint] = []
    for i, pt in enumerate(track):
        if 0 < i < n - 1:
            left = steps[i]
            right = steps[i + 1]
            if left is not None and right is not None and left > R4_ISOLATED_NORM and right > R4_ISOLATED_NORM:
                continue
        filtered.append(pt)
    if not filtered:
        return track[0].as_tuple()
    return _apply_r1_on_track(filtered, crease_w, k=k, t=t)
