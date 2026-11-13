"""CLI script to score a pipeline batch run against ground-truth labels."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.library import get_library_dir, load_library_catalog  # noqa: E402
from scoring import (  # noqa: E402
    DEFAULT_TOLERANCES,
    aggregate_scores,
    format_markdown_report,
    format_per_clip_csv,
    load_legacy_zones,
    score_clip,
)


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


def get_default_reports_dir() -> Path:
    env_dir = os.environ.get("EVAL_REPORTS_DIR", "").strip()
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return (REPO_ROOT / "eval" / "reports").resolve()


def load_final_calibrated_labels(labels_dir: Path) -> List[Dict[str, Any]]:
    if not labels_dir.is_dir():
        return []
    labels: List[Dict[str, Any]] = []
    for path in sorted(labels_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[WARN] Skipping unreadable label {path.name}: {exc}", file=sys.stderr)
            continue
        if not isinstance(data, dict):
            continue
        if data.get("status") != "final" or data.get("calibration_gt") is None:
            continue
        labels.append(data)
    return labels


def run_scoring(
    *,
    run_name: str,
    tolerances: Sequence[int] = DEFAULT_TOLERANCES,
    labels_dir: Optional[Path] = None,
    library_dir: Optional[Path] = None,
    runs_dir: Optional[Path] = None,
    reports_dir: Optional[Path] = None,
) -> Tuple[Path, Path, Path]:
    resolved_labels_dir = (labels_dir or get_default_labels_dir()).resolve()
    resolved_library_dir = (library_dir or get_library_dir()).resolve()
    resolved_runs_dir = (runs_dir or get_default_runs_dir()).resolve()
    resolved_reports_dir = (reports_dir or get_default_reports_dir()).resolve()

    run_dir = resolved_runs_dir / run_name
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run directory does not exist: {run_dir}")

    run_info_path = run_dir / "run_info.json"
    run_info: Dict[str, Any] = {}
    if run_info_path.is_file():
        try:
            run_info = json.loads(run_info_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[WARN] Could not parse {run_info_path}: {exc}", file=sys.stderr)

    catalog = load_library_catalog(resolved_library_dir)
    labels = load_final_calibrated_labels(resolved_labels_dir)
    zones = load_legacy_zones()

    # If the run was restricted with --only, score the clips in the run (or all final labels if present in run_dir)
    run_clip_ids = {
        p.name for p in run_dir.iterdir() if p.is_dir() and (p / "results.json").is_file()
    }
    if run_info.get("clips"):
        recorded_ids = {str(c.get("clip_id")) for c in run_info["clips"] if c.get("clip_id")}
        selected_labels = [l for l in labels if str(l.get("clip_id")) in recorded_ids]
    elif run_clip_ids:
        selected_labels = [l for l in labels if str(l.get("clip_id")) in run_clip_ids]
    else:
        selected_labels = labels

    clip_scores: List[Dict[str, Any]] = []
    for label in selected_labels:
        clip_id = str(label["clip_id"])
        results_path = run_dir / clip_id / "results.json"
        results_data: Optional[Dict[str, Any]] = None
        if results_path.is_file():
            results_data = json.loads(results_path.read_text(encoding="utf-8"))

        lib_entry = catalog.get(clip_id) or {}
        expected_fc = lib_entry.get("frame_count")
        if expected_fc is None:
            expected_fc = label.get("frame_count")
        expected_fc_int = int(expected_fc) if isinstance(expected_fc, (int, float)) else None

        scored = score_clip(
            label,
            results_data,
            expected_frame_count=expected_fc_int,
            zones=zones,
        )
        clip_scores.append(scored)

    summary = aggregate_scores(
        clip_scores,
        tolerances=tolerances,
        zones=zones,
        run_info=run_info,
    )

    resolved_reports_dir.mkdir(parents=True, exist_ok=True)
    md_path = resolved_reports_dir / f"{run_name}.md"
    csv_path = resolved_reports_dir / f"{run_name}_per_clip.csv"
    json_path = resolved_reports_dir / f"{run_name}_summary.json"

    md_path.write_text(format_markdown_report(summary, run_name), encoding="utf-8")
    csv_path.write_text(format_per_clip_csv(clip_scores), encoding="utf-8")
    json_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote report: {md_path}")
    print(f"Wrote CSV:    {csv_path}")
    print(f"Wrote JSON:   {json_path}")
    return md_path, csv_path, json_path


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score a baseline tracker batch run against ground-truth labels."
    )
    parser.add_argument(
        "--run",
        required=True,
        type=str,
        help="Run name under eval/runs/<run_name>.",
    )
    parser.add_argument(
        "--tolerances",
        type=str,
        default="0,1,2",
        help="Comma-separated frame error tolerances (default: 0,1,2).",
    )
    parser.add_argument(
        "--labels-dir",
        type=Path,
        default=None,
        help="Optional override for labels directory.",
    )
    parser.add_argument(
        "--library-dir",
        type=Path,
        default=None,
        help="Optional override for library directory.",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=None,
        help="Optional override for runs directory.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=None,
        help="Optional override for reports directory.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    tols = [int(x.strip()) for x in args.tolerances.split(",") if x.strip()]
    run_scoring(
        run_name=args.run,
        tolerances=tols,
        labels_dir=args.labels_dir,
        library_dir=args.library_dir,
        runs_dir=args.runs_dir,
        reports_dir=args.reports_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
