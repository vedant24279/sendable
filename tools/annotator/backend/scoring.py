"""Pure scoring functions and report formatters for baseline tracker evaluation."""

from __future__ import annotations

import csv
import importlib.util
import io
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.calib import fit_homography, pixel_to_world  # noqa: E402

DEFAULT_TOLERANCES: Tuple[int, ...] = (0, 1, 2)
DEFAULT_ZONES_PATH = (
    REPO_ROOT / "backend" / "worker" / "legacy" / "Zone-div_V8m" / "zones.py"
)


def load_legacy_zones(
    zones_py_path: Optional[Path] = None,
) -> List[Tuple[float, float, str]]:
    """Dynamically load ZONES from backend/worker/legacy/Zone-div_V8m/zones.py at runtime."""
    target = (zones_py_path or DEFAULT_ZONES_PATH).resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Legacy zones.py not found at {target}")
    spec = importlib.util.spec_from_file_location("_legacy_zones_runtime", str(target))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not create module spec for {target}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw_zones = getattr(module, "ZONES", None)
    if not isinstance(raw_zones, list):
        raise ValueError(f"ZONES list not found in {target}")
    parsed: List[Tuple[float, float, str]] = []
    for item in raw_zones:
        y0, y1, _color, name = item
        parsed.append((float(y0), float(y1), str(name)))
    return parsed


def classify_pitch_z_zone(
    pitch_z_m: float,
    zones: Sequence[Tuple[float, float, str]],
) -> str:
    """Classify a labelled or predicted pitch_z_m into a zone name using runtime ZONES."""
    for y0, y1, name in zones:
        if y0 <= pitch_z_m < y1:
            return name
    if zones:
        if pitch_z_m < zones[0][0]:
            return "PAST_BAT_CREASE"
        if pitch_z_m >= zones[-1][1]:
            return "PAST_BOWL_CREASE"
    return "OUT_OF_BOUNDS"


def _safe_float(val: Any) -> Optional[float]:
    if val is None or isinstance(val, bool):
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _safe_int(val: Any) -> Optional[int]:
    if val is None or isinstance(val, bool):
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def load_ball_detections_csv(csv_path: Path) -> Dict[int, Dict[str, float]]:
    """Parse ball detection bounding-box rows keyed by frame index from a pipeline CSV."""
    if not csv_path.is_file():
        return {}
    lines = csv_path.read_text(encoding="utf-8", errors="replace").splitlines()
    header: Optional[List[str]] = None
    in_ball_section = False
    out: Dict[int, Dict[str, float]] = {}

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            if in_ball_section and header is not None:
                break
            continue
        if stripped.startswith("---"):
            upper = stripped.upper()
            if "BALL DETECTIONS" in upper:
                in_ball_section = True
                header = None
                continue
            if in_ball_section:
                break
            continue

        if header is None:
            cols = [c.strip() for c in next(csv.reader([raw_line]))]
            if "frame" in cols:
                header = cols
                in_ball_section = True
            continue

        vals = next(csv.reader([raw_line]))
        row = dict(zip(header, vals))
        frame_idx = _safe_int(row.get("frame"))
        if frame_idx is None:
            continue
        cls_name = (row.get("class") or "ball").strip().lower()
        if cls_name and cls_name != "ball":
            continue

        parsed: Dict[str, float] = {}
        for col in ("height", "width", "y1", "y2", "cx", "cy"):
            num = _safe_float(row.get(col))
            if num is not None:
                parsed[col] = num
        if "height" not in parsed and "y2" in parsed and "y1" in parsed:
            parsed["height"] = parsed["y2"] - parsed["y1"]
        if parsed and frame_idx not in out:
            out[frame_idx] = parsed

    return out


def _select_system_bounce_centre(
    raw_traj: Sequence[Any],
    sys_bounce_frame: Optional[int],
) -> Tuple[str, Optional[int], Optional[float], Optional[float]]:
    """Select system ball centre (x, y) at sys_bounce_frame.

    Prefers a non-interpolated point at sys_bounce_frame ("exact").
    Otherwise falls back to the nearest non-interpolated point within +-1 frame ("approx").
    Returns (status, frame, x, y) where status is "exact", "approx", or "no_centre".
    """
    if sys_bounce_frame is None:
        return "no_centre", None, None, None

    non_interp_by_frame: Dict[int, Tuple[float, float]] = {}
    for pt in raw_traj:
        if not isinstance(pt, dict):
            continue
        if bool(pt.get("interpolated", False)):
            continue
        f_idx = _safe_int(pt.get("frame"))
        x_val = _safe_float(pt.get("x"))
        y_val = _safe_float(pt.get("y"))
        if f_idx is None or x_val is None or y_val is None:
            continue
        if f_idx not in non_interp_by_frame:
            non_interp_by_frame[f_idx] = (x_val, y_val)

    if sys_bounce_frame in non_interp_by_frame:
        cx, cy = non_interp_by_frame[sys_bounce_frame]
        return "exact", sys_bounce_frame, cx, cy

    for delta in (-1, 1):
        cand_f = sys_bounce_frame + delta
        if cand_f in non_interp_by_frame:
            cx, cy = non_interp_by_frame[cand_f]
            return "approx", cand_f, cx, cy

    return "no_centre", None, None, None


