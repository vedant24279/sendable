"""
System calibration residual report.

Computes stump residual for every delivery clip with a system calibration in results.json,
and prints min, median, max, and the 10 worst clips.
"""

from __future__ import annotations
import json
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.calib import fit_homography


def get_repo_root() -> Path:
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "backend").is_dir() and (current / "tools").is_dir():
            return current
        current = current.parent
    return Path.cwd().resolve()


def generate_calibration_report() -> Dict[str, Any]:
    repo_root = get_repo_root()
    jobs_dir = repo_root / "backend" / "_tracker_work" / "jobs"

    if not jobs_dir.is_dir():
        print(f"Jobs directory not found at: {jobs_dir}", file=sys.stderr)
        return {}

    results: List[Tuple[str, float]] = []

    # Iterate over all job subdirectories
    for job_path in sorted(jobs_dir.iterdir()):
        if not job_path.is_dir():
            continue
        results_file = job_path / "results.json"
        if not results_file.is_file():
            continue

        try:
            data = json.loads(results_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Skipping {job_path.name}: failed to read JSON ({e})", file=sys.stderr)
            continue

        calib = data.get("calibration")
        if not calib or not isinstance(calib, dict):
            continue

        required_keys = ("bat_L", "bat_R", "bowl_L", "bowl_R", "bat_stump", "bowl_stump")
        if not all(k in calib for k in required_keys):
            continue

        try:
            fit_res = fit_homography(calib)
            results.append((job_path.name, fit_res.residual_px))
        except Exception as e:
            print(f"Error computing homography for {job_path.name}: {e}", file=sys.stderr)

    if not results:
        print("No valid system calibrations found.")
        return {}

    residuals = [r[1] for r in results]
    min_res = min(residuals)
    median_res = statistics.median(residuals)
    max_res = max(residuals)

    # Sort descending by residual for the 10 worst clips
    sorted_worst = sorted(results, key=lambda x: x[1], reverse=True)[:10]

    print("=" * 60)
    print("CRICKET SYSTEM CALIBRATION RESIDUAL REPORT")
    print("=" * 60)
    print(f"Total clips analyzed: {len(results)}")
    print(f"Min residual:    {min_res:.2f} px")
    print(f"Median residual: {median_res:.2f} px")
    print(f"Max residual:    {max_res:.2f} px")
    print("-" * 60)
    print("10 Worst Clips (highest stump residual):")
    for rank, (clip_id, res_px) in enumerate(sorted_worst, start=1):
        print(f"  {rank:2d}. {clip_id:12s} : {res_px:6.2f} px")
    print("=" * 60)

    return {
        "count": len(results),
        "min": min_res,
        "median": median_res,
        "max": max_res,
        "worst_10": sorted_worst,
    }


if __name__ == "__main__":
    generate_calibration_report()
