"""Measure post-impact raw detection coverage vs results.json trajectory coverage."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from release_rules import get_bowler_crease_width_px
from trace_impact import BallCandidate, parse_rich_ball_by_frame
from trace_release import (
    _safe_int,
    get_default_analysis_dir,
    get_default_labels_dir,
    get_default_runs_dir,
)

OUTLIER_DIST_CREASE_FRAC: float = 0.20


@dataclass(frozen=True)
class PostImpactClipCoverage:
    """Post-impact coverage metrics for a single clip over [impact_frame, last_visible_frame]."""

    clip_id: str
    ball_colour: str
    impact_frame: int
    last_visible_frame: int
    n_frames: int
    raw_det_frames: int
    raw_coverage_frac: float
    longest_gap_frames: int
    outlier_detections: int
    traj_frames: int
    traj_non_interp_frames: int
    traj_coverage_frac: float
    traj_last_frame: Optional[int]


def _longest_missing_run(
    start_frame: int,
    end_frame: int,
    present_frames: Dict[int, Any],
) -> int:
    longest = 0
    current = 0
    for f in range(start_frame, end_frame + 1):
        if f not in present_frames:
            current += 1
            if current > longest:
                longest = current
        else:
            current = 0
    return longest


def _count_outlier_detections(
    start_frame: int,
    end_frame: int,
    ball_by_frame: Dict[int, List[BallCandidate]],
    crease_width_px: float,
) -> int:
    """Count detections in [start_frame, end_frame] > 0.2*W from nearest in adjacent frames on both sides."""
    threshold_px = OUTLIER_DIST_CREASE_FRAC * crease_width_px
    det_frames = [f for f in range(start_frame, end_frame + 1) if f in ball_by_frame]
    if len(det_frames) < 3:
        return 0

    outliers = 0
    for idx in range(1, len(det_frames) - 1):
        f_cur = det_frames[idx]
        f_prev = det_frames[idx - 1]
        f_next = det_frames[idx + 1]
        prev_cands = ball_by_frame[f_prev]
        next_cands = ball_by_frame[f_next]
        if not prev_cands or not next_cands:
            continue
        for cand in ball_by_frame[f_cur]:
            d_prev = min(
                math.hypot(cand.cx - p.cx, cand.cy - p.cy) for p in prev_cands
            )
            d_next = min(
                math.hypot(cand.cx - n.cx, cand.cy - n.cy) for n in next_cands
            )
            if d_prev > threshold_px and d_next > threshold_px:
                outliers += 1
    return outliers


def compute_clip_post_impact_coverage(
    label: Dict[str, Any],
    raw_dump: Dict[str, Any],
    results: Optional[Dict[str, Any]],
) -> Optional[PostImpactClipCoverage]:
    """Compute post-impact coverage between labelled impact frame and last_visible_frame."""
    clip_id = str(label.get("clip_id") or "unknown")
    ball_colour = str(label.get("ball_colour") or "unknown").lower()

    impact = label.get("impact")
    if not isinstance(impact, dict):
        return None
    if str(impact.get("type") or "none").lower() == "none":
        return None
    imp_f = _safe_int(impact.get("frame"))
    last_vis_f = _safe_int(label.get("last_visible_frame"))
    if imp_f is None or last_vis_f is None or last_vis_f < imp_f:
        return None

    calib = label.get("calibration_gt") or {}
    calib_pts = calib.get("points") if isinstance(calib, dict) else {}
    crease_w = get_bowler_crease_width_px(calib_pts)

    n_frames = last_vis_f - imp_f + 1
    ball_by_frame = parse_rich_ball_by_frame(raw_dump.get("ball"))

    raw_det_frames = sum(1 for f in range(imp_f, last_vis_f + 1) if f in ball_by_frame)
    raw_cov = raw_det_frames / n_frames if n_frames > 0 else 0.0
    longest_gap = _longest_missing_run(imp_f, last_vis_f, ball_by_frame)
    outliers = _count_outlier_detections(imp_f, last_vis_f, ball_by_frame, crease_w)

    traj_by_frame: Dict[int, Dict[str, Any]] = {}
    for pt in (results or {}).get("trajectory") or []:
        if isinstance(pt, dict):
            tf = _safe_int(pt.get("frame"))
            if tf is not None:
                traj_by_frame[tf] = pt

    traj_frames = sum(1 for f in range(imp_f, last_vis_f + 1) if f in traj_by_frame)
    traj_non_interp = sum(
        1
        for f in range(imp_f, last_vis_f + 1)
        if f in traj_by_frame and not bool(traj_by_frame[f].get("interpolated", False))
    )
    traj_cov = traj_frames / n_frames if n_frames > 0 else 0.0
    traj_last_f = max(traj_by_frame) if traj_by_frame else None

    return PostImpactClipCoverage(
        clip_id=clip_id,
        ball_colour=ball_colour,
        impact_frame=imp_f,
        last_visible_frame=last_vis_f,
        n_frames=n_frames,
        raw_det_frames=raw_det_frames,
        raw_coverage_frac=raw_cov,
        longest_gap_frames=longest_gap,
        outlier_detections=outliers,
        traj_frames=traj_frames,
        traj_non_interp_frames=traj_non_interp,
        traj_coverage_frac=traj_cov,
        traj_last_frame=traj_last_f,
    )


def render_post_impact_coverage_markdown(
    run_name: str,
    rows: Sequence[PostImpactClipCoverage],
) -> str:
    """Format post-impact coverage comparison table as Markdown."""
    lines: List[str] = [
        f"# Post-Impact Coverage — `{run_name}`",
        "",
        "- Interval: inclusive frames `[labelled_impact_frame .. last_visible_frame]`.",
        "- Outliers: raw detections whose distance to the nearest detection in the adjacent detected frames is `> 0.2 * W` on both sides.",
        "",
        "## Per-Clip Post-Impact Coverage",
        "",
        "| Clip | Ball | Impact (`L`) | Last Visible | Frames | Raw Det Frames | Raw Coverage | Longest Gap | Outliers (`>0.2W`) | `results.json` Traj Frames | `results.json` Coverage | `results.json` Last Frame |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for r in rows:
        last_tf = str(r.traj_last_frame) if r.traj_last_frame is not None else "—"
        lines.append(
            f"| `{r.clip_id}` | `{r.ball_colour}` | {r.impact_frame} | {r.last_visible_frame} | "
            f"{r.n_frames} | {r.raw_det_frames}/{r.n_frames} | {100.0 * r.raw_coverage_frac:.1f}% | "
            f"{r.longest_gap_frames} | {r.outlier_detections} | "
            f"{r.traj_frames}/{r.n_frames} | {100.0 * r.traj_coverage_frac:.1f}% | {last_tf} |"
        )

    if rows:
        tot_frames = sum(r.n_frames for r in rows)
        tot_raw = sum(r.raw_det_frames for r in rows)
        tot_traj = sum(r.traj_frames for r in rows)
        tot_outliers = sum(r.outlier_detections for r in rows)
        max_gap = max(r.longest_gap_frames for r in rows)
        raw_fracs = np.asarray([r.raw_coverage_frac for r in rows], dtype=np.float64)
        traj_fracs = np.asarray([r.traj_coverage_frac for r in rows], dtype=np.float64)

        lines.append(
            f"| **Mean / Total** | — | — | — | **{tot_frames}** | **{tot_raw}/{tot_frames}** | "
            f"**{100.0 * float(np.mean(raw_fracs)):.1f}%** (med {100.0 * float(np.median(raw_fracs)):.1f}%) | "
            f"max {max_gap} | **{tot_outliers}** | **{tot_traj}/{tot_frames}** | "
            f"**{100.0 * float(np.mean(traj_fracs)):.1f}%** (med {100.0 * float(np.median(traj_fracs)):.1f}%) | — |"
        )

    return "\n".join(lines).rstrip() + "\n"


def run_post_impact_coverage(
    run_name: str,
    labels_dir: Path,
    runs_dir: Path,
    analysis_dir: Path,
) -> Path:
    """Compute post-impact coverage across clips and write Markdown report."""
    run_dir = runs_dir / run_name
    if not labels_dir.is_dir():
        raise FileNotFoundError(f"Labels directory not found: {labels_dir}")
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    rows: List[PostImpactClipCoverage] = []
    for label_path in sorted(labels_dir.glob("*.json")):
        if label_path.name.startswith("_"):
            continue
        label = json.loads(label_path.read_text(encoding="utf-8"))
        if not isinstance(label, dict) or label.get("status") != "final":
            continue
        clip_id = str(label.get("clip_id") or label_path.stem)
        raw_path = run_dir / clip_id / "raw_ball_detections.json"
        if not raw_path.is_file():
            continue
        raw_dump = json.loads(raw_path.read_text(encoding="utf-8"))
        res_path = run_dir / clip_id / "results.json"
        results = (
            json.loads(res_path.read_text(encoding="utf-8"))
            if res_path.is_file()
            else None
        )
        cov = compute_clip_post_impact_coverage(label, raw_dump, results)
        if cov is not None:
            rows.append(cov)

    analysis_dir.mkdir(parents=True, exist_ok=True)
    out_path = analysis_dir / f"post_impact_coverage_{run_name}.md"
    out_path.write_text(
        render_post_impact_coverage_markdown(run_name, rows),
        encoding="utf-8",
    )
    return out_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default="release_dump_1")
    parser.add_argument("--labels-dir", type=Path, default=None)
    parser.add_argument("--runs-dir", type=Path, default=None)
    parser.add_argument("--analysis-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    labels_dir = (
        args.labels_dir.resolve()
        if args.labels_dir is not None
        else get_default_labels_dir()
    )
    runs_dir = (
        args.runs_dir.resolve()
        if args.runs_dir is not None
        else get_default_runs_dir()
    )
    analysis_dir = (
        args.analysis_dir.resolve()
        if args.analysis_dir is not None
        else get_default_analysis_dir()
    )

    out_path = run_post_impact_coverage(
        run_name=args.run,
        labels_dir=labels_dir,
        runs_dir=runs_dir,
        analysis_dir=analysis_dir,
    )
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
