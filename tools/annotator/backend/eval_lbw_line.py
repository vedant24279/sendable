"""Evaluate the line-only LBW prediction on the labelled clips.

For every final label with a results.json in eval/runs/<run>, recompute the
line-only prediction twice (labelled batter hand, then batter_hand=None),
compare X_s with the homography-lifted probe (eval/analysis/lbw_lifted_<lifted>.csv)
and write eval/analysis/lbw_line_<lifted>.md.

All labelled clips are on-field LBW "out" decisions, so this is a sanity check,
not an accuracy measure.

Usage:
    python tools/annotator/backend/eval_lbw_line.py --run lbw_line_1
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pipeline.lbw_line import (  # noqa: E402
    IMPACT_Z_M,
    POST_BOUNCE_SPEED_FACTOR,
    RELEASE_Z_M,
    compute_lbw_line,
)

XS_AGREEMENT_M = 0.05


def _compute(results: Dict[str, Any], hand: Optional[str]) -> Optional[Dict[str, Any]]:
    ev = results.get("events") or {}
    return compute_lbw_line(
        corners=results.get("calibration") or {},
        fps=float((results.get("video") or {}).get("fps") or 0.0),
        release=ev.get("release"),
        bounce_centre=ev.get("bounce"),
        impact=ev.get("impact"),
        trajectory=results.get("trajectory") or [],
        trajectory_post=results.get("trajectory_post"),
        batter_hand=hand,
    )


def _compute_with_label_impact(
    results: Dict[str, Any], label: Dict[str, Any], hand: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Diagnostic only: the same model with the LABELLED impact frame/pixel instead of events.impact."""
    imp = label.get("impact") or {}
    if imp.get("frame") is None or imp.get("x") is None:
        return None
    ev = dict(results.get("events") or {})
    ev["impact"] = {"frame": int(imp["frame"]), "x": float(imp["x"]), "y": float(imp["y"])}
    return compute_lbw_line(
        corners=results.get("calibration") or {},
        fps=float((results.get("video") or {}).get("fps") or 0.0),
        release=ev.get("release"),
        bounce_centre=ev.get("bounce"),
        impact=ev["impact"],
        trajectory=results.get("trajectory") or [],
        trajectory_post=results.get("trajectory_post"),
        batter_hand=hand,
    )


def _none_reason(results: Dict[str, Any]) -> str:
    ev = results.get("events") or {}
    imp, rel, bnc = ev.get("impact"), ev.get("release"), ev.get("bounce")
    if not imp:
        return "no impact event"
    if not rel or not bnc:
        return "no release/bounce event"
    if int(bnc["frame"]) <= int(rel["frame"]):
        return f"bounce frame {bnc['frame']} not after release frame {rel['frame']}"
    return "timing/geometry invalid"


def _load_lifted(path: Path) -> Dict[str, Dict[str, Optional[float]]]:
    """Per clip: X_s, oracle X_s and post-bounce arrival time (s) of the lifted probe."""
    out: Dict[str, Dict[str, Optional[float]]] = {}
    if not path.is_file():
        return out
    def num(row: Dict[str, str], key: str) -> Optional[float]:
        v = row.get(key, "")
        return float(v) if v else None
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["clip_id"]] = {
                "xs": num(row, "X_s_m"),
                "ora_xs": num(row, "ora_X_s_m"),
                "arrival_rel_s": num(row, "arrival_time_rel_s"),
            }
    return out


def _fmt(v: Optional[float], nd: int = 3, sign: bool = False) -> str:
    if v is None:
        return "—"
    return f"{v:+.{nd}f}" if sign else f"{v:.{nd}f}"


