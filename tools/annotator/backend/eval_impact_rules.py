"""Evaluate heuristic impact-frame rules and leave-one-out CV on raw dumps."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from impact_rules import (
    I1_THETA_VALUES,
    I5_THETA_VALUES,
    I5_UP_VALUES,
    rule_i1_direction_change,
    rule_i2_max_turn,
    rule_i3_speed_drop,
    rule_i4_last_seen,
    rule_i5a_ascending_first,
    rule_i5b_ascending_max_turn,
    rule_i6a_ungated_first,
    rule_i6b_ungated_max_turn,
)
from trace_release import (
    _safe_float,
    _safe_int,
    get_default_analysis_dir,
    get_default_labels_dir,
    get_default_runs_dir,
)

ImpactRuleFn = Callable[
    [Dict[str, Any], Dict[str, Any]],
    Optional[Tuple[int, float, float]],
]

_FAMILY_ORDER: Dict[str, int] = {
    "I5b": 0,
    "I5a": 1,
    "I6b": 2,
    "I6a": 3,
    "I1": 4,
    "I2": 5,
    "I3": 6,
    "I4": 7,
}


@dataclass(frozen=True)
class ImpactRuleSpec:
    """Named impact rule configuration."""

    name: str
    family: str
    fn: ImpactRuleFn
    param_sort: float = 0.0


@dataclass(frozen=True)
class ImpactClipInput:
    """Loaded clip inputs for impact rule evaluation."""

    clip_id: str
    ball_colour: str
    impact_type: str
    label_frame: int
    label_x: float
    label_y: float
    calib_points: Dict[str, Any]
    raw_dump: Dict[str, Any]
    sys_deviation: Optional[Tuple[int, float, float]] = None


@dataclass(frozen=True)
class ImpactClipPrediction:
    """Single clip prediction, signed frame error, and pixel distance."""

    clip_id: str
    ball_colour: str
    label_frame: int
    pred_frame: Optional[int]
    pred_x: Optional[float]
    pred_y: Optional[float]
    frame_error: Optional[int]
    px_error: Optional[float]


@dataclass(frozen=True)
class ImpactRuleSummary:
    """Aggregated metrics for an impact rule across clips."""

    spec: ImpactRuleSpec
    n_total: int
    n_found: int
    n_exact: int
    n_within_1: int
    n_within_2: int
    mae: Optional[float]
    px_median: Optional[float]
    px_p90: Optional[float]
    predictions: Tuple[ImpactClipPrediction, ...]


@dataclass(frozen=True)
class ImpactLooFoldResult:
    """Held-out clip evaluation for LOO."""

    clip_id: str
    ball_colour: str
    label_frame: int
    chosen_rule: str
    pred_frame: Optional[int]
    frame_error: Optional[int]
    px_error: Optional[float]


@dataclass(frozen=True)
class ImpactLooResult:
    """Aggregated LOO CV metrics."""

    family_label: str
    n_total: int
    n_found: int
    n_exact: int
    n_within_1: int
    n_within_2: int
    mae: Optional[float]
    px_median: Optional[float]
    px_p90: Optional[float]
    folds: Tuple[ImpactLooFoldResult, ...]


def build_impact_rule_specs() -> List[ImpactRuleSpec]:
    """Return all impact rules and parameter variants."""
    specs: List[ImpactRuleSpec] = []
    for theta in I1_THETA_VALUES:
        specs.append(
            ImpactRuleSpec(
                name=f"I1(theta={int(theta)})",
                family="I1",
                param_sort=theta,
                fn=lambda dump, pts, _th=theta: rule_i1_direction_change(
                    dump, pts, theta_deg=_th
                ),
            )
        )
    specs.append(ImpactRuleSpec(name="I2(max_turn)", family="I2", fn=rule_i2_max_turn))
    specs.append(ImpactRuleSpec(name="I3(speed_drop)", family="I3", fn=rule_i3_speed_drop))
    specs.append(
        ImpactRuleSpec(
            name="I4(+1)",
            family="I4",
            param_sort=1.0,
            fn=lambda dump, pts: rule_i4_last_seen(dump, pts, plus_one=True),
        )
    )
    specs.append(
        ImpactRuleSpec(
            name="I4(last_seen)",
            family="I4",
            param_sort=0.0,
            fn=lambda dump, pts: rule_i4_last_seen(dump, pts, plus_one=False),
        )
    )
    for up_val in I5_UP_VALUES:
        for theta in I5_THETA_VALUES:
            p_sort = up_val * 1000.0 + theta
            specs.append(
                ImpactRuleSpec(
                    name=f"I5a(up={up_val:.2f},theta={int(theta)})",
                    family="I5a",
                    param_sort=p_sort,
                    fn=lambda dump, pts, _u=up_val, _th=theta: rule_i5a_ascending_first(
                        dump, pts, up_frac=_u, theta_deg=_th
                    ),
                )
            )
    for up_val in I5_UP_VALUES:
        for theta in I5_THETA_VALUES:
            p_sort = up_val * 1000.0 + theta
            specs.append(
                ImpactRuleSpec(
                    name=f"I5b(up={up_val:.2f},theta={int(theta)})",
                    family="I5b",
                    param_sort=p_sort,
                    fn=lambda dump, pts, _u=up_val, _th=theta: rule_i5b_ascending_max_turn(
                        dump, pts, up_frac=_u, theta_deg=_th
                    ),
                )
            )
    for up_val in I5_UP_VALUES:
        for theta in I5_THETA_VALUES:
            p_sort = up_val * 1000.0 + theta
            specs.append(
                ImpactRuleSpec(
                    name=f"I6a(up={up_val:.2f},theta={int(theta)})",
                    family="I6a",
                    param_sort=p_sort,
                    fn=lambda dump, pts, _u=up_val, _th=theta: rule_i6a_ungated_first(
                        dump, pts, up_frac=_u, theta_deg=_th
                    ),
                )
            )
    for up_val in I5_UP_VALUES:
        for theta in I5_THETA_VALUES:
            p_sort = up_val * 1000.0 + theta
            specs.append(
                ImpactRuleSpec(
                    name=f"I6b(up={up_val:.2f},theta={int(theta)})",
                    family="I6b",
                    param_sort=p_sort,
                    fn=lambda dump, pts, _u=up_val, _th=theta: rule_i6b_ungated_max_turn(
                        dump, pts, up_frac=_u, theta_deg=_th
                    ),
                )
            )
    return specs


def _extract_system_deviation(results_path: Path) -> Optional[Tuple[int, float, float]]:
    if not results_path.is_file():
        return None
    try:
        data = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    events = data.get("events")
    if not isinstance(events, dict):
        return None
    dev = events.get("deviation")
    if not isinstance(dev, dict):
        return None
    df = _safe_int(dev.get("frame"))
    dx = _safe_float(dev.get("x"))
    dy = _safe_float(dev.get("y"))
    if df is None or dx is None or dy is None:
        return None
    return (df, dx, dy)


def load_impact_clip_inputs(run_dir: Path, labels_dir: Path) -> List[ImpactClipInput]:
    """Load final labelled clips with non-none impact and raw_ball_detections.json."""
    if not labels_dir.is_dir():
        raise FileNotFoundError(f"Labels directory not found: {labels_dir}")
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    clips: List[ImpactClipInput] = []
    for label_path in sorted(labels_dir.glob("*.json")):
        if label_path.name.startswith("_"):
            continue
        with label_path.open("r", encoding="utf-8") as fh:
            label = json.load(fh)
        if not isinstance(label, dict) or label.get("status") != "final":
            continue
        calib = label.get("calibration_gt")
        impact = label.get("impact")
        if not isinstance(calib, dict) or not isinstance(calib.get("points"), dict):
            continue
        if not isinstance(impact, dict):
            continue
        imp_type = str(impact.get("type") or "none").lower()
        if imp_type == "none":
            continue
        imp_frame = _safe_int(impact.get("frame"))
        imp_x = _safe_float(impact.get("x"))
        imp_y = _safe_float(impact.get("y"))
        if imp_frame is None or imp_x is None or imp_y is None:
            continue

        clip_id = str(label.get("clip_id") or label_path.stem)
        dump_path = run_dir / clip_id / "raw_ball_detections.json"
        if not dump_path.is_file():
            continue
        with dump_path.open("r", encoding="utf-8") as fh:
            raw_dump = json.load(fh)
        if not isinstance(raw_dump, dict):
            continue
        sys_dev = _extract_system_deviation(run_dir / clip_id / "results.json")

        clips.append(
            ImpactClipInput(
                clip_id=clip_id,
                ball_colour=str(label.get("ball_colour") or "unknown"),
                impact_type=imp_type,
                label_frame=imp_frame,
                label_x=imp_x,
                label_y=imp_y,
                calib_points=calib["points"],
                raw_dump=raw_dump,
                sys_deviation=sys_dev,
            )
        )
    return clips


def _aggregate_metrics(
    frame_errors: Sequence[Optional[int]],
    px_errors: Sequence[Optional[float]],
) -> Tuple[int, int, int, int, int, Optional[float], Optional[float], Optional[float]]:
    n_total = len(frame_errors)
    scored_f = [e for e in frame_errors if e is not None]
    n_found = len(scored_f)
    n_exact = sum(1 for e in scored_f if e == 0)
    n_within_1 = sum(1 for e in scored_f if abs(e) <= 1)
    n_within_2 = sum(1 for e in scored_f if abs(e) <= 2)
    mae = (sum(abs(e) for e in scored_f) / n_found) if n_found > 0 else None

    valid_px = [p for p in px_errors if p is not None]
    if valid_px:
        arr = np.asarray(valid_px, dtype=np.float64)
        px_median = float(np.median(arr))
        px_p90 = float(np.percentile(arr, 90))
    else:
        px_median = None
        px_p90 = None
    return n_total, n_found, n_exact, n_within_1, n_within_2, mae, px_median, px_p90


def evaluate_impact_rule(
    spec: ImpactRuleSpec,
    clips: Sequence[ImpactClipInput],
) -> ImpactRuleSummary:
    """Evaluate a single impact rule across clips."""
    preds: List[ImpactClipPrediction] = []
    f_errs: List[Optional[int]] = []
    px_errs: List[Optional[float]] = []

    for clip in clips:
        res = spec.fn(clip.raw_dump, clip.calib_points)
        if res is not None:
            pf, px, py = res
            fe: Optional[int] = pf - clip.label_frame
            pe: Optional[float] = float(math.hypot(px - clip.label_x, py - clip.label_y))
        else:
            pf = None
            px = None
            py = None
            fe = None
            pe = None
        preds.append(
            ImpactClipPrediction(
                clip_id=clip.clip_id,
                ball_colour=clip.ball_colour,
                label_frame=clip.label_frame,
                pred_frame=pf,
                pred_x=px,
                pred_y=py,
                frame_error=fe,
                px_error=pe,
            )
        )
        f_errs.append(fe)
        px_errs.append(pe)

    n_total, n_found, n_exact, n_within_1, n_within_2, mae, px_med, px_p90 = (
        _aggregate_metrics(f_errs, px_errs)
    )
    return ImpactRuleSummary(
        spec=spec,
        n_total=n_total,
        n_found=n_found,
        n_exact=n_exact,
        n_within_1=n_within_1,
        n_within_2=n_within_2,
        mae=mae,
        px_median=px_med,
        px_p90=px_p90,
        predictions=tuple(preds),
    )


def evaluate_system_deviation(
    clips: Sequence[ImpactClipInput],
) -> ImpactRuleSummary:
    """Evaluate the pipeline's events.deviation as a reference impact row."""
    spec = ImpactRuleSpec(
        name="SYSTEM(deviation)",
        family="REF",
        fn=lambda _dump, _pts: None,
    )
    preds: List[ImpactClipPrediction] = []
    f_errs: List[Optional[int]] = []
    px_errs: List[Optional[float]] = []

    for clip in clips:
        if clip.sys_deviation is not None:
            pf, px, py = clip.sys_deviation
            fe: Optional[int] = pf - clip.label_frame
            pe: Optional[float] = float(math.hypot(px - clip.label_x, py - clip.label_y))
        else:
            pf = None
            px = None
            py = None
            fe = None
            pe = None
        preds.append(
            ImpactClipPrediction(
                clip_id=clip.clip_id,
                ball_colour=clip.ball_colour,
                label_frame=clip.label_frame,
                pred_frame=pf,
                pred_x=px,
                pred_y=py,
                frame_error=fe,
                px_error=pe,
            )
        )
        f_errs.append(fe)
        px_errs.append(pe)

    n_total, n_found, n_exact, n_within_1, n_within_2, mae, px_med, px_p90 = (
        _aggregate_metrics(f_errs, px_errs)
    )
    return ImpactRuleSummary(
        spec=spec,
        n_total=n_total,
        n_found=n_found,
        n_exact=n_exact,
        n_within_1=n_within_1,
        n_within_2=n_within_2,
        mae=mae,
        px_median=px_med,
        px_p90=px_p90,
        predictions=tuple(preds),
    )


