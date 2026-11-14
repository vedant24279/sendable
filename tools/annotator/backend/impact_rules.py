"""Candidate impact detection rules evaluated on raw pass-1 ball dumps."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from release_rules import (
    TrackPoint,
    _safe_float,
    _safe_int,
    build_track,
    get_bowler_crease_width_px,
)
from trace_impact import vector_angle_diff_deg

I1_THETA_VALUES: Tuple[float, ...] = (20.0, 30.0, 45.0)
I2_WINDOW_MIN_OFFSET: int = 1
I2_WINDOW_MAX_OFFSET: int = 12
I3_SPEED_DROP_RATIO: float = 0.5
I4_WINDOW_MIN_OFFSET: int = 1
I4_WINDOW_MAX_OFFSET: int = 14
I4_BASE_DY_PX: float = 90.0
I4_REF_BOWL_CREASE_WIDTH_PX: float = 540.0


@dataclass(frozen=True)
class _Step:
    vx: float
    vy: float
    speed_norm: float


def _extract_bounce_frame(raw_dump: Dict[str, Any]) -> Optional[int]:
    sb = raw_dump.get("streaming_bounce")
    if not isinstance(sb, (list, tuple)) or not sb:
        return None
    return _safe_int(sb[0])


def _get_batter_stump_y_px(calib_points: Dict[str, Any]) -> float:
    stump = calib_points.get("bat_stump")
    if isinstance(stump, (list, tuple)) and len(stump) >= 2:
        val = _safe_float(stump[1])
        if val is not None:
            return val
    bat_l = calib_points.get("bat_L")
    bat_r = calib_points.get("bat_R")
    if (
        isinstance(bat_l, (list, tuple))
        and isinstance(bat_r, (list, tuple))
        and len(bat_l) >= 2
        and len(bat_r) >= 2
    ):
        yl = _safe_float(bat_l[1])
        yr = _safe_float(bat_r[1])
        if yl is not None and yr is not None:
            return 0.5 * (yl + yr)
    raise ValueError("calibration points must contain bat_stump or bat_L/bat_R")


def _build_steps(track: Sequence[TrackPoint], crease_width_px: float) -> List[_Step]:
    """Return list of N-1 steps where step[i] is transition track[i] -> track[i+1]."""
    steps: List[_Step] = []
    for i in range(len(track) - 1):
        p0 = track[i]
        p1 = track[i + 1]
        dt = max(1, p1.frame - p0.frame)
        vx = (p1.x - p0.x) / dt
        vy = (p1.y - p0.y) / dt
        spd = math.hypot(vx, vy) / crease_width_px
        steps.append(_Step(vx=vx, vy=vy, speed_norm=spd))
    return steps


def rule_i1_direction_change(
    raw_dump: Dict[str, Any],
    calib_points: Dict[str, Any],
    *,
    theta_deg: float,
) -> Optional[Tuple[int, float, float]]:
    """I1: first post-bounce frame where mean(prev 2 steps) vs next step >= theta_deg."""
    bounce_f = _extract_bounce_frame(raw_dump)
    if bounce_f is None:
        return None
    track = build_track(raw_dump)
    if len(track) < 4:
        return None
    crease_w = get_bowler_crease_width_px(calib_points)
    steps = _build_steps(track, crease_w)

    for i in range(2, len(track) - 1):
        pt = track[i]
        if pt.frame <= bounce_f:
            continue
        mean_prev = (
            0.5 * (steps[i - 2].vx + steps[i - 1].vx),
            0.5 * (steps[i - 2].vy + steps[i - 1].vy),
        )
        next_vec = (steps[i].vx, steps[i].vy)
        ang = vector_angle_diff_deg(mean_prev, next_vec)
        if ang is not None and ang >= theta_deg:
            return pt.as_tuple()
    return None


def rule_i2_max_turn(
    raw_dump: Dict[str, Any],
    calib_points: Dict[str, Any],
) -> Optional[Tuple[int, float, float]]:
    """I2: frame in [bounce+1, bounce+12] with largest incoming-vs-outgoing turn angle."""
    bounce_f = _extract_bounce_frame(raw_dump)
    if bounce_f is None:
        return None
    track = build_track(raw_dump)
    if len(track) < 3:
        return None
    crease_w = get_bowler_crease_width_px(calib_points)
    steps = _build_steps(track, crease_w)

    lo = bounce_f + I2_WINDOW_MIN_OFFSET
    hi = bounce_f + I2_WINDOW_MAX_OFFSET
    best_pt: Optional[TrackPoint] = None
    best_ang: Optional[float] = None
    for i in range(1, len(track) - 1):
        pt = track[i]
        if pt.frame < lo or pt.frame > hi:
            continue
        ang = vector_angle_diff_deg(
            (steps[i - 1].vx, steps[i - 1].vy),
            (steps[i].vx, steps[i].vy),
        )
        if ang is None:
            continue
        if best_ang is None or ang > best_ang:
            best_ang = ang
            best_pt = pt
    return best_pt.as_tuple() if best_pt is not None else None


def rule_i3_speed_drop(
    raw_dump: Dict[str, Any],
    calib_points: Dict[str, Any],
) -> Optional[Tuple[int, float, float]]:
    """I3: first post-bounce frame where next step <= 0.5*mean(prev 2) or dy flips sign."""
    bounce_f = _extract_bounce_frame(raw_dump)
    if bounce_f is None:
        return None
    track = build_track(raw_dump)
    if len(track) < 4:
        return None
    crease_w = get_bowler_crease_width_px(calib_points)
    steps = _build_steps(track, crease_w)

    for i in range(2, len(track) - 1):
        pt = track[i]
        if pt.frame <= bounce_f:
            continue
        mean_prev_spd = 0.5 * (steps[i - 2].speed_norm + steps[i - 1].speed_norm)
        spd_drop = (
            mean_prev_spd > 1e-9
            and steps[i].speed_norm <= I3_SPEED_DROP_RATIO * mean_prev_spd
        )
        vy_sign_flip = steps[i - 1].vy * steps[i].vy < 0.0
        if spd_drop or vy_sign_flip:
            return pt.as_tuple()
    return None


def rule_i4_last_seen(
    raw_dump: Dict[str, Any],
    calib_points: Dict[str, Any],
    *,
    plus_one: bool = True,
) -> Optional[Tuple[int, float, float]]:
    """I4: last detection in [bounce+1, bounce+14] near batter stump line (+1 or raw)."""
    bounce_f = _extract_bounce_frame(raw_dump)
    if bounce_f is None:
        return None
    track = build_track(raw_dump)
    if not track:
        return None
    crease_w = get_bowler_crease_width_px(calib_points)
    bat_stump_y = _get_batter_stump_y_px(calib_points)
    max_dy_px = I4_BASE_DY_PX * (crease_w / I4_REF_BOWL_CREASE_WIDTH_PX)

    lo = bounce_f + I4_WINDOW_MIN_OFFSET
    hi = bounce_f + I4_WINDOW_MAX_OFFSET
    chosen: Optional[TrackPoint] = None
    for pt in track:
        if pt.frame < lo or pt.frame > hi:
            continue
        if abs(pt.y - bat_stump_y) <= max_dy_px:
            chosen = pt
    if chosen is None:
        return None
    out_frame = chosen.frame + 1 if plus_one else chosen.frame
    return (out_frame, chosen.x, chosen.y)
