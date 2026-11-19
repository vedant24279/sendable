"""Offline evaluation & gap-robustness benchmark for backend.pipeline.track_engine."""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

TOOLS_BACKEND = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_BACKEND.parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(TOOLS_BACKEND) not in sys.path:
    sys.path.insert(0, str(TOOLS_BACKEND))
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from pipeline.track_engine import analyse_track  # noqa: E402
from score import run_scoring  # noqa: E402
from scoring import classify_pitch_z_zone, load_legacy_zones  # noqa: E402

DEFAULT_DUMP_RUN = "dump_all_1"
DEFAULT_OUT_RUN = "track_1"
DEFAULT_BASE_RUN = "lbw_ui_3"
GAP_K_VALUES: Tuple[int, ...] = (0, 2, 3, 5)


def deleted_window_frames(center_frame: int, k: int) -> set[int]:
    if k <= 0:
        return set()
    start = center_frame - (k // 2)
    return {start + i for i in range(k)}


def filter_ball_by_frame(
    ball_by_frame: Mapping[Any, Any],
    drop_frames: set[int],
) -> Dict[int, Any]:
    out: Dict[int, Any] = {}
    for k, v in ball_by_frame.items():
        try:
            f = int(k)
        except (TypeError, ValueError):
            continue
        if f not in drop_frames:
            out[f] = v
    return out


def _load_final_red_pink_labels(labels_dir: Path) -> List[Dict[str, Any]]:
    labels: List[Dict[str, Any]] = []
    for path in sorted(labels_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") != "final" or data.get("calibration_gt") is None:
            continue
        if str(data.get("ball_colour") or "").lower() not in ("red", "pink"):
            continue
        labels.append(data)
    return labels


def _median_p90(vals: Sequence[float]) -> Tuple[Optional[float], Optional[float]]:
    if not vals:
        return None, None
    arr = np.asarray(vals, dtype=np.float64)
    return float(np.median(arr)), float(np.percentile(arr, 90))


def _summarize_per_clip_csv(
    csv_path: Path,
    clip_filter: Optional[set[str]] = None,
    colour_filter: Optional[str] = None,
) -> Dict[str, Any]:
    if not csv_path.is_file():
        return {}
    with csv_path.open("r", encoding="utf-8", newline="") as fp:
        rows = list(csv.DictReader(fp))
    if clip_filter is not None:
        rows = [r for r in rows if r["clip_id"] in clip_filter]
    if colour_filter is not None:
        rows = [r for r in rows if r["ball_colour"] == colour_filter]
    if not rows:
        return {"n": 0}

    n = len(rows)
    rel_f = [r for r in rows if r["release_found"] == "True" and r["release_frame_error"] != ""]
    rel_1 = [r for r in rel_f if abs(float(r["release_frame_error"])) <= 1.0]

    clear = [r for r in rows if r.get("is_unclear") != "True"]
    bnc_f = [r for r in clear if r["bounce_found"] == "True" and r["bounce_frame_error"] != ""]
    bnc_1 = [r for r in bnc_f if abs(float(r["bounce_frame_error"])) <= 1.0]
    bnc_m = [
        float(r["bounce_centre_ground_error_m"])
        for r in bnc_f
        if r.get("bounce_centre_ground_error_m", "") != ""
    ]

    contact = [r for r in clear if r["label_impact_type"] not in ("", "none", "None")]
    imp_f = [r for r in contact if r["sys_impact_present"] == "True" and r["impact_frame_error"] != ""]
    imp_1 = [r for r in imp_f if abs(float(r["impact_frame_error"])) <= 1.0]

    noc = [r for r in clear if r["label_impact_type"] == "none"]
    false_imp = [r for r in noc if r["false_marker_impact"] == "True"]

    bnc_m_med, bnc_m_p90 = _median_p90(bnc_m)
    return {
        "n": n,
        "rel_found": f"{len(rel_f)}/{n} ({len(rel_f)/n*100:.1f}%)",
        "rel_1f": f"{len(rel_1)/len(rel_f)*100:.1f}%" if rel_f else "—",
        "bnc_found": f"{len(bnc_f)}/{len(clear)} ({len(bnc_f)/len(clear)*100:.1f}%)" if clear else "—",
        "bnc_1f": f"{len(bnc_1)/len(bnc_f)*100:.1f}%" if bnc_f else "—",
        "bnc_ctr_med_m": f"{bnc_m_med:.3f}" if bnc_m_med is not None else "—",
        "imp_found": f"{len(imp_f)}/{len(contact)} ({len(imp_f)/len(contact)*100:.1f}%)" if contact else "—",
        "imp_1f": f"{len(imp_1)/len(imp_f)*100:.1f}%" if imp_f else "—",
        "false_imp": f"{len(false_imp)}/{len(noc)} ({len(false_imp)/len(noc)*100:.1f}%)" if noc else "0/0",
    }


def _build_results_json(
    clip_id: str,
    label: Dict[str, Any],
    dump_results: Dict[str, Any],
    engine_out: Dict[str, Any],
    zones: Sequence[Tuple[float, float, str]],
) -> Dict[str, Any]:
    events = dict(engine_out["events"])
    bnc = events.get("bounce")
    if isinstance(bnc, dict) and bnc.get("pitch_z_m") is not None:
        bnc["zone"] = classify_pitch_z_zone(float(bnc["pitch_z_m"]), zones)

    traj = [
        {
            "frame": int(pt["frame"]),
            "x": int(round(float(pt["x"]))),
            "y": int(round(float(pt["y"]))),
            "interpolated": False,
            "conf": pt.get("conf"),
        }
        for pt in engine_out["track"]
    ]

    return {
        "schema_version": 1,
        "clip_id": clip_id,
        "ball_type": dump_results.get("ball_type") or label.get("ball_colour"),
        "video": dump_results.get("video") or {},
        "calibration": dump_results.get("calibration") or {},
        "events": events,
        "trajectory": traj,
        "trajectory_post": [],
        "bridge": engine_out["bridge"],
        "evidence": engine_out["evidence"],
        "observed": engine_out["observed"],
        "notes": engine_out["notes"],
        "outputs": {},
        "stats": {"source": "track_engine_offline"},
    }


def run_offline_evaluation(
    *,
    dump_run: str = DEFAULT_DUMP_RUN,
    out_run: str = DEFAULT_OUT_RUN,
    base_run: str = DEFAULT_BASE_RUN,
    labels_dir: Optional[Path] = None,
    runs_dir: Optional[Path] = None,
    reports_dir: Optional[Path] = None,
    analysis_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    lbl_dir = (labels_dir or (REPO_ROOT / "eval" / "labels")).resolve()
    r_dir = (runs_dir or (REPO_ROOT / "eval" / "runs")).resolve()
    rep_dir = (reports_dir or (REPO_ROOT / "eval" / "reports")).resolve()
    ana_dir = (analysis_dir or (REPO_ROOT / "eval" / "analysis")).resolve()

    dump_dir = r_dir / dump_run
    out_dir = r_dir / out_run
    out_dir.mkdir(parents=True, exist_ok=True)
    ana_dir.mkdir(parents=True, exist_ok=True)

    labels = _load_final_red_pink_labels(lbl_dir)
    zones = load_legacy_zones()
    clip_ids: set[str] = set()
    raw_cache: Dict[str, Tuple[Dict[str, Any], Dict[str, Any], float, Dict[str, Any]]] = {}

    for lbl in labels:
        cid = str(lbl["clip_id"])
        raw_p = dump_dir / cid / "raw_ball_detections.json"
        res_p = dump_dir / cid / "results.json"
        if not raw_p.is_file() or not res_p.is_file():
            continue
        raw_data = json.loads(raw_p.read_text(encoding="utf-8"))
        dump_res = json.loads(res_p.read_text(encoding="utf-8"))
        corners = dump_res.get("calibration") or (lbl.get("calibration_gt") or {}).get("points") or {}
        fps = float(raw_data.get("fps") or (dump_res.get("video") or {}).get("fps") or 30.0)
        ball_by_frame = raw_data.get("ball") or {}

        eng_out = analyse_track(
            ball_by_frame, fps, corners, batter_hand=lbl.get("batter_hand")
        )
        res_out = _build_results_json(cid, lbl, dump_res, eng_out, zones)
        clip_out_dir = out_dir / cid
        clip_out_dir.mkdir(parents=True, exist_ok=True)
        (clip_out_dir / "results.json").write_text(
            json.dumps(res_out, indent=2), encoding="utf-8"
        )
        clip_ids.add(cid)
        raw_cache[cid] = (lbl, ball_by_frame, fps, corners)

    run_info = {
        "run_name": out_run,
        "utc_time": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_dump": dump_run,
        "env": {"track_engine": "offline_v1"},
        "clips": [{"clip_id": cid} for cid in sorted(clip_ids)],
    }
    (out_dir / "run_info.json").write_text(json.dumps(run_info, indent=2), encoding="utf-8")

    # Run unchanged score.py scoring
    md_p, csv_p, _ = run_scoring(
        run_name=out_run,
        labels_dir=lbl_dir,
        runs_dir=r_dir,
        reports_dir=rep_dir,
    )

    # Gap test (k = 0, 2, 3, 5 around bounce and impact)
    base_csv = rep_dir / f"{base_run}_per_clip.csv"
    base_bnc_errs: List[float] = []
    base_imp_errs: List[float] = []
    if base_csv.is_file():
        with base_csv.open("r", encoding="utf-8", newline="") as fp:
            for r in csv.DictReader(fp):
                if r["clip_id"] not in clip_ids:
                    continue
                if r["bounce_found"] == "True" and r["bounce_frame_error"] != "":
                    base_bnc_errs.append(abs(float(r["bounce_frame_error"])))
                if (
                    r["label_impact_type"] not in ("", "none", "None")
                    and r["sys_impact_present"] == "True"
                    and r["impact_frame_error"] != ""
                ):
                    base_imp_errs.append(abs(float(r["impact_frame_error"])))

    gap_results: Dict[str, List[Dict[str, Any]]] = {"bounce": [], "impact": []}
    for kind in ("bounce", "impact"):
        for k in GAP_K_VALUES:
            errs: List[float] = []
            missed = 0
            total = 0
            for cid in sorted(clip_ids):
                lbl, ball_bf, fps, corners = raw_cache[cid]
                if kind == "bounce":
                    ev = lbl.get("bounce") or {}
                    if ev.get("frame") is None:
                        continue
                    total += 1
                    drop = deleted_window_frames(int(ev["frame"]), k)
                    sub_ball = filter_ball_by_frame(ball_bf, drop)
                    out = analyse_track(sub_ball, fps, corners, batter_hand=lbl.get("batter_hand"))
                    pred = out["events"].get("bounce")
                    if pred is None:
                        missed += 1
                    else:
                        errs.append(abs(float(pred["subframe"]) - float(ev["frame"])))
                else:
                    ev = lbl.get("impact") or {}
                    if ev.get("frame") is None or str(ev.get("type") or "none").lower() == "none":
                        continue
                    total += 1
                    drop = deleted_window_frames(int(ev["frame"]), k)
                    sub_ball = filter_ball_by_frame(ball_bf, drop)
                    out = analyse_track(sub_ball, fps, corners, batter_hand=lbl.get("batter_hand"))
                    pred = out["events"].get("impact")
                    if pred is None:
                        missed += 1
                    else:
                        errs.append(abs(float(pred["subframe"]) - float(ev["frame"])))
            med, p90 = _median_p90(errs)
            gap_results[kind].append(
                {
                    "k": k,
                    "n": total,
                    "found": total - missed,
                    "missed": missed,
                    "med_err_f": med,
                    "p90_err_f": p90,
                }
            )

    # Collect comparison summaries
    track_all = _summarize_per_clip_csv(csv_p, clip_ids)
    track_red = _summarize_per_clip_csv(csv_p, clip_ids, "red")
    track_pink = _summarize_per_clip_csv(csv_p, clip_ids, "pink")

    lbw_all = _summarize_per_clip_csv(base_csv, clip_ids)
    lbw_red = _summarize_per_clip_csv(base_csv, clip_ids, "red")
    lbw_pink = _summarize_per_clip_csv(base_csv, clip_ids, "pink")

    p1_red_csv = rep_dir / "phase1_red_38_per_clip.csv"
    p2_pink_csv = rep_dir / "phase2_pink_17_per_clip.csv"
    p1_red = _summarize_per_clip_csv(p1_red_csv, clip_ids, "red") if p1_red_csv.is_file() else None
    p2_pink = _summarize_per_clip_csv(p2_pink_csv, clip_ids, "pink") if p2_pink_csv.is_file() else None

    base_bnc_med, base_bnc_p90 = _median_p90(base_bnc_errs)
    base_imp_med, base_imp_p90 = _median_p90(base_imp_errs)

    analysis_md = ana_dir / f"{out_run}_eval.md"
    lines = [
        f"# Track Engine Offline Evaluation (`{out_run}` vs `{base_run}`)",
        "",
        f"- Clips evaluated: `{len(clip_ids)}` (`red`: `{track_red.get('n', 0)}`, `pink`: `{track_pink.get('n', 0)}`)",
        f"- Score report: `{md_p}`",
        "",
        "## Comparison (`track_1` vs `lbw_ui_3`)",
        "",
        "| Run / Slice | Rel Found / ±1f | Bnc Found / ±1f / Ctr(m) | Imp Found / ±1f | False Imp (none) |",
        "| --- | --- | --- | --- | --- |",
        f"| `track_1` ALL | {track_all.get('rel_found')} / {track_all.get('rel_1f')} | {track_all.get('bnc_found')} / {track_all.get('bnc_1f')} / {track_all.get('bnc_ctr_med_m')}m | {track_all.get('imp_found')} / {track_all.get('imp_1f')} | {track_all.get('false_imp')} |",
        f"| `lbw_ui_3` ALL | {lbw_all.get('rel_found')} / {lbw_all.get('rel_1f')} | {lbw_all.get('bnc_found')} / {lbw_all.get('bnc_1f')} / {lbw_all.get('bnc_ctr_med_m')}m | {lbw_all.get('imp_found')} / {lbw_all.get('imp_1f')} | {lbw_all.get('false_imp')} |",
        f"| `track_1` red | {track_red.get('rel_found')} / {track_red.get('rel_1f')} | {track_red.get('bnc_found')} / {track_red.get('bnc_1f')} / {track_red.get('bnc_ctr_med_m')}m | {track_red.get('imp_found')} / {track_red.get('imp_1f')} | {track_red.get('false_imp')} |",
        f"| `lbw_ui_3` red | {lbw_red.get('rel_found')} / {lbw_red.get('rel_1f')} | {lbw_red.get('bnc_found')} / {lbw_red.get('bnc_1f')} / {lbw_red.get('bnc_ctr_med_m')}m | {lbw_red.get('imp_found')} / {lbw_red.get('imp_1f')} | {lbw_red.get('false_imp')} |",
        f"| `track_1` pink | {track_pink.get('rel_found')} / {track_pink.get('rel_1f')} | {track_pink.get('bnc_found')} / {track_pink.get('bnc_1f')} / {track_pink.get('bnc_ctr_med_m')}m | {track_pink.get('imp_found')} / {track_pink.get('imp_1f')} | {track_pink.get('false_imp')} |",
        f"| `lbw_ui_3` pink | {lbw_pink.get('rel_found')} / {lbw_pink.get('rel_1f')} | {lbw_pink.get('bnc_found')} / {lbw_pink.get('bnc_1f')} / {lbw_pink.get('bnc_ctr_med_m')}m | {lbw_pink.get('imp_found')} / {lbw_pink.get('imp_1f')} | {lbw_pink.get('false_imp')} |",
    ]
    if p1_red:
        lines.append(
            f"| `phase1_red_38` red | {p1_red.get('rel_found')} / {p1_red.get('rel_1f')} | {p1_red.get('bnc_found')} / {p1_red.get('bnc_1f')} / {p1_red.get('bnc_ctr_med_m')}m | {p1_red.get('imp_found')} / {p1_red.get('imp_1f')} | {p1_red.get('false_imp')} |"
        )
    if p2_pink:
        lines.append(
            f"| `phase2_pink_17` pink | {p2_pink.get('rel_found')} / {p2_pink.get('rel_1f')} | {p2_pink.get('bnc_found')} / {p2_pink.get('bnc_1f')} / {p2_pink.get('bnc_ctr_med_m')}m | {p2_pink.get('imp_found')} / {p2_pink.get('imp_1f')} | {p2_pink.get('false_imp')} |"
        )

    lines += [
        "",
        "## Gap Robustness Test",
        "",
        "| Event | Setting / k | Found / n | Med |err| (f) | p90 |err| (f) |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    if base_bnc_med is not None:
        lines.append(f"| bounce | `lbw_ui_3` (k=0) | {len(base_bnc_errs)}/{len(clip_ids)} | {base_bnc_med:.2f} | {base_bnc_p90:.2f} |")
    for row in gap_results["bounce"]:
        med_s = f"{row['med_err_f']:.2f}" if row["med_err_f"] is not None else "—"
        p90_s = f"{row['p90_err_f']:.2f}" if row["p90_err_f"] is not None else "—"
        lines.append(f"| bounce | engine k={row['k']} | {row['found']}/{row['n']} | {med_s} | {p90_s} |")
    if base_imp_med is not None:
        lines.append(f"| impact | `lbw_ui_3` (k=0) | {len(base_imp_errs)}/{gap_results['impact'][0]['n']} | {base_imp_med:.2f} | {base_imp_p90:.2f} |")
    for row in gap_results["impact"]:
        med_s = f"{row['med_err_f']:.2f}" if row["med_err_f"] is not None else "—"
        p90_s = f"{row['p90_err_f']:.2f}" if row["p90_err_f"] is not None else "—"
        lines.append(f"| impact | engine k={row['k']} | {row['found']}/{row['n']} | {med_s} | {p90_s} |")

    analysis_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "n_clips": len(clip_ids),
        "track_all": track_all,
        "track_red": track_red,
        "track_pink": track_pink,
        "lbw_all": lbw_all,
        "lbw_red": lbw_red,
        "lbw_pink": lbw_pink,
        "gap": gap_results,
        "base_bnc_med_p90": (base_bnc_med, base_bnc_p90),
        "base_imp_med_p90": (base_imp_med, base_imp_p90),
        "analysis_md": str(analysis_md),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate track_engine offline.")
    parser.add_argument("--dump-run", default=DEFAULT_DUMP_RUN)
    parser.add_argument("--out-run", default=DEFAULT_OUT_RUN)
    parser.add_argument("--base-run", default=DEFAULT_BASE_RUN)
    args = parser.parse_args(argv)
    summary = run_offline_evaluation(
        dump_run=args.dump_run, out_run=args.out_run, base_run=args.base_run
    )
    print(Path(summary["analysis_md"]).read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
