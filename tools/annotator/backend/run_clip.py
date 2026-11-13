"""CLI wrapper to run the cricket ball tracking pipeline on a single video clip.

Usage:
    python run_clip.py \
        --video <path> \
        --calibration '{"bat_L":[778,434],"bat_R":[1083,430],"bowl_L":[739,764],"bowl_R":[1115,768],"bat_stump":[936,426],"bowl_stump":[922,784]}' \
        --ball-type <white|red|pink> \
        --out <dir>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
LEGACY_V8M_DIR = BACKEND_DIR / "worker" / "legacy" / "Zone-div_V8m"
MODELS_DIR = BACKEND_DIR / "models"

REQUIRED_CALIBRATION_KEYS = (
    "bat_L",
    "bat_R",
    "bowl_L",
    "bowl_R",
    "bat_stump",
    "bowl_stump",
)

BALL_TYPE_CONFIG: Dict[str, Dict[str, Any]] = {
    "white": {
        "weights_env": "TRACKER_WEIGHTS_WHITE",
        "default_weights": MODELS_DIR / "whiteball.onnx",
        "legacy_env": "TRACKER_LEGACY_DIR_WHITE",
        "default_legacy": LEGACY_V8M_DIR,
    },
    "red": {
        "weights_env": "TRACKER_WEIGHTS_RED",
        "default_weights": MODELS_DIR / "redsepv2.onnx",
        "legacy_env": "TRACKER_LEGACY_DIR_RED",
        "default_legacy": LEGACY_V8M_DIR,
    },
    "pink": {
        "weights_env": "TRACKER_WEIGHTS_PINK",
        "default_weights": MODELS_DIR / "pinkoct.onnx",
        "legacy_env": "TRACKER_LEGACY_DIR_PINK",
        "default_legacy": LEGACY_V8M_DIR,
    },
}


def parse_calibration_arg(raw_calib: str) -> Dict[str, List[int]]:
    """Parse --calibration from a JSON string or path to a JSON file and validate the 6 points."""
    text = raw_calib.strip()
    data: Any
    if not text.startswith("{"):
        cand_path = Path(text)
        if cand_path.is_file():
            text = cand_path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid calibration JSON: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Calibration JSON must be a JSON object")

    missing = [k for k in REQUIRED_CALIBRATION_KEYS if k not in data]
    if missing:
        raise ValueError(f"Calibration missing required point(s): {', '.join(missing)}")

    normalized: Dict[str, List[int]] = {}
    for k in REQUIRED_CALIBRATION_KEYS:
        pt = data[k]
        if not isinstance(pt, (list, tuple)) or len(pt) != 2:
            raise ValueError(f"Calibration point '{k}' must be [x, y]")
        try:
            x = int(round(float(pt[0])))
            y = int(round(float(pt[1])))
        except (TypeError, ValueError) as e:
            raise ValueError(f"Calibration point '{k}' coordinates must be numeric") from e
        normalized[k] = [x, y]

    return normalized


def resolve_pipeline_config(ball_type: str) -> Dict[str, Path]:
    """Return weights_path and legacy_dir for a given ball_type ('white', 'red', 'pink')."""
    bt = ball_type.strip().lower()
    if bt not in BALL_TYPE_CONFIG:
        raise ValueError(f"Unsupported ball_type: {ball_type!r}. Expected white, red, or pink.")
    cfg = BALL_TYPE_CONFIG[bt]
    weights_path = Path(os.environ.get(cfg["weights_env"], str(cfg["default_weights"])))
    legacy_dir = Path(os.environ.get(cfg["legacy_env"], str(cfg["default_legacy"])))
    return {
        "weights_path": weights_path,
        "legacy_dir": legacy_dir,
    }


def _ensure_cuda_dll_paths() -> None:
    """Ensure CUDA / cuDNN shared library directories are on PATH for onnxruntime-gpu."""
    candidates: List[Path] = []
    cuda_env = os.environ.get("CUDA_PATH")
    if cuda_env:
        candidates.append(Path(cuda_env) / "bin" / "x64")
        candidates.append(Path(cuda_env) / "bin")
    prog_files = os.environ.get("ProgramFiles")
    if prog_files:
        cuda_root = Path(prog_files) / "NVIDIA GPU Computing Toolkit" / "CUDA"
        if cuda_root.is_dir():
            for ver_dir in sorted(cuda_root.iterdir(), reverse=True):
                candidates.append(ver_dir / "bin" / "x64")
                candidates.append(ver_dir / "bin")
    for prefix in {Path(sys.prefix), Path(sys.base_prefix)}:
        candidates.append(prefix / "Lib" / "site-packages" / "torch" / "lib")

    current_path = os.environ.get("PATH", "")
    path_parts = current_path.split(os.pathsep) if current_path else []
    added: List[str] = []
    for cand in candidates:
        cand_str = str(cand)
        if cand.is_dir() and cand_str not in path_parts and cand_str not in added:
            added.append(cand_str)
    if added:
        os.environ["PATH"] = os.pathsep.join(added + path_parts)


def _load_process_video(legacy_dir: Path) -> Callable[..., dict]:
    """Configure sys.path and environment for legacy tracker and import pipeline.process_video."""
    _ensure_cuda_dll_paths()
    os.environ["TRACKER_LEGACY_DIR"] = str(legacy_dir)
    if str(legacy_dir) not in sys.path:
        sys.path.insert(0, str(legacy_dir))
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    from pipeline import process_video  # type: ignore[import-not-found]
    return process_video


def run_clip(
    video_path: Path,
    calibration: Dict[str, List[int]],
    ball_type: str,
    output_dir: Path,
    *,
    process_fn: Optional[Callable[..., dict]] = None,
) -> dict:
    """Configure environment for ball_type and run process_video into output_dir."""
    video_path = Path(video_path).resolve()
    if not video_path.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    bt = ball_type.strip().lower()
    cfg = resolve_pipeline_config(bt)
    weights_path = cfg["weights_path"].resolve()
    legacy_dir = cfg["legacy_dir"].resolve()

    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    os.environ["TRACKER_LEGACY_DIR"] = str(legacy_dir)
    os.environ["TRACKER_BALL_TYPE"] = bt
    os.environ.setdefault("TRACKER_BALL_ASSETS_DIR", str(REPO_ROOT / "frontend" / "public"))

    fn = process_fn if process_fn is not None else _load_process_video(legacy_dir)
    return fn(
        video_path=video_path,
        output_dir=out_dir,
        calibration=calibration,
        weights_path=weights_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the cricket ball tracker pipeline on a single video clip."
    )
    parser.add_argument(
        "--video",
        required=True,
        type=Path,
        help="Path to input video file.",
    )
    parser.add_argument(
        "--calibration",
        required=True,
        type=str,
        help="JSON string (or path to JSON file) with bat_L, bat_R, bowl_L, bowl_R, bat_stump, bowl_stump as [x, y].",
    )
    parser.add_argument(
        "--ball-type",
        required=True,
        choices=["white", "red", "pink"],
        help="Ball colour/type (white, red, pink).",
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output directory where results.json and other artifacts will be written.",
    )
    return parser


def main(
    argv: Optional[List[str]] = None,
    *,
    process_fn: Optional[Callable[..., dict]] = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    calib = parse_calibration_arg(args.calibration)
    run_clip(
        video_path=args.video,
        calibration=calib,
        ball_type=args.ball_type,
        output_dir=args.out,
        process_fn=process_fn,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
