"""Post-pass-1 ascending-vertex impact detector and post-impact track collector
(`TRACKER_IMPACT_MODE=vertex`).

Implements Rule I5b ("ascending vertex, bat-stump gated, max turn") and
post-impact nearest-neighbour point collection:
- see eval/analysis/impact_rules_release_dump_1.md
- see eval/analysis/post_impact_coverage_release_dump_1.md
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

# Chosen from Phase 1b rule search & LOO CV on release_dump_1:
# see eval/analysis/impact_rules_release_dump_1.md
UP: float = 0.01
THETA: float = 30.0
SPEED_RATIO: float = 0.6

# Bat-stump spatial gate (multiples of bowler-end crease width W):
STUMP_DX_MAX: float = 0.30
STUMP_DY_ABOVE_MAX: float = 0.35
STUMP_DY_BELOW_MAX: float = 0.05

# Post-impact continuation limits:
# see eval/analysis/post_impact_coverage_release_dump_1.md
POST_IMPACT_MAX_MISSING_FRAMES: int = 3
POST_IMPACT_MAX_STEP_W: float = 0.25


@dataclass(frozen=True)
class _TrackPoint:
    frame: int
    x: float
    y: float
    conf: float


@dataclass(frozen=True)
class _Step:
    vx: float
    vy: float
    speed_norm: float


def _marker_xy(marker: Any) -> Optional[Tuple[float, float]]:
    if marker is None:
        return None
    if isinstance(marker, Mapping):
        if "x" in marker and "y" in marker and marker["x"] is not None and marker["y"] is not None:
            return float(marker["x"]), float(marker["y"])
        return None
    if isinstance(marker, Sequence) and len(marker) >= 2:
        return float(marker[0]), float(marker[1])
    return None


def _crease_width_px(markers: Optional[Mapping[str, Any]]) -> Optional[float]:
    if not markers:
        return None
    bowl_l = _marker_xy(markers.get("bowl_L"))
    bowl_r = _marker_xy(markers.get("bowl_R"))
    if bowl_l is None or bowl_r is None:
        return None
    width = bowl_r[0] - bowl_l[0]
    return width if width > 0.0 else None


def _batter_stump_xy_px(markers: Optional[Mapping[str, Any]]) -> Optional[Tuple[float, float]]:
    if not markers:
        return None
    stump = _marker_xy(markers.get("bat_stump"))
    if stump is not None:
        return stump
    bat_l = _marker_xy(markers.get("bat_L"))
    bat_r = _marker_xy(markers.get("bat_R"))
    if bat_l is not None and bat_r is not None:
        return 0.5 * (bat_l[0] + bat_r[0]), 0.5 * (bat_l[1] + bat_r[1])
    return None


def _extract_candidates(
    dets: Sequence[Mapping[str, Any]],
) -> List[Tuple[float, float, float]]:
    candidates: List[Tuple[float, float, float]] = []
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
) -> List[_TrackPoint]:
    track: List[_TrackPoint] = []
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


def _build_steps(track: Sequence[_TrackPoint], crease_width_px: float) -> List[_Step]:
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


def _vector_angle_diff_deg(
    v1: Tuple[float, float],
    v2: Tuple[float, float],
) -> Optional[float]:
    m1 = math.hypot(v1[0], v1[1])
    m2 = math.hypot(v2[0], v2[1])
    if m1 <= 1e-9 or m2 <= 1e-9:
        return None
    a1 = math.degrees(math.atan2(v1[1], v1[0]))
    a2 = math.degrees(math.atan2(v2[1], v2[0]))
    return abs(((a2 - a1 + 180.0) % 360.0) - 180.0)


def find_impact_vertex(
    ball_by_frame: Mapping[int, Sequence[Mapping[str, Any]]],
    markers: Optional[Mapping[str, Any]],
    bounce_frame: Optional[int],
    *,
    up: float = UP,
    theta: float = THETA,
    speed_ratio: float = SPEED_RATIO,
) -> Optional[Dict[str, int]]:
    """Return ``{"frame": int, "x": int, "y": int}`` for the I5b ascending-vertex impact, or ``None``.

    Implements Rule I5b exactly as in ``tools/annotator/backend/impact_rules.py``:
    among post-bounce track vertices with at least 2 incoming and 2 outgoing steps
    that are ascending (``in_vy <= -up * W``), turn by ``>= theta`` degrees or slow
    down to ``<= speed_ratio * in_spd``, and lie inside the batter-stump spatial
    gate, returns the vertex with the largest direction change.
    """
    if bounce_frame is None or not markers or not ball_by_frame:
        return None
    crease_w = _crease_width_px(markers)
    bat_stump = _batter_stump_xy_px(markers)
    if crease_w is None or bat_stump is None:
        return None

    track = _build_track(ball_by_frame)
    if len(track) < 5:
        return None

    steps = _build_steps(track, crease_w)
    stump_x, stump_y = bat_stump
    max_dx = STUMP_DX_MAX * crease_w
    min_y = stump_y - STUMP_DY_ABOVE_MAX * crease_w
    max_y = stump_y + STUMP_DY_BELOW_MAX * crease_w
    min_up_vy = -up * crease_w

    b_frame = int(bounce_frame)
    candidates: List[Tuple[_TrackPoint, float]] = []

    for i in range(2, len(track) - 2):
        pt = track[i]
        if pt.frame <= b_frame:
            continue
        in_vx = 0.5 * (steps[i - 2].vx + steps[i - 1].vx)
        in_vy = 0.5 * (steps[i - 2].vy + steps[i - 1].vy)
        if in_vy > min_up_vy:
            continue

        out_vx = 0.5 * (steps[i].vx + steps[i + 1].vx)
        out_vy = 0.5 * (steps[i].vy + steps[i + 1].vy)
        turn_deg = _vector_angle_diff_deg((in_vx, in_vy), (out_vx, out_vy))

        in_spd = 0.5 * (steps[i - 2].speed_norm + steps[i - 1].speed_norm)
        out_spd = 0.5 * (steps[i].speed_norm + steps[i + 1].speed_norm)
        speed_drop = in_spd > 1e-9 and out_spd <= speed_ratio * in_spd
        turns_enough = turn_deg is not None and turn_deg >= theta
        if not (turns_enough or speed_drop):
            continue

        if abs(pt.x - stump_x) > max_dx or pt.y < min_y or pt.y > max_y:
            continue

        candidates.append((pt, turn_deg if turn_deg is not None else 0.0))

    if not candidates:
        return None

    chosen = max(candidates, key=lambda item: item[1])[0]
    return {
        "frame": int(chosen.frame),
        "x": int(round(chosen.x)),
        "y": int(round(chosen.y)),
    }


def find_post_impact_points(
    ball_by_frame: Mapping[int, Sequence[Mapping[str, Any]]],
    markers: Optional[Mapping[str, Any]],
    impact_frame: Optional[int],
    *,
    max_missing_frames: int = POST_IMPACT_MAX_MISSING_FRAMES,
    max_step_w: float = POST_IMPACT_MAX_STEP_W,
) -> List[Dict[str, Any]]:
    """Collect continuous nearest-to-previous track points after ``impact_frame``.

    Stops when a missing-frame gap exceeds ``max_missing_frames`` (default 3,
    i.e. ``f - prev_f > 4``) or the Euclidean step distance exceeds
    ``max_step_w * W`` (default ``0.25 * W``).
    Returns ``[{"frame": int, "x": int, "y": int, "conf": float}]``.
    """
    if impact_frame is None or not markers or not ball_by_frame:
        return []
    crease_w = _crease_width_px(markers)
    if crease_w is None:
        return []

    track = _build_track(ball_by_frame)
    if not track:
        return []

    imp_f = int(impact_frame)
    anchor: Optional[_TrackPoint] = None
    start_idx = 0
    for idx, pt in enumerate(track):
        if pt.frame <= imp_f:
            anchor = pt
            start_idx = idx + 1
        else:
            break

    out: List[Dict[str, Any]] = []
    prev_pt: Optional[_TrackPoint] = anchor
    prev_frame: int = anchor.frame if anchor is not None else imp_f

    for pt in track[start_idx:]:
        missing_frames = pt.frame - prev_frame - 1
        if missing_frames > max_missing_frames:
            break
        if prev_pt is not None:
            step_dist = math.hypot(pt.x - prev_pt.x, pt.y - prev_pt.y)
            if step_dist > max_step_w * crease_w:
                break
        out.append(
            {
                "frame": int(pt.frame),
                "x": int(round(pt.x)),
                "y": int(round(pt.y)),
                "conf": round(float(pt.conf), 4),
            }
        )
        prev_pt = pt
        prev_frame = pt.frame

    return out
