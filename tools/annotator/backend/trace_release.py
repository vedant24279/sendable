"""Analyze raw pass-1 ball detections around labelled release frames."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def get_default_labels_dir() -> Path:
    env_dir = os.environ.get("LABELS_DIR", "").strip()
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return (REPO_ROOT / "eval" / "labels").resolve()


def get_default_runs_dir() -> Path:
    env_dir = os.environ.get("EVAL_RUNS_DIR", "").strip()
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return (REPO_ROOT / "eval" / "runs").resolve()


def get_default_analysis_dir() -> Path:
    return (REPO_ROOT / "eval" / "analysis").resolve()


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


def _parse_ball_by_frame(raw_ball: Any) -> Dict[int, List[Dict[str, float]]]:
    out: Dict[int, List[Dict[str, float]]] = {}
    if not isinstance(raw_ball, dict):
        return out
    for raw_k, raw_list in raw_ball.items():
        f_idx = _safe_int(raw_k)
        if f_idx is None or not isinstance(raw_list, list):
            continue
        cands: List[Dict[str, float]] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            cx = _safe_float(item.get("cx"))
            cy = _safe_float(item.get("cy"))
            conf = _safe_float(item.get("conf"))
            if cx is None or cy is None:
                continue
            cands.append({"cx": cx, "cy": cy, "conf": conf if conf is not None else 0.0})
        if cands:
            out[f_idx] = cands
    return out


def _nearest_prev_dist_px(
    curr_cands: Sequence[Dict[str, float]],
    prev_cands: Sequence[Dict[str, float]],
) -> Optional[float]:
    if not curr_cands or not prev_cands:
        return None
    best: Optional[float] = None
    for c in curr_cands:
        for p in prev_cands:
            d = math.hypot(c["cx"] - p["cx"], c["cy"] - p["cy"])
            if best is None or d < best:
                best = d
    return best


def _format_candidates(cands: Sequence[Dict[str, float]]) -> str:
    if not cands:
        return "—"
    return "; ".join(
        f"({c['cx']:.1f}, {c['cy']:.1f}, {c['conf']:.3f})"
        for c in cands
    )


def trace_clip_release(
    label: Dict[str, Any],
    raw_dump: Dict[str, Any],
    results: Optional[Dict[str, Any]],
    *,
    window: int = 10,
) -> Dict[str, Any]:
    """Compute per-clip summary metrics and per-frame trace rows around labelled release."""
    clip_id = str(label.get("clip_id", "unknown"))
    ball_colour = str(label.get("ball_colour") or "unknown").lower()

    lbl_rel = label.get("release") or {}
    lbl_f = _safe_int(lbl_rel.get("frame"))

    str_rel = raw_dump.get("streaming_release")
    stream_f = _safe_int(str_rel.get("frame")) if isinstance(str_rel, dict) else None

    res_events = (results or {}).get("events") or {}
    fin_rel = res_events.get("release")
    final_f = _safe_int(fin_rel.get("frame")) if isinstance(fin_rel, dict) else None

    ball_by_frame = _parse_ball_by_frame(raw_dump.get("ball"))
    frame_count = _safe_int(raw_dump.get("frame_count"))

    detections_between: Optional[int] = None
    if lbl_f is not None and final_f is not None:
        lo = min(lbl_f, final_f)
        hi = max(lbl_f, final_f)
        detections_between = sum(1 for f in range(lo + 1, hi) if f in ball_by_frame)

    rows: List[Dict[str, Any]] = []
    if lbl_f is not None:
        start_f = max(0, lbl_f - window)
        end_f = lbl_f + window
        if frame_count is not None and frame_count > 0:
            end_f = min(end_f, frame_count - 1)
        for f in range(start_f, end_f + 1):
            marks_list: List[str] = []
            if f == lbl_f:
                marks_list.append("L")
            if stream_f is not None and f == stream_f:
                marks_list.append("S")
            if final_f is not None and f == final_f:
                marks_list.append("O")
            marks = ",".join(marks_list)
            cands = ball_by_frame.get(f, [])
            prev_cands = ball_by_frame.get(f - 1, [])
            step_dist = _nearest_prev_dist_px(cands, prev_cands)
            rows.append(
                {
                    "clip_id": clip_id,
                    "ball_colour": ball_colour,
                    "labelled_frame": lbl_f,
                    "streaming_release_frame": stream_f,
                    "final_release_frame": final_f,
                    "detections_between_count": detections_between,
                    "frame": f,
                    "marks": marks,
                    "n_candidates": len(cands),
                    "candidates_str": _format_candidates(cands),
                    "candidates": cands,
                    "step_dist_px": step_dist,
                }
            )

    return {
        "clip_id": clip_id,
        "ball_colour": ball_colour,
        "frame_count": frame_count,
        "labelled_frame": lbl_f,
        "streaming_release_frame": stream_f,
        "final_release_frame": final_f,
        "detections_between_count": detections_between,
        "rows": rows,
    }


def format_release_traces_csv(clip_traces: Sequence[Dict[str, Any]]) -> str:
    """Format all clip trace rows as a flat CSV string."""
    fieldnames = [
        "clip_id",
        "ball_colour",
        "labelled_frame",
        "streaming_release_frame",
        "final_release_frame",
        "detections_between_count",
        "frame",
        "marks",
        "n_candidates",
        "candidates",
        "step_dist_px",
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
                    "labelled_frame": row["labelled_frame"],
                    "streaming_release_frame": row["streaming_release_frame"],
                    "final_release_frame": row["final_release_frame"],
                    "detections_between_count": row["detections_between_count"],
                    "frame": row["frame"],
                    "marks": row["marks"],
                    "n_candidates": row["n_candidates"],
                    "candidates": row["candidates_str"],
                    "step_dist_px": (
                        f"{row['step_dist_px']:.2f}"
                        if row["step_dist_px"] is not None
                        else ""
                    ),
                }
            )
    return buf.getvalue()


def format_release_traces_md(
    clip_traces: Sequence[Dict[str, Any]],
    run_name: str,
    window: int,
) -> str:
    """Format the summary table and per-clip frame traces in Markdown."""
    lines: List[str] = []
    lines.append(f"# Release Traces: `{run_name}`")
    lines.append("")
    lines.append(
        f"- **Window**: `±{window}` frames around labelled release (`L` = labelled release, "
        "`S` = streaming ReleaseDetector before override, `O` = final release in `results.json`)"
    )
    lines.append(
        "- **Detections between**: count of frames strictly between `final_release` and "
        "`labelled_release` (`min < f < max`) containing at least one raw ball detection."
    )
    lines.append("")
    lines.append("## Summary Table")
    lines.append("")
    lines.append(
        "| Clip ID | Ball | Labelled Frame (`L`) | Streaming Release (`S`) | "
        "Final Release (`O`) | Detections Between (`O` ↔ `L`) |"
    )
    lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
    for clip in clip_traces:
        lbl_s = str(clip["labelled_frame"]) if clip["labelled_frame"] is not None else "—"
        str_s = (
            str(clip["streaming_release_frame"])
            if clip["streaming_release_frame"] is not None
            else "null"
        )
        fin_s = (
            str(clip["final_release_frame"])
            if clip["final_release_frame"] is not None
            else "null"
        )
        btw_s = (
            str(clip["detections_between_count"])
            if clip["detections_between_count"] is not None
            else "—"
        )
        lines.append(
            f"| `{clip['clip_id']}` | `{clip['ball_colour']}` | {lbl_s} | "
            f"{str_s} | {fin_s} | {btw_s} |"
        )
    lines.append("")

    for clip in clip_traces:
        lines.append(f"## Clip `{clip['clip_id']}` ({clip['ball_colour']})")
        lines.append("")
        lines.append(
            f"- Labelled release (`L`): `{clip['labelled_frame']}` | "
            f"Streaming release (`S`): `{clip['streaming_release_frame']}` | "
            f"Final release (`O`): `{clip['final_release_frame']}` | "
            f"Detections between `O` and `L`: `{clip['detections_between_count']}`"
        )
        lines.append("")
        lines.append("| Frame | Marks | Ball Candidates `(cx, cy, conf)` | Step Dist (px) |")
        lines.append("| ---: | --- | --- | ---: |")
        for row in clip.get("rows", []):
            marks_s = row["marks"] or "—"
            step_s = (
                f"{row['step_dist_px']:.1f}"
                if row["step_dist_px"] is not None
                else "—"
            )
            lines.append(
                f"| {row['frame']} | {marks_s} | {row['candidates_str']} | {step_s} |"
            )
        lines.append("")

    return "\n".join(lines)


def run_trace_release(
    *,
    run_name: str,
    window: int = 10,
    labels_dir: Optional[Path] = None,
    runs_dir: Optional[Path] = None,
    analysis_dir: Optional[Path] = None,
) -> Tuple[Path, Path, List[Dict[str, Any]]]:
    """Trace release detections for all final labels present in a run and write MD/CSV reports."""
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

            clip_id = str(label.get("clip_id") or path.stem)
            clip_run_dir = run_dir / clip_id
            if not clip_run_dir.is_dir():
                continue

            raw_path = clip_run_dir / "raw_ball_detections.json"
            if not raw_path.is_file():
                print(
                    f"[WARN] Skipping {clip_id}: missing {raw_path.name}",
                    file=sys.stderr,
                )
                continue
            raw_dump = json.loads(raw_path.read_text(encoding="utf-8"))

            results_path = clip_run_dir / "results.json"
            results_data = (
                json.loads(results_path.read_text(encoding="utf-8"))
                if results_path.is_file()
                else None
            )

            trace = trace_clip_release(
                label,
                raw_dump,
                results_data,
                window=window,
            )
            clip_traces.append(trace)

            print(
                f"=== {clip_id} ({trace['ball_colour']}) "
                f"L={trace['labelled_frame']} S={trace['streaming_release_frame']} "
                f"O={trace['final_release_frame']} between={trace['detections_between_count']} ==="
            )
            print("frame | marks | candidates | step_px")
            for row in trace["rows"]:
                step_s = (
                    f"{row['step_dist_px']:.1f}"
                    if row["step_dist_px"] is not None
                    else "-"
                )
                print(
                    f"{row['frame']:>5} | {row['marks'] or '-':<5} | "
                    f"{row['candidates_str']} | {step_s}"
                )
            print()

    resolved_analysis_dir.mkdir(parents=True, exist_ok=True)
    md_path = resolved_analysis_dir / f"release_traces_{run_name}.md"
    csv_path = resolved_analysis_dir / f"release_traces_{run_name}.csv"

    md_path.write_text(
        format_release_traces_md(clip_traces, run_name, window),
        encoding="utf-8",
    )
    csv_path.write_text(
        format_release_traces_csv(clip_traces),
        encoding="utf-8",
    )

    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")
    return md_path, csv_path, clip_traces


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trace raw pass-1 ball detections around labelled release frames."
    )
    parser.add_argument(
        "--run",
        required=True,
        type=str,
        help="Run name under eval/runs/<run_name>.",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=10,
        help="Frame half-window around labelled release (default: 10).",
    )
    parser.add_argument(
        "--labels-dir",
        type=Path,
        default=None,
        help="Optional override for labels directory.",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=None,
        help="Optional override for runs directory.",
    )
    parser.add_argument(
        "--analysis-dir",
        type=Path,
        default=None,
        help="Optional override for eval/analysis directory.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    run_trace_release(
        run_name=args.run,
        window=args.window,
        labels_dir=args.labels_dir,
        runs_dir=args.runs_dir,
        analysis_dir=args.analysis_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