def impact_rule_rank_key(summary: ImpactRuleSummary) -> Tuple[Any, ...]:
    """Rank rules by ±1 hits, exact hits, ±2 hits, lowest MAE/px, and found count."""
    mae_val = summary.mae if summary.mae is not None else float("inf")
    px_med = summary.px_median if summary.px_median is not None else float("inf")
    return (
        -summary.n_within_1,
        -summary.n_exact,
        -summary.n_within_2,
        mae_val,
        px_med,
        -summary.n_found,
        _FAMILY_ORDER.get(summary.spec.family, 99),
        summary.spec.param_sort,
        summary.spec.name,
    )


def run_impact_leave_one_out(
    specs: Sequence[ImpactRuleSpec],
    clips: Sequence[ImpactClipInput],
    family_label: str,
) -> ImpactLooResult:
    """Pick best rule in `specs` on N-1 clips and score the held-out clip."""
    if not specs:
        raise ValueError("specs must not be empty")
    if len(clips) < 2:
        raise ValueError("leave-one-out requires at least 2 clips")

    folds: List[ImpactLooFoldResult] = []
    f_errs: List[Optional[int]] = []
    px_errs: List[Optional[float]] = []

    for hold_idx, held_out in enumerate(clips):
        train_clips = [c for idx, c in enumerate(clips) if idx != hold_idx]
        train_summaries = [evaluate_impact_rule(spec, train_clips) for spec in specs]
        best_spec = min(train_summaries, key=impact_rule_rank_key).spec

        res = best_spec.fn(held_out.raw_dump, held_out.calib_points)
        if res is not None:
            pf, px, py = res
            fe: Optional[int] = pf - held_out.label_frame
            pe: Optional[float] = float(
                math.hypot(px - held_out.label_x, py - held_out.label_y)
            )
        else:
            pf = None
            fe = None
            pe = None
        folds.append(
            ImpactLooFoldResult(
                clip_id=held_out.clip_id,
                ball_colour=held_out.ball_colour,
                label_frame=held_out.label_frame,
                chosen_rule=best_spec.name,
                pred_frame=pf,
                frame_error=fe,
                px_error=pe,
            )
        )
        f_errs.append(fe)
        px_errs.append(pe)

    n_total, n_found, n_exact, n_within_1, n_within_2, mae, px_med, px_p90 = (
        _aggregate_metrics(f_errs, px_errs)
    )
    return ImpactLooResult(
        family_label=family_label,
        n_total=n_total,
        n_found=n_found,
        n_exact=n_exact,
        n_within_1=n_within_1,
        n_within_2=n_within_2,
        mae=mae,
        px_median=px_med,
        px_p90=px_p90,
        folds=tuple(folds),
    )


