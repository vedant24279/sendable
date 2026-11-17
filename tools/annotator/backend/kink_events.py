"""Evaluate piecewise Huber curve fits for bounce and impact vs detection recall.

Reads final labels (`eval/labels/*.json`), pass-1 raw ball dumps
(`eval/runs/<run>/<clip>/raw_ball_detections.json`), and v2 pipeline outputs
(`eval/runs/<run>/<clip>/results.json`), then writes:
  - eval/analysis/kink_events_<run>.md
  - eval/analysis/kink_events_<run>.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import least_squares

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from impact_rules import rule_i5b_ascending_max_turn  # noqa: E402
from release_rules import TrackPoint, _safe_float, _safe_int, build_track  # noqa: E402
from scoring import _median_and_p90  # noqa: E402

DEFAULT_HUBER_F_SCALE: float = 2.0
SEARCH_HALF_WINDOW: float = 3.0
SEARCH_STEP_FRAME: float = 0.05
OUTGOING_POST_IMPACT_FRAMES: int = 6
GAP_K_VALUES: Tuple[int, ...] = (0, 2, 3, 5)
I5B_UP_FRAC: float = 0.01
I5B_THETA_DEG: float = 30.0


# ── Fitting primitives ──────────────────────────────────────────────────────
def _eval_poly(dt: np.ndarray | float, coeffs: np.ndarray) -> np.ndarray | float:
    out = np.zeros_like(dt, dtype=np.float64) if isinstance(dt, np.ndarray) else 0.0
    for power, c in enumerate(coeffs):
        out = out + float(c) * (dt ** power)
    return out


def fit_poly_huber(
    ts: Sequence[float],
    vs: Sequence[float],
    degree: int,
    *,
    f_scale: float = DEFAULT_HUBER_F_SCALE,
) -> Optional[Tuple[float, np.ndarray]]:
    """Fit `v(t) = sum_{p=0..degree} c_p (t - t_ref)^p` using Huber loss.

    Returns `(t_ref, coeffs_low_to_high)` or None if fewer than `degree + 1` points
    or degenerate time span.
    """
    if len(ts) < degree + 1 or len(ts) != len(vs):
        return None
    t_arr = np.asarray(ts, dtype=np.float64)
    v_arr = np.asarray(vs, dtype=np.float64)
    if len(np.unique(t_arr)) < degree + 1:
        return None

    t_ref = 0.5 * float(t_arr.min() + t_arr.max())
    dt = t_arr - t_ref

    # Least-squares polynomial seed in centered coordinates (high-to-low from polyfit).
    c_init = np.polyfit(dt, v_arr, degree)[::-1].astype(np.float64)
    if not np.all(np.isfinite(c_init)):
        return None

    res = least_squares(
        lambda c: _eval_poly(dt, c) - v_arr,
        c_init,
        loss="huber",
        f_scale=f_scale,
    )
    if not np.all(np.isfinite(res.x)):
        return None
    return t_ref, res.x.astype(np.float64)


def fit_segment_2d(
    pts: Sequence[TrackPoint],
    *,
    y_degree: int,
    f_scale: float = DEFAULT_HUBER_F_SCALE,
) -> Optional[Tuple[Tuple[float, np.ndarray], Tuple[float, np.ndarray]]]:
    """Fit x(t) linearly and y(t) with `y_degree` (1 or 2) using Huber loss."""
    ts = [float(p.frame) for p in pts]
    xs = [float(p.x) for p in pts]
    ys = [float(p.y) for p in pts]
    fx = fit_poly_huber(ts, xs, 1, f_scale=f_scale)
    fy = fit_poly_huber(ts, ys, y_degree, f_scale=f_scale)
    if fx is None or fy is None:
        return None
    return fx, fy


def _eval_segment_2d(
    fit: Tuple[Tuple[float, np.ndarray], Tuple[float, np.ndarray]],
    t: float,
) -> Tuple[float, float]:
    (tx, cx), (ty, cy) = fit
    return float(_eval_poly(t - tx, cx)), float(_eval_poly(t - ty, cy))


def find_closest_approach(
    fit_a: Tuple[Tuple[float, np.ndarray], Tuple[float, np.ndarray]],
    fit_b: Tuple[Tuple[float, np.ndarray], Tuple[float, np.ndarray]],
    t_center: float,
    *,
    half_window: float = SEARCH_HALF_WINDOW,
    step: float = SEARCH_STEP_FRAME,
) -> Tuple[float, float, float, float]:
    """Minimize distance between two fitted 2D curves on `[t_center - half_window, t_center + half_window]`.

    Returns `(t_best, mid_x, mid_y, min_dist_px)`.
    """
    n_steps = int(round((2.0 * half_window) / step))
    best: Optional[Tuple[float, float, float, float]] = None
    for i in range(n_steps + 1):
        t = (t_center - half_window) + i * step
        ax, ay = _eval_segment_2d(fit_a, t)
        bx, by = _eval_segment_2d(fit_b, t)
        d = math.hypot(ax - bx, ay - by)
        if best is None or d < best[3]:
            best = (round(t, 4), 0.5 * (ax + bx), 0.5 * (ay + by), d)
    assert best is not None
    return best


# ── Segment selection & event fits ──────────────────────────────────────────
def _points_in_range(
    track_by_frame: Mapping[int, TrackPoint],
    lo: int,
    hi: int,
) -> List[TrackPoint]:
    if hi < lo:
        return []
    return [track_by_frame[f] for f in range(lo, hi + 1) if f in track_by_frame]


def _fit_post_bounce_segment(
    track_by_frame: Mapping[int, TrackPoint],
    bnc_f: int,
    post_hi: int,
    *,
    f_scale: float = DEFAULT_HUBER_F_SCALE,
) -> Optional[Tuple[Tuple[float, np.ndarray], Tuple[float, np.ndarray]]]:
    pts = _points_in_range(track_by_frame, bnc_f + 1, post_hi)
    if len(pts) < 2:
        return None
    y_deg = 1 if len(pts) < 5 else 2
    return fit_segment_2d(pts, y_degree=y_deg, f_scale=f_scale)


def fit_bounce_kink(
    track_by_frame: Mapping[int, TrackPoint],
    lbl_rel_f: Optional[int],
    lbl_bnc_f: Optional[int],
    lbl_imp_f: Optional[int],
    lbl_last_vis_f: Optional[int],
    *,
    f_scale: float = DEFAULT_HUBER_F_SCALE,
) -> Optional[Dict[str, Any]]:
    """2b: Fit pre-bounce (release+1 .. bounce-1) vs post-bounce (bounce+1 .. impact-1)."""
    if lbl_rel_f is None or lbl_bnc_f is None:
        return None
    post_hi = (lbl_imp_f - 1) if lbl_imp_f is not None else lbl_last_vis_f
    if post_hi is None:
        return None

    pre_pts = _points_in_range(track_by_frame, lbl_rel_f + 1, lbl_bnc_f - 1)
    fit_pre = fit_segment_2d(pre_pts, y_degree=2, f_scale=f_scale)
    fit_post = _fit_post_bounce_segment(track_by_frame, lbl_bnc_f, post_hi, f_scale=f_scale)
    if fit_pre is None or fit_post is None:
        return None

    t_b, x_b, y_b, gap_px = find_closest_approach(fit_pre, fit_post, float(lbl_bnc_f))
    return {
        "t": t_b,
        "x": x_b,
        "y": y_b,
        "fit_gap_px": gap_px,
        "n_pre": len(pre_pts),
        "n_post": len(_points_in_range(track_by_frame, lbl_bnc_f + 1, post_hi)),
    }


def fit_impact_kink(
    track_by_frame: Mapping[int, TrackPoint],
    lbl_bnc_f: Optional[int],
    lbl_imp_f: Optional[int],
    *,
    f_scale: float = DEFAULT_HUBER_F_SCALE,
) -> Optional[Dict[str, Any]]:
    """2c: Fit post-bounce segment vs outgoing segment (impact+1 .. impact+6)."""
    if lbl_bnc_f is None or lbl_imp_f is None:
        return None
    fit_in = _fit_post_bounce_segment(track_by_frame, lbl_bnc_f, lbl_imp_f - 1, f_scale=f_scale)
    out_pts = _points_in_range(
        track_by_frame, lbl_imp_f + 1, lbl_imp_f + OUTGOING_POST_IMPACT_FRAMES
    )
    fit_out = fit_segment_2d(out_pts, y_degree=1, f_scale=f_scale)
    if fit_in is None or fit_out is None:
        return None

    t_i, x_i, y_i, gap_px = find_closest_approach(fit_in, fit_out, float(lbl_imp_f))
    return {
        "t": t_i,
        "x": x_i,
        "y": y_i,
        "fit_gap_px": gap_px,
        "n_in": len(_points_in_range(track_by_frame, lbl_bnc_f + 1, lbl_imp_f - 1)),
        "n_out": len(out_pts),
    }


# ── Recall & gap helpers ────────────────────────────────────────────────────
def longest_missing_gap(present_frames: set[int], lo: int, hi: int) -> int:
    """Maximum consecutive frames in `[lo, hi]` with no detection."""
    if hi < lo:
        return 0
    best = 0
    cur = 0
    for f in range(lo, hi + 1):
        if f in present_frames:
            cur = 0
        else:
            cur += 1
            if cur > best:
                best = cur
    return best


def compute_recall_metrics(
    track_by_frame: Mapping[int, TrackPoint],
    lbl_rel_f: Optional[int],
    lbl_bnc_f: Optional[int],
    lbl_imp_f: Optional[int],
    lbl_last_vis_f: Optional[int],
) -> Dict[str, Any]:
    """2a: detection recall over [release, last_visible], split before/after impact, plus longest gaps."""
    present = set(track_by_frame.keys())
    if lbl_rel_f is None or lbl_last_vis_f is None or lbl_last_vis_f < lbl_rel_f:
        return {
            "det_overall": 0,
            "tot_overall": 0,
            "recall_overall": None,
            "det_before_imp": None,
            "tot_before_imp": None,
            "recall_before_imp": None,
            "det_after_imp": None,
            "tot_after_imp": None,
            "recall_after_imp": None,
            "gap_overall": None,
            "gap_bnc_win": None,
            "gap_imp_win": None,
        }

    tot_overall = lbl_last_vis_f - lbl_rel_f + 1
    det_overall = sum(1 for f in range(lbl_rel_f, lbl_last_vis_f + 1) if f in present)
    gap_overall = longest_missing_gap(present, lbl_rel_f, lbl_last_vis_f)

    det_before: Optional[int] = None
    tot_before: Optional[int] = None
    rec_before: Optional[float] = None
    det_after: Optional[int] = None
    tot_after: Optional[int] = None
    rec_after: Optional[float] = None
    if lbl_imp_f is not None:
        b_hi = min(lbl_imp_f, lbl_last_vis_f)
        tot_before = max(0, b_hi - lbl_rel_f + 1)
        det_before = sum(1 for f in range(lbl_rel_f, b_hi + 1) if f in present)
        rec_before = (det_before / tot_before) if tot_before > 0 else None

        a_lo = lbl_imp_f + 1
        tot_after = max(0, lbl_last_vis_f - a_lo + 1)
        det_after = sum(1 for f in range(a_lo, lbl_last_vis_f + 1) if f in present)
        rec_after = (det_after / tot_after) if tot_after > 0 else None

    gap_bnc = (
        longest_missing_gap(present, max(0, lbl_bnc_f - 3), lbl_bnc_f + 3)
        if lbl_bnc_f is not None
        else None
    )
    gap_imp = (
        longest_missing_gap(present, max(0, lbl_imp_f - 3), lbl_imp_f + 3)
        if lbl_imp_f is not None
        else None
    )

    return {
        "det_overall": det_overall,
        "tot_overall": tot_overall,
        "recall_overall": det_overall / tot_overall,
        "det_before_imp": det_before,
        "tot_before_imp": tot_before,
        "recall_before_imp": rec_before,
        "det_after_imp": det_after,
        "tot_after_imp": tot_after,
        "recall_after_imp": rec_after,
        "gap_overall": gap_overall,
        "gap_bnc_win": gap_bnc,
        "gap_imp_win": gap_imp,
    }


# ── Gap deletion & vertex-rule check (2e) ───────────────────────────────────
def deleted_window_frames(center_frame: int, k: int) -> set[int]:
    """Return `k` consecutive frame indices centred on `center_frame`."""
    if k <= 0:
        return set()
    start = center_frame - (k // 2)
    return {start + i for i in range(k)}


def delete_frames_from_dump(
    raw_dump: Mapping[str, Any],
    frames_to_delete: Iterable[int],
    *,
    bounce_frame_override: Optional[int] = None,
) -> Dict[str, Any]:
    """Return a copy of `raw_dump` with `frames_to_delete` omitted from `ball`."""
    drop = {str(int(f)) for f in frames_to_delete}
    raw_ball = raw_dump.get("ball") or {}
    new_ball = {
        k: v for k, v in raw_ball.items() if str(k) not in drop
    }
    out = dict(raw_dump)
    out["ball"] = new_ball
    if bounce_frame_override is not None:
        out["streaming_bounce"] = [int(bounce_frame_override), 0.0, 0.0]
    return out


# ── Aggregation helpers ─────────────────────────────────────────────────────
def _summarize_errors(
    abs_time_errs: Sequence[Optional[float]],
    px_errs: Sequence[Optional[float]],
    total_n: int,
) -> Dict[str, Any]:
    valid_t = [float(e) for e in abs_time_errs if e is not None]
    valid_px = [float(e) for e in px_errs if e is not None]
    n_found = len(valid_t)
    t_med, t_p90 = _median_and_p90(valid_t)
    px_med, px_p90 = _median_and_p90(valid_px)
    return {
        "n_total": total_n,
        "n_found": n_found,
        "found_rate": (n_found / total_n) if total_n > 0 else None,
        "t_med": t_med,
        "t_p90": t_p90,
        "px_med": px_med,
        "px_p90": px_p90,
        "share_05": (sum(1 for e in valid_t if e <= 0.5 + 1e-9) / n_found) if n_found else None,
        "share_10": (sum(1 for e in valid_t if e <= 1.0 + 1e-9) / n_found) if n_found else None,
        "share_20": (sum(1 for e in valid_t if e <= 2.0 + 1e-9) / n_found) if n_found else None,
    }


def _extract_sys_bounce_centre(
    results: Mapping[str, Any],
    track_by_frame: Mapping[int, TrackPoint],
) -> Optional[Tuple[int, float, float]]:
    bnc = (results.get("events") or {}).get("bounce")
    if not isinstance(bnc, dict):
        return None
    bf = _safe_int(bnc.get("frame"))
    if bf is None:
        return None
    for pt in results.get("trajectory") or []:
        if isinstance(pt, dict) and not pt.get("interpolated") and _safe_int(pt.get("frame")) == bf:
            px = _safe_float(pt.get("x"))
            py = _safe_float(pt.get("y"))
            if px is not None and py is not None:
                return (bf, px, py)
    if bf in track_by_frame:
        tp = track_by_frame[bf]
        return (bf, tp.x, tp.y)
    bx = _safe_float(bnc.get("x"))
    by = _safe_float(bnc.get("y"))
    if bx is not None and by is not None:
        return (bf, bx, by)
    return None


def _extract_sys_impact(results: Mapping[str, Any]) -> Optional[Tuple[int, float, float]]:
    imp = (results.get("events") or {}).get("impact")
    if not isinstance(imp, dict):
        return None
    f = _safe_int(imp.get("frame"))
    x = _safe_float(imp.get("x"))
    y = _safe_float(imp.get("y"))
    if f is None or x is None or y is None:
        return None
    return (f, x, y)


# ── Dataset evaluation ──────────────────────────────────────────────────────
def evaluate_clip(
    label: Mapping[str, Any],
    raw_dump: Mapping[str, Any],
    results: Mapping[str, Any],
) -> Dict[str, Any]:
    """Compute recall, bounce/impact kink fits vs system v2, and gap-deletion sweeps for one clip."""
    clip_id = str(label.get("clip_id", "unknown"))
    colour = str(label.get("ball_colour") or "unknown").lower()
    calib_pts = (label.get("calibration_gt") or {}).get("points") or {}

    lbl_rel = label.get("release") or {}
    lbl_bnc = label.get("bounce") or {}
    lbl_imp = label.get("impact") or {}
    lbl_rel_f = _safe_int(lbl_rel.get("frame"))
    lbl_bnc_f = _safe_int(lbl_bnc.get("frame"))
    lbl_bnc_x = _safe_float(lbl_bnc.get("x"))
    lbl_bnc_y = _safe_float(lbl_bnc.get("y"))
    lbl_imp_type = str(lbl_imp.get("type") or "none").lower()
    lbl_imp_f = _safe_int(lbl_imp.get("frame"))
    lbl_imp_x = _safe_float(lbl_imp.get("x"))
    lbl_imp_y = _safe_float(lbl_imp.get("y"))
    lbl_last_vis_f = _safe_int(label.get("last_visible_frame"))

    track = build_track(dict(raw_dump))
    track_by_frame = {pt.frame: pt for pt in track}

    recall = compute_recall_metrics(
        track_by_frame, lbl_rel_f, lbl_bnc_f, lbl_imp_f, lbl_last_vis_f
    )

    # Bounce fit vs system
    bnc_fit = fit_bounce_kink(
        track_by_frame, lbl_rel_f, lbl_bnc_f, lbl_imp_f, lbl_last_vis_f
    )
    bnc_fit_dt: Optional[float] = None
    bnc_fit_px: Optional[float] = None
    if bnc_fit is not None and lbl_bnc_f is not None and lbl_bnc_x is not None and lbl_bnc_y is not None:
        bnc_fit_dt = abs(bnc_fit["t"] - lbl_bnc_f)
        bnc_fit_px = math.hypot(bnc_fit["x"] - lbl_bnc_x, bnc_fit["y"] - lbl_bnc_y)

    sys_bnc = _extract_sys_bounce_centre(results, track_by_frame)
    bnc_sys_dt: Optional[float] = None
    bnc_sys_px: Optional[float] = None
    if sys_bnc is not None and lbl_bnc_f is not None and lbl_bnc_x is not None and lbl_bnc_y is not None:
        bnc_sys_dt = abs(float(sys_bnc[0] - lbl_bnc_f))
        bnc_sys_px = math.hypot(sys_bnc[1] - lbl_bnc_x, sys_bnc[2] - lbl_bnc_y)

    # Impact fit vs system
    has_lbl_imp = (
        lbl_imp_type != "none"
        and lbl_imp_f is not None
        and lbl_imp_x is not None
        and lbl_imp_y is not None
    )
    imp_fit = fit_impact_kink(track_by_frame, lbl_bnc_f, lbl_imp_f) if has_lbl_imp else None
    imp_fit_dt: Optional[float] = None
    imp_fit_px: Optional[float] = None
    if imp_fit is not None and lbl_imp_f is not None and lbl_imp_x is not None and lbl_imp_y is not None:
        imp_fit_dt = abs(imp_fit["t"] - lbl_imp_f)
        imp_fit_px = math.hypot(imp_fit["x"] - lbl_imp_x, imp_fit["y"] - lbl_imp_y)

    sys_imp = _extract_sys_impact(results)
    imp_sys_dt: Optional[float] = None
    imp_sys_px: Optional[float] = None
    if has_lbl_imp and sys_imp is not None and lbl_imp_f is not None and lbl_imp_x is not None and lbl_imp_y is not None:
        imp_sys_dt = abs(float(sys_imp[0] - lbl_imp_f))
        imp_sys_px = math.hypot(sys_imp[1] - lbl_imp_x, sys_imp[2] - lbl_imp_y)

    # Gap robustness (2e)
    bnc_gap_rows: Dict[int, Dict[str, Optional[float]]] = {}
    if lbl_bnc_f is not None and lbl_bnc_x is not None and lbl_bnc_y is not None:
        for k in GAP_K_VALUES:
            drop = deleted_window_frames(lbl_bnc_f, k)
            reduced = {f: pt for f, pt in track_by_frame.items() if f not in drop}
            refit = fit_bounce_kink(reduced, lbl_rel_f, lbl_bnc_f, lbl_imp_f, lbl_last_vis_f)
            dt_err = abs(refit["t"] - lbl_bnc_f) if refit is not None else None
            px_err = (
                math.hypot(refit["x"] - lbl_bnc_x, refit["y"] - lbl_bnc_y)
                if refit is not None
                else None
            )
            # Current bounce frame treated as miss when its detection is deleted
            sys_miss = sys_bnc is None or (sys_bnc[0] not in reduced)
            bnc_gap_rows[k] = {
                "fit_dt": dt_err,
                "fit_px": px_err,
                "sys_dt": None if sys_miss else bnc_sys_dt,
                "sys_px": None if sys_miss else bnc_sys_px,
            }

    imp_gap_rows: Dict[int, Dict[str, Optional[float]]] = {}
    if has_lbl_imp and lbl_imp_f is not None and lbl_imp_x is not None and lbl_imp_y is not None:
        bnc_override = sys_bnc[0] if sys_bnc is not None else None
        for k in GAP_K_VALUES:
            drop = deleted_window_frames(lbl_imp_f, k)
            reduced = {f: pt for f, pt in track_by_frame.items() if f not in drop}
            refit = fit_impact_kink(reduced, lbl_bnc_f, lbl_imp_f)
            fit_dt = abs(refit["t"] - lbl_imp_f) if refit is not None else None
            fit_px = (
                math.hypot(refit["x"] - lbl_imp_x, refit["y"] - lbl_imp_y)
                if refit is not None
                else None
            )

            edited_dump = delete_frames_from_dump(
                raw_dump, drop, bounce_frame_override=bnc_override
            )
            try:
                v_pred = rule_i5b_ascending_max_turn(
                    edited_dump, calib_pts, up_frac=I5B_UP_FRAC, theta_deg=I5B_THETA_DEG
                )
            except ValueError:
                v_pred = None
            if v_pred is not None and int(v_pred[0]) in reduced:
                v_dt: Optional[float] = abs(float(v_pred[0] - lbl_imp_f))
                v_px: Optional[float] = math.hypot(v_pred[1] - lbl_imp_x, v_pred[2] - lbl_imp_y)
            else:
                v_dt = None
                v_px = None

            imp_gap_rows[k] = {
                "fit_dt": fit_dt,
                "fit_px": fit_px,
                "vertex_dt": v_dt,
                "vertex_px": v_px,
            }

    return {
        "clip_id": clip_id,
        "ball_colour": colour,
        "impact_type": lbl_imp_type,
        "lbl_rel_f": lbl_rel_f,
        "lbl_bnc_f": lbl_bnc_f,
        "lbl_imp_f": lbl_imp_f,
        "lbl_last_vis_f": lbl_last_vis_f,
        **recall,
        "bnc_fit_t": bnc_fit["t"] if bnc_fit else None,
        "bnc_fit_dt": bnc_fit_dt,
        "bnc_fit_px": bnc_fit_px,
        "bnc_fit_n_pre": bnc_fit["n_pre"] if bnc_fit else None,
        "bnc_fit_n_post": bnc_fit["n_post"] if bnc_fit else None,
        "bnc_sys_f": sys_bnc[0] if sys_bnc else None,
        "bnc_sys_dt": bnc_sys_dt,
        "bnc_sys_px": bnc_sys_px,
        "imp_fit_t": imp_fit["t"] if imp_fit else None,
        "imp_fit_dt": imp_fit_dt,
        "imp_fit_px": imp_fit_px,
        "imp_fit_n_in": imp_fit["n_in"] if imp_fit else None,
        "imp_fit_n_out": imp_fit["n_out"] if imp_fit else None,
        "imp_sys_f": sys_imp[0] if sys_imp else None,
        "imp_sys_dt": imp_sys_dt,
        "imp_sys_px": imp_sys_px,
        "sys_false_impact_on_none": (sys_imp is not None) if lbl_imp_type == "none" else None,
        "bnc_gaps": bnc_gap_rows,
        "imp_gaps": imp_gap_rows,
    }


def _fmt_f(val: Optional[float], digits: int = 2, suffix: str = "") -> str:
    if val is None or not math.isfinite(val):
        return "—"
    return f"{val:.{digits}f}{suffix}"


def _fmt_pct(val: Optional[float]) -> str:
    if val is None or not math.isfinite(val):
        return "—"
    return f"{val * 100:.1f}%"


def _summarize_recall_rows(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    det_all = sum(r["det_overall"] for r in rows)
    tot_all = sum(r["tot_overall"] for r in rows)
    det_bef = sum(r["det_before_imp"] for r in rows if r["det_before_imp"] is not None)
    tot_bef = sum(r["tot_before_imp"] for r in rows if r["tot_before_imp"] is not None)
    det_aft = sum(r["det_after_imp"] for r in rows if r["det_after_imp"] is not None)
    tot_aft = sum(r["tot_after_imp"] for r in rows if r["tot_after_imp"] is not None)

    g_all = [r["gap_overall"] for r in rows if r["gap_overall"] is not None]
    g_bnc = [r["gap_bnc_win"] for r in rows if r["gap_bnc_win"] is not None]
    g_imp = [r["gap_imp_win"] for r in rows if r["gap_imp_win"] is not None]
    return {
        "n_clips": len(rows),
        "recall_overall": (det_all / tot_all) if tot_all else None,
        "recall_before": (det_bef / tot_bef) if tot_bef else None,
        "recall_after": (det_aft / tot_aft) if tot_aft else None,
        "gap_all_med": float(np.median(g_all)) if g_all else None,
        "gap_all_max": int(max(g_all)) if g_all else None,
        "gap_bnc_med": float(np.median(g_bnc)) if g_bnc else None,
        "gap_bnc_max": int(max(g_bnc)) if g_bnc else None,
        "gap_imp_med": float(np.median(g_imp)) if g_imp else None,
        "gap_imp_max": int(max(g_imp)) if g_imp else None,
    }


def _summarize_csv(rows: Sequence[Mapping[str, Any]]) -> str:
    cols = [
        "clip_id", "ball_colour", "impact_type",
        "lbl_rel_f", "lbl_bnc_f", "lbl_imp_f", "lbl_last_vis_f",
        "recall_overall", "recall_before_imp", "recall_after_imp",
        "gap_overall", "gap_bnc_win", "gap_imp_win",
        "bnc_fit_t", "bnc_fit_dt", "bnc_fit_px", "bnc_sys_f", "bnc_sys_dt", "bnc_sys_px",
        "imp_fit_t", "imp_fit_dt", "imp_fit_px", "imp_sys_f", "imp_sys_dt", "imp_sys_px",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols)
    writer.writeheader()
    for r in rows:
        out_r = {}
        for c in cols:
            v = r.get(c)
            out_r[c] = f"{v:.4f}" if isinstance(v, float) else ("" if v is None else str(v))
        writer.writerow(out_r)
    return buf.getvalue()


def build_report(rows: Sequence[Dict[str, Any]], run_name: str, missing_dumps: Sequence[str]) -> str:
    """Format the full markdown report matching sections 2a-2e and 3."""
    lines: List[str] = [
        f"# Kink Events & Detection Recall Report: `{run_name}`",
        "",
        f"- **Clips analysed (with dump + results)**: `{len(rows)}`",
        f"- **Final clips skipped (missing dump/results)**: `{len(missing_dumps)}`"
        + (f" ({', '.join(missing_dumps)})" if missing_dumps else ""),
    ]

    # Counts by ball colour & impact type
    by_colour: Dict[str, int] = {}
    by_imp: Dict[str, int] = {}
    for r in rows:
        by_colour[r["ball_colour"]] = by_colour.get(r["ball_colour"], 0) + 1
        by_imp[r["impact_type"]] = by_imp.get(r["impact_type"], 0) + 1
    lines.append(
        "- **Counts by ball colour**: "
        + ", ".join(f"`{k}`={v}" for k, v in sorted(by_colour.items()))
    )
    lines.append(
        "- **Counts by impact type**: "
        + ", ".join(f"`{k}`={v}" for k, v in sorted(by_imp.items()))
    )
    lines.append("")

    # 1. Recall by colour
    lines.extend([
        "## 1. Detection Recall by Ball Colour",
        "",
        "| Ball Colour | n | Overall `[rel, last_vis]` | Before Impact | After Impact | Longest Gap Overall (med / max) | Gap `bnc±3` (med / max) | Gap `imp±3` (med / max) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for name, subset in [
        ("red", [r for r in rows if r["ball_colour"] == "red"]),
        ("pink", [r for r in rows if r["ball_colour"] == "pink"]),
        ("white", [r for r in rows if r["ball_colour"] == "white"]),
        ("ALL", list(rows)),
    ]:
        if not subset:
            continue
        s = _summarize_recall_rows(subset)
        lines.append(
            f"| `{name}` | {s['n_clips']} | {_fmt_pct(s['recall_overall'])} | "
            f"{_fmt_pct(s['recall_before'])} | {_fmt_pct(s['recall_after'])} | "
            f"{_fmt_f(s['gap_all_med'], 1)} / {s['gap_all_max'] if s['gap_all_max'] is not None else '—'} | "
            f"{_fmt_f(s['gap_bnc_med'], 1)} / {s['gap_bnc_max'] if s['gap_bnc_max'] is not None else '—'} | "
            f"{_fmt_f(s['gap_imp_med'], 1)} / {s['gap_imp_max'] if s['gap_imp_max'] is not None else '—'} |"
        )
    lines.append("")

    # 2. Bounce & Impact: Fit vs Current System
    lines.extend([
        "## 2. Bounce & Impact: Piecewise Huber Fit vs Current System (`results.json`)",
        "",
        "| Event (Slice) | Method | n | Found | Med `|Δt|` (f) | P90 `|Δt|` (f) | `≤0.5f` | `≤1f` | `≤2f` | Med Px | P90 Px |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])

    bnc_rows = [r for r in rows if r["lbl_bnc_f"] is not None]
    for label_slice, sub in [("Bounce (ALL)", bnc_rows), ("Bounce (red)", [r for r in bnc_rows if r["ball_colour"] == "red"]), ("Bounce (pink)", [r for r in bnc_rows if r["ball_colour"] == "pink"])]:
        if not sub:
            continue
        for mname, dt_key, px_key in [
            ("Kink fit", "bnc_fit_dt", "bnc_fit_px"),
            ("Current system", "bnc_sys_dt", "bnc_sys_px"),
        ]:
            st = _summarize_errors([r[dt_key] for r in sub], [r[px_key] for r in sub], len(sub))
            lines.append(
                f"| {label_slice} | {mname} | {st['n_total']} | {st['n_found']}/{st['n_total']} ({_fmt_pct(st['found_rate'])}) | "
                f"{_fmt_f(st['t_med'])} | {_fmt_f(st['t_p90'])} | "
                f"{_fmt_pct(st['share_05'])} | {_fmt_pct(st['share_10'])} | {_fmt_pct(st['share_20'])} | "
                f"{_fmt_f(st['px_med'], 1)} | {_fmt_f(st['px_p90'], 1)} |"
            )

    for label_slice, types in [
        ("Impact (`bat+pad`)", ("bat", "pad")),
        ("Impact (`bat`)", ("bat",)),
        ("Impact (`pad`)", ("pad",)),
        ("Impact (`stumps`)", ("stumps",)),
    ]:
        sub = [r for r in rows if r["impact_type"] in types and r["lbl_imp_f"] is not None]
        if not sub:
            continue
        for mname, dt_key, px_key in [
            ("Kink fit", "imp_fit_dt", "imp_fit_px"),
            ("Current system", "imp_sys_dt", "imp_sys_px"),
        ]:
            st = _summarize_errors([r[dt_key] for r in sub], [r[px_key] for r in sub], len(sub))
            lines.append(
                f"| {label_slice} | {mname} | {st['n_total']} | {st['n_found']}/{st['n_total']} ({_fmt_pct(st['found_rate'])}) | "
                f"{_fmt_f(st['t_med'])} | {_fmt_f(st['t_p90'])} | "
                f"{_fmt_pct(st['share_05'])} | {_fmt_pct(st['share_10'])} | {_fmt_pct(st['share_20'])} | "
                f"{_fmt_f(st['px_med'], 1)} | {_fmt_f(st['px_p90'], 1)} |"
            )

    none_rows = [r for r in rows if r["impact_type"] == "none"]
    if none_rows:
        fp = sum(1 for r in none_rows if r["sys_false_impact_on_none"])
        lines.append("")
        lines.append(
            f"- **Impact type `none`** (`n={len(none_rows)}`): no label impact event; current system emitted a false impact marker on `{fp}/{len(none_rows)}` clips."
        )
    lines.append("")

    # 3. Gap robustness (k = 0, 2, 3, 5)
    lines.extend([
        "## 3. Gap Robustness (`k` Consecutive Deleted Frames)",
        "",
        "| Event (Slice) | `k` | Method | n | Found | Med `|Δt|` (f) | P90 `|Δt|` (f) | Med Px | P90 Px |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for k in GAP_K_VALUES:
        sub_b = [r for r in bnc_rows if k in r["bnc_gaps"]]
        st_bf = _summarize_errors(
            [r["bnc_gaps"][k]["fit_dt"] for r in sub_b],
            [r["bnc_gaps"][k]["fit_px"] for r in sub_b],
            len(sub_b),
        )
        st_bs = _summarize_errors(
            [r["bnc_gaps"][k]["sys_dt"] for r in sub_b],
            [r["bnc_gaps"][k]["sys_px"] for r in sub_b],
            len(sub_b),
        )
        for mname, st in [("Kink fit", st_bf), ("Current frame surviving", st_bs)]:
            lines.append(
                f"| Bounce (ALL) | {k} | {mname} | {st['n_total']} | {st['n_found']}/{st['n_total']} ({_fmt_pct(st['found_rate'])}) | "
                f"{_fmt_f(st['t_med'])} | {_fmt_f(st['t_p90'])} | {_fmt_f(st['px_med'], 1)} | {_fmt_f(st['px_p90'], 1)} |"
            )

    bp_rows = [r for r in rows if r["impact_type"] in ("bat", "pad") and r["lbl_imp_f"] is not None]
    for k in GAP_K_VALUES:
        sub_i = [r for r in bp_rows if k in r["imp_gaps"]]
        st_if = _summarize_errors(
            [r["imp_gaps"][k]["fit_dt"] for r in sub_i],
            [r["imp_gaps"][k]["fit_px"] for r in sub_i],
            len(sub_i),
        )
        st_iv = _summarize_errors(
            [r["imp_gaps"][k]["vertex_dt"] for r in sub_i],
            [r["imp_gaps"][k]["vertex_px"] for r in sub_i],
            len(sub_i),
        )
        for mname, st in [("Kink fit", st_if), ("Current vertex rule (I5b)", st_iv)]:
            lines.append(
                f"| Impact (`bat+pad`) | {k} | {mname} | {st['n_total']} | {st['n_found']}/{st['n_total']} ({_fmt_pct(st['found_rate'])}) | "
                f"{_fmt_f(st['t_med'])} | {_fmt_f(st['t_p90'])} | {_fmt_f(st['px_med'], 1)} | {_fmt_f(st['px_p90'], 1)} |"
            )
    lines.append("")

    # 4. Worst clips (> 1 frame or > 15 px on bounce fit or impact fit)
    worst: List[Dict[str, Any]] = []
    for r in rows:
        b_bad = (r["bnc_fit_dt"] is not None and r["bnc_fit_dt"] > 1.0) or (
            r["bnc_fit_px"] is not None and r["bnc_fit_px"] > 15.0
        ) or (r["lbl_bnc_f"] is not None and r["bnc_fit_dt"] is None)
        i_bad = (r["imp_fit_dt"] is not None and r["imp_fit_dt"] > 1.0) or (
            r["imp_fit_px"] is not None and r["imp_fit_px"] > 15.0
        ) or (r["impact_type"] in ("bat", "pad", "stumps") and r["lbl_imp_f"] is not None and r["imp_fit_dt"] is None)
        if b_bad or i_bad:
            worst.append(r)

    lines.extend([
        "## 4. Clips Worse Than 1 Frame or 15 px (or Missed Fit)",
        "",
        f"Count: `{len(worst)}/{len(rows)}` clips.",
        "",
        "| Clip ID | Ball | Imp Type | Recall | Bnc Fit (`|Δt|` / px) | Bnc Sys (`|Δt|` / px) | Imp Fit (`|Δt|` / px) | Imp Sys (`|Δt|` / px) | Reason / Gaps |",
        "| --- | --- | --- | ---: | --- | --- | --- | --- | --- |",
    ])
    for r in worst:
        b_str = (
            "MISSED"
            if r["bnc_fit_dt"] is None
            else f"{_fmt_f(r['bnc_fit_dt'])}f / {_fmt_f(r['bnc_fit_px'], 1)}px"
        )
        bs_str = (
            "MISSED"
            if r["bnc_sys_dt"] is None
            else f"{_fmt_f(r['bnc_sys_dt'], 0)}f / {_fmt_f(r['bnc_sys_px'], 1)}px"
        )
        if r["impact_type"] == "none":
            i_str = "n/a"
            is_str = "FP" if r["sys_false_impact_on_none"] else "none"
        else:
            i_str = (
                "MISSED"
                if r["imp_fit_dt"] is None
                else f"{_fmt_f(r['imp_fit_dt'])}f / {_fmt_f(r['imp_fit_px'], 1)}px"
            )
            is_str = (
                "MISSED"
                if r["imp_sys_dt"] is None
                else f"{_fmt_f(r['imp_sys_dt'], 0)}f / {_fmt_f(r['imp_sys_px'], 1)}px"
            )
        reason = (
            f"gap_b={r['gap_bnc_win']}, gap_i={r['gap_imp_win']}, "
            f"pre={r['bnc_fit_n_pre']}, post={r['bnc_fit_n_post']}, out={r['imp_fit_n_out']}"
        )
        lines.append(
            f"| `{r['clip_id']}` | `{r['ball_colour']}` | `{r['impact_type']}` | "
            f"{_fmt_pct(r['recall_overall'])} | {b_str} | {bs_str} | {i_str} | {is_str} | {reason} |"
        )
    lines.append("")

    # 5. Per-clip table
    lines.extend([
        "## 5. Per-Clip Table",
        "",
        "| Clip ID | Ball | Imp Type | Recall (All / Bef / Aft) | Gaps (All / B±3 / I±3) | Bnc Fit (`|Δt|` / px) | Bnc Sys (`|Δt|` / px) | Imp Fit (`|Δt|` / px) | Imp Sys (`|Δt|` / px) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for r in rows:
        rec_s = f"{_fmt_pct(r['recall_overall'])} / {_fmt_pct(r['recall_before_imp'])} / {_fmt_pct(r['recall_after_imp'])}"
        gap_s = f"{r['gap_overall'] if r['gap_overall'] is not None else '—'} / {r['gap_bnc_win'] if r['gap_bnc_win'] is not None else '—'} / {r['gap_imp_win'] if r['gap_imp_win'] is not None else '—'}"
        bf_s = "MISSED" if r["bnc_fit_dt"] is None else f"{_fmt_f(r['bnc_fit_dt'])}f / {_fmt_f(r['bnc_fit_px'], 1)}px"
        bs_s = "MISSED" if r["bnc_sys_dt"] is None else f"{_fmt_f(r['bnc_sys_dt'], 0)}f / {_fmt_f(r['bnc_sys_px'], 1)}px"
        if r["impact_type"] == "none":
            if_s = "n/a"
            is_s = "FP" if r["sys_false_impact_on_none"] else "none"
        else:
            if_s = "MISSED" if r["imp_fit_dt"] is None else f"{_fmt_f(r['imp_fit_dt'])}f / {_fmt_f(r['imp_fit_px'], 1)}px"
            is_s = "MISSED" if r["imp_sys_dt"] is None else f"{_fmt_f(r['imp_sys_dt'], 0)}f / {_fmt_f(r['imp_sys_px'], 1)}px"
        lines.append(
            f"| `{r['clip_id']}` | `{r['ball_colour']}` | `{r['impact_type']}` | {rec_s} | {gap_s} | {bf_s} | {bs_s} | {if_s} | {is_s} |"
        )
    lines.append("")
    return "\n".join(lines)


def run_evaluation(
    *,
    run_name: str = "dump_all_1",
    labels_dir: Optional[Path] = None,
    runs_dir: Optional[Path] = None,
    out_md: Optional[Path] = None,
    out_csv: Optional[Path] = None,
) -> Tuple[Path, Path]:
    resolved_labels = (labels_dir or (REPO_ROOT / "eval" / "labels")).resolve()
    resolved_runs = (runs_dir or (REPO_ROOT / "eval" / "runs")).resolve()
    run_dir = resolved_runs / run_name
    analysis_dir = REPO_ROOT / "eval" / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_md or (analysis_dir / f"kink_events_{run_name}.md")
    csv_path = out_csv or (analysis_dir / f"kink_events_{run_name}.csv")

    rows: List[Dict[str, Any]] = []
    missing: List[str] = []
    for lbl_path in sorted(resolved_labels.glob("*.json")):
        if lbl_path.name.startswith("_"):
            continue
        lbl = json.loads(lbl_path.read_text(encoding="utf-8"))
        if lbl.get("status") != "final":
            continue
        clip_id = str(lbl.get("clip_id") or lbl_path.stem)
        dump_path = run_dir / clip_id / "raw_ball_detections.json"
        res_path = run_dir / clip_id / "results.json"
        if not dump_path.is_file() or not res_path.is_file():
            missing.append(clip_id)
            continue
        raw_dump = json.loads(dump_path.read_text(encoding="utf-8"))
        results = json.loads(res_path.read_text(encoding="utf-8"))
        rows.append(evaluate_clip(lbl, raw_dump, results))

    md_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(build_report(rows, run_name, missing), encoding="utf-8")
    csv_path.write_text(_summarize_csv(rows), encoding="utf-8")
    return md_path, csv_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate piecewise kink fits and recall.")
    ap.add_argument("--run", default="dump_all_1", help="Run folder under eval/runs/")
    ap.add_argument("--out-md", type=Path, default=None)
    ap.add_argument("--out-csv", type=Path, default=None)
    args = ap.parse_args(argv)
    md_path, csv_path = run_evaluation(run_name=args.run, out_md=args.out_md, out_csv=args.out_csv)
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
