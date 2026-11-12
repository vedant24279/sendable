"""
System calibration residual and signed world error report.

Computes:
1. Stump residual (RMS pixel error) for every delivery clip with a system calibration.
2. Signed world errors (dx_bat, dz_bat, dx_bowl, dz_bowl in metres) from clicked stump pixels.
3. Distribution breakdown (< 4 px, 4-12 px, > 12 px) and summary stats (mean, median, p10, p90).
4. Exports tools/annotator/calib_report.csv.
"""

from __future__ import annotations
import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.calib import compute_stump_world_errors, fit_homography, pixel_to_world


def get_repo_root() -> Path:
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "backend").is_dir() and (current / "tools").is_dir():
            return current
        current = current.parent
    return Path.cwd().resolve()


def generate_calibration_report(csv_path: Optional[Path] = None) -> Dict[str, Any]:
    repo_root = get_repo_root()
    jobs_dir = repo_root / "backend" / "_tracker_work" / "jobs"
    file_pattern = "backend/_tracker_work/jobs/*/results.json"

    if not jobs_dir.is_dir():
        print(f"Jobs directory not found at: {jobs_dir}", file=sys.stderr)
        return {}

    records: List[Dict[str, Any]] = []

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
            errors = compute_stump_world_errors(calib, H=fit_res.H)
            records.append({
                "clip_id": job_path.name,
                "ball_type": data.get("ball_type") or "",
                "residual_px": float(fit_res.residual_px),
                "dx_bat": float(errors["dx_bat"]),
                "dz_bat": float(errors["dz_bat"]),
                "dx_bowl": float(errors["dx_bowl"]),
                "dz_bowl": float(errors["dz_bowl"]),
            })
        except Exception as e:
            print(f"Error computing calibration metrics for {job_path.name}: {e}", file=sys.stderr)

    if not records:
        print("No valid system calibrations found.")
        return {}

    total_count = len(records)
    residuals = [r["residual_px"] for r in records]
    min_res = min(residuals)
    median_res = statistics.median(residuals)
    max_res = max(residuals)

    # Residual threshold breakdown
    count_low = sum(1 for r in residuals if r < 4.0)
    count_mid = sum(1 for r in residuals if 4.0 <= r <= 12.0)
    count_high = sum(1 for r in residuals if r > 12.0)

    # World error distribution metrics (signed, metres)
    metrics_summary: Dict[str, Dict[str, float]] = {}
    metric_keys = ("dx_bat", "dz_bat", "dx_bowl", "dz_bowl")
    for key in metric_keys:
        vals = np.array([r[key] for r in records], dtype=np.float64)
        metrics_summary[key] = {
            "mean": float(np.mean(vals)),
            "median": float(np.median(vals)),
            "p10": float(np.percentile(vals, 10)),
            "p90": float(np.percentile(vals, 90)),
        }

    # Top 10 worst clips by residual_px
    sorted_worst = sorted(records, key=lambda x: x["residual_px"], reverse=True)[:10]

    # Write CSV
    if csv_path is None:
        csv_path = repo_root / "tools" / "annotator" / "calib_report.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["clip_id", "ball_type", "residual_px", "dx_bat", "dz_bat", "dx_bowl", "dz_bowl"])
        for r in records:
            writer.writerow([
                r["clip_id"],
                r["ball_type"],
                f"{r['residual_px']:.4f}",
                f"{r['dx_bat']:.4f}",
                f"{r['dz_bat']:.4f}",
                f"{r['dx_bowl']:.4f}",
                f"{r['dz_bowl']:.4f}",
            ])

    # Print formatted report
    print("=" * 70)
    print("CRICKET SYSTEM CALIBRATION RESIDUAL & SIGNED WORLD ERROR REPORT")
    print("=" * 70)
    print(f"File path pattern : {file_pattern}")
    print(f"Clips read        : {total_count}")
    print("-" * 70)
    print("Residual Breakdown:")
    print(f"  residual < 4 px  (pass)   : {count_low:3d}  ({count_low / total_count * 100:5.1f}%)")
    print(f"  4 to 12 px       (warning): {count_mid:3d}  ({count_mid / total_count * 100:5.1f}%)")
    print(f"  residual > 12 px (error)  : {count_high:3d}  ({count_high / total_count * 100:5.1f}%)")
    print("-" * 70)
    print("Stump World Errors (signed, metres):")
    print("  Metric          Mean        Median           p10           p90")
    print("  " + "-" * 56)
    for k in metric_keys:
        s = metrics_summary[k]
        print(f"  {k:8s} :  {s['mean']:+9.3f} m   {s['median']:+9.3f} m   {s['p10']:+9.3f} m   {s['p90']:+9.3f} m")
    print("-" * 70)
    print("Residual Summary Statistics:")
    print(f"  Min residual    :  {min_res:6.2f} px")
    print(f"  Median residual :  {median_res:6.2f} px")
    print(f"  Max residual    :  {max_res:6.2f} px")
    print("-" * 70)
    print("10 Worst Clips (highest stump residual):")
    for rank, item in enumerate(sorted_worst, start=1):
        print(
            f"  {rank:2d}. {item['clip_id']:12s} : {item['residual_px']:6.2f} px  "
            f"(dx_bat={item['dx_bat']:+6.3f}m, dz_bat={item['dz_bat']:+6.3f}m, "
            f"dx_bowl={item['dx_bowl']:+6.3f}m, dz_bowl={item['dz_bowl']:+6.3f}m)"
        )
    print("-" * 70)
    rel_csv = csv_path.relative_to(repo_root) if csv_path.is_relative_to(repo_root) else csv_path
    print(f"CSV report written to: {rel_csv} ({total_count} rows)")
    print("=" * 70)

    return {
        "pattern": file_pattern,
        "count": total_count,
        "residual_breakdown": {
            "lt_4": count_low,
            "4_to_12": count_mid,
            "gt_12": count_high,
        },
        "metrics_summary": metrics_summary,
        "min_residual": min_res,
        "median_residual": median_res,
        "max_residual": max_res,
        "worst_10": sorted_worst,
        "csv_path": str(csv_path),
    }


if __name__ == "__main__":
    generate_calibration_report()