def _fmt_signed(err: Optional[int]) -> str:
    if err is None:
        return "NA"
    if err > 0:
        return f"+{err}"
    return str(err)


def _fmt_opt(val: Optional[float], spec: str = ".2f") -> str:
    return format(val, spec) if val is not None else "NA"


def _fmt_count_of_found(count: int, n_found: int, n_total: int) -> str:
    pct_tot = (100.0 * count / n_total) if n_total else 0.0
    if n_found > 0:
        return f"{count}/{n_found} ({pct_tot:.1f}% of {n_total})"
    return f"0/0 (0.0% of {n_total})"


def _select_top_rules_for_breakdown(
    ranked_summaries: Sequence[ImpactRuleSummary],
) -> List[ImpactRuleSummary]:
    """Return top 3 ranked rules plus up to 3 top distinct-prediction rules if tied."""
    chosen: List[ImpactRuleSummary] = list(ranked_summaries[:3])
    seen_names = {s.spec.name for s in chosen}
    seen_sigs = {tuple(p.pred_frame for p in s.predictions) for s in chosen}
    distinct_count = len(seen_sigs)
    for s in ranked_summaries[3:]:
        if distinct_count >= 3:
            break
        sig = tuple(p.pred_frame for p in s.predictions)
        if sig not in seen_sigs and s.spec.name not in seen_names:
            chosen.append(s)
            seen_names.add(s.spec.name)
            seen_sigs.add(sig)
            distinct_count += 1
    return chosen