def evaluate(run: str, lifted_name: str) -> str:
    labels_dir = REPO_ROOT / "eval" / "labels"
    run_dir = REPO_ROOT / "eval" / "runs" / run
    lifted = _load_lifted(REPO_ROOT / "eval" / "analysis" / f"lbw_lifted_{lifted_name}.csv")

    rows: List[Dict[str, Any]] = []
    for lf in sorted(labels_dir.glob("*.json")):
        lbl = json.loads(lf.read_text(encoding="utf-8"))
        if lbl.get("status") != "final":
            continue
        cid = lbl["clip_id"]
        rj = run_dir / cid / "results.json"
        if not rj.is_file():
            continue
        res = json.loads(rj.read_text(encoding="utf-8"))
        hand = lbl.get("batter_hand") if lbl.get("batter_hand") in ("right", "left") else None
        rows.append(
            {
                "clip_id": cid,
                "hand": hand,
                "label": lbl,
                "res": res,
                "lbw": _compute(res, hand),
                "lbw_none": _compute(res, None),
                "lbw_right": _compute(res, "right"),
                "lbw_oracle": _compute_with_label_impact(res, lbl, hand),
                "reason": _none_reason(res),
                "lifted": lifted.get(cid) or {},
                "lifted_xs": (lifted.get(cid) or {}).get("xs"),
            }
        )

    solved = [r for r in rows if r["lbw"] is not None]
    unsolved = [r for r in rows if r["lbw"] is None]

    # Consistency of the batch run's stored "lbw" block (the batch used batter_hand=right for all).
    stored_checked = stored_equal = 0
    for r in rows:
        stored = r["res"].get("lbw")
        if stored is None:
            continue
        stored_checked += 1
        if stored == r["lbw_right"]:
            stored_equal += 1
    stored_absent = [r["clip_id"] for r in rows if "lbw" not in r["res"]]

    lines: List[str] = []
    lines.append(f"# Line-Only LBW Prediction (`{run}`)")
    lines.append("")
    lines.append(
        "> **Sanity check, not an accuracy measure.** All 14 labelled clips are on-field LBW "
        "**\"out\"** decisions (all pad impacts). Only the LINE is evaluated: height at the stumps is "
        "not recoverable from the single camera. The expected outcome is mostly `OUT_LINE` / `HITTING`; "
        "anything else is a sign of a geometry or event problem, not of a wrong decision."
    )
    lines.append("")
    lines.append(
        f"Clips with labels and `{run}` results: `{len(rows)}`; line prediction computed: `{len(solved)}`; "
        f"not computable: `{len(unsolved)}`. Batch `lbw` blocks stored in results.json: "
        f"`{stored_checked}` (equal to a recomputation with `batter_hand=right`: `{stored_equal}`); "
        f"results.json without an `lbw` key: `{len(stored_absent)}`"
        + (f" (`{', '.join(stored_absent)}`)." if stored_absent else ".")
    )
    lines.append("")

    # ── Per-clip table ─────────────────────────────────────────────────────
    lines.append("## 1. Per-clip results (labelled batter hand)")
    lines.append("")
    lines.append(
        "| Clip | Hand | Pitch `(X, Z)` m | Pitch side / verdict | Impact `X` m | Impact side / verdict | "
        "`X_s` m | σ m | Wickets | Margin m | Stable | Slope pts flag | Overall |"
    )
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for r in rows:
        b = r["lbw"]
        if b is None:
            lines.append(
                f"| `{r['clip_id']}` | {r['hand']} | — | — | — | — | — | — | — | — | — | — | "
                f"**not computed** ({r['reason']}) |"
            )
            continue
        p, i, w = b["pitching"], b["impact"], b["wickets"]
        lines.append(
            f"| `{r['clip_id']}` | {r['hand']} | `({p['x']:+.3f}, {p['z']:.2f})` | "
            f"{p['side']} / `{p['verdict']}` | `{i['x']:+.3f}` | {i['side']} / `{i['verdict']}` | "
            f"`{w['x']:+.3f}` | `{w['sigma']:.3f}` | `{w['verdict']}` | `{w['margin_m']:+.3f}` | "
            f"{'yes' if w['stable'] else '**no**'} | {'flag' if b['slope_flag'] else 'ok'} | `{b['overall']}` |"
        )
    lines.append("")

    # ── Verdict counts ─────────────────────────────────────────────────────
    def counts(key: str, sub: str) -> Counter:
        return Counter(r["lbw"][key][sub] for r in solved)

    lines.append("## 2. Verdict counts (labelled hand)")
    lines.append("")
    n = len(solved)
    lines.append(f"Computed clips: `{n}`.")
    lines.append("")
    lines.append("| Stage | Counts |")
    lines.append("| :--- | :--- |")
    for title, c in (
        ("Pitching", counts("pitching", "verdict")),
        ("Impact", counts("impact", "verdict")),
        ("Wickets", counts("wickets", "verdict")),
    ):
        lines.append(f"| {title} | " + ", ".join(f"`{k}`: {v}" for k, v in sorted(c.items())) + " |")
    ov = Counter(r["lbw"]["overall"] for r in solved)
    lines.append("| Overall | " + ", ".join(f"`{k}`: {v}" for k, v in sorted(ov.items())) + " |")
    lines.append("")
    wv = counts("wickets", "verdict")
    lines.append(
        "Wickets shares: "
        + ", ".join(f"`{k}` {wv.get(k, 0)}/{n} (`{100.0 * wv.get(k, 0) / max(n, 1):.1f}%`)" for k in ("HITTING", "UMPIRES_CALL", "MISSING"))
        + "."
    )
    sigmas = [r["lbw"]["wickets"]["sigma"] for r in solved]
    lines.append("")
    lines.append(
        f"Mean σ (wickets lateral uncertainty): `{statistics.mean(sigmas):.3f} m` "
        f"(min `{min(sigmas):.3f}`, max `{max(sigmas):.3f}`)." if sigmas else "Mean σ: —"
    )
    lines.append("")
    unstable = [r for r in solved if not r["lbw"]["wickets"]["stable"]]
    lines.append(f"### Verdicts that are not stable (`|margin| <= 2σ`): `{len(unstable)}/{n}`")
    lines.append("")
    if unstable:
        lines.append("| Clip | Wickets | `X_s` m | Margin m | 2σ m | Overall |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
        for r in unstable:
            w = r["lbw"]["wickets"]
            lines.append(
                f"| `{r['clip_id']}` | `{w['verdict']}` | `{w['x']:+.3f}` | `{w['margin_m']:+.3f}` | "
                f"`{2 * w['sigma']:.3f}` | `{r['lbw']['overall']}` |"
            )
        silent = [r["clip_id"] for r in unstable if r["lbw"]["wickets"]["verdict"] == "MISSING"]
        if silent:
            lines.append("")
            lines.append(
                f"Note: `{', '.join(silent)}` have an unstable `MISSING`; by the specified rule an unstable miss "
                "does not make the overall `NOT_OUT_LINE`, so it falls through to `OUT_LINE`/`UMPIRES_CALL`."
            )
    else:
        lines.append("None.")
    lines.append("")

    # ── Comparison with lifted probe ───────────────────────────────────────
    lines.append("## 3. `X_s` versus the homography-lifted probe")
    lines.append("")
    lines.append(
        f"Reference: `X_s_m` (main run, `k=0`, `e in [0.3, 0.8]`, system impact) of `lbw_lifted_{lifted_name}.csv`. "
        f"Agreement threshold: `{XS_AGREEMENT_M * 100:.0f} cm`."
    )
    lines.append("")
    lines.append("| Clip | Line `X_s` m | Lifted `X_s` m | Δ m | `X_i` m | Slope term `ΔX` m | Slope pts | Agrees |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    diffs: List[Tuple[str, float]] = []
    for r in solved:
        w, i = r["lbw"]["wickets"], r["lbw"]["impact"]
        lx = r["lifted_xs"]
        slope_term = w["x"] - i["x"]
        if lx is None:
            lines.append(
                f"| `{r['clip_id']}` | `{w['x']:+.3f}` | — | — | `{i['x']:+.3f}` | `{slope_term:+.3f}` | "
                f"{'flag' if r['lbw']['slope_flag'] else 'ok'} | n/a (lifted fit not available) |"
            )
            continue
        d = w["x"] - lx
        diffs.append((r["clip_id"], d))
        lines.append(
            f"| `{r['clip_id']}` | `{w['x']:+.3f}` | `{lx:+.3f}` | `{d:+.3f}` | `{i['x']:+.3f}` | "
            f"`{slope_term:+.3f}` | {'flag' if r['lbw']['slope_flag'] else 'ok'} | "
            f"{'yes' if abs(d) <= XS_AGREEMENT_M else '**no**'} |"
        )
    lines.append("")
    if diffs:
        ok = [c for c, d in diffs if abs(d) <= XS_AGREEMENT_M]
        bad = [(c, d) for c, d in diffs if abs(d) > XS_AGREEMENT_M]
        abs_d = [abs(d) for _, d in diffs]
        lines.append(
            f"Within `{XS_AGREEMENT_M * 100:.0f} cm`: `{len(ok)}/{len(diffs)}`; median |Δ| `{statistics.median(abs_d):.3f} m`, "
            f"max |Δ| `{max(abs_d):.3f} m`."
        )
        lines.append("")
        if bad:
            lines.append("Clips differing by more than 5 cm: " + ", ".join(f"`{c}` ({d:+.3f} m)" for c, d in bad) + ".")
        else:
            lines.append("No clip differs by more than 5 cm.")
        lines.append("")

    # ── Why the clips differ ───────────────────────────────────────────────
    lines.append("### Why the clips differ")
    lines.append("")
    lines.append(
        "Two model differences explain the gaps. (a) The line model takes the post-bounce lateral slope directly from "
        "the post-bounce points and always extrapolates from a pad `1.0 m` from the stump line "
        f"(post-bounce along-pitch speed `{POST_BOUNCE_SPEED_FACTOR}` x pre-bounce); the lifted fit ties the post-bounce "
        "lateral velocity to the pre-bounce one (times `f`) and its time to the stumps follows from a poorly determined "
        "`f`/height, so its bounce→stumps time differs from the line model's (see the frame columns). (b) `events.impact` is a trajectory vertex and "
        "can be one frame after the labelled impact, i.e. on the post-contact deflection, which changes `X_i` and the slope."
    )
    lines.append("")
    lines.append(
        "| Clip | Impact frame sys / label | Line `X_s` | Line `X_s` (labelled impact) | Lifted `X_s` | Lifted `X_s` (oracle impact) | "
        "Line frames bounce→stumps | Lifted frames bounce→stumps | Cause (differs > 5 cm) |"
    )
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
    for r in solved:
        b = r["lbw"]
        ev = r["res"]["events"]
        rel_f, bnc_f, imp_f = int(ev["release"]["frame"]), int(ev["bounce"]["frame"]), int(ev["impact"]["frame"])
        lbl_imp_f = (r["label"].get("impact") or {}).get("frame")
        vz = POST_BOUNCE_SPEED_FACTOR * (RELEASE_Z_M - b["pitching"]["z"]) / (bnc_f - rel_f)
        line_frames = (imp_f - bnc_f) + IMPACT_Z_M / vz
        arr = r["lifted"].get("arrival_rel_s")
        fps = float((r["res"].get("video") or {}).get("fps") or 30.0)
        lifted_frames = None if arr is None else arr * fps
        orc = r["lbw_oracle"]
        orc_xs = None if orc is None else orc["wickets"]["x"]
        lx, lox = r["lifted_xs"], r["lifted"].get("ora_xs")
        causes: List[str] = []
        if lx is not None and abs(b["wickets"]["x"] - lx) > XS_AGREEMENT_M:
            if lbl_imp_f is not None and int(lbl_imp_f) != imp_f:
                causes.append(f"system impact {imp_f - int(lbl_imp_f):+d} frame vs label")
            if lifted_frames is not None and abs(lifted_frames - line_frames) >= 1.0:
                causes.append(f"lifted bounce→stumps time differs by {lifted_frames - line_frames:+.1f} frames")
            if orc_xs is not None and lox is not None and abs(orc_xs - lox) > XS_AGREEMENT_M:
                causes.append(f"still {orc_xs - lox:+.3f} m apart with the labelled impact (lateral slope model)")
            if b["slope_flag"]:
                causes.append("slope flag (<3 points): slope set to 0")
            if not causes:
                causes.append("no single cause identified")
        lines.append(
            f"| `{r['clip_id']}` | {imp_f} / {lbl_imp_f} | `{b['wickets']['x']:+.3f}` | `{_fmt(orc_xs, 3, True)}` | "
            f"`{_fmt(lx, 3, True)}` | `{_fmt(lox, 3, True)}` | `{line_frames:.1f}` | `{_fmt(lifted_frames, 1)}` | "
            f"{'; '.join(causes) if causes else '—'} |"
        )
    lines.append("")

    # ── Hand None pass ─────────────────────────────────────────────────────
    lines.append("## 4. Second pass: `batter_hand = None`")
    lines.append("")
    none_solved = [r for r in rows if r["lbw_none"] is not None]
    ov0 = Counter(r["lbw_none"]["overall"] for r in none_solved)
    wv0 = Counter(r["lbw_none"]["wickets"]["verdict"] for r in none_solved)
    pv0 = Counter(r["lbw_none"]["pitching"]["verdict"] for r in none_solved)
    iv0 = Counter(r["lbw_none"]["impact"]["verdict"] for r in none_solved)
    lines.append(f"Computed clips: `{len(none_solved)}`. Sides are `None`; the leg-side pitching rule cannot apply.")
    lines.append("")
    lines.append("| Stage | Counts |")
    lines.append("| :--- | :--- |")
    for title, c in (("Pitching", pv0), ("Impact", iv0), ("Wickets", wv0), ("Overall", ov0)):
        lines.append(f"| {title} | " + ", ".join(f"`{k}`: {v}" for k, v in sorted(c.items())) + " |")
    lines.append("")
    changed = [
        r["clip_id"]
        for r in solved
        if r["lbw_none"] is not None and r["lbw_none"]["overall"] != r["lbw"]["overall"]
    ]
    xs_changed = [
        r["clip_id"]
        for r in solved
        if r["lbw_none"] is not None and r["lbw_none"]["wickets"]["x"] != r["lbw"]["wickets"]["x"]
    ]
    lines.append(
        f"Clips whose overall verdict changes when the hand is unknown: "
        + (", ".join(f"`{c}`" for c in changed) if changed else "none")
        + f". Clips whose `X_s` changes: " + (", ".join(f"`{c}`" for c in xs_changed) if xs_changed else "none (X_s does not depend on the hand).")
    )
    lines.append("")

    # ── Not computed ───────────────────────────────────────────────────────
    lines.append("## 5. Clips without a line prediction")
    lines.append("")
    if unsolved:
        for r in unsolved:
            lines.append(f"- `{r['clip_id']}`: {r['reason']}.")
    else:
        lines.append("None.")
    lines.append("")
    lines.append("## 6. Assumptions to confirm")
    lines.append("")
    # Sign sanity: recompute with the constant flipped (temporarily; the sign logic depends only on it).
    from backend.pipeline import lbw_line as _lbw_mod

    orig = _lbw_mod.OFF_SIDE_IS_IMAGE_LEFT_FOR_RIGHT_HANDER
    try:
        _lbw_mod.OFF_SIDE_IS_IMAGE_LEFT_FOR_RIGHT_HANDER = not orig
        flipped = [_compute(r["res"], r["hand"]) for r in rows]
    finally:
        _lbw_mod.OFF_SIDE_IS_IMAGE_LEFT_FOR_RIGHT_HANDER = orig
    flipped = [b for b in flipped if b is not None]
    fp = Counter(b["pitching"]["verdict"] for b in flipped)
    fo = Counter(b["overall"] for b in flipped)
    cur_p = counts("pitching", "verdict")
    lines.append(
        f"- `OFF_SIDE_IS_IMAGE_LEFT_FOR_RIGHT_HANDER = {orig}` in `backend/pipeline/lbw_line.py` (off side for a right-hander is the "
        "image left, `X < 0`). **To be confirmed by the user**; all off/leg logic depends only on this constant. "
        f"Data check on these {len(flipped)} computed labelled-out clips: pitching verdicts are "
        + ", ".join(f"`{k}` {v}" for k, v in sorted(cur_p.items()))
        + f" with the current value and "
        + ", ".join(f"`{k}` {v}" for k, v in sorted(fp.items()))
        + f" with it flipped (overall `{dict(sorted(fo.items()))}`). Pitching outside leg cannot be out, so the flipped value "
        "would call most of these on-field outs not out; this supports the current value but does not prove it."
    )

    lines.append("- Release assumed `19.5 m` from the stump line; post-bounce along-pitch speed `0.85 x` pre-bounce; pad `1.0 m` (σ `0.6 m`) from the stump line.")
    lines.append("- Height is not evaluated; the impact type is not classified (pad assumed).")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate the line-only LBW prediction.")
    ap.add_argument("--run", default="lbw_line_1", help="Run under eval/runs/")
    ap.add_argument("--lifted", default="v2_1", help="Suffix of eval/analysis/lbw_lifted_<suffix>.csv")
    ap.add_argument("--out", default=None, help="Output markdown (default eval/analysis/lbw_line_<lifted>.md)")
    args = ap.parse_args()
    md = evaluate(args.run, args.lifted)
    out = Path(args.out) if args.out else REPO_ROOT / "eval" / "analysis" / f"lbw_line_{args.lifted}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
