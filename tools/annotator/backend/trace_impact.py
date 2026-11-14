"""Trace raw pass-1 ball detections and track kinematics around labelled impacts."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from release_rules import get_bowler_crease_width_px
from trace_release import (
    _safe_float,
    _safe_int,
    get_default_analysis_dir,
    get_default_labels_dir,
    get_default_runs_dir,
)


@dataclass(frozen=True)
class BallCandidate:
    """One raw YOLO ball detection in a frame."""

    cx: float
    cy: float
    conf: float
    width: float
    height: float


@dataclass(frozen=True)
class TrackStepRow:
    """Kinematics for the nearest-to-previous chosen candidate on a frame."""

    frame: int
    cand: BallCandidate
    dt: Optional[int]
    dx: Optional[float]
    dy: Optional[float]
    speed_norm: Optional[float]
    angle_deg: Optional[float]
    angle_change_prev_deg: Optional[float]


def parse_rich_ball_by_frame(raw_ball: Any) -> Dict[int, List[BallCandidate]]:
    """Parse raw_ball_detections['ball'] preserving bbox width and height."""
    out: Dict[int, List[BallCandidate]] = {}
    if not isinstance(raw_ball, dict):
        return out
    for raw_k, raw_list in raw_ball.items():
        f_idx = _safe_int(raw_k)
        if f_idx is None or not isinstance(raw_list, list):
            continue
        cands: List[BallCandidate] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            cx = _safe_float(item.get("cx"))
            cy = _safe_float(item.get("cy"))
            x1 = _safe_float(item.get("x1"))
            y1 = _safe_float(item.get("y1"))
            x2 = _safe_float(item.get("x2"))
            y2 = _safe_float(item.get("y2"))
            conf = _safe_float(item.get("conf"))
            if cx is None or cy is None:
                continue
            width = (x2 - x1) if (x1 is not None and x2 is not None) else 0.0
            height = (y2 - y1) if (y1 is not None and y2 is not None) else 0.0
            cands.append(
                BallCandidate(
                    cx=cx,
                    cy=cy,
                    conf=conf if conf is not None else 0.0,
                    width=width,
                    height=height,
                )
            )
        if cands:
            out[f_idx] = cands
    return out


def shortest_angle_diff_deg(a_deg: float, b_deg: float) -> float:
    """Return smallest unsigned angle difference in degrees in [0, 180]."""
    diff = (a_deg - b_deg + 180.0) % 360.0 - 180.0
    return abs(diff)


def vector_angle_diff_deg(
    v1: Tuple[float, float],
    v2: Tuple[float, float],
) -> Optional[float]:
    """Return unsigned angle in degrees between two 2D vectors, or None if zero-length."""
    m1 = math.hypot(v1[0], v1[1])
    m2 = math.hypot(v2[0], v2[1])
    if m1 <= 1e-9 or m2 <= 1e-9:
        return None
    a1 = math.degrees(math.atan2(v1[1], v1[0]))
    a2 = math.degrees(math.atan2(v2[1], v2[0]))
    return shortest_angle_diff_deg(a1, a2)


def build_track_kinematics(
    ball_by_frame: Dict[int, List[BallCandidate]],
    crease_width_px: float,
) -> List[TrackStepRow]:
    """Build nearest-to-previous track over all frames and compute per-step kinematics."""
    if not ball_by_frame or crease_width_px <= 0.0:
        return []
    ordered_frames = sorted(ball_by_frame)
    first_f = ordered_frames[0]
    first_cand = max(ball_by_frame[first_f], key=lambda c: c.conf)
    chosen: List[Tuple[int, BallCandidate]] = [(first_f, first_cand)]
    for f_idx in ordered_frames[1:]:
        prev_c = chosen[-1][1]
        best = min(
            ball_by_frame[f_idx],
            key=lambda c: (math.hypot(c.cx - prev_c.cx, c.cy - prev_c.cy), -c.conf),
        )
        chosen.append((f_idx, best))

    rows: List[TrackStepRow] = []
    angles: List[Optional[float]] = []
    for i, (f_idx, cand) in enumerate(chosen):
        if i == 0:
            rows.append(
                TrackStepRow(
                    frame=f_idx,
                    cand=cand,
                    dt=None,
                    dx=None,
                    dy=None,
                    speed_norm=None,
                    angle_deg=None,
                    angle_change_prev_deg=None,
                )
            )
            angles.append(None)
            continue

        prev_f, prev_c = chosen[i - 1]
        dt = max(1, f_idx - prev_f)
        dx = cand.cx - prev_c.cx
        dy = cand.cy - prev_c.cy
        speed_norm = math.hypot(dx, dy) / (dt * crease_width_px)
        angle_deg = math.degrees(math.atan2(dy, dx)) if (dx != 0.0 or dy != 0.0) else None
        prev_angle = angles[-1]
        angle_change = (
            shortest_angle_diff_deg(angle_deg, prev_angle)
            if (angle_deg is not None and prev_angle is not None)
            else None
        )
        angles.append(angle_deg)
        rows.append(
            TrackStepRow(
                frame=f_idx,
                cand=cand,
                dt=dt,
                dx=dx,
                dy=dy,
                speed_norm=speed_norm,
                angle_deg=angle_deg,
                angle_change_prev_deg=angle_change,
            )
        )
    return rows


def _format_candidates_rich(cands: Sequence[BallCandidate]) -> str:
    if not cands:
        return "—"
    return "; ".join(
        f"({c.cx:.1f}, {c.cy:.1f}, {c.conf:.3f}, {c.width:.0f}x{c.height:.0f})"
        for c in cands
    )


def _turn_angle_at_track_index(track_rows: Sequence[TrackStepRow], idx: int) -> Optional[float]:
    """Angle in degrees between incoming step (idx-1 -> idx) and outgoing step (idx -> idx+1)."""
    if idx <= 0 or idx + 1 >= len(track_rows):
        return None
    a_in = track_rows[idx].angle_deg
    a_out = track_rows[idx + 1].angle_deg
    if a_in is None or a_out is None:
        return None
    return shortest_angle_diff_deg(a_out, a_in)


def _largest_turn_frame_in_window(
    track_rows: Sequence[TrackStepRow],
    bounce_frame: Optional[int],
) -> Tuple[Optional[int], Optional[float]]:
    if bounce_frame is None:
        return None, None
    lo = bounce_frame + 1
    hi = bounce_frame + 12
    best_f: Optional[int] = None
    best_deg: Optional[float] = None
    for idx, row in enumerate(track_rows):
        if row.frame < lo or row.frame > hi:
            continue
        turn = _turn_angle_at_track_index(track_rows, idx)
        if turn is None:
            continue
        if best_deg is None or turn > best_deg:
            best_deg = turn
            best_f = row.frame
    return best_f, best_deg


def _speed_ratio_at_frame(
    track_rows: Sequence[TrackStepRow],
    target_frame: Optional[int],
) -> Optional[float]:
    """Mean of 2 outgoing step speeds / mean of 2 incoming step speeds at target_frame."""
    if target_frame is None:
        return None
    target_idx: Optional[int] = None
    for i, row in enumerate(track_rows):
        if row.frame == target_frame:
            target_idx = i
            break
    if target_idx is None:
        return None
    if target_idx < 2 or target_idx + 2 >= len(track_rows):
        return None
    before = [track_rows[target_idx - 1].speed_norm, track_rows[target_idx].speed_norm]
    after = [track_rows[target_idx + 1].speed_norm, track_rows[target_idx + 2].speed_norm]
    if any(v is None for v in before + after):
        return None
    mean_before = 0.5 * (float(before[0]) + float(before[1]))  # type: ignore[arg-type]
    mean_after = 0.5 * (float(after[0]) + float(after[1]))  # type: ignore[arg-type]
    if mean_before <= 1e-9:
        return None
    return mean_after / mean_before


def trace_clip_impact(
    label: Dict[str, Any],
    raw_dump: Dict[str, Any],
    results: Optional[Dict[str, Any]],
    *,
    before: int = 8,
    after: int = 12,
) -> Dict[str, Any]:
    """Compute per-clip summary metrics and per-frame trace rows around labelled impact."""
    clip_id = str(label.get("clip_id", "unknown"))
    ball_colour = str(label.get("ball_colour") or "unknown").lower()

    lbl_bnc = label.get("bounce") or {}
    lbl_bnc_f = _safe_int(lbl_bnc.get("frame"))

    lbl_imp = label.get("impact") or {}
    lbl_imp_f = _safe_int(lbl_imp.get("frame"))
    lbl_imp_type = str(lbl_imp.get("type") or "none").lower()

    res_events = (results or {}).get("events") or {}
    sys_dev = res_events.get("deviation")
    sys_dev_f = _safe_int(sys_dev.get("frame")) if isinstance(sys_dev, dict) else None

    calib = label.get("calibration_gt") or {}
    calib_pts = calib.get("points") if isinstance(calib, dict) else {}
    crease_w = get_bowler_crease_width_px(calib_pts)

    ball_by_frame = parse_rich_ball_by_frame(raw_dump.get("ball"))
    track_rows = build_track_kinematics(ball_by_frame, crease_w)
    track_by_frame = {row.frame: row for row in track_rows}
    frame_count = _safe_int(raw_dump.get("frame_count"))

    last_det_at_or_after_bounce: Optional[int] = None
    if lbl_bnc_f is not None:
        post_bnc = [f for f in ball_by_frame if f >= lbl_bnc_f]
        if post_bnc:
            last_det_at_or_after_bounce = max(post_bnc)

    dets_next_3: Optional[int] = None
    if lbl_imp_f is not None:
        dets_next_3 = sum(
            1 for f in range(lbl_imp_f + 1, lbl_imp_f + 4) if f in ball_by_frame
        )

    max_turn_f, max_turn_deg = _largest_turn_frame_in_window(track_rows, lbl_bnc_f)
    speed_ratio_at_imp = _speed_ratio_at_frame(track_rows, lbl_imp_f)

    rows: List[Dict[str, Any]] = []
    if lbl_imp_f is not None:
        start_f = max(0, lbl_imp_f - before)
        end_f = lbl_imp_f + after
        if frame_count is not None and frame_count > 0:
            end_f = min(end_f, frame_count - 1)
        for f in range(start_f, end_f + 1):
            marks_list: List[str] = []
            if lbl_bnc_f is not None and f == lbl_bnc_f:
                marks_list.append("B")
            if f == lbl_imp_f:
                marks_list.append("L")
            if sys_dev_f is not None and f == sys_dev_f:
                marks_list.append("D")
            marks = ",".join(marks_list)
            cands = ball_by_frame.get(f, [])
            t_row = track_by_frame.get(f)
            rows.append(
                {
                    "clip_id": clip_id,
                    "ball_colour": ball_colour,
                    "labelled_bounce_frame": lbl_bnc_f,
                    "labelled_impact_frame": lbl_imp_f,
                    "system_deviation_frame": sys_dev_f,
                    "frame": f,
                    "marks": marks,
                    "n_candidates": len(cands),
                    "candidates_str": _format_candidates_rich(cands),
                    "track_cx": t_row.cand.cx if t_row else None,
                    "track_cy": t_row.cand.cy if t_row else None,
                    "dx": t_row.dx if t_row else None,
                    "dy": t_row.dy if t_row else None,
                    "speed_norm": t_row.speed_norm if t_row else None,
                    "angle_deg": t_row.angle_deg if t_row else None,
                    "angle_change_prev_deg": t_row.angle_change_prev_deg if t_row else None,
                }
            )

    return {
        "clip_id": clip_id,
        "ball_colour": ball_colour,
        "impact_type": lbl_imp_type,
        "labelled_bounce_frame": lbl_bnc_f,
        "labelled_impact_frame": lbl_imp_f,
        "system_deviation_frame": sys_dev_f,
        "last_det_at_or_after_bounce": last_det_at_or_after_bounce,
        "dets_next_3_after_impact": dets_next_3,
        "max_turn_frame": max_turn_f,
        "max_turn_deg": max_turn_deg,
        "speed_ratio_at_impact": speed_ratio_at_imp,
        "rows": rows,
    }


def _fmt_num(val: Optional[float], spec: str = ".1f", dash: str = "—") -> str:
    if val is None:
        return dash
    return format(val, spec)


def format_impact_traces_csv(clip_traces: Sequence[Dict[str, Any]]) -> str:
    """Format per-frame impact traces as CSV."""
    fieldnames = [
        "clip_id",
        "ball_colour",
        "labelled_bounce_frame",
        "labelled_impact_frame",
        "system_deviation_frame",
        "frame",
        "marks",
        "n_candidates",
        "candidates",
        "dx",
        "dy",
        "speed_norm",
        "angle_deg",
        "angle_change_prev_deg",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for clip in clip_traces:
        for row in clip.get("rows", []):
            writer.writerow(
                {
                    "clip_id": row["clip_id"],
                    "ball_colour": row["ball_colour"],
                    "labelled_bounce_frame": row["labelled_bounce_frame"],
                    "labelled_impact_frame": row["labelled_impact_frame"],
                    "system_deviation_frame": row["system_deviation_frame"],
                    "frame": row["frame"],
                    "marks": row["marks"],
                    "n_candidates": row["n_candidates"],
                    "candidates": row["candidates_str"],
                    "dx": _fmt_num(row["dx"], ".1f", ""),
                    "dy": _fmt_num(row["dy"], ".1f", ""),
                    "speed_norm": _fmt_num(row["speed_norm"], ".4f", ""),
                    "angle_deg": _fmt_num(row["angle_deg"], ".1f", ""),
                    "angle_change_prev_deg": _fmt_num(row["angle_change_prev_deg"], ".1f", ""),
                }
            )
    return buf.getvalue()


def format_impact_traces_md(
    clip_traces: Sequence[Dict[str, Any]],
    run_name: str,
    before: int,
    after: int,
) -> str:
    """Format summary table and per-clip kinematics traces as Markdown."""
    lines: List[str] = [
        f"# Impact Traces: `{run_name}`",
        "",
        f"- **Window**: `L - {before}` to `L + {after}` (`B` = labelled bounce frame, `L` = labelled impact frame, `D` = system deviation frame)",
        "- **Step kinematics**: `(dx, dy)` and normalised speed `(px/frame) / (bowl_R.x - bowl_L.x)` along nearest-to-previous track; direction angle `atan2(dy, dx)` and unsigned change from previous step.",
        "",
        "## Summary Table",
        "",
        "| Clip ID | Ball | Label Bounce (`B`) | Label Impact (`L`) | Sys Dev (`D`) | Last Det >= `B` | Dets in `[L+1..L+3]` | Max Turn Frame (`[B+1..B+12]`) | Speed Ratio at `L` (after2 / before2) |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for c in clip_traces:
        turn_s = (
            f"{c['max_turn_frame']} ({c['max_turn_deg']:.1f}°)"
            if c["max_turn_frame"] is not None and c["max_turn_deg"] is not None
            else "—"
        )
        ratio_s = (
            f"{c['speed_ratio_at_impact']:.2f}"
            if c["speed_ratio_at_impact"] is not None
            else "—"
        )
        lines.append(
            f"| `{c['clip_id']}` | `{c['ball_colour']}` | "
            f"{c['labelled_bounce_frame'] if c['labelled_bounce_frame'] is not None else '—'} | "
            f"{c['labelled_impact_frame'] if c['labelled_impact_frame'] is not None else '—'} | "
            f"{c['system_deviation_frame'] if c['system_deviation_frame'] is not None else 'null'} | "
            f"{c['last_det_at_or_after_bounce'] if c['last_det_at_or_after_bounce'] is not None else '—'} | "
            f"{c['dets_next_3_after_impact'] if c['dets_next_3_after_impact'] is not None else '—'} | "
            f"{turn_s} | {ratio_s} |"
        )
    lines.append("")

    for c in clip_traces:
        lines.append(f"## Clip `{c['clip_id']}` ({c['ball_colour']}, {c['impact_type']})")
        lines.append("")
        lines.append(
            f"- Bounce (`B`): `{c['labelled_bounce_frame']}` | "
            f"Labelled impact (`L`): `{c['labelled_impact_frame']}` | "
            f"System deviation (`D`): `{c['system_deviation_frame']}` | "
            f"Last det >= `B`: `{c['last_det_at_or_after_bounce']}` | "
            f"Dets in `[L+1..L+3]`: `{c['dets_next_3_after_impact']}` | "
            f"Max turn `[B+1..B+12]`: `{c['max_turn_frame']}` | "
            f"Speed ratio at `L`: `{_fmt_num(c['speed_ratio_at_impact'], '.2f')}`"
        )
        lines.append("")
        lines.append(
            "| Frame | Marks | Candidates `(cx, cy, conf, wxh)` | Step `(dx, dy)` | Norm Speed | Dir (deg) | ΔDir (deg) |"
        )
        lines.append("| ---: | --- | --- | --- | ---: | ---: | ---: |")
        for row in c.get("rows", []):
            vec_s = (
                f"({row['dx']:+.1f}, {row['dy']:+.1f})"
                if row["dx"] is not None and row["dy"] is not None
                else "—"
            )
            lines.append(
                f"| {row['frame']} | {row['marks'] or '—'} | {row['candidates_str']} | "
                f"{vec_s} | {_fmt_num(row['speed_norm'], '.4f')} | "
                f"{_fmt_num(row['angle_deg'], '+.1f')} | "
                f"{_fmt_num(row['angle_change_prev_deg'], '.1f')} |"
            )
        lines.append("")

    return "\n".join(lines)


def run_trace_impact(
    *,
    run_name: str,
    before: int = 8,
    after: int = 12,
    labels_dir: Optional[Path] = None,
    runs_dir: Optional[Path] = None,
    analysis_dir: Optional[Path] = None,
) -> Tuple[Path, Path, List[Dict[str, Any]]]:
    """Trace raw detections around labelled impacts and write Markdown/CSV reports."""
    resolved_labels_dir = (labels_dir or get_default_labels_dir()).resolve()
    resolved_runs_dir = (runs_dir or get_default_runs_dir()).resolve()
    resolved_analysis_dir = (analysis_dir or get_default_analysis_dir()).resolve()

    run_dir = resolved_runs_dir / run_name
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run directory does not exist: {run_dir}")

    clip_traces: List[Dict[str, Any]] = []
    if resolved_labels_dir.is_dir():
        for path in sorted(resolved_labels_dir.glob("*.json")):
            if path.name.startswith("_"):
                continue
            try:
                label = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                print(f"[WARN] Skipping unreadable label {path.name}: {exc}", file=sys.stderr)
                continue
            if not isinstance(label, dict) or label.get("status") != "final":
                continue
            impact = label.get("impact")
            if not isinstance(impact, dict):
                continue
            imp_type = str(impact.get("type") or "none").lower()
            if imp_type == "none" or _safe_int(impact.get("frame")) is None:
                continue

            clip_id = str(label.get("clip_id") or path.stem)
            clip_run_dir = run_dir / clip_id
            raw_path = clip_run_dir / "raw_ball_detections.json"
            if not raw_path.is_file():
                continue
            raw_dump = json.loads(raw_path.read_text(encoding="utf-8"))
            res_path = clip_run_dir / "results.json"
            results_data = (
                json.loads(res_path.read_text(encoding="utf-8"))
                if res_path.is_file()
                else None
            )

            trace = trace_clip_impact(
                label,
                raw_dump,
                results_data,
                before=before,
                after=after,
            )
            clip_traces.append(trace)

            print(
                f"=== {clip_id} ({trace['ball_colour']}) "
                f"B={trace['labelled_bounce_frame']} L={trace['labelled_impact_frame']} "
                f"D={trace['system_deviation_frame']} last_det={trace['last_det_at_or_after_bounce']} "
                f"next3={trace['dets_next_3_after_impact']} max_turn={trace['max_turn_frame']} "
                f"spd_ratio={_fmt_num(trace['speed_ratio_at_impact'], '.2f')} ==="
            )
            for row in trace["rows"]:
                vec_s = (
                    f"({row['dx']:+.1f},{row['dy']:+.1f})"
                    if row["dx"] is not None and row["dy"] is not None
                    else "-"
                )
                print(
                    f"{row['frame']:>4} | {row['marks'] or '-':<5} | {row['candidates_str']} | "
                    f"{vec_s} | {_fmt_num(row['speed_norm'], '.4f', '-')} | "
                    f"{_fmt_num(row['angle_deg'], '+.1f', '-')} | "
                    f"{_fmt_num(row['angle_change_prev_deg'], '.1f', '-')}"
                )
            print()

    resolved_analysis_dir.mkdir(parents=True, exist_ok=True)
    md_path = resolved_analysis_dir / f"impact_traces_{run_name}.md"
    csv_path = resolved_analysis_dir / f"impact_traces_{run_name}.csv"
    md_path.write_text(
        format_impact_traces_md(clip_traces, run_name, before, after),
        encoding="utf-8",
    )
    csv_path.write_text(format_impact_traces_csv(clip_traces), encoding="utf-8")
    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")
    return md_path, csv_path, clip_traces


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trace raw pass-1 ball detections around labelled impact frames."
    )
    parser.add_argument("--run", required=True, type=str)
    parser.add_argument("--before", type=int, default=8)
    parser.add_argument("--after", type=int, default=12)
    parser.add_argument("--labels-dir", type=Path, default=None)
    parser.add_argument("--runs-dir", type=Path, default=None)
    parser.add_argument("--analysis-dir", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    run_trace_impact(
        run_name=args.run,
        before=args.before,
        after=args.after,
        labels_dir=args.labels_dir,
        runs_dir=args.runs_dir,
        analysis_dir=args.analysis_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