def render_impact_markdown(
    run_name: str,
    clips: Sequence[ImpactClipInput],
    ranked_summaries: Sequence[ImpactRuleSummary],
    loo_results: Sequence[ImpactLooResult],
    deviation_summary: Optional[ImpactRuleSummary] = None,
) -> str:
    """Format ranked table, LOO CV, best-3 per-clip errors, and wrong clips."""
    lines: List[str] = [
        f"# Impact Rule Search — {run_name}",
        "",
        f"- Final labelled clips with non-none impact & raw detections: **{len(clips)}**",
        f"- Rules evaluated: **{len(ranked_summaries)}**",
        "",
        "## Ranked Rules (In-Sample)",
        "",
        "| Rank | Rule | Found | Exact (0) | Within ±1 | Within ±2 | MAE (frames) | Px Dist (med / p90) |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    if deviation_summary is not None:
        s = deviation_summary
        found_pct = (100.0 * s.n_found / s.n_total) if s.n_total else 0.0
        px_s = f"{_fmt_opt(s.px_median, '.1f')} / {_fmt_opt(s.px_p90, '.1f')}"
        lines.append(
            f"| ref | {s.spec.name} | {s.n_found}/{s.n_total} ({found_pct:.1f}%) | "
            f"{_fmt_count_of_found(s.n_exact, s.n_found, s.n_total)} | "
            f"{_fmt_count_of_found(s.n_within_1, s.n_found, s.n_total)} | "
            f"{_fmt_count_of_found(s.n_within_2, s.n_found, s.n_total)} | "
            f"{_fmt_opt(s.mae, '.2f')} | {px_s} |"
        )
    for rank, s in enumerate(ranked_summaries, start=1):
        found_pct = (100.0 * s.n_found / s.n_total) if s.n_total else 0.0
        px_s = f"{_fmt_opt(s.px_median, '.1f')} / {_fmt_opt(s.px_p90, '.1f')}"
        lines.append(
            f"| {rank} | {s.spec.name} | {s.n_found}/{s.n_total} ({found_pct:.1f}%) | "
            f"{_fmt_count_of_found(s.n_exact, s.n_found, s.n_total)} | "
            f"{_fmt_count_of_found(s.n_within_1, s.n_found, s.n_total)} | "
            f"{_fmt_count_of_found(s.n_within_2, s.n_found, s.n_total)} | "
            f"{_fmt_opt(s.mae, '.2f')} | {px_s} |"
        )

    lines.extend(
        [
            "",
            "## Leave-One-Out Cross-Validation (LOO)",
            "",
            "| Candidate Set | Found | Exact (0) | Within ±1 | Within ±2 | MAE (frames) | Px Dist (med / p90) |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for loo in loo_results:
        found_pct = (100.0 * loo.n_found / loo.n_total) if loo.n_total else 0.0
        px_s = f"{_fmt_opt(loo.px_median, '.1f')} / {_fmt_opt(loo.px_p90, '.1f')}"
        lines.append(
            f"| {loo.family_label} | {loo.n_found}/{loo.n_total} ({found_pct:.1f}%) | "
            f"{_fmt_count_of_found(loo.n_exact, loo.n_found, loo.n_total)} | "
            f"{_fmt_count_of_found(loo.n_within_1, loo.n_found, loo.n_total)} | "
            f"{_fmt_count_of_found(loo.n_within_2, loo.n_found, loo.n_total)} | "
            f"{_fmt_opt(loo.mae, '.2f')} | {px_s} |"
        )

    for loo in loo_results:
        lines.extend(
            [
                "",
                f"### LOO Folds — {loo.family_label}",
                "",
                "| Clip | Ball | Label | Chosen Rule | Pred | Err (rule - label) | Px Dist |",
                "|---|---|---:|---|---:|---:|---:|",
            ]
        )
        for fold in loo.folds:
            pred_s = str(fold.pred_frame) if fold.pred_frame is not None else "NA"
            lines.append(
                f"| {fold.clip_id} | {fold.ball_colour} | {fold.label_frame} | "
                f"{fold.chosen_rule} | {pred_s} | {_fmt_signed(fold.frame_error)} | "
                f"{_fmt_opt(fold.px_error, '.1f')} |"
            )

    best_rules = _select_top_rules_for_breakdown(ranked_summaries)
    if best_rules:
        lines.extend(
            [
                "",
                "## Per-Clip Signed Errors (`rule - label`) — Best 3 Rules",
                "",
            ]
        )
        header_cols = ["Clip", "Ball", "Label"] + [s.spec.name for s in best_rules]
        lines.append("| " + " | ".join(header_cols) + " |")
        lines.append("|---|---|---:|" + "---:|" * len(best_rules))
        for idx, clip in enumerate(clips):
            row = [clip.clip_id, clip.ball_colour, str(clip.label_frame)]
            for s in best_rules:
                p = s.predictions[idx]
                row.append(_fmt_signed(p.frame_error))
            lines.append("| " + " | ".join(row) + " |")

        lines.extend(
            [
                "",
                "## Clips Still Wrong for Each of the Best 3 Rules",
                "",
            ]
        )
        for s in best_rules:
            missed = [p for p in s.predictions if p.frame_error is None]
            outside_1 = [
                p for p in s.predictions if p.frame_error is not None and abs(p.frame_error) > 1
            ]
            exact_1_only = [
                p for p in s.predictions if p.frame_error is not None and abs(p.frame_error) == 1
            ]
            lines.append(f"### {s.spec.name}")
            if missed:
                items = ", ".join(
                    f"`{p.clip_id}` ({p.ball_colour}: label={p.label_frame}, pred=None)"
                    for p in missed
                )
                lines.append(f"- Missed ({len(missed)}): {items}")
            else:
                lines.append("- Missed: none")
            if outside_1:
                items = ", ".join(
                    f"`{p.clip_id}` ({p.ball_colour}: label={p.label_frame}, pred={p.pred_frame}, "
                    f"err={_fmt_signed(p.frame_error)}, px={_fmt_opt(p.px_error, '.1f')})"
                    for p in outside_1
                )
                lines.append(f"- Outside ±1 ({len(outside_1)}): {items}")
            else:
                lines.append("- Outside ±1: none")
            if exact_1_only:
                items = ", ".join(
                    f"`{p.clip_id}` ({p.ball_colour}: label={p.label_frame}, pred={p.pred_frame}, "
                    f"err={_fmt_signed(p.frame_error)}, px={_fmt_opt(p.px_error, '.1f')})"
                    for p in exact_1_only
                )
                lines.append(f"- Off by ±1 ({len(exact_1_only)}): {items}")
            else:
                lines.append("- Off by ±1: none")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def evaluate_impact_run(
    run_name: str,
    labels_dir: Path,
    runs_dir: Path,
    analysis_dir: Path,
) -> Path:
    """Evaluate all impact rules and LOO on `run_name` and write Markdown report."""
    run_dir = runs_dir / run_name
    clips = load_impact_clip_inputs(run_dir=run_dir, labels_dir=labels_dir)
    if not clips:
        raise RuntimeError(
            f"No final labelled impact clips with raw_ball_detections.json under {run_dir}"
        )

    specs = build_impact_rule_specs()
    summaries = [evaluate_impact_rule(spec, clips) for spec in specs]
    ranked = sorted(summaries, key=impact_rule_rank_key)
    dev_summary = evaluate_system_deviation(clips)

    i1_specs = [s for s in specs if s.family == "I1"]
    i4_specs = [s for s in specs if s.family == "I4"]
    i5a_specs = [s for s in specs if s.family == "I5a"]
    i5b_specs = [s for s in specs if s.family == "I5b"]
    i5_specs = [s for s in specs if s.family in ("I5a", "I5b")]
    i6a_specs = [s for s in specs if s.family == "I6a"]
    i6b_specs = [s for s in specs if s.family == "I6b"]
    i6_specs = [s for s in specs if s.family in ("I6a", "I6b")]
    loo_results = [
        run_impact_leave_one_out(i1_specs, clips, "I1 (theta)"),
        run_impact_leave_one_out(i4_specs, clips, "I4 (+1 vs last_seen)"),
        run_impact_leave_one_out(i5a_specs, clips, "I5a (up, theta)"),
        run_impact_leave_one_out(i5b_specs, clips, "I5b (up, theta)"),
        run_impact_leave_one_out(i5_specs, clips, "I5 (I5a + I5b)"),
        run_impact_leave_one_out(i6a_specs, clips, "I6a (up, theta)"),
        run_impact_leave_one_out(i6b_specs, clips, "I6b (up, theta)"),
        run_impact_leave_one_out(i6_specs, clips, "I6 (I6a + I6b)"),
        run_impact_leave_one_out(specs, clips, "ALL (I1..I6)"),
    ]

    analysis_dir.mkdir(parents=True, exist_ok=True)
    out_path = analysis_dir / f"impact_rules_{run_name}.md"
    out_path.write_text(
        render_impact_markdown(
            run_name=run_name,
            clips=clips,
            ranked_summaries=ranked,
            loo_results=loo_results,
            deviation_summary=dev_summary,
        ),
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

    out_path = evaluate_impact_run(
        run_name=args.run,
        labels_dir=labels_dir,
        runs_dir=runs_dir,
        analysis_dir=analysis_dir,
    )
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
