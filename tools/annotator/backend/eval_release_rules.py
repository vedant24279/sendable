"""Evaluate heuristic release-frame rules and leave-one-out CV on raw dumps."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from release_rules import (
    R1_K_VALUES,
    R1_T_VALUES,
    rule_r0_streaming,
    rule_r1_flight_run,
    rule_r2_apex,
    rule_r3_deceleration,
    rule_r4_filtered_flight_run,
)
from trace_release import (
    _safe_int,
    get_default_analysis_dir,
    get_default_labels_dir,
    get_default_runs_dir,
)

RuleFn = Callable[[Dict[str, Any], Dict[str, Any]], Optional[Tuple[int, float, float]]]

_FAMILY_ORDER: Dict[str, int] = {
    "R0": 0,
    "R2": 1,
    "R3": 2,
    "R1": 3,
    "R4": 4,
}


@dataclass(frozen=True)
class RuleSpec:
    """Named release rule configuration."""

    name: str
    family: str
    fn: RuleFn
    k: int = 0
    t: float = 0.0


@dataclass(frozen=True)
class ClipEvalInput:
    """Loaded clip inputs for release rule evaluation."""

    clip_id: str
    ball_colour: str
    label_frame: int
    calib_points: Dict[str, Any]
    raw_dump: Dict[str, Any]


@dataclass(frozen=True)
class ClipPrediction:
    """Single clip prediction and signed error for a rule."""

    clip_id: str
    ball_colour: str
    label_frame: int
    pred_frame: Optional[int]
    error: Optional[int]


@dataclass(frozen=True)
class RuleSummary:
    """Aggregated metrics for a rule across a set of clips."""

    spec: RuleSpec
    n_total: int
    n_scored: int
    n_missing: int
    n_exact: int
    n_within_1: int
    n_within_2: int
    mae: Optional[float]
    predictions: Tuple[ClipPrediction, ...]


@dataclass(frozen=True)
class LooFoldResult:
    """Single held-out clip result from leave-one-out selection."""

    clip_id: str
    ball_colour: str
    label_frame: int
    chosen_rule: str
    pred_frame: Optional[int]
    error: Optional[int]


@dataclass(frozen=True)
class LooResult:
    """Aggregated leave-one-out cross-validation metrics for a rule family."""

    family_label: str
    n_total: int
    n_scored: int
    n_missing: int
    n_exact: int
    n_within_1: int
    n_within_2: int
    mae: Optional[float]
    folds: Tuple[LooFoldResult, ...]


def build_rule_specs() -> List[RuleSpec]:
    """Return all release rules and parameter grid entries to evaluate."""
    specs: List[RuleSpec] = [
        RuleSpec(name="R0", family="R0", fn=rule_r0_streaming),
    ]
    for k in R1_K_VALUES:
        for t in R1_T_VALUES:
            specs.append(
                RuleSpec(
                    name=f"R1(K={k},T={t:.3f})",
                    family="R1",
                    k=k,
                    t=t,
                    fn=lambda dump, pts, _k=k, _t=t: rule_r1_flight_run(
                        dump, pts, k=_k, t=_t
                    ),
                )
            )
    specs.append(RuleSpec(name="R2", family="R2", fn=rule_r2_apex))
    specs.append(RuleSpec(name="R3", family="R3", fn=rule_r3_deceleration))
    for k in R1_K_VALUES:
        for t in R1_T_VALUES:
            specs.append(
                RuleSpec(
                    name=f"R4(K={k},T={t:.3f})",
                    family="R4",
                    k=k,
                    t=t,
                    fn=lambda dump, pts, _k=k, _t=t: rule_r4_filtered_flight_run(
                        dump, pts, k=_k, t=_t
                    ),
                )
            )
    return specs


def load_clip_inputs(run_dir: Path, labels_dir: Path) -> List[ClipEvalInput]:
    """Load final labelled clips that have a matching raw_ball_detections.json."""
    if not labels_dir.is_dir():
        raise FileNotFoundError(f"Labels directory not found: {labels_dir}")
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    clips: List[ClipEvalInput] = []
    for label_path in sorted(labels_dir.glob("*.json")):
        with label_path.open("r", encoding="utf-8") as fh:
            label = json.load(fh)
        if not isinstance(label, dict) or label.get("status") != "final":
            continue
        calib = label.get("calibration_gt")
        release = label.get("release")
        if not isinstance(calib, dict) or not isinstance(calib.get("points"), dict):
            continue
        if not isinstance(release, dict):
            continue
        label_frame = _safe_int(release.get("frame"))
        if label_frame is None:
            continue

        clip_id = str(label.get("clip_id") or label_path.stem)
        dump_path = run_dir / clip_id / "raw_ball_detections.json"
        if not dump_path.is_file():
            continue
        with dump_path.open("r", encoding="utf-8") as fh:
            raw_dump = json.load(fh)
        if not isinstance(raw_dump, dict):
            continue

        clips.append(
            ClipEvalInput(
                clip_id=clip_id,
                ball_colour=str(label.get("ball_colour") or "unknown"),
                label_frame=label_frame,
                calib_points=calib["points"],
                raw_dump=raw_dump,
            )
        )
    return clips


def _aggregate_counts(
    errors: Sequence[Optional[int]],
) -> Tuple[int, int, int, int, int, int, Optional[float]]:
    n_total = len(errors)
    scored = [err for err in errors if err is not None]
    n_scored = len(scored)
    n_missing = n_total - n_scored
    n_exact = sum(1 for err in scored if err == 0)
    n_within_1 = sum(1 for err in scored if abs(err) <= 1)
    n_within_2 = sum(1 for err in scored if abs(err) <= 2)
    mae = (sum(abs(err) for err in scored) / n_scored) if n_scored > 0 else None
    return n_total, n_scored, n_missing, n_exact, n_within_1, n_within_2, mae


def evaluate_rule(spec: RuleSpec, clips: Sequence[ClipEvalInput]) -> RuleSummary:
    """Evaluate a single rule across all clips."""
    preds: List[ClipPrediction] = []
    errors: List[Optional[int]] = []
    for clip in clips:
        result = spec.fn(clip.raw_dump, clip.calib_points)
        pred_frame = result[0] if result is not None else None
        error = (pred_frame - clip.label_frame) if pred_frame is not None else None
        preds.append(
            ClipPrediction(
                clip_id=clip.clip_id,
                ball_colour=clip.ball_colour,
                label_frame=clip.label_frame,
                pred_frame=pred_frame,
                error=error,
            )
        )
        errors.append(error)

    n_total, n_scored, n_missing, n_exact, n_within_1, n_within_2, mae = (
        _aggregate_counts(errors)
    )
    return RuleSummary(
        spec=spec,
        n_total=n_total,
        n_scored=n_scored,
        n_missing=n_missing,
        n_exact=n_exact,
        n_within_1=n_within_1,
        n_within_2=n_within_2,
        mae=mae,
        predictions=tuple(preds),
    )


def rule_rank_key(summary: RuleSummary) -> Tuple[Any, ...]:
    """Sort key putting highest ±1 accuracy first, then exact, ±2, and lowest MAE."""
    mae_val = summary.mae if summary.mae is not None else float("inf")
    return (
        -summary.n_within_1,
        -summary.n_exact,
        -summary.n_within_2,
        mae_val,
        -summary.n_scored,
        _FAMILY_ORDER.get(summary.spec.family, 99),
        summary.spec.k,
        summary.spec.name,
    )


def run_leave_one_out(
    specs: Sequence[RuleSpec],
    clips: Sequence[ClipEvalInput],
    family_label: str,
) -> LooResult:
    """Pick the best rule in `specs` on N-1 clips and score the held-out clip."""
    if not specs:
        raise ValueError("specs must not be empty")
    if len(clips) < 2:
        raise ValueError("leave-one-out requires at least 2 clips")

    folds: List[LooFoldResult] = []
    errors: List[Optional[int]] = []
    for hold_idx, held_out in enumerate(clips):
        train_clips = [c for idx, c in enumerate(clips) if idx != hold_idx]
        train_summaries = [evaluate_rule(spec, train_clips) for spec in specs]
        best_spec = min(train_summaries, key=rule_rank_key).spec

        result = best_spec.fn(held_out.raw_dump, held_out.calib_points)
        pred_frame = result[0] if result is not None else None
        error = (pred_frame - held_out.label_frame) if pred_frame is not None else None
        folds.append(
            LooFoldResult(
                clip_id=held_out.clip_id,
                ball_colour=held_out.ball_colour,
                label_frame=held_out.label_frame,
                chosen_rule=best_spec.name,
                pred_frame=pred_frame,
                error=error,
            )
        )
        errors.append(error)

    n_total, n_scored, n_missing, n_exact, n_within_1, n_within_2, mae = (
        _aggregate_counts(errors)
    )
    return LooResult(
        family_label=family_label,
        n_total=n_total,
        n_scored=n_scored,
        n_missing=n_missing,
        n_exact=n_exact,
        n_within_1=n_within_1,
        n_within_2=n_within_2,
        mae=mae,
        folds=tuple(folds),
    )


def _fmt_signed(err: Optional[int]) -> str:
    if err is None:
        return "NA"
    if err > 0:
        return f"+{err}"
    return str(err)


def _fmt_mae(mae: Optional[float]) -> str:
    if mae is None:
        return "NA"
    return f"{mae:.2f}"


def render_markdown(
    run_name: str,
    clips: Sequence[ClipEvalInput],
    ranked_summaries: Sequence[RuleSummary],
    loo_results: Sequence[LooResult],
) -> str:
    """Format ranked table, LOO totals, best-3 per-clip errors, and wrong clips."""
    lines: List[str] = [
        f"# Release Rule Search — {run_name}",
        "",
        f"- Final labelled clips with raw detections: **{len(clips)}**",
        f"- Rules evaluated: **{len(ranked_summaries)}**",
        "",
        "## Ranked Rules (In-Sample)",
        "",
        "| Rank | Rule | Exact (0) | Within ±1 | Within ±2 | MAE (frames) | Scored |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for rank, s in enumerate(ranked_summaries, start=1):
        lines.append(
            f"| {rank} | {s.spec.name} | {s.n_exact}/{s.n_total} | "
            f"{s.n_within_1}/{s.n_total} | {s.n_within_2}/{s.n_total} | "
            f"{_fmt_mae(s.mae)} | {s.n_scored}/{s.n_total} |"
        )

    lines.extend(
        [
            "",
            "## Leave-One-Out Cross-Validation (LOO)",
            "",
            "| Candidate Set | Exact (0) | Within ±1 | Within ±2 | MAE (frames) | Threshold (>=11/14 ±1) |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for loo in loo_results:
        threshold_note = (
            "PASS" if loo.n_total == 14 and loo.n_within_1 >= 11 else f"{loo.n_within_1}/{loo.n_total}"
        )
        lines.append(
            f"| {loo.family_label} | {loo.n_exact}/{loo.n_total} | "
            f"{loo.n_within_1}/{loo.n_total} | {loo.n_within_2}/{loo.n_total} | "
            f"{_fmt_mae(loo.mae)} | {threshold_note} |"
        )

    for loo in loo_results:
        lines.extend(
            [
                "",
                f"### LOO Folds — {loo.family_label}",
                "",
                "| Clip | Ball | Label | Chosen Rule | Pred | Err (rule - label) |",
                "|---|---|---:|---|---:|---:|",
            ]
        )
        for fold in loo.folds:
            pred_txt = str(fold.pred_frame) if fold.pred_frame is not None else "NA"
            lines.append(
                f"| {fold.clip_id} | {fold.ball_colour} | {fold.label_frame} | "
                f"{fold.chosen_rule} | {pred_txt} | {_fmt_signed(fold.error)} |"
            )

    best3 = list(ranked_summaries[:3])
    if best3:
        lines.extend(
            [
                "",
                "## Per-Clip Signed Errors (`rule - label`) — Best 3 Rules",
                "",
            ]
        )
        header_cols = ["Clip", "Ball", "Label"] + [s.spec.name for s in best3]
        lines.append("| " + " | ".join(header_cols) + " |")
        lines.append("|---|---|---:|" + "---:|" * len(best3))
        for idx, clip in enumerate(clips):
            row = [clip.clip_id, clip.ball_colour, str(clip.label_frame)]
            for s in best3:
                p = s.predictions[idx]
                row.append(_fmt_signed(p.error))
            lines.append("| " + " | ".join(row) + " |")

        lines.extend(
            [
                "",
                "## Clips Still Wrong for Each of the Best 3 Rules",
                "",
            ]
        )
        for s in best3:
            outside_1 = [
                p for p in s.predictions if p.error is None or abs(p.error) > 1
            ]
            exact_1_only = [p for p in s.predictions if p.error is not None and abs(p.error) == 1]
            lines.append(f"### {s.spec.name}")
            if not outside_1:
                lines.append("- Outside ±1: none")
            else:
                items = ", ".join(
                    f"`{p.clip_id}` ({p.ball_colour}: label={p.label_frame}, pred={p.pred_frame}, err={_fmt_signed(p.error)})"
                    for p in outside_1
                )
                lines.append(f"- Outside ±1 ({len(outside_1)}): {items}")
            if not exact_1_only:
                lines.append("- Off by ±1: none")
            else:
                items = ", ".join(
                    f"`{p.clip_id}` ({p.ball_colour}: label={p.label_frame}, pred={p.pred_frame}, err={_fmt_signed(p.error)})"
                    for p in exact_1_only
                )
                lines.append(f"- Off by ±1 ({len(exact_1_only)}): {items}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def evaluate_run(
    run_name: str,
    labels_dir: Path,
    runs_dir: Path,
    analysis_dir: Path,
) -> Path:
    """Evaluate all rules and LOO on `run_name` and write Markdown report."""
    run_dir = runs_dir / run_name
    clips = load_clip_inputs(run_dir=run_dir, labels_dir=labels_dir)
    if not clips:
        raise RuntimeError(
            f"No final labelled clips with raw_ball_detections.json under {run_dir}"
        )

    specs = build_rule_specs()
    summaries = [evaluate_rule(spec, clips) for spec in specs]
    ranked = sorted(summaries, key=rule_rank_key)

    r1_specs = [s for s in specs if s.family == "R1"]
    r4_specs = [s for s in specs if s.family == "R4"]
    r1_r4_specs = [s for s in specs if s.family in {"R1", "R4"}]
    loo_results = [
        run_leave_one_out(r1_specs, clips, "R1"),
        run_leave_one_out(r4_specs, clips, "R4"),
        run_leave_one_out(r1_r4_specs, clips, "R1+R4"),
        run_leave_one_out(specs, clips, "ALL (R0..R4)"),
    ]

    analysis_dir.mkdir(parents=True, exist_ok=True)
    out_path = analysis_dir / f"release_rules_{run_name}.md"
    out_path.write_text(
        render_markdown(
            run_name=run_name,
            clips=clips,
            ranked_summaries=ranked,
            loo_results=loo_results,
        ),
        encoding="utf-8",
    )
    return out_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        default="release_dump_1",
        help="Run name under eval/runs/ containing raw_ball_detections.json",
    )
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
        args.runs_dir.resolve() if args.runs_dir is not None else get_default_runs_dir()
    )
    analysis_dir = (
        args.analysis_dir.resolve()
        if args.analysis_dir is not None
        else get_default_analysis_dir()
    )

    out_path = evaluate_run(
        run_name=args.run,
        labels_dir=labels_dir,
        runs_dir=runs_dir,
        analysis_dir=analysis_dir,
    )
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
