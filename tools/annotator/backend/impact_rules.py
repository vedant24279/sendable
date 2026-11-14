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
I5_UP_VALUES: Tuple[float, ...] = (0.01, 0.02)
I5_THETA_VALUES: Tuple[float, ...] = (20.0, 30.0, 45.0)
I5_SPEED_RATIO: float = 0.6
I5_GATE_HALF_WIDTH_FRAC: float = 0.30
I5_GATE_ABOVE_FRAC: float = 0.35
I5_GATE_BELOW_FRAC: float = 0.05


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


def _get_batter_stump_xy_px(calib_points: Dict[str, Any]) -> Tuple[float, float]:
    stump = calib_points.get("bat_stump")
    if isinstance(stump, (list, tuple)) and len(stump) >= 2:
        sx = _safe_float(stump[0])
        sy = _safe_float(stump[1])
        if sx is not None and sy is not None:
            return (sx, sy)
    bat_l = calib_points.get("bat_L")
    bat_r = calib_points.get("bat_R")
    if (
        isinstance(bat_l, (list, tuple))
        and isinstance(bat_r, (list, tuple))
        and len(bat_l) >= 2
        and len(bat_r) >= 2
    ):
        xl = _safe_float(bat_l[0])
        yl = _safe_float(bat_l[1])
        xr = _safe_float(bat_r[0])
        yr = _safe_float(bat_r[1])
        if xl is not None and yl is not None and xr is not None and yr is not None:
            return (0.5 * (xl + xr), 0.5 * (yl + yr))
    raise ValueError("calibration points must contain bat_stump or bat_L/bat_R")


def _get_batter_stump_y_px(calib_points: Dict[str, Any]) -> float:
    return _get_batter_stump_xy_px(calib_points)[1]


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


def rule_i5_ascending_vertex(
    raw_dump: Dict[str, Any],
    calib_points: Dict[str, Any],
    *,
    up_frac: float = 0.01,
    theta_deg: float = 30.0,
    pick_max_turn: bool = False,
    use_spatial_gate: bool = True,
) -> Optional[Tuple[int, float, float]]:
    """I5/I6 post-bounce ascending vertex rule with optional batter-stump spatial gate."""
    bounce_f = _extract_bounce_frame(raw_dump)
    if bounce_f is None:
        return None
    track = build_track(raw_dump)
    if len(track) < 5:
        return None
    crease_w = get_bowler_crease_width_px(calib_points)
    steps = _build_steps(track, crease_w)

    if use_spatial_gate:
        stump_x, stump_y = _get_batter_stump_xy_px(calib_points)
        max_dx = I5_GATE_HALF_WIDTH_FRAC * crease_w
        min_y = stump_y - I5_GATE_ABOVE_FRAC * crease_w
        max_y = stump_y + I5_GATE_BELOW_FRAC * crease_w
    else:
        stump_x = 0.0
        max_dx = float("inf")
        min_y = float("-inf")
        max_y = float("inf")

    min_up_vy = -up_frac * crease_w
    candidates: List[Tuple[TrackPoint, float]] = []

    for i in range(2, len(track) - 2):
        pt = track[i]
        if pt.frame <= bounce_f:
            continue
        in_vx = 0.5 * (steps[i - 2].vx + steps[i - 1].vx)
        in_vy = 0.5 * (steps[i - 2].vy + steps[i - 1].vy)
        if in_vy > min_up_vy:
            continue

        out_vx = 0.5 * (steps[i].vx + steps[i + 1].vx)
        out_vy = 0.5 * (steps[i].vy + steps[i + 1].vy)
        turn_deg = vector_angle_diff_deg((in_vx, in_vy), (out_vx, out_vy))

        in_spd = 0.5 * (steps[i - 2].speed_norm + steps[i - 1].speed_norm)
        out_spd = 0.5 * (steps[i].speed_norm + steps[i + 1].speed_norm)
        speed_drop = in_spd > 1e-9 and out_spd <= I5_SPEED_RATIO * in_spd
        turns_enough = turn_deg is not None and turn_deg >= theta_deg
        if not (turns_enough or speed_drop):
            continue

        if use_spatial_gate:
            if abs(pt.x - stump_x) > max_dx or pt.y < min_y or pt.y > max_y:
                continue

        candidates.append((pt, turn_deg if turn_deg is not None else 0.0))

    if not candidates:
        return None
    if pick_max_turn:
        chosen = max(candidates, key=lambda item: item[1])[0]
    else:
        chosen = candidates[0][0]
    return chosen.as_tuple()


def rule_i5a_ascending_first(
    raw_dump: Dict[str, Any],
    calib_points: Dict[str, Any],
    *,
    up_frac: float,
    theta_deg: float,
) -> Optional[Tuple[int, float, float]]:
    """I5a: first ascending vertex inside batter-stump spatial gate."""
    return rule_i5_ascending_vertex(
        raw_dump,
        calib_points,
        up_frac=up_frac,
        theta_deg=theta_deg,
        pick_max_turn=False,
        use_spatial_gate=True,
    )


def rule_i5b_ascending_max_turn(
    raw_dump: Dict[str, Any],
    calib_points: Dict[str, Any],
    *,
    up_frac: float,
    theta_deg: float,
) -> Optional[Tuple[int, float, float]]:
    """I5b: largest-turn ascending vertex inside batter-stump spatial gate."""
    return rule_i5_ascending_vertex(
        raw_dump,
        calib_points,
        up_frac=up_frac,
        theta_deg=theta_deg,
        pick_max_turn=True,
        use_spatial_gate=True,
    )


def rule_i6a_ungated_first(
    raw_dump: Dict[str, Any],
    calib_points: Dict[str, Any],
    *,
    up_frac: float,
    theta_deg: float,
) -> Optional[Tuple[int, float, float]]:
    """I6a: first ascending vertex without spatial gate."""
    return rule_i5_ascending_vertex(
        raw_dump,
        calib_points,
        up_frac=up_frac,
        theta_deg=theta_deg,
        pick_max_turn=False,
        use_spatial_gate=False,
    )


def rule_i6b_ungated_max_turn(
    raw_dump: Dict[str, Any],
    calib_points: Dict[str, Any],
    *,
    up_frac: float,
    theta_deg: float,
) -> Optional[Tuple[int, float, float]]:
    """I6b: largest-turn ascending vertex without spatial gate."""
    return rule_i5_ascending_vertex(
        raw_dump,
        calib_points,
        up_frac=up_frac,
        theta_deg=theta_deg,
        pick_max_turn=True,
        use_spatial_gate=False,
    )