def _compute_segment_coverage(
    start_frame: Optional[int],
    end_frame: Optional[int],
    traj_by_frame: Dict[int, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if start_frame is None or end_frame is None or end_frame < start_frame:
        return None
    total_frames = end_frame - start_frame + 1
    if total_frames <= 0:
        return None
    present_count = 0
    non_interp_count = 0
    for f in range(start_frame, end_frame + 1):
        pt = traj_by_frame.get(f)
        if pt is not None:
            present_count += 1
            if not bool(pt.get("interpolated", False)):
                non_interp_count += 1
    return {
        "start_frame": start_frame,
        "end_frame": end_frame,
        "total_frames": total_frames,
        "present_frames": present_count,
        "non_interpolated_frames": non_interp_count,
        "coverage_fraction": present_count / total_frames,
        "non_interpolated_fraction": non_interp_count / total_frames,
    }


def score_clip(
    label: Dict[str, Any],
    results: Optional[Dict[str, Any]],
    *,
    expected_frame_count: Optional[int] = None,
    zones: Optional[Sequence[Tuple[float, float, str]]] = None,
    detections_by_frame: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Compute per-clip comparison metrics between a ground-truth label and pipeline results.json."""
    active_zones = list(zones) if zones is not None else load_legacy_zones()

    clip_id = str(label.get("clip_id", "unknown"))
    ball_colour = str(label.get("ball_colour") or "unknown").lower()
    raw_split = label.get("split")
    split = str(raw_split).lower() if isinstance(raw_split, str) and raw_split else "none"
    flags = label.get("flags") if isinstance(label.get("flags"), list) else []
    is_unclear = "unclear" in flags

    # Calibration GT homography & quality
    calib_gt = label.get("calibration_gt") or {}
    calib_points = calib_gt.get("points") or {}
    stump_confirmed = calib_gt.get("stump_confirmed") or {}
    confirmed_stumps = sum(
        1 for k in ("bat_stump", "bowl_stump") if bool(stump_confirmed.get(k, False))
    )
    fit_res = fit_homography(calib_points, stump_confirmed=stump_confirmed)
    H = fit_res.H
    residual_px = _safe_float(calib_gt.get("residual_px"))
    if residual_px is None and fit_res.residual_px is not None:
        residual_px = float(fit_res.residual_px)

    if results is None:
        return {
            "clip_id": clip_id,
            "ball_colour": ball_colour,
            "split": split,
            "flags": list(flags),
            "is_unclear": is_unclear,
            "has_results": False,
            "frame_count_mismatch": False,
            "expected_frame_count": expected_frame_count,
            "results_frame_count": None,
            "confirmed_stumps": confirmed_stumps,
            "residual_px": residual_px,
        }

    video_meta = results.get("video") or {}
    results_frame_count = _safe_int(video_meta.get("frame_count"))
    frame_count_mismatch = (
        expected_frame_count is not None
        and results_frame_count is not None
        and expected_frame_count != results_frame_count
    )

    # Trajectory map
    raw_traj = results.get("trajectory") or []
    traj_by_frame: Dict[int, Dict[str, Any]] = {}
    for pt in raw_traj:
        if isinstance(pt, dict):
            f_idx = _safe_int(pt.get("frame"))
            if f_idx is not None:
                traj_by_frame[f_idx] = pt

    lbl_release = label.get("release") or {}
    lbl_bounce = label.get("bounce") or {}
    lbl_impact = label.get("impact") or {}
    lbl_rel_frame = _safe_int(lbl_release.get("frame"))
    lbl_imp_frame = _safe_int(lbl_impact.get("frame"))
    lbl_last_vis = _safe_int(label.get("last_visible_frame"))

    cov_rel_to_imp = _compute_segment_coverage(lbl_rel_frame, lbl_imp_frame, traj_by_frame)
    cov_imp_to_last = _compute_segment_coverage(lbl_imp_frame, lbl_last_vis, traj_by_frame)

    events = results.get("events") or {}

    # 1. Release
    sys_release = events.get("release")
    lbl_rel_x = _safe_float(lbl_release.get("x"))
    lbl_rel_y = _safe_float(lbl_release.get("y"))
    has_lbl_release = (
        lbl_rel_frame is not None and lbl_rel_x is not None and lbl_rel_y is not None
    )
    release_found = isinstance(sys_release, dict) and _safe_int(sys_release.get("frame")) is not None
    release_frame_error: Optional[int] = None
    release_px_error: Optional[float] = None
    if has_lbl_release and release_found:
        sys_rel_f = _safe_int(sys_release.get("frame"))
        sys_rel_x = _safe_float(sys_release.get("x"))
        sys_rel_y = _safe_float(sys_release.get("y"))
        if sys_rel_f is not None:
            release_frame_error = sys_rel_f - lbl_rel_frame
        if sys_rel_x is not None and sys_rel_y is not None:
            release_px_error = float(math.hypot(sys_rel_x - lbl_rel_x, sys_rel_y - lbl_rel_y))

    # 2. Bounce
    sys_bounce = events.get("bounce")
    lbl_bnc_frame = _safe_int(lbl_bounce.get("frame"))
    lbl_bnc_x = _safe_float(lbl_bounce.get("x"))
    lbl_bnc_y = _safe_float(lbl_bounce.get("y"))
    has_lbl_bounce = (
        lbl_bnc_frame is not None and lbl_bnc_x is not None and lbl_bnc_y is not None
    )
    bounce_found = isinstance(sys_bounce, dict) and _safe_int(sys_bounce.get("frame")) is not None

    bounce_frame_error: Optional[int] = None
    bounce_px_error: Optional[float] = None
    lbl_bnc_wx: Optional[float] = None
    lbl_bnc_wz: Optional[float] = None
    sys_bnc_wx: Optional[float] = None
    sys_bnc_wz: Optional[float] = None
    bounce_ground_error_m: Optional[float] = None
    bounce_pitch_z_error_m: Optional[float] = None
    bounce_pitch_x_error_m: Optional[float] = None
    sys_length_m: Optional[float] = None
    sys_length_minus_label_z_m: Optional[float] = None
    label_zone: Optional[str] = None
    system_zone: Optional[str] = None
    zone_match: Optional[bool] = None

    bounce_centre_status: Optional[str] = None
    bounce_centre_frame: Optional[int] = None
    bounce_centre_x: Optional[float] = None
    bounce_centre_y: Optional[float] = None
    bounce_centre_px_error: Optional[float] = None
    bounce_centre_dx: Optional[float] = None
    bounce_centre_dy: Optional[float] = None
    bounce_centre_wx: Optional[float] = None
    bounce_centre_wz: Optional[float] = None
    bounce_centre_ground_error_m: Optional[float] = None
    bounce_centre_pitch_z_error_m: Optional[float] = None
    bounce_centre_pitch_x_error_m: Optional[float] = None
    system_zone_recomputed: Optional[str] = None
    zone_match_recomputed: Optional[bool] = None

    bounce_marker_dx: Optional[float] = None
    bounce_marker_dy: Optional[float] = None
    bounce_det_box_height_px: Optional[float] = None
    bounce_marker_dy_over_box_height: Optional[float] = None

    if has_lbl_bounce:
        lbl_bnc_wx, lbl_bnc_wz = pixel_to_world(H, lbl_bnc_x, lbl_bnc_y)
        label_zone = classify_pitch_z_zone(lbl_bnc_wz, active_zones)

    if bounce_found:
        sys_bnc_f = _safe_int(sys_bounce.get("frame"))
        sys_bnc_x = _safe_float(sys_bounce.get("x"))
        sys_bnc_y = _safe_float(sys_bounce.get("y"))
        sys_length_m = _safe_float(sys_bounce.get("length_m"))
        raw_sys_zone = sys_bounce.get("zone")
        system_zone = str(raw_sys_zone) if raw_sys_zone is not None else None

        (
            bounce_centre_status,
            bounce_centre_frame,
            bounce_centre_x,
            bounce_centre_y,
        ) = _select_system_bounce_centre(raw_traj, sys_bnc_f)

        if bounce_centre_x is not None and bounce_centre_y is not None:
            bounce_centre_wx, bounce_centre_wz = pixel_to_world(H, bounce_centre_x, bounce_centre_y)
            system_zone_recomputed = classify_pitch_z_zone(bounce_centre_wz, active_zones)

        if detections_by_frame is not None and sys_bnc_f is not None:
            det_row = detections_by_frame.get(sys_bnc_f)
            if isinstance(det_row, dict):
                h_val = _safe_float(det_row.get("height"))
                if h_val is not None and h_val > 0:
                    bounce_det_box_height_px = h_val

        if has_lbl_bounce:
            if sys_bnc_f is not None:
                bounce_frame_error = sys_bnc_f - lbl_bnc_frame
            if sys_bnc_x is not None and sys_bnc_y is not None:
                bounce_marker_dx = float(sys_bnc_x - lbl_bnc_x)
                bounce_marker_dy = float(sys_bnc_y - lbl_bnc_y)
                if bounce_det_box_height_px is not None:
                    bounce_marker_dy_over_box_height = float(
                        bounce_marker_dy / bounce_det_box_height_px
                    )
                bounce_px_error = float(math.hypot(bounce_marker_dx, bounce_marker_dy))
                sys_bnc_wx, sys_bnc_wz = pixel_to_world(H, sys_bnc_x, sys_bnc_y)
                if lbl_bnc_wx is not None and lbl_bnc_wz is not None:
                    bounce_pitch_x_error_m = float(sys_bnc_wx - lbl_bnc_wx)
                    bounce_pitch_z_error_m = float(sys_bnc_wz - lbl_bnc_wz)
                    bounce_ground_error_m = float(
                        math.hypot(bounce_pitch_x_error_m, bounce_pitch_z_error_m)
                    )
            if bounce_centre_x is not None and bounce_centre_y is not None:
                bounce_centre_dx = float(bounce_centre_x - lbl_bnc_x)
                bounce_centre_dy = float(bounce_centre_y - lbl_bnc_y)
                bounce_centre_px_error = float(
                    math.hypot(bounce_centre_dx, bounce_centre_dy)
                )
                if (
                    bounce_centre_wx is not None
                    and bounce_centre_wz is not None
                    and lbl_bnc_wx is not None
                    and lbl_bnc_wz is not None
                ):
                    bounce_centre_pitch_x_error_m = float(bounce_centre_wx - lbl_bnc_wx)
                    bounce_centre_pitch_z_error_m = float(bounce_centre_wz - lbl_bnc_wz)
                    bounce_centre_ground_error_m = float(
                        math.hypot(
                            bounce_centre_pitch_x_error_m,
                            bounce_centre_pitch_z_error_m,
                        )
                    )
            if sys_length_m is not None and lbl_bnc_wz is not None:
                sys_length_minus_label_z_m = float(sys_length_m - lbl_bnc_wz)
            if label_zone is not None and system_zone is not None:
                zone_match = label_zone == system_zone
            if label_zone is not None and system_zone_recomputed is not None:
                zone_match_recomputed = label_zone == system_zone_recomputed

    # 3. Impact & Deviation candidate
    lbl_imp_type = str(lbl_impact.get("type") or "none").lower()
    lbl_imp_x = _safe_float(lbl_impact.get("x"))
    lbl_imp_y = _safe_float(lbl_impact.get("y"))
    has_lbl_impact_contact = (
        lbl_imp_type != "none"
        and lbl_imp_frame is not None
        and lbl_imp_x is not None
        and lbl_imp_y is not None
    )

    sys_impact = events.get("impact")
    sys_impact_present = (
        isinstance(sys_impact, dict) and _safe_int(sys_impact.get("frame")) is not None
    )
    sys_impact_type: Optional[str] = None
    if isinstance(sys_impact, dict) and sys_impact.get("type") is not None:
        sys_impact_type = str(sys_impact.get("type")).lower()

    sys_deviation = events.get("deviation")
    deviation_present = (
        isinstance(sys_deviation, dict) and _safe_int(sys_deviation.get("frame")) is not None
    )
    dev_frame_error: Optional[int] = None
    dev_px_error: Optional[float] = None
    if has_lbl_impact_contact and deviation_present:
        dev_f = _safe_int(sys_deviation.get("frame"))
        dev_x = _safe_float(sys_deviation.get("x"))
        dev_y = _safe_float(sys_deviation.get("y"))
        if dev_f is not None:
            dev_frame_error = dev_f - lbl_imp_frame
        if dev_x is not None and dev_y is not None:
            dev_px_error = float(math.hypot(dev_x - lbl_imp_x, dev_y - lbl_imp_y))

    is_no_contact_clip = lbl_imp_type == "none"
    false_marker_impact: Optional[bool] = sys_impact_present if is_no_contact_clip else None
    false_marker_deviation: Optional[bool] = deviation_present if is_no_contact_clip else None

    stats = results.get("stats") or {}
    processing_time_sec = _safe_float(stats.get("processing_time_sec"))

    return {
        "clip_id": clip_id,
        "ball_colour": ball_colour,
        "split": split,
        "flags": list(flags),
        "is_unclear": is_unclear,
        "has_results": True,
        "frame_count_mismatch": frame_count_mismatch,
        "expected_frame_count": expected_frame_count,
        "results_frame_count": results_frame_count,
        "confirmed_stumps": confirmed_stumps,
        "residual_px": residual_px,
        "coverage_release_to_impact": cov_rel_to_imp,
        "coverage_impact_to_last_visible": cov_imp_to_last,
        "has_lbl_release": has_lbl_release,
        "release_found": release_found,
        "release_frame_error": release_frame_error,
        "release_px_error": release_px_error,
        "has_lbl_bounce": has_lbl_bounce,
        "bounce_found": bounce_found,
        "bounce_frame_error": bounce_frame_error,
        "bounce_px_error": bounce_px_error,
        "label_bounce_pitch_x_m": lbl_bnc_wx,
        "label_bounce_pitch_z_m": lbl_bnc_wz,
        "system_bounce_pitch_x_m": sys_bnc_wx,
        "system_bounce_pitch_z_m": sys_bnc_wz,
        "bounce_ground_error_m": bounce_ground_error_m,
        "bounce_pitch_z_error_m": bounce_pitch_z_error_m,
        "bounce_pitch_x_error_m": bounce_pitch_x_error_m,
        "system_length_m": sys_length_m,
        "sys_length_minus_label_z_m": sys_length_minus_label_z_m,
        "label_zone": label_zone,
        "system_zone": system_zone,
        "zone_match": zone_match,
        "bounce_centre_status": bounce_centre_status,
        "bounce_centre_frame": bounce_centre_frame,
        "bounce_centre_x": bounce_centre_x,
        "bounce_centre_y": bounce_centre_y,
        "bounce_centre_px_error": bounce_centre_px_error,
        "bounce_centre_dx": bounce_centre_dx,
        "bounce_centre_dy": bounce_centre_dy,
        "bounce_centre_pitch_x_m": bounce_centre_wx,
        "bounce_centre_pitch_z_m": bounce_centre_wz,
        "bounce_centre_ground_error_m": bounce_centre_ground_error_m,
        "bounce_centre_pitch_z_error_m": bounce_centre_pitch_z_error_m,
        "bounce_centre_pitch_x_error_m": bounce_centre_pitch_x_error_m,
        "system_zone_recomputed": system_zone_recomputed,
        "zone_match_recomputed": zone_match_recomputed,
        "bounce_marker_dx": bounce_marker_dx,
        "bounce_marker_dy": bounce_marker_dy,
        "bounce_det_box_height_px": bounce_det_box_height_px,
        "bounce_marker_dy_over_box_height": bounce_marker_dy_over_box_height,
        "label_impact_type": lbl_imp_type,
        "has_lbl_impact_contact": has_lbl_impact_contact,
        "sys_impact_present": sys_impact_present,
        "sys_impact_type": sys_impact_type,
        "deviation_present": deviation_present,
        "deviation_frame_error": dev_frame_error,
        "deviation_px_error": dev_px_error,
        "is_no_contact_clip": is_no_contact_clip,
        "false_marker_impact": false_marker_impact,
        "false_marker_deviation": false_marker_deviation,
        "processing_time_sec": processing_time_sec,
    }


def _median_and_p90(values: Sequence[float]) -> Tuple[Optional[float], Optional[float]]:
    if not values:
        return None, None
    arr = np.asarray(values, dtype=np.float64)
    return float(np.median(arr)), float(np.percentile(arr, 90))


def _mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return float(np.mean(np.asarray(values, dtype=np.float64)))


def _shares_within_tolerances(
    frame_errors: Sequence[int],
    tolerances: Sequence[int],
) -> Dict[str, Optional[float]]:
    n = len(frame_errors)
    if n == 0:
        return {str(t): None for t in tolerances}
    return {
        str(t): sum(1 for e in frame_errors if abs(e) <= t) / n
        for t in tolerances
    }


def _summarize_slice(
    clips: Sequence[Dict[str, Any]],
    tolerances: Sequence[int] = DEFAULT_TOLERANCES,
) -> Dict[str, Any]:
    """Summarize metrics over a subset of clip score dicts (aligned & with results)."""
    valid = [
        c for c in clips if c.get("has_results") and not c.get("frame_count_mismatch")
    ]
    clear = [c for c in valid if not c.get("is_unclear")]

    # Trajectory coverage (across valid clips)
    rel_imp_covs = [
        c["coverage_release_to_impact"]
        for c in valid
        if c.get("coverage_release_to_impact") is not None
    ]
    imp_last_covs = [
        c["coverage_impact_to_last_visible"]
        for c in valid
        if c.get("coverage_impact_to_last_visible") is not None
    ]

    cov_summary = {
        "release_to_impact": {
            "n": len(rel_imp_covs),
            "mean_coverage": _mean([x["coverage_fraction"] for x in rel_imp_covs]),
            "mean_non_interpolated": _mean(
                [x["non_interpolated_fraction"] for x in rel_imp_covs]
            ),
        },
        "impact_to_last_visible": {
            "n": len(imp_last_covs),
            "mean_coverage": _mean([x["coverage_fraction"] for x in imp_last_covs]),
            "mean_non_interpolated": _mean(
                [x["non_interpolated_fraction"] for x in imp_last_covs]
            ),
        },
    }

    # Release (stays in release even if unclear)
    rel_Pool = [c for c in valid if c.get("has_lbl_release")]
    rel_found = [c for c in rel_Pool if c.get("release_found")]
    rel_f_errs = [
        int(c["release_frame_error"])
        for c in rel_found
        if c.get("release_frame_error") is not None
    ]
    rel_abs_f_errs = [abs(e) for e in rel_f_errs]
    rel_px_errs = [
        float(c["release_px_error"])
        for c in rel_found
        if c.get("release_px_error") is not None
    ]
    rel_f_med, rel_f_p90 = _median_and_p90(rel_abs_f_errs)
    rel_px_med, rel_px_p90 = _median_and_p90(rel_px_errs)

    release_summary = {
        "n_labelled": len(rel_Pool),
        "n_found": len(rel_found),
        "found_rate": (len(rel_found) / len(rel_Pool)) if rel_Pool else None,
        "n": len(rel_f_errs),
        "frame_error_signed_mean": _mean(rel_f_errs),
        "frame_abs_error_median": rel_f_med,
        "frame_abs_error_p90": rel_f_p90,
        "within_tolerance": _shares_within_tolerances(rel_f_errs, tolerances),
        "pixel_error_median": rel_px_med,
        "pixel_error_p90": rel_px_p90,
        "pixel_error_mean": _mean(rel_px_errs),
    }

    # Bounce (excludes unclear clips)
    bnc_pool = [c for c in clear if c.get("has_lbl_bounce")]
    bnc_found = [c for c in bnc_pool if c.get("bounce_found")]
    bnc_f_errs = [
        int(c["bounce_frame_error"])
        for c in bnc_found
        if c.get("bounce_frame_error") is not None
    ]
    bnc_abs_f_errs = [abs(e) for e in bnc_f_errs]
    bnc_px_errs = [
        float(c["bounce_px_error"])
        for c in bnc_found
        if c.get("bounce_px_error") is not None
    ]
    bnc_gnd_errs = [
        float(c["bounce_ground_error_m"])
        for c in bnc_found
        if c.get("bounce_ground_error_m") is not None
    ]
    bnc_z_errs = [
        float(c["bounce_pitch_z_error_m"])
        for c in bnc_found
        if c.get("bounce_pitch_z_error_m") is not None
    ]
    bnc_x_errs = [
        float(c["bounce_pitch_x_error_m"])
        for c in bnc_found
        if c.get("bounce_pitch_x_error_m") is not None
    ]
    bnc_len_diffs = [
        float(c["sys_length_minus_label_z_m"])
        for c in bnc_found
        if c.get("sys_length_minus_label_z_m") is not None
    ]
    bnc_zone_matches = [
        bool(c["zone_match"])
        for c in bnc_found
        if c.get("zone_match") is not None
    ]

    bnc_f_med, bnc_f_p90 = _median_and_p90(bnc_abs_f_errs)
    bnc_px_med, bnc_px_p90 = _median_and_p90(bnc_px_errs)
    bnc_gnd_med, bnc_gnd_p90 = _median_and_p90(bnc_gnd_errs)
    bnc_z_abs_med, _ = _median_and_p90([abs(e) for e in bnc_z_errs])
    bnc_x_abs_med, _ = _median_and_p90([abs(e) for e in bnc_x_errs])
    bnc_len_med, _ = _median_and_p90(bnc_len_diffs)

    bounce_summary = {
        "n_labelled": len(bnc_pool),
        "n_found": len(bnc_found),
        "found_rate": (len(bnc_found) / len(bnc_pool)) if bnc_pool else None,
        "n": len(bnc_f_errs),
        "frame_error_signed_mean": _mean(bnc_f_errs),
        "frame_abs_error_median": bnc_f_med,
        "frame_abs_error_p90": bnc_f_p90,
        "within_tolerance": _shares_within_tolerances(bnc_f_errs, tolerances),
        "pixel_error_median": bnc_px_med,
        "pixel_error_p90": bnc_px_p90,
        "ground_error_m_median": bnc_gnd_med,
        "ground_error_m_p90": bnc_gnd_p90,
        "ground_error_m_mean": _mean(bnc_gnd_errs),
        "pitch_z_error_m_signed_mean": _mean(bnc_z_errs),
        "pitch_z_error_m_abs_median": bnc_z_abs_med,
        "pitch_x_error_m_signed_mean": _mean(bnc_x_errs),
        "pitch_x_error_m_abs_median": bnc_x_abs_med,
        "sys_length_minus_label_z_m_signed_mean": _mean(bnc_len_diffs),
        "sys_length_minus_label_z_m_median": bnc_len_med,
        "zone_agreement_rate": (
            sum(1 for m in bnc_zone_matches if m) / len(bnc_zone_matches)
            if bnc_zone_matches
            else None
        ),
        "n_zone": len(bnc_zone_matches),
    }

    # Bounce Group B: Centre vs centre (excludes unclear clips)
    c_exact = sum(1 for c in bnc_found if c.get("bounce_centre_status") == "exact")
    c_approx = sum(1 for c in bnc_found if c.get("bounce_centre_status") == "approx")
    c_no_centre = sum(1 for c in bnc_found if c.get("bounce_centre_status") == "no_centre")
    c_px_errs = [
        float(c["bounce_centre_px_error"])
        for c in bnc_found
        if c.get("bounce_centre_px_error") is not None
    ]
    c_dx_vals = [
        float(c["bounce_centre_dx"])
        for c in bnc_found
        if c.get("bounce_centre_dx") is not None
    ]
    c_dy_vals = [
        float(c["bounce_centre_dy"])
        for c in bnc_found
        if c.get("bounce_centre_dy") is not None
    ]
    c_gnd_errs = [
        float(c["bounce_centre_ground_error_m"])
        for c in bnc_found
        if c.get("bounce_centre_ground_error_m") is not None
    ]
    c_z_errs = [
        float(c["bounce_centre_pitch_z_error_m"])
        for c in bnc_found
        if c.get("bounce_centre_pitch_z_error_m") is not None
    ]
    c_x_errs = [
        float(c["bounce_centre_pitch_x_error_m"])
        for c in bnc_found
        if c.get("bounce_centre_pitch_x_error_m") is not None
    ]
    c_zone_matches = [
        bool(c["zone_match_recomputed"])
        for c in bnc_found
        if c.get("zone_match_recomputed") is not None
    ]

    c_px_med, c_px_p90 = _median_and_p90(c_px_errs)
    c_dx_med, _ = _median_and_p90(c_dx_vals)
    c_dy_med, _ = _median_and_p90(c_dy_vals)
    c_gnd_med, c_gnd_p90 = _median_and_p90(c_gnd_errs)
    c_z_signed_med, _ = _median_and_p90(c_z_errs)
    c_z_abs_med, _ = _median_and_p90([abs(e) for e in c_z_errs])
    c_x_signed_med, _ = _median_and_p90(c_x_errs)
    c_x_abs_med, _ = _median_and_p90([abs(e) for e in c_x_errs])

    bounce_centre_summary = {
        "n_labelled": len(bnc_pool),
        "n_found": len(bnc_found),
        "n_exact": c_exact,
        "n_approx": c_approx,
        "n_no_centre": c_no_centre,
        "n_with_centre": c_exact + c_approx,
        "n_frame": len(bnc_f_errs),
        "frame_error_signed_mean": _mean(bnc_f_errs),
        "frame_abs_error_median": bnc_f_med,
        "frame_abs_error_p90": bnc_f_p90,
        "within_tolerance": _shares_within_tolerances(bnc_f_errs, tolerances),
        "n": len(c_px_errs),
        "pixel_error_median": c_px_med,
        "pixel_error_p90": c_px_p90,
        "pixel_error_mean": _mean(c_px_errs),
        "dx_mean": _mean(c_dx_vals),
        "dx_median": c_dx_med,
        "dy_mean": _mean(c_dy_vals),
        "dy_median": c_dy_med,
        "ground_error_m_median": c_gnd_med,
        "ground_error_m_p90": c_gnd_p90,
        "ground_error_m_mean": _mean(c_gnd_errs),
        "pitch_z_error_m_signed_mean": _mean(c_z_errs),
        "pitch_z_error_m_signed_median": c_z_signed_med,
        "pitch_z_error_m_abs_median": c_z_abs_med,
        "pitch_x_error_m_signed_mean": _mean(c_x_errs),
        "pitch_x_error_m_signed_median": c_x_signed_med,
        "pitch_x_error_m_abs_median": c_x_abs_med,
        "n_zone": len(c_zone_matches),
        "zone_agreement_rate": (
            sum(1 for m in c_zone_matches if m) / len(c_zone_matches)
            if c_zone_matches
            else None
        ),
    }

    # Bounce Group C: Marker offset (as-reported marker minus label)
    m_dx_vals = [
        float(c["bounce_marker_dx"])
        for c in bnc_found
        if c.get("bounce_marker_dx") is not None
    ]
    m_dy_vals = [
        float(c["bounce_marker_dy"])
        for c in bnc_found
        if c.get("bounce_marker_dy") is not None
    ]
    m_ratio_vals = [
        float(c["bounce_marker_dy_over_box_height"])
        for c in bnc_found
        if c.get("bounce_marker_dy_over_box_height") is not None
    ]
    m_dx_med, _ = _median_and_p90(m_dx_vals)
    m_dy_med, _ = _median_and_p90(m_dy_vals)
    m_ratio_med, _ = _median_and_p90(m_ratio_vals)

    bounce_marker_offset_summary = {
        "n": len(m_dx_vals),
        "dx_mean": _mean(m_dx_vals),
        "dx_median": m_dx_med,
        "dy_mean": _mean(m_dy_vals),
        "dy_median": m_dy_med,
        "n_with_box_height": len(m_ratio_vals),
        "dy_over_box_height_mean": _mean(m_ratio_vals),
        "dy_over_box_height_median": m_ratio_med,
    }

    # Impact & Deviation candidate (excludes unclear clips)
    imp_all = clear
    sys_imp_count = sum(1 for c in imp_all if c.get("sys_impact_present"))
    dev_all_count = sum(1 for c in imp_all if c.get("deviation_present"))

    imp_contact_pool = [c for c in clear if c.get("has_lbl_impact_contact")]
    dev_on_contact = [c for c in imp_contact_pool if c.get("deviation_present")]
    dev_f_errs = [
        int(c["deviation_frame_error"])
        for c in dev_on_contact
        if c.get("deviation_frame_error") is not None
    ]
    dev_abs_f_errs = [abs(e) for e in dev_f_errs]
    dev_px_errs = [
        float(c["deviation_px_error"])
        for c in dev_on_contact
        if c.get("deviation_px_error") is not None
    ]
    dev_f_med, dev_f_p90 = _median_and_p90(dev_abs_f_errs)
    dev_px_med, dev_px_p90 = _median_and_p90(dev_px_errs)

    # Impact type accuracy when system provides a type
    typed_clips = [
        c
        for c in imp_contact_pool
        if c.get("sys_impact_type") is not None
    ]
    if typed_clips:
        type_acc: Any = sum(
            1 for c in typed_clips if c["sys_impact_type"] == c["label_impact_type"]
        ) / len(typed_clips)
    else:
        type_acc = "n/a (system provides no impact type)"

    no_contact_pool = [c for c in clear if c.get("is_no_contact_clip")]
    false_imp_count = sum(1 for c in no_contact_pool if c.get("false_marker_impact"))
    false_dev_count = sum(1 for c in no_contact_pool if c.get("false_marker_deviation"))

    impact_summary = {
        "n_clips": len(imp_all),
        "sys_impact_non_null_count": sys_imp_count,
        "sys_impact_non_null_share": (sys_imp_count / len(imp_all)) if imp_all else None,
        "deviation_present_count": dev_all_count,
        "deviation_present_share": (dev_all_count / len(imp_all)) if imp_all else None,
        "n_contact_labelled": len(imp_contact_pool),
        "n_deviation_on_contact": len(dev_f_errs),
        "deviation_on_contact_share": (
            len(dev_on_contact) / len(imp_contact_pool) if imp_contact_pool else None
        ),
        "deviation_frame_error_signed_mean": _mean(dev_f_errs),
        "deviation_frame_abs_error_median": dev_f_med,
        "deviation_frame_abs_error_p90": dev_f_p90,
        "deviation_within_tolerance": _shares_within_tolerances(dev_f_errs, tolerances),
        "deviation_pixel_error_median": dev_px_med,
        "deviation_pixel_error_p90": dev_px_p90,
        "impact_type_accuracy": type_acc,
        "n_no_contact_labelled": len(no_contact_pool),
        "false_marker_impact_count": false_imp_count,
        "false_marker_impact_rate": (
            false_imp_count / len(no_contact_pool) if no_contact_pool else None
        ),
        "false_marker_deviation_count": false_dev_count,
        "false_marker_deviation_rate": (
            false_dev_count / len(no_contact_pool) if no_contact_pool else None
        ),
    }

    # Runtime
    runtimes = [
        float(c["processing_time_sec"])
        for c in valid
        if c.get("processing_time_sec") is not None
    ]
    rt_med, rt_p90 = _median_and_p90(runtimes)
    runtime_summary = {
        "n": len(runtimes),
        "mean_sec": _mean(runtimes),
        "median_sec": rt_med,
        "p90_sec": rt_p90,
        "min_sec": min(runtimes) if runtimes else None,
        "max_sec": max(runtimes) if runtimes else None,
    }

    return {
        "n_valid_clips": len(valid),
        "n_clear_clips": len(clear),
        "n_unclear_clips": len(valid) - len(clear),
        "trajectory_coverage": cov_summary,
        "release": release_summary,
        "bounce": bounce_summary,
        "bounce_as_reported": bounce_summary,
        "bounce_centre_vs_centre": bounce_centre_summary,
        "bounce_marker_offset": bounce_marker_offset_summary,
        "impact": impact_summary,
        "lbw": "n/a (not implemented in the system)",
        "runtime": runtime_summary,
    }


def _build_zone_confusion(
    clips: Sequence[Dict[str, Any]],
    zone_names: Sequence[str],
    *,
    sys_zone_key: str = "system_zone",
) -> Dict[str, Any]:
    ordered_labels = list(zone_names)
    for c in clips:
        if c.get("has_results") and not c.get("frame_count_mismatch") and not c.get("is_unclear"):
            lz = c.get("label_zone")
            sz = c.get(sys_zone_key)
            if lz and lz not in ordered_labels:
                ordered_labels.append(lz)
            if sz and sz not in ordered_labels:
                ordered_labels.append(sz)

    matrix: Dict[str, Dict[str, int]] = {
        lz: {sz: 0 for sz in ordered_labels} for lz in ordered_labels
    }
    n_scored = 0
    n_agree = 0
    for c in clips:
        if (
            not c.get("has_results")
            or c.get("frame_count_mismatch")
            or c.get("is_unclear")
        ):
            continue
        lz = c.get("label_zone")
        sz = c.get(sys_zone_key)
        if lz is not None and sz is not None:
            matrix[lz][sz] = matrix.get(lz, {}).get(sz, 0) + 1
            n_scored += 1
            if lz == sz:
                n_agree += 1

    return {
        "zones": ordered_labels,
        "matrix": matrix,
        "n": n_scored,
        "agreement_count": n_agree,
        "agreement_rate": (n_agree / n_scored) if n_scored > 0 else None,
    }


def _build_calibration_quality(clips: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    both_derived = sum(1 for c in clips if c.get("confirmed_stumps") == 0)
    one_confirmed = sum(1 for c in clips if c.get("confirmed_stumps") == 1)
    both_confirmed = sum(1 for c in clips if c.get("confirmed_stumps") == 2)
    residuals = [
        float(c["residual_px"])
        for c in clips
        if c.get("residual_px") is not None
    ]
    return {
        "n_clips": len(clips),
        "both_stumps_derived_count": both_derived,
        "one_stump_confirmed_count": one_confirmed,
        "both_stumps_confirmed_count": both_confirmed,
        "n_with_residual": len(residuals),
        "mean_residual_px": _mean(residuals),
        "max_residual_px": max(residuals) if residuals else None,
    }


def _build_worst_5(clips: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    valid = [c for c in clips if c.get("has_results") and not c.get("frame_count_mismatch")]
    clear = [c for c in valid if not c.get("is_unclear")]

    def _top5(
        pool: Sequence[Dict[str, Any]],
        key: str,
        use_abs: bool = False,
    ) -> List[Dict[str, Any]]:
        items = []
        for c in pool:
            val = c.get(key)
            if val is not None:
                score_val = abs(float(val)) if use_abs else float(val)
                items.append(
                    {
                        "clip_id": c["clip_id"],
                        "ball_colour": c["ball_colour"],
                        "split": c["split"],
                        "value": float(val),
                        "sort_key": score_val,
                    }
                )
        items.sort(key=lambda x: (-x["sort_key"], x["clip_id"]))
        return [
            {
                "clip_id": x["clip_id"],
                "ball_colour": x["ball_colour"],
                "split": x["split"],
                "value": x["value"],
            }
            for x in items[:5]
        ]

    return {
        "release_frame_abs_error": _top5(valid, "release_frame_error", use_abs=True),
        "release_pixel_error": _top5(valid, "release_px_error", use_abs=False),
        "bounce_frame_abs_error": _top5(clear, "bounce_frame_error", use_abs=True),
        "bounce_ground_error_m": _top5(clear, "bounce_ground_error_m", use_abs=False),
        "deviation_frame_abs_error": _top5(clear, "deviation_frame_error", use_abs=True),
        "deviation_pixel_error": _top5(clear, "deviation_px_error", use_abs=False),
    }


def aggregate_scores(
    clip_scores: Sequence[Dict[str, Any]],
    *,
    tolerances: Sequence[int] = DEFAULT_TOLERANCES,
    zones: Optional[Sequence[Tuple[float, float, str]]] = None,
    run_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Aggregate per-clip score dictionaries into overall, by-colour, and by-split summaries."""
    active_zones = list(zones) if zones is not None else load_legacy_zones()
    zone_names = [z[2] for z in active_zones]

    mismatched_clips = [
        {
            "clip_id": c["clip_id"],
            "expected_frame_count": c.get("expected_frame_count"),
            "results_frame_count": c.get("results_frame_count"),
        }
        for c in clip_scores
        if c.get("frame_count_mismatch")
    ]
    missing_results_clips = [
        c["clip_id"] for c in clip_scores if not c.get("has_results")
    ]
    unclear_clips = [
        {
            "clip_id": c["clip_id"],
            "ball_colour": c["ball_colour"],
            "split": c["split"],
            "flags": c.get("flags", []),
            "release_frame_error": c.get("release_frame_error"),
            "bounce_frame_error": c.get("bounce_frame_error"),
            "bounce_ground_error_m": c.get("bounce_ground_error_m"),
            "deviation_frame_error": c.get("deviation_frame_error"),
        }
        for c in clip_scores
        if c.get("is_unclear")
    ]

    overall = _summarize_slice(clip_scores, tolerances=tolerances)

    by_ball_colour: Dict[str, Any] = {}
    colours = sorted({c["ball_colour"] for c in clip_scores if c.get("ball_colour")})
    for col in ("white", "red", "pink"):
        if col not in colours:
            colours.append(col)
    for col in colours:
        subset = [c for c in clip_scores if c.get("ball_colour") == col]
        by_ball_colour[col] = _summarize_slice(subset, tolerances=tolerances)

    by_split: Dict[str, Any] = {}
    for sp in ("dev", "final", "none"):
        subset = [c for c in clip_scores if c.get("split") == sp]
        by_split[sp] = _summarize_slice(subset, tolerances=tolerances)

    return {
        "run_info": run_info or {},
        "tolerances": list(tolerances),
        "zones_thresholds": [
            {"z_min_m": z[0], "z_max_m": z[1], "name": z[2]} for z in active_zones
        ],
        "frame_alignment": {
            "n_total_labels": len(clip_scores),
            "n_with_results": len(clip_scores) - len(missing_results_clips),
            "n_aligned": len(clip_scores) - len(missing_results_clips) - len(mismatched_clips),
            "n_mismatched": len(mismatched_clips),
            "mismatched_clips": mismatched_clips,
            "missing_results_clips": missing_results_clips,
        },
        "overall": overall,
        "by_ball_colour": by_ball_colour,
        "by_split": by_split,
        "zone_confusion": _build_zone_confusion(
            clip_scores, zone_names, sys_zone_key="system_zone"
        ),
        "zone_confusion_recomputed": _build_zone_confusion(
            clip_scores, zone_names, sys_zone_key="system_zone_recomputed"
        ),
        "calibration_quality": _build_calibration_quality(clip_scores),
        "unclear_clips": unclear_clips,
        "worst_5_per_metric": _build_worst_5(clip_scores),
        "per_clip": list(clip_scores),
    }


def _fmt_num(val: Optional[float], digits: int = 2, suffix: str = "") -> str:
    if val is None:
        return "—"
    return f"{val:.{digits}f}{suffix}"


def _fmt_pct(val: Optional[float], digits: int = 1) -> str:
    if val is None:
        return "—"
    return f"{val * 100.0:.{digits}f}%"


def format_per_clip_csv(clip_scores: Sequence[Dict[str, Any]]) -> str:
    """Format per-clip metrics as a CSV string."""
    fieldnames = [
        "clip_id",
        "ball_colour",
        "split",
        "is_unclear",
        "has_results",
        "frame_count_mismatch",
        "expected_frame_count",
        "results_frame_count",
        "confirmed_stumps",
        "residual_px",
        "cov_rel_imp_fraction",
        "cov_rel_imp_non_interp",
        "cov_imp_last_fraction",
        "cov_imp_last_non_interp",
        "release_found",
        "release_frame_error",
        "release_px_error",
        "bounce_found",
        "bounce_frame_error",
        "bounce_px_error",
        "label_bounce_pitch_x_m",
        "label_bounce_pitch_z_m",
        "system_bounce_pitch_x_m",
        "system_bounce_pitch_z_m",
        "bounce_ground_error_m",
        "bounce_pitch_z_error_m",
        "bounce_pitch_x_error_m",
        "system_length_m",
        "sys_length_minus_label_z_m",
        "bounce_centre_status",
        "bounce_centre_frame",
        "bounce_centre_x",
        "bounce_centre_y",
        "bounce_centre_px_error",
        "bounce_centre_dx",
        "bounce_centre_dy",
        "bounce_centre_pitch_x_m",
        "bounce_centre_pitch_z_m",
        "bounce_centre_ground_error_m",
        "bounce_centre_pitch_z_error_m",
        "bounce_centre_pitch_x_error_m",
        "bounce_marker_dx",
        "bounce_marker_dy",
        "bounce_det_box_height_px",
        "bounce_marker_dy_over_box_height",
        "label_zone",
        "system_zone",
        "zone_match",
        "system_zone_recomputed",
        "zone_match_recomputed",
        "label_impact_type",
        "sys_impact_present",
        "deviation_present",
        "deviation_frame_error",
        "deviation_px_error",
        "false_marker_impact",
        "false_marker_deviation",
        "processing_time_sec",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for c in clip_scores:
        c_ri = c.get("coverage_release_to_impact") or {}
        c_il = c.get("coverage_impact_to_last_visible") or {}
        row = {k: c.get(k) for k in fieldnames}
        row["cov_rel_imp_fraction"] = c_ri.get("coverage_fraction")
        row["cov_rel_imp_non_interp"] = c_ri.get("non_interpolated_fraction")
        row["cov_imp_last_fraction"] = c_il.get("coverage_fraction")
        row["cov_imp_last_non_interp"] = c_il.get("non_interpolated_fraction")
        writer.writerow(row)
    return buf.getvalue()


def format_markdown_report(summary: Dict[str, Any], run_name: str) -> str:
    """Format the full evaluation Markdown report."""
    lines: List[str] = []
    run_info = summary.get("run_info") or {}
    fa = summary["frame_alignment"]
    ov = summary["overall"]
    tols = summary.get("tolerances") or [0, 1, 2]
    t0, t1, t2 = (str(tols[0]), str(tols[1]), str(tols[2])) if len(tols) >= 3 else ("0", "1", "2")

    lines.append(f"# Baseline Evaluation Report: `{run_name}`")
    lines.append("")
    lines.append("## 1. Run Info")
    lines.append("")
    lines.append(f"- **Run name**: `{run_info.get('run_name', run_name)}`")
    lines.append(f"- **UTC time**: `{run_info.get('utc_time', 'unknown')}`")
    lines.append(f"- **Git commit**: `{run_info.get('git_commit', 'unknown')}`")
    lines.append(
        f"- **Pipeline/worker dirty**: `{run_info.get('pipeline_or_worker_dirty', False)}`"
    )
    lines.append(
        f"- **Legacy tracker folder**: `{run_info.get('legacy_tracker_folder', 'Zone-div_V8m')}`"
    )
    lines.append(
        f"- **Ball types in run**: `{', '.join(run_info.get('ball_types', [])) or 'none'}`"
    )
    lines.append(
        f"- **Frame alignment**: `{fa['n_aligned']}/{fa['n_with_results']}` aligned "
        f"(`{fa['n_mismatched']}` mismatched excluded, `{ len(fa['missing_results_clips']) }` missing results)"
    )
    if fa["mismatched_clips"]:
        for m in fa["mismatched_clips"]:
            lines.append(
                f"  - Mismatch excluded: `{m['clip_id']}` "
                f"(label/library={m['expected_frame_count']}, results={m['results_frame_count']})"
            )
    lines.append("")
    lines.append("## Conventions")
    lines.append("")
    lines.append(
        "- **As reported**: Compares `events.bounce` (`frame`, `x`, `y`, `zone`) in `results.json` directly against the human-labelled bounce centre. "
        "Note that the tracker writes the ball bounding-box bottom edge (`y2`) as `events.bounce.y`."
    )
    lines.append(
        "- **Centre vs centre**: Uses the system ball trajectory centre `(x, y)` at `events.bounce.frame` (preferring non-interpolated points; "
        "`approx` falls back to the nearest non-interpolated point within `±1` frame; `no_centre` if none exists), and projects both system centre and label centre through the ground-truth homography. "
        "Signed errors are `system - label` (`+dx` = right, `+dy` = lower on screen, `+pitch_z_m` = further down pitch toward bowling end)."
    )
    lines.append(
        "- **Marker offset**: Signed pixel offset `as_reported_marker - label` (`dx`, `dy`), plus `dy / box_height` using the ball detection bounding-box `height` at `events.bounce.frame` from the detections CSV (expected `~ +0.5` when the marker sits at `y2` and both detect the same ball)."
    )
    lines.append(
        "- **Zones**: `label_zone` is classified from the human bounce centre `pitch_z_m` through the GT homography (`Zone-div_V8m/zones.py` thresholds); "
        "`system_zone` is `events.bounce.zone` as reported; `system_zone_recomputed` is classified from the system trajectory centre pixel through the GT homography."
    )
    lines.append("")

    # Headline Table
    rel = ov["release"]
    bnc = ov["bounce"]
    bnc_cc = ov["bounce_centre_vs_centre"]
    bnc_mo = ov["bounce_marker_offset"]
    imp = ov["impact"]
    rt = ov["runtime"]
    cov_ri = ov["trajectory_coverage"]["release_to_impact"]
    cov_il = ov["trajectory_coverage"]["impact_to_last_visible"]

    lines.append("## 2. Headline Table (Overall)")
    lines.append("")
    lines.append("| Metric | n | Value |")
    lines.append("| --- | ---: | --- |")
    lines.append(
        f"| Trajectory coverage `[release, impact]` (total / non-interp) | {cov_ri['n']} | "
        f"{_fmt_pct(cov_ri['mean_coverage'])} / {_fmt_pct(cov_ri['mean_non_interpolated'])} |"
    )
    lines.append(
        f"| Trajectory coverage `[impact, last_visible]` (total / non-interp) | {cov_il['n']} | "
        f"{_fmt_pct(cov_il['mean_coverage'])} / {_fmt_pct(cov_il['mean_non_interpolated'])} |"
    )
    lines.append(
        f"| Release found rate | {rel['n_labelled']} | "
        f"{rel['n_found']}/{rel['n_labelled']} ({_fmt_pct(rel['found_rate'])}) |"
    )
    lines.append(
        f"| Release frame error (`0` / `±{t1}` / `±{t2}` frames) | {rel['n']} | "
        f"{_fmt_pct(rel['within_tolerance'].get(t0))} / "
        f"{_fmt_pct(rel['within_tolerance'].get(t1))} / "
        f"{_fmt_pct(rel['within_tolerance'].get(t2))} "
        f"(med\\|err\\|={_fmt_num(rel['frame_abs_error_median'], 1)}, p90={_fmt_num(rel['frame_abs_error_p90'], 1)}) |"
    )
    lines.append(
        f"| Release pixel distance (median / p90) | {rel['n']} | "
        f"{_fmt_num(rel['pixel_error_median'], 1, ' px')} / {_fmt_num(rel['pixel_error_p90'], 1, ' px')} |"
    )
    lines.append(
        f"| **Bounce — As reported**: found rate (excl. unclear) | {bnc['n_labelled']} | "
        f"{bnc['n_found']}/{bnc['n_labelled']} ({_fmt_pct(bnc['found_rate'])}) |"
    )
    lines.append(
        f"| **Bounce — As reported**: frame error (`0` / `±{t1}` / `±{t2}` frames) | {bnc['n']} | "
        f"{_fmt_pct(bnc['within_tolerance'].get(t0))} / "
        f"{_fmt_pct(bnc['within_tolerance'].get(t1))} / "
        f"{_fmt_pct(bnc['within_tolerance'].get(t2))} "
        f"(med\\|err\\|={_fmt_num(bnc['frame_abs_error_median'], 1)}, p90={_fmt_num(bnc['frame_abs_error_p90'], 1)}) |"
    )
    lines.append(
        f"| **Bounce — As reported**: pixel distance (median / p90) | {bnc['n']} | "
        f"{_fmt_num(bnc['pixel_error_median'], 1, ' px')} / {_fmt_num(bnc['pixel_error_p90'], 1, ' px')} |"
    )
    lines.append(
        f"| **Bounce — As reported**: ground error in metres (median / p90) | {bnc['n']} | "
        f"{_fmt_num(bnc['ground_error_m_median'], 3, ' m')} / {_fmt_num(bnc['ground_error_m_p90'], 3, ' m')} |"
    )
    lines.append(
        f"| **Bounce — As reported**: `pitch_z_m` error (signed mean / median abs) | {bnc['n']} | "
        f"{_fmt_num(bnc['pitch_z_error_m_signed_mean'], 3, ' m')} / {_fmt_num(bnc['pitch_z_error_m_abs_median'], 3, ' m')} |"
    )
    lines.append(
        f"| **Bounce — As reported**: `pitch_x_m` error (signed mean / median abs) | {bnc['n']} | "
        f"{_fmt_num(bnc['pitch_x_error_m_signed_mean'], 3, ' m')} / {_fmt_num(bnc['pitch_x_error_m_abs_median'], 3, ' m')} |"
    )
    lines.append(
        f"| **Bounce — As reported**: system `length_m` minus label `pitch_z_m` (signed mean / median) | {bnc['n']} | "
        f"{_fmt_num(bnc['sys_length_minus_label_z_m_signed_mean'], 3, ' m')} / {_fmt_num(bnc['sys_length_minus_label_z_m_median'], 3, ' m')} |"
    )
    lines.append(
        f"| **Bounce — As reported**: zone agreement | {bnc['n_zone']} | {_fmt_pct(bnc['zone_agreement_rate'])} |"
    )
    lines.append(
        f"| **Bounce — Centre vs centre**: centre availability (`exact` / `approx` / `no_centre`) | {bnc_cc['n_found']} | "
        f"`{bnc_cc['n_exact']}` / `{bnc_cc['n_approx']}` / `{bnc_cc['n_no_centre']}` |"
    )
    lines.append(
        f"| **Bounce — Centre vs centre**: frame error (`0` / `±{t1}` / `±{t2}` frames) | {bnc_cc['n_frame']} | "
        f"{_fmt_pct(bnc_cc['within_tolerance'].get(t0))} / "
        f"{_fmt_pct(bnc_cc['within_tolerance'].get(t1))} / "
        f"{_fmt_pct(bnc_cc['within_tolerance'].get(t2))} "
        f"(med\\|err\\|={_fmt_num(bnc_cc['frame_abs_error_median'], 1)}, p90={_fmt_num(bnc_cc['frame_abs_error_p90'], 1)}) |"
    )
    lines.append(
        f"| **Bounce — Centre vs centre**: pixel distance (median / p90) | {bnc_cc['n']} | "
        f"{_fmt_num(bnc_cc['pixel_error_median'], 1, ' px')} / {_fmt_num(bnc_cc['pixel_error_p90'], 1, ' px')} |"
    )
    lines.append(
        f"| **Bounce — Centre vs centre**: signed `dx` (mean / median) | {bnc_cc['n']} | "
        f"{_fmt_num(bnc_cc['dx_mean'], 2, ' px')} / {_fmt_num(bnc_cc['dx_median'], 2, ' px')} |"
    )
    lines.append(
        f"| **Bounce — Centre vs centre**: signed `dy` (mean / median) | {bnc_cc['n']} | "
        f"{_fmt_num(bnc_cc['dy_mean'], 2, ' px')} / {_fmt_num(bnc_cc['dy_median'], 2, ' px')} |"
    )
    lines.append(
        f"| **Bounce — Centre vs centre**: ground error in metres (median / p90) | {bnc_cc['n']} | "
        f"{_fmt_num(bnc_cc['ground_error_m_median'], 3, ' m')} / {_fmt_num(bnc_cc['ground_error_m_p90'], 3, ' m')} |"
    )
    lines.append(
        f"| **Bounce — Centre vs centre**: `pitch_z_m` error (signed mean / median / median abs) | {bnc_cc['n']} | "
        f"{_fmt_num(bnc_cc['pitch_z_error_m_signed_mean'], 3, ' m')} / "
        f"{_fmt_num(bnc_cc['pitch_z_error_m_signed_median'], 3, ' m')} / "
        f"{_fmt_num(bnc_cc['pitch_z_error_m_abs_median'], 3, ' m')} |"
    )
    lines.append(
        f"| **Bounce — Centre vs centre**: `pitch_x_m` error (signed mean / median / median abs) | {bnc_cc['n']} | "
        f"{_fmt_num(bnc_cc['pitch_x_error_m_signed_mean'], 3, ' m')} / "
        f"{_fmt_num(bnc_cc['pitch_x_error_m_signed_median'], 3, ' m')} / "
        f"{_fmt_num(bnc_cc['pitch_x_error_m_abs_median'], 3, ' m')} |"
    )
    lines.append(
        f"| **Bounce — Centre vs centre**: recomputed zone agreement | {bnc_cc['n_zone']} | {_fmt_pct(bnc_cc['zone_agreement_rate'])} |"
    )
    lines.append(
        f"| **Bounce — Marker offset**: signed `dx` (`marker - label`, mean / median) | {bnc_mo['n']} | "
        f"{_fmt_num(bnc_mo['dx_mean'], 2, ' px')} / {_fmt_num(bnc_mo['dx_median'], 2, ' px')} |"
    )
    lines.append(
        f"| **Bounce — Marker offset**: signed `dy` (`marker - label`, mean / median) | {bnc_mo['n']} | "
        f"{_fmt_num(bnc_mo['dy_mean'], 2, ' px')} / {_fmt_num(bnc_mo['dy_median'], 2, ' px')} |"
    )
    lines.append(
        f"| **Bounce — Marker offset**: `dy / box_height` (median / mean) | {bnc_mo['n_with_box_height']} | "
        f"{_fmt_num(bnc_mo['dy_over_box_height_median'], 3)} / {_fmt_num(bnc_mo['dy_over_box_height_mean'], 3)} |"
    )
    lines.append(
        f"| Impact (`events.impact` non-null share) | {imp['n_clips']} | "
        f"{imp['sys_impact_non_null_count']}/{imp['n_clips']} ({_fmt_pct(imp['sys_impact_non_null_share'])}) |"
    )
    lines.append(
        f"| Deviation candidate (`events.deviation` present on contact clips) | {imp['n_contact_labelled']} | "
        f"{imp['n_deviation_on_contact']}/{imp['n_contact_labelled']} ({_fmt_pct(imp['deviation_on_contact_share'])}) |"
    )
    lines.append(
        f"| Deviation vs Impact frame error (`0` / `±{t1}` / `±{t2}` frames) | {imp['n_deviation_on_contact']} | "
        f"{_fmt_pct(imp['deviation_within_tolerance'].get(t0))} / "
        f"{_fmt_pct(imp['deviation_within_tolerance'].get(t1))} / "
        f"{_fmt_pct(imp['deviation_within_tolerance'].get(t2))} "
        f"(med\\|err\\|={_fmt_num(imp['deviation_frame_abs_error_median'], 1)}, p90={_fmt_num(imp['deviation_frame_abs_error_p90'], 1)}) |"
    )
    lines.append(
        f"| Deviation vs Impact pixel distance (median / p90) | {imp['n_deviation_on_contact']} | "
        f"{_fmt_num(imp['deviation_pixel_error_median'], 1, ' px')} / {_fmt_num(imp['deviation_pixel_error_p90'], 1, ' px')} |"
    )
    lines.append(
        f"| Impact type accuracy | {imp['n_contact_labelled']} | {imp['impact_type_accuracy']} |"
    )
    lines.append(
        f"| False-marker rate on labelled `none` (impact / deviation) | {imp['n_no_contact_labelled']} | "
        f"{_fmt_pct(imp['false_marker_impact_rate'])} / {_fmt_pct(imp['false_marker_deviation_rate'])} |"
    )
    lines.append(f"| LBW | 0 | {ov['lbw']} |")
    lines.append(
        f"| Runtime per clip (mean / median / p90) | {rt['n']} | "
        f"{_fmt_num(rt['mean_sec'], 2, ' s')} / {_fmt_num(rt['median_sec'], 2, ' s')} / {_fmt_num(rt['p90_sec'], 2, ' s')} |"
    )
    lines.append("")

    # 3. Detail Tables by Ball Colour and Split
    lines.append("## 3. Detail Tables")
    lines.append("")

    def _append_breakdown_table(title: str, groups: Dict[str, Any]) -> None:
        lines.append(f"### {title}")
        lines.append("")
        lines.append(
            f"| Slice | n (valid / clear) | Cov `[rel,imp]` | Release Found | Rel `±{t1}f` | Rel Med px | "
            f"Bounce Found | Bnc `±{t1}f` | Bnc Med m (rep / ctr) | Dev on Contact | Dev `±{t1}f` | Dev Med px | Runtime Med |"
        )
        lines.append(
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
        )
        for name, s in groups.items():
            r_s = s["release"]
            b_s = s["bounce"]
            bc_s = s["bounce_centre_vs_centre"]
            i_s = s["impact"]
            t_s = s["runtime"]
            c_ri_s = s["trajectory_coverage"]["release_to_impact"]
            lines.append(
                f"| `{name}` | {s['n_valid_clips']} / {s['n_clear_clips']} | "
                f"{_fmt_pct(c_ri_s['mean_coverage'])} (n={c_ri_s['n']}) | "
                f"{r_s['n_found']}/{r_s['n_labelled']} | "
                f"{_fmt_pct(r_s['within_tolerance'].get(t1))} | "
                f"{_fmt_num(r_s['pixel_error_median'], 1)} | "
                f"{b_s['n_found']}/{b_s['n_labelled']} | "
                f"{_fmt_pct(b_s['within_tolerance'].get(t1))} | "
                f"{_fmt_num(b_s['ground_error_m_median'], 3)} / {_fmt_num(bc_s['ground_error_m_median'], 3)} | "
                f"{i_s['n_deviation_on_contact']}/{i_s['n_contact_labelled']} | "
                f"{_fmt_pct(i_s['deviation_within_tolerance'].get(t1))} | "
                f"{_fmt_num(i_s['deviation_pixel_error_median'], 1)} | "
                f"{_fmt_num(t_s['median_sec'], 2, 's')} |"
            )
        lines.append("")

    _append_breakdown_table("3.1 Breakdown by Ball Colour", summary["by_ball_colour"])
    _append_breakdown_table("3.2 Breakdown by Split (`dev` / `final` / `none`)", summary["by_split"])

    # 3.3 Per-Clip Detail Table
    lines.append("### 3.3 Per-Clip Detail Table")
    lines.append("")
    lines.append(
        "| Clip ID | Ball | Split | Unclear | Rel Err (f / px) | As-rep Bnc (f / px / m) | "
        "Centre vs Centre (`status`: `dx`,`dy` / px / m) | Marker Offset (`dx`,`dy` / `dy/h`) | "
        "`pitch_z` Err rep/ctr (m) | Zone (`lbl` -> `rep` / `recomp`) | Dev vs Imp (f / px) | Runtime (s) |"
    )
    lines.append(
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: |"
    )
    for c in summary["per_clip"]:
        rel_str = (
            f"{c.get('release_frame_error')}f / {_fmt_num(c.get('release_px_error'), 1)}px"
            if c.get("release_found")
            else "missed"
        )
        bnc_str = (
            f"{c.get('bounce_frame_error')}f / {_fmt_num(c.get('bounce_px_error'), 1)}px / "
            f"{_fmt_num(c.get('bounce_ground_error_m'), 3)}m"
            if c.get("bounce_found")
            else "missed"
        )
        c_status = c.get("bounce_centre_status")
        if not c.get("bounce_found"):
            cc_str = "missed"
        elif c_status == "no_centre":
            cc_str = "`no_centre`"
        else:
            cc_str = (
                f"`{c_status}`: {_fmt_num(c.get('bounce_centre_dx'), 1)},{_fmt_num(c.get('bounce_centre_dy'), 1)} / "
                f"{_fmt_num(c.get('bounce_centre_px_error'), 1)}px / "
                f"{_fmt_num(c.get('bounce_centre_ground_error_m'), 3)}m"
            )
        if not c.get("bounce_found"):
            mo_str = "missed"
        else:
            mo_str = (
                f"{_fmt_num(c.get('bounce_marker_dx'), 1)},{_fmt_num(c.get('bounce_marker_dy'), 1)} / "
                f"{_fmt_num(c.get('bounce_marker_dy_over_box_height'), 2)}"
            )
        dev_str = (
            f"{c.get('deviation_frame_error')}f / {_fmt_num(c.get('deviation_px_error'), 1)}px"
            if c.get("deviation_present") and c.get("has_lbl_impact_contact")
            else ("present (no-contact)" if c.get("deviation_present") else "none")
        )
        lines.append(
            f"| `{c['clip_id']}` | `{c['ball_colour']}` | `{c['split']}` | "
            f"`{'yes' if c.get('is_unclear') else 'no'}` | {rel_str} | {bnc_str} | "
            f"{cc_str} | {mo_str} | "
            f"{_fmt_num(c.get('bounce_pitch_z_error_m'), 3)} / {_fmt_num(c.get('bounce_centre_pitch_z_error_m'), 3)} | "
            f"`{c.get('label_zone') or '—'}` -> `{c.get('system_zone') or '—'}` / `{c.get('system_zone_recomputed') or '—'}` | "
            f"{dev_str} | {_fmt_num(c.get('processing_time_sec'), 2)} |"
        )
    lines.append("")

    # 3.4 Zone Confusion Table
    zc_rep = summary["zone_confusion"]
    zc_rec = summary["zone_confusion_recomputed"]
    z_list = zc_rec["zones"]
    lines.append("### 3.4 Bounce Zone Agreement & Confusion Matrix (Recomputed from System Centre)")
    lines.append("")
    lines.append(
        f"Thresholds loaded at runtime from `backend/worker/legacy/Zone-div_V8m/zones.py`: "
        + ", ".join(
            f"`{z['name']}`: `[{z['z_min_m']:.2f}, {z['z_max_m']:.2f}) m`"
            for z in summary["zones_thresholds"]
        )
    )
    lines.append("")
    lines.append(
        f"- **System zone (as reported) agreement**: `{zc_rep['agreement_count']}/{zc_rep['n']}` ({_fmt_pct(zc_rep['agreement_rate'])})"
    )
    lines.append(
        f"- **System zone (recomputed from system centre) agreement**: `{zc_rec['agreement_count']}/{zc_rec['n']}` ({_fmt_pct(zc_rec['agreement_rate'])})"
    )
    lines.append("")
    header = "| Labelled \\\\ System Recomputed | " + " | ".join(f"`{z}`" for z in z_list) + " |"
    sep = "| --- | " + " | ".join("---:" for _ in z_list) + " |"
    lines.append(header)
    lines.append(sep)
    for lz in z_list:
        row_cells = [str(zc_rec["matrix"].get(lz, {}).get(sz, 0)) for sz in z_list]
        lines.append(f"| **`{lz}`** | " + " | ".join(row_cells) + " |")
    lines.append("")

    # 3.5 Calibration Quality
    cq = summary["calibration_quality"]
    lines.append("### 3.5 Calibration Quality of the Labels")
    lines.append("")
    lines.append(f"- **Total clips scored**: `{cq['n_clips']}`")
    lines.append(f"- **Both stumps derived (`0` confirmed)**: `{cq['both_stumps_derived_count']}`")
    lines.append(f"- **One stump confirmed (`1` confirmed)**: `{cq['one_stump_confirmed_count']}`")
    lines.append(f"- **Both stumps confirmed (`2` confirmed)**: `{cq['both_stumps_confirmed_count']}`")
    lines.append(
        f"- **Homography `residual_px` (n={cq['n_with_residual']})**: "
        f"mean={_fmt_num(cq['mean_residual_px'], 2, ' px')}, "
        f"max={_fmt_num(cq['max_residual_px'], 2, ' px')}"
    )
    lines.append("")

    # 3.6 Unclear Clips Section
    lines.append("### 3.6 Clips Flagged `unclear`")
    lines.append("")
    lines.append(
        "Clips with the `unclear` flag are included in Release metrics, "
        "excluded from Bounce and Impact tolerance/error tables, and listed below:"
    )
    lines.append("")
    if not summary["unclear_clips"]:
        lines.append("_No clips had the `unclear` flag in this run._")
    else:
        lines.append(
            "| Clip ID | Ball | Split | Flags | Release Frame Err | Bounce Frame Err | Bounce Ground Err (m) | Dev Frame Err |"
        )
        lines.append("| --- | --- | --- | --- | ---: | ---: | ---: | ---: |")
        for u in summary["unclear_clips"]:
            lines.append(
                f"| `{u['clip_id']}` | `{u['ball_colour']}` | `{u['split']}` | "
                f"`{', '.join(u['flags'])}` | {u.get('release_frame_error', '—')} | "
                f"{u.get('bounce_frame_error', '—')} | {_fmt_num(u.get('bounce_ground_error_m'), 3)} | "
                f"{u.get('deviation_frame_error', '—')} |"
            )
    lines.append("")

    # 4. Worst 5 Clips per Metric
    lines.append("## 4. Worst 5 Clips per Metric")
    lines.append("")
    w5 = summary["worst_5_per_metric"]
    metric_titles = [
        ("release_frame_abs_error", "Release Frame Error (frames)", 0),
        ("release_pixel_error", "Release Pixel Distance (px)", 1),
        ("bounce_frame_abs_error", "Bounce Frame Error (frames, excl. unclear)", 0),
        ("bounce_ground_error_m", "Bounce Ground Error (m, excl. unclear)", 3),
        ("deviation_frame_abs_error", "Deviation vs Impact Frame Error (frames, excl. unclear)", 0),
        ("deviation_pixel_error", "Deviation vs Impact Pixel Distance (px, excl. unclear)", 1),
    ]
    for key, title, digits in metric_titles:
        lines.append(f"### {title}")
        items = w5.get(key) or []
        if not items:
            lines.append("- _No scored clips_")
        else:
            for rank, item in enumerate(items, start=1):
                val_str = (
                    f"{int(round(item['value']))}"
                    if digits == 0
                    else f"{item['value']:.{digits}f}"
                )
                lines.append(
                    f"{rank}. `{item['clip_id']}` (`{item['ball_colour']}`, split=`{item['split']}`): **{val_str}**"
                )
        lines.append("")

    # 5. Caveats
    lines.append("## 5. Caveats")
    lines.append("")
    lines.append(
        "- **Small sample sizes**: The current baseline evaluation set has a small number of final clips; "
        "percentile estimates (`p90`) and subgroup breakdowns (`ball_colour`, `split`) have high variance until more clips are annotated."
    )
    lines.append(
        "- **Labels made blind to the pipeline**: Ground-truth labels (`release`, `bounce`, `impact`, `calibration_gt`) "
        "were annotated independently in the annotator UI without inspecting pipeline predictions."
    )
    lines.append(
        "- **30 fps temporal resolution limits**: At ~30 fps (~33.3 ms per frame), a fast delivery travels ~0.9–1.2 m between consecutive frames. "
        "A 1-frame sampling difference near bounce or impact naturally introduces 0.5–1.2 m of along-pitch distance difference even when pixel localization is accurate."
    )
    lines.append(
        "- **Legacy `zones.py` length bug (`19.68 m` vs `17.68 m`)**: The legacy tracker sets `BOWL_CREASE_Y = 1.22 + 19.68 = 20.90 m` "
        "instead of the regulation `1.22 + 17.68 = 18.90 m` (`calib_constants.py`), systematically inflating `system.bounce.length_m` relative to true `pitch_z_m`."
    )
    lines.append("")

    return "\n".join(lines)
