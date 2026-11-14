"""Batch runner for the baseline cricket ball tracking pipeline on final labels."""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.library import find_library_clip_video, get_library_dir  # noqa: E402

REQUIRED_CALIB_KEYS: Tuple[str, ...] = (
    "bat_L",
    "bat_R",
    "bowl_L",
    "bowl_R",
    "bat_stump",
    "bowl_stump",
)
ALLOWED_BALL_TYPES: Set[str] = {"white", "red", "pink"}
LEGACY_TRACKER_FOLDER = "Zone-div_V8m"


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


def resolve_pipeline_python() -> Path:
    env_py = os.environ.get("PIPELINE_PYTHON", "").strip()
    if env_py:
        return Path(env_py).expanduser().resolve()
    venv_dir = REPO_ROOT / "backend" / ".venv-pipeline"
    win_py = venv_dir / "Scripts" / "python.exe"
    if win_py.is_file():
        return win_py.resolve()
    posix_py = venv_dir / "bin" / "python"
    if posix_py.is_file():
        return posix_py.resolve()
    return win_py.resolve()


def get_git_commit() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except OSError:
        pass
    return "unknown"


def is_pipeline_or_worker_dirty() -> bool:
    try:
        proc = subprocess.run(
            [
                "git",
                "status",
                "--porcelain",
                "--",
                "backend/pipeline",
                "backend/worker",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return bool(proc.stdout.strip())
    except OSError:
        pass
    return False


def build_rounded_calibration(calibration_gt: Dict[str, Any]) -> Dict[str, List[int]]:
    points = calibration_gt.get("points")
    if not isinstance(points, dict):
        raise ValueError("calibration_gt.points is missing or not a dict")
    rounded: Dict[str, List[int]] = {}
    for key in REQUIRED_CALIB_KEYS:
        pt = points.get(key)
        if not isinstance(pt, (list, tuple)) or len(pt) != 2:
            raise ValueError(f"calibration_gt.points.{key} must be a [x, y] pair")
        rounded[key] = [int(round(float(pt[0]))), int(round(float(pt[1])))]
    return rounded


def discover_eligible_labels(
    labels_dir: Path,
    only_ids: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    if not labels_dir.is_dir():
        return []
    eligible: List[Dict[str, Any]] = []
    for path in sorted(labels_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[WARN] Skipping unreadable label file {path.name}: {exc}", file=sys.stderr)
            continue
        if not isinstance(data, dict):
            continue
        clip_id = str(data.get("clip_id") or path.stem)
        if only_ids is not None and clip_id not in only_ids:
            continue
        if data.get("status") != "final":
            continue
        if data.get("calibration_gt") is None:
            continue
        eligible.append(data)
    return eligible


def parse_env_vars(raw_envs: Optional[Sequence[str]]) -> Dict[str, str]:
    """Parse repeatable KEY=VALUE pairs into a dictionary."""
    parsed: Dict[str, str] = {}
    for item in raw_envs or ():
        if "=" not in item:
            raise ValueError(f"Invalid --env entry {item!r}: expected KEY=VALUE")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid --env entry {item!r}: empty key")
        parsed[key] = value
    return parsed


def run_batch(
    *,
    run_name: str,
    only_ids: Optional[Set[str]] = None,
    skip_existing: bool = False,
    dry_run: bool = False,
    extra_env: Optional[Dict[str, str]] = None,
    labels_dir: Optional[Path] = None,
    library_dir: Optional[Path] = None,
    runs_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    resolved_labels_dir = (labels_dir or get_default_labels_dir()).resolve()
    resolved_library_dir = (library_dir or get_library_dir()).resolve()
    resolved_runs_dir = (runs_dir or get_default_runs_dir()).resolve()
    run_dir = resolved_runs_dir / run_name
    pipeline_py = resolve_pipeline_python()
    run_clip_script = (BACKEND_DIR / "run_clip.py").resolve()
    env_overrides = dict(extra_env or {})
    sub_env: Optional[Dict[str, str]] = None
    if env_overrides:
        sub_env = os.environ.copy()
        sub_env.update(env_overrides)

    labels = discover_eligible_labels(resolved_labels_dir, only_ids=only_ids)
    utc_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(
        f"Batch run '{run_name}' | labels_dir={resolved_labels_dir} | "
        f"eligible_final_clips={len(labels)} | dry_run={dry_run}"
    )

    clip_records: List[Dict[str, Any]] = []
    ball_types_used: Set[str] = set()

    for label in labels:
        clip_id = str(label["clip_id"])
        ball_colour = label.get("ball_colour")
        if not isinstance(ball_colour, str) or ball_colour.lower() not in ALLOWED_BALL_TYPES:
            msg = f"Skipping {clip_id}: ball_colour is {ball_colour!r} (must be white|red|pink)"
            print(f"[SKIP] {msg}")
            clip_records.append(
                {
                    "clip_id": clip_id,
                    "ball_type": ball_colour,
                    "status": "skipped_no_ball_colour",
                    "wall_clock_sec": 0.0,
                    "message": msg,
                }
            )
            continue

        ball_type = ball_colour.lower()
        ball_types_used.add(ball_type)

        try:
            calib_int = build_rounded_calibration(label["calibration_gt"])
        except Exception as exc:
            msg = f"Skipping {clip_id}: invalid calibration_gt ({exc})"
            print(f"[SKIP] {msg}")
            clip_records.append(
                {
                    "clip_id": clip_id,
                    "ball_type": ball_type,
                    "status": "failed_calibration",
                    "wall_clock_sec": 0.0,
                    "message": msg,
                }
            )
            continue

        found = find_library_clip_video(clip_id, resolved_library_dir)
        if found is None:
            msg = f"Skipping {clip_id}: video not found in library catalog at {resolved_library_dir}"
            print(f"[SKIP] {msg}")
            clip_records.append(
                {
                    "clip_id": clip_id,
                    "ball_type": ball_type,
                    "status": "missing_video",
                    "wall_clock_sec": 0.0,
                    "message": msg,
                }
            )
            continue

        video_path, _entry = found
        clip_out_dir = run_dir / clip_id
        results_path = clip_out_dir / "results.json"

        if skip_existing and results_path.is_file():
            print(f"[SKIP] {clip_id}: results.json already exists at {results_path}")
            clip_records.append(
                {
                    "clip_id": clip_id,
                    "ball_type": ball_type,
                    "status": "skipped_existing",
                    "wall_clock_sec": 0.0,
                }
            )
            continue

        calib_json = json.dumps(calib_int, separators=(",", ":"))
        cmd = [
            str(pipeline_py),
            str(run_clip_script),
            "--video",
            str(video_path),
            "--calibration",
            calib_json,
            "--ball-type",
            ball_type,
            "--out",
            str(clip_out_dir),
        ]

        if dry_run:
            print(
                f"[DRY-RUN] clip={clip_id} ball_type={ball_type} "
                f"video={video_path.name} out={clip_out_dir} calib={calib_json}"
            )
            clip_records.append(
                {
                    "clip_id": clip_id,
                    "ball_type": ball_type,
                    "status": "dry_run",
                    "wall_clock_sec": 0.0,
                    "calibration": calib_int,
                    "video_name": video_path.name,
                }
            )
            continue

        clip_out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[RUN] {clip_id} ({ball_type}) -> {clip_out_dir}")
        t0 = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(REPO_ROOT),
                env=sub_env,
                capture_output=True,
                text=True,
                check=False,
            )
            elapsed = round(time.perf_counter() - t0, 3)
            if proc.returncode == 0 and results_path.is_file():
                print(f"[OK] {clip_id} finished in {elapsed:.2f}s")
                clip_records.append(
                    {
                        "clip_id": clip_id,
                        "ball_type": ball_type,
                        "status": "ok",
                        "wall_clock_sec": elapsed,
                    }
                )
            else:
                stderr_lines = (proc.stderr or proc.stdout or "").strip().splitlines()
                stderr_tail = "\n".join(stderr_lines[-20:])
                print(
                    f"[FAIL] {clip_id} exited with code {proc.returncode} after {elapsed:.2f}s",
                    file=sys.stderr,
                )
                clip_records.append(
                    {
                        "clip_id": clip_id,
                        "ball_type": ball_type,
                        "status": "failed",
                        "returncode": proc.returncode,
                        "wall_clock_sec": elapsed,
                        "stderr_tail": stderr_tail,
                    }
                )
        except Exception as exc:
            elapsed = round(time.perf_counter() - t0, 3)
            print(f"[FAIL] {clip_id} subprocess error: {exc}", file=sys.stderr)
            clip_records.append(
                {
                    "clip_id": clip_id,
                    "ball_type": ball_type,
                    "status": "failed",
                    "wall_clock_sec": elapsed,
                    "stderr_tail": str(exc),
                }
            )

    run_info: Dict[str, Any] = {
        "run_name": run_name,
        "utc_time": utc_now,
        "git_commit": get_git_commit(),
        "pipeline_or_worker_dirty": is_pipeline_or_worker_dirty(),
        "legacy_tracker_folder": LEGACY_TRACKER_FOLDER,
        "ball_types": sorted(ball_types_used),
        "env": env_overrides,
        "clips": clip_records,
    }

    if not dry_run:
        run_dir.mkdir(parents=True, exist_ok=True)
        run_info_path = run_dir / "run_info.json"
        run_info_path.write_text(json.dumps(run_info, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {run_info_path}")

    return run_info


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    default_run_name = "run_" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    parser = argparse.ArgumentParser(
        description="Run the cricket ball tracking pipeline over all final calibrated labels."
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated list of clip_ids to process (e.g. c_3d27ed64,c_3f1fc736).",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=default_run_name,
        help="Run name under eval/runs/<run_name> (default: run_<YYYYMMDD_HHMMSS>).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip clips that already have eval/runs/<run_name>/<clip_id>/results.json.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be executed without running the pipeline or writing files.",
    )
    parser.add_argument(
        "--labels-dir",
        type=Path,
        default=None,
        help="Optional override for labels directory (defaults to LABELS_DIR or eval/labels).",
    )
    parser.add_argument(
        "--library-dir",
        type=Path,
        default=None,
        help="Optional override for library directory (defaults to ANNOTATOR_LIBRARY_DIR).",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=None,
        help="Optional override for runs directory (defaults to EVAL_RUNS_DIR or eval/runs).",
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Repeatable environment variable overrides passed to every run_clip subprocess.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    only_ids: Optional[Set[str]] = None
    if args.only:
        only_ids = {part.strip() for part in args.only.split(",") if part.strip()}
    parsed_env = parse_env_vars(args.env)
    run_batch(
        run_name=args.run_name,
        only_ids=only_ids,
        skip_existing=args.skip_existing,
        dry_run=args.dry_run,
        extra_env=parsed_env,
        labels_dir=args.labels_dir,
        library_dir=args.library_dir,
        runs_dir=args.runs_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
