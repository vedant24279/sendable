"""Offline global ball-tracking and piecewise curve-fit event engine.

Pure numpy/math implementation (no environment variables, no ``tools/`` imports).
Entry point: :func:`analyse_track`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from .lbw_line import fit_ground_homography, pixel_to_ground

# ── Constants ───────────────────────────────────────────────────────────────
MAX_GAP_FRAMES: int = 12
MIN_CHAIN_LEN: int = 4
MIN_CHAIN_SPAN_W: float = 0.01
DUP_DIST_PX: float = 0.5

MISS_PENALTY: float = 2.5
MAX_STEP_W_PER_FRAME: float = 0.16
BASE_TOL_W: float = 0.030
GAP_TOL_W_PER_FRAME: float = 0.018
HUBER_TRANS_SCALE: float = 1.0

RELEASE_STEP_MIN_FRAC: float = 0.40

HUBER_IRLS_DELTA_PX: float = 2.5
HUBER_IRLS_ITERS: int = 8
BIC_SIGMA_PX: float = 2.0
H_C_MIN_BIC_MARGIN: float = 6.0
KINK_NOISE_MULT: float = 3.0
MIN_S1_FRAMES: int = 6
MIN_POST_BOUNCE_FRAMES: int = 3
MAX_CONTACT_AFTER_BOUNCE_FRAMES: float = 12.0
BATTER_MAX_ABS_X_M: float = 0.6
BATTER_MAX_Z_M: float = 3.0
PITCH_MAX_ABS_X_M: float = 1.65
PITCH_MIN_Z_M: float = -0.5
PITCH_MAX_Z_M: float = 21.0
GRID_STEP_FRAME: float = 0.25
INTERSECT_HALF_WIN_FRAMES: float = 3.0
INTERSECT_FINE_STEP: float = 0.05
BOOTSTRAP_RESAMPLES: int = 50
BOOTSTRAP_SEED: int = 20261120


@dataclass(frozen=True)
class _Cand:
    frame: int
    x: float
    y: float
    conf: float


# ── Helpers & Geometry ──────────────────────────────────────────────────────
def _parse_candidates(
    ball_by_frame: Mapping[Any, Sequence[Mapping[str, Any]]],
) -> Tuple[List[int], Dict[int, List[_Cand]]]:
    parsed: Dict[int, List[_Cand]] = {}
    for k, raw_list in ball_by_frame.items():
        try:
            f = int(k)
        except (TypeError, ValueError):
            continue
        cands: List[_Cand] = []
        for d in raw_list or ():
            cls_name = d.get("class_name")
            if cls_name is not None and str(cls_name).lower() != "ball":
                continue
            if "cx" in d and "cy" in d:
                cx, cy = float(d["cx"]), float(d["cy"])
            elif all(key in d for key in ("x1", "y1", "x2", "y2")):
                cx = 0.5 * (float(d["x1"]) + float(d["x2"]))
                cy = 0.5 * (float(d["y1"]) + float(d["y2"]))
            elif "x" in d and "y" in d:
                cx, cy = float(d["x"]), float(d["y"])
            else:
                continue
            conf = float(d.get("conf", 0.5))
            cands.append(_Cand(frame=f, x=cx, y=cy, conf=max(1e-3, min(1.0, conf))))
        if cands:
            parsed[f] = cands
    frames = sorted(parsed.keys())
    return frames, parsed


def _huber_cost(u: float, delta: float = HUBER_TRANS_SCALE) -> float:
    au = abs(u)
    if au <= delta:
        return 0.5 * au * au
    return delta * (au - 0.5 * delta)


def _chain_span_px(chain: Sequence[_Cand]) -> float:
    if len(chain) < 2:
        return 0.0
    xs = [c.x for c in chain]
    ys = [c.y for c in chain]
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))


# ── Step 1: Global Viterbi Tracking ─────────────────────────────────────────
def _run_viterbi_chain(
    frames: Sequence[int],
    cands_by_frame: Mapping[int, Sequence[_Cand]],
    W: float,
    excluded: set[Tuple[int, int]],
) -> Optional[List[Tuple[int, int, _Cand]]]:
    """Extract highest-scoring chain over active nodes via 2nd-order-velocity DP."""
    nodes: List[Tuple[int, int, _Cand]] = []
    for f in frames:
        for ci, cand in enumerate(cands_by_frame[f]):
            if (f, ci) not in excluded:
                nodes.append((f, ci, cand))
    if not nodes:
        return None

    n = len(nodes)
    # dp[i] = min cost ending at node i; prev[i] = predecessor node index (-1 if start)
    dp = [0.0] * n
    prev = [-1] * n
    # Initialize each node as potential chain start (reward -MISS_PENALTY per detection)
    for i, (_, _, c) in enumerate(nodes):
        dp[i] = -math.log(c.conf) - MISS_PENALTY

    # Index nodes by frame for fast lookback within MAX_GAP_FRAMES
    by_frame: Dict[int, List[int]] = {}
    for idx, (f, _, _) in enumerate(nodes):
        by_frame.setdefault(f, []).append(idx)
    active_frames = sorted(by_frame.keys())

    for fi_pos, f_cur in enumerate(active_frames):
        cur_indices = by_frame[f_cur]
        # Look back over active frames within [f_cur - MAX_GAP_FRAMES, f_cur - 1]
        for fj_pos in range(fi_pos - 1, -1, -1):
            f_prev = active_frames[fj_pos]
            dt = f_cur - f_prev
            if dt > MAX_GAP_FRAMES:
                break
            tol_w = BASE_TOL_W + GAP_TOL_W_PER_FRAME * dt
            max_step_w = MAX_STEP_W_PER_FRAME * dt + BASE_TOL_W

            for p_idx in by_frame[f_prev]:
                _, _, c_prev = nodes[p_idx]
                pp_idx = prev[p_idx]
                if pp_idx >= 0:
                    _, _, c_pprev = nodes[pp_idx]
                    dt_prev = max(1, c_prev.frame - c_pprev.frame)
                    vx = (c_prev.x - c_pprev.x) / dt_prev
                    vy = (c_prev.y - c_pprev.y) / dt_prev
                    pred_x = c_prev.x + vx * dt
                    pred_y = c_prev.y + vy * dt
                else:
                    pred_x = c_prev.x
                    pred_y = c_prev.y

                for c_idx in cur_indices:
                    _, _, c_cur = nodes[c_idx]
                    step_w = math.hypot(c_cur.x - c_prev.x, c_cur.y - c_prev.y) / W
                    if step_w > max_step_w:
                        continue
                    err_w = math.hypot(c_cur.x - pred_x, c_cur.y - pred_y) / W
                    if pp_idx >= 0 and err_w > max_step_w:
                        continue
                    # Relative to MISS baseline, missed gap frames cost 0 (small 0.15/f density tie-break)
                    trans_cost = 0.15 * (dt - 1) + 2.0 * _huber_cost(err_w / tol_w)
                    emit_cost = -math.log(c_cur.conf) - MISS_PENALTY
                    cand_cost = dp[p_idx] + trans_cost + emit_cost
                    if cand_cost < dp[c_idx]:
                        dp[c_idx] = cand_cost
                        prev[c_idx] = p_idx

    best_end = min(range(n), key=lambda idx: dp[idx])
    rev: List[Tuple[int, int, _Cand]] = []
    cur = best_end
    while cur >= 0:
        rev.append(nodes[cur])
        cur = prev[cur]
    rev.reverse()
    return rev


def extract_best_track(
    ball_by_frame: Mapping[Any, Sequence[Mapping[str, Any]]],
    corners: Mapping[str, Sequence[float]],
) -> Tuple[List[_Cand], List[str]]:
    """Run iterative Viterbi extraction, dropping chains < 4 dets or static (< 0.01 W)."""
    frames, cands_by_frame = _parse_candidates(ball_by_frame)
    notes: List[str] = []
    if not frames:
        return [], ["no_ball_detections"]

    w_px = abs(float(corners["bowl_R"][0]) - float(corners["bowl_L"][0]))
    if w_px < 10.0:
        w_px = 450.0
        notes.append("fallback_norm_width")

    excluded: set[Tuple[int, int]] = set()
    valid_chains: List[Tuple[float, List[_Cand]]] = []

    for _ in range(12):
        res = _run_viterbi_chain(frames, cands_by_frame, w_px, excluded)
        if res is None:
            break
        for f, ci, _ in res:
            excluded.add((f, ci))
        chain = [item[2] for item in res]
        if len(chain) < MIN_CHAIN_LEN:
            notes.append(f"dropped_short_chain:{len(chain)}")
            continue
        if _chain_span_px(chain) < MIN_CHAIN_SPAN_W * w_px:
            notes.append(f"dropped_static_chain:{len(chain)}")
            continue
        # Score valid moving chain (lower cost is better; prefer longer + confident)
        score = sum(-math.log(c.conf) - MISS_PENALTY for c in chain)
        valid_chains.append((score, chain))
        # Also stop if remaining frames have fewer than MIN_CHAIN_LEN candidates
        rem = sum(
            1
            for f in frames
            for ci in range(len(cands_by_frame[f]))
            if (f, ci) not in excluded
        )
        if rem < MIN_CHAIN_LEN:
            break

    if not valid_chains:
        return [], notes + ["no_valid_moving_chain"]

    valid_chains.sort(key=lambda item: item[0])
    best_score, best_chain = valid_chains[0]
    # Prefer an earlier substantial delivery chain (>= 8 pts) if separated by > MAX_GAP_FRAMES
    # from a later post-hit / roll-back chain.
    earliest_substantial = [
        ch for _, ch in valid_chains
        if len(ch) >= 8 and ch[-1].frame + MAX_GAP_FRAMES < best_chain[0].frame
    ]
    if earliest_substantial:
        earliest_substantial.sort(key=lambda ch: ch[0].frame)
        return earliest_substantial[0], notes
    return best_chain, notes


# ── Effective Time Axis & Duplicate Collapsing ──────────────────────────────
@dataclass
class _Knot:
    eff_t: float
    orig_frame: float
    x: float
    y: float
    frames: List[int]


def _build_effective_time_axis(
    chain: Sequence[_Cand],
) -> Tuple[List[Dict[str, Any]], List[_Knot], int]:
    """Collapse consecutive detections within 0.5 px into one effective time step."""
    if not chain:
        return [], [], 0

    track_obs: List[Dict[str, Any]] = []
    knots: List[_Knot] = []
    dup_frames = 0
    cum_dups = 0

    group: List[Tuple[_Cand, float]] = []
    prev_c: Optional[_Cand] = None

    for c in chain:
        if prev_c is not None and math.hypot(c.x - prev_c.x, c.y - prev_c.y) <= DUP_DIST_PX:
            dup_frames += 1
            cum_dups += 1
            eff_t = float(c.frame - cum_dups)
            # Ensure collapsed duplicate shares the exact same eff_t as predecessor
            if group:
                eff_t = group[-1][1]
            group.append((c, eff_t))
        else:
            if group:
                eff0 = group[0][1]
                knots.append(
                    _Knot(
                        eff_t=eff0,
                        orig_frame=float(np.mean([g[0].frame for g in group])),
                        x=float(np.mean([g[0].x for g in group])),
                        y=float(np.mean([g[0].y for g in group])),
                        frames=[g[0].frame for g in group],
                    )
                )
            eff_t = float(c.frame - cum_dups)
            group = [(c, eff_t)]

        track_obs.append(
            {
                "frame": int(c.frame),
                "eff_t": float(eff_t),
                "x": float(c.x),
                "y": float(c.y),
                "conf": round(float(c.conf), 4),
                "interpolated": False,
            }
        )
        prev_c = c

    if group:
        eff0 = group[0][1]
        knots.append(
            _Knot(
                eff_t=eff0,
                orig_frame=float(np.mean([g[0].frame for g in group])),
                x=float(np.mean([g[0].x for g in group])),
                y=float(np.mean([g[0].y for g in group])),
                frames=[g[0].frame for g in group],
            )
        )

    return track_obs, knots, dup_frames


def _eff_to_orig_frame(knots: Sequence[_Knot], t_eff: float) -> float:
    if not knots:
        return float(t_eff)
    if len(knots) == 1:
        return float(knots[0].orig_frame + (t_eff - knots[0].eff_t))
    effs = [k.eff_t for k in knots]
    origs = [float(k.frames[0]) for k in knots]
    if t_eff <= effs[0]:
        return origs[0] + (t_eff - effs[0])
    if t_eff >= effs[-1]:
        return origs[-1] + (t_eff - effs[-1])
    return float(np.interp(t_eff, effs, origs))


def _orig_to_eff_frame(knots: Sequence[_Knot], f_orig: float) -> float:
    if not knots:
        return float(f_orig)
    effs = [k.eff_t for k in knots]
    origs = [float(k.frames[0]) for k in knots]
    if f_orig <= origs[0]:
        return effs[0] + (f_orig - origs[0])
    if f_orig >= origs[-1]:
        return effs[-1] + (f_orig - origs[-1])
    return float(np.interp(f_orig, origs, effs))


# ── Step 4: Release Pruning ─────────────────────────────────────────────────
def _find_release_knot_idx(knots: Sequence[_Knot]) -> int:
    """Move forward from index 0 to the first point of the longest fast flight streak in S1."""
    n = len(knots)
    if n < 3:
        return 0

    all_steps: List[float] = []
    for i in range(n - 1):
        dt = max(1e-6, knots[i + 1].eff_t - knots[i].eff_t)
        all_steps.append(math.hypot(knots[i + 1].x - knots[i].x, knots[i + 1].y - knots[i].y) / dt)

    # Locate the first pre-bounce downward peak in y (skipping initial upward loop/arm-swing)
    s1_end = min(n - 1, 20)
    # Find min-y apex in first half if ball loops upward first, then peak after apex
    apex_i = min(range(min(n, 14)), key=lambda i: knots[i].y)
    start_search = max(3, apex_i + 2)
    for i in range(start_search, min(n - 1, 32)):
        if knots[i].y >= knots[i - 1].y and knots[i].y > knots[i + 1].y:
            s1_end = i
            break

    s1_steps = all_steps[: max(3, min(s1_end, 12))]
    if not s1_steps:
        return 0
    med_step = float(np.median(s1_steps))
    thresh = RELEASE_STEP_MIN_FRAC * med_step

    # Only prune leading slow arm-swing points before the first fast flight streak (>= 3 steps).
    # Never jump past an already-started flight streak due to a single mid-S1 telecine step.
    if len(all_steps) >= 3 and all(sp >= thresh for sp in all_steps[:3]):
        return 0

    max_prune = max(1, s1_end // 2)
    cur_start: Optional[int] = None
    cur_len = 0
    for i, sp in enumerate(all_steps[: max(3, s1_end)]):
        if sp >= thresh:
            if cur_start is None:
                cur_start = i
                cur_len = 1
            else:
                cur_len += 1
            if cur_len >= 3 and cur_start <= max_prune:
                return cur_start
        else:
            cur_start = None
            cur_len = 0

    return 0


# ── Step 2: Fast Huber IRLS Polynomial Fits & Model Selection ───────────────
@dataclass(frozen=True)
class _PolyFit1D:
    t_ref: float
    coeffs: np.ndarray  # low-to-high powers: c0 + c1*dt + c2*dt^2
    degree: int

    def eval(self, t: float | np.ndarray) -> float | np.ndarray:
        dt = t - self.t_ref
        out = self.coeffs[0]
        if self.degree >= 1:
            out = out + self.coeffs[1] * dt
        if self.degree >= 2:
            out = out + self.coeffs[2] * (dt * dt)
        return out

    def deriv(self, t: float) -> float:
        dt = t - self.t_ref
        d = float(self.coeffs[1]) if self.degree >= 1 else 0.0
        if self.degree >= 2:
            d += 2.0 * float(self.coeffs[2]) * dt
        return d


@dataclass(frozen=True)
class _SegFit2D:
    fx: _PolyFit1D
    fy: _PolyFit1D
    rx: np.ndarray
    ry: np.ndarray
    huber_sum: float
    rms_px: float
    n_pts: int
    n_params: int

    def eval_xy(self, t: float) -> Tuple[float, float]:
        return float(self.fx.eval(t)), float(self.fy.eval(t))

    def vel_xy(self, t: float) -> Tuple[float, float]:
        return self.fx.deriv(t), self.fy.deriv(t)


def _fit_poly_huber_irls(
    ts: np.ndarray,
    vs: np.ndarray,
    degree: int,
    *,
    delta: float = HUBER_IRLS_DELTA_PX,
    iters: int = HUBER_IRLS_ITERS,
) -> Optional[_PolyFit1D]:
    n = len(ts)
    if n < degree + 1 or len(np.unique(ts)) < degree + 1:
        return None
    t_ref = 0.5 * float(ts[0] + ts[-1])
    dt = ts - t_ref
    # Design matrix [1, dt, dt^2]
    if degree == 1:
        X = np.column_stack((np.ones(n, dtype=np.float64), dt))
    else:
        X = np.column_stack((np.ones(n, dtype=np.float64), dt, dt * dt))

    w = np.ones(n, dtype=np.float64)
    coeffs = np.zeros(degree + 1, dtype=np.float64)
    for _ in range(iters):
        sw = np.sqrt(w)
        Xw = X * sw[:, None]
        vw = vs * sw
        sol, _, _, _ = np.linalg.lstsq(Xw, vw, rcond=None)
        if not np.all(np.isfinite(sol)):
            return None
        coeffs = sol
        r = np.abs(X @ coeffs - vs)
        w = np.where(r <= delta, 1.0, delta / np.maximum(r, 1e-9))

    return _PolyFit1D(t_ref=t_ref, coeffs=coeffs, degree=degree)


def _huber_loss_sum(r: np.ndarray, delta: float = HUBER_IRLS_DELTA_PX) -> float:
    ar = np.abs(r)
    quad = ar <= delta
    return float(
        np.sum(np.where(quad, 0.5 * ar * ar, delta * (ar - 0.5 * delta)))
    )


def _fit_seg_cached(
    ts: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    i0: int,
    i1: int,  # exclusive
    deg_x: int,
    deg_y: int,
    cache: Dict[Tuple[int, int, int, int], Optional[_SegFit2D]],
) -> Optional[_SegFit2D]:
    key = (i0, i1, deg_x, deg_y)
    if key in cache:
        return cache[key]
    t_sub = ts[i0:i1]
    x_sub = xs[i0:i1]
    y_sub = ys[i0:i1]
    fx = _fit_poly_huber_irls(t_sub, x_sub, deg_x)
    fy = _fit_poly_huber_irls(t_sub, y_sub, deg_y)
    if fx is None or fy is None:
        cache[key] = None
        return None
    rx = np.asarray(fx.eval(t_sub), dtype=np.float64) - x_sub
    ry = np.asarray(fy.eval(t_sub), dtype=np.float64) - y_sub
    hsum = _huber_loss_sum(rx) + _huber_loss_sum(ry)
    n_pts = i1 - i0
    dof = max(1, 2 * n_pts - ((deg_x + 1) + (deg_y + 1)))
    rms_px = math.sqrt(float(np.sum(rx * rx + ry * ry)) / dof)
    fit = _SegFit2D(
        fx=fx,
        fy=fy,
        rx=rx,
        ry=ry,
        huber_sum=hsum,
        rms_px=rms_px,
        n_pts=n_pts,
        n_params=(deg_x + 1) + (deg_y + 1),
    )
    cache[key] = fit
    return fit


def _fit_best_s1(
    ts: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    i0: int,
    i1: int,
    n_total: int,
    cache: Dict[Tuple[int, int, int, int], Optional[_SegFit2D]],
) -> Optional[_SegFit2D]:
    """S1: x linear or quadratic (BIC selected), y quadratic."""
    n_seg = i1 - i0
    if n_seg < 3:
        return None
    f_lin = _fit_seg_cached(ts, xs, ys, i0, i1, 1, 2, cache)
    f_quad = _fit_seg_cached(ts, xs, ys, i0, i1, 2, 2, cache) if n_seg >= 4 else None
    if f_lin is None:
        return f_quad
    if f_quad is None:
        return f_lin
    pen = math.log(max(4, 2 * n_total))
    bic_lin = 2.0 * f_lin.huber_sum / (BIC_SIGMA_PX ** 2) + f_lin.n_params * pen
    bic_quad = 2.0 * f_quad.huber_sum / (BIC_SIGMA_PX ** 2) + f_quad.n_params * pen
    return f_quad if bic_quad < bic_lin else f_lin


def _fit_best_s2(
    ts: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    i0: int,
    i1: int,
    n_total: int,
    cache: Dict[Tuple[int, int, int, int], Optional[_SegFit2D]],
) -> Optional[_SegFit2D]:
    """S2: x linear, y linear (or quadratic if >= 6 points and BIC improves)."""
    n_seg = i1 - i0
    if n_seg < 2:
        return None
    f_lin = _fit_seg_cached(ts, xs, ys, i0, i1, 1, 1, cache)
    f_quad = _fit_seg_cached(ts, xs, ys, i0, i1, 1, 2, cache) if n_seg >= 6 else None
    if f_lin is None:
        return f_quad
    if f_quad is None:
        return f_lin
    pen = math.log(max(4, 2 * n_total))
    bic_lin = 2.0 * f_lin.huber_sum / (BIC_SIGMA_PX ** 2) + f_lin.n_params * pen
    bic_quad = 2.0 * f_quad.huber_sum / (BIC_SIGMA_PX ** 2) + f_quad.n_params * pen
    return f_quad if bic_quad < bic_lin else f_lin


def _find_closest_approach(
    seg_a: _SegFit2D,
    seg_b: _SegFit2D,
    t_center: float,
    *,
    half_win: float = INTERSECT_HALF_WIN_FRAMES,
    step: float = INTERSECT_FINE_STEP,
) -> Tuple[float, float, float, float]:
    n_steps = max(2, int(round((2.0 * half_win) / step)))
    ts = np.linspace(t_center - half_win, t_center + half_win, n_steps + 1)
    ax = np.asarray(seg_a.fx.eval(ts), dtype=np.float64)
    ay = np.asarray(seg_a.fy.eval(ts), dtype=np.float64)
    bx = np.asarray(seg_b.fx.eval(ts), dtype=np.float64)
    by = np.asarray(seg_b.fy.eval(ts), dtype=np.float64)
    dists = np.hypot(ax - bx, ay - by)
    idx = int(np.argmin(dists))
    return (
        float(ts[idx]),
        0.5 * float(ax[idx] + bx[idx]),
        0.5 * float(ay[idx] + by[idx]),
        float(dists[idx]),
    )


def _is_on_pitch(H: np.ndarray, x: float, y: float) -> Tuple[bool, Optional[float], Optional[float]]:
    try:
        wx, wz = pixel_to_ground(H, x, y)
    except ValueError:
        return False, None, None
    ok = (abs(wx) <= PITCH_MAX_ABS_X_M) and (PITCH_MIN_Z_M <= wz <= PITCH_MAX_Z_M)
    return ok, float(wx), float(wz)


def _is_in_batter_region(H: np.ndarray, x: float, y: float) -> Tuple[bool, Optional[float], Optional[float]]:
    try:
        wx, wz = pixel_to_ground(H, x, y)
    except ValueError:
        return False, None, None
    ok = (abs(wx) < BATTER_MAX_ABS_X_M) and (wz < BATTER_MAX_Z_M)
    return ok, float(wx), float(wz)


def _kink_metrics(
    seg2: _SegFit2D,
    seg3: _SegFit2D,
    t_c: float,
    ts_seg2: np.ndarray,
    ts_seg3: np.ndarray,
) -> Tuple[float, float, float, float]:
    """Compute (angle_deg, speed_ratio, combined_noise_px, kink_snr) at contact t_c."""
    vx2, vy2 = seg2.vel_xy(t_c)
    vx3, vy3 = seg3.vel_xy(t_c)
    sp2 = math.hypot(vx2, vy2)
    sp3 = math.hypot(vx3, vy3)
    if sp2 < 1e-6 or sp3 < 1e-6:
        return 0.0, 1.0, 999.0, 0.0
    cos_a = max(-1.0, min(1.0, (vx2 * vx3 + vy2 * vy3) / (sp2 * sp3)))
    angle_deg = math.degrees(math.acos(cos_a))
    speed_ratio = sp3 / sp2

    # Combined fit noise and perpendicular direction-change deflection at S3 endpoint
    noise2 = max(seg2.rms_px, 1.0)
    noise3 = max(seg3.rms_px, 1.0)
    comb_noise_px = math.hypot(noise2, noise3)

    # Perpendicular deviation of S3 from S2's tangent direction at t_c (filters longitudinal slowdown)
    t_end3 = float(ts_seg3[-1])
    dt_out = max(1.0, t_end3 - t_c)
    perp_deflection_px = abs(vx2 * vy3 - vy2 * vx3) / sp2 * dt_out
    kink_snr = perp_deflection_px / comb_noise_px
    return angle_deg, speed_ratio, comb_noise_px, kink_snr


# ── Step 3: Bootstrap Uncertainty & Observed Neighbors ──────────────────────
def _bootstrap_sigma_frames(
    ts: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    knots: Sequence[_Knot],
    rel_idx: int,
    split_b: int,
    split_c: Optional[int],
    end_c: Optional[int],
    s1_deg_x: int,
    s2_deg_y: int,
    t_b_center: float,
    t_c_center: Optional[float],
) -> Tuple[Optional[float], Optional[float]]:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    tb_samples: List[float] = []
    tc_samples: List[float] = []

    n = len(ts)
    end_s2 = split_c if split_c is not None else n
    end_s3 = end_c if end_c is not None else n
    t1, x1, y1 = ts[rel_idx:split_b], xs[rel_idx:split_b], ys[rel_idx:split_b]
    t2, x2, y2 = ts[split_b:end_s2], xs[split_b:end_s2], ys[split_b:end_s2]
    t3, x3, y3 = (
        (ts[end_s2:end_s3], xs[end_s2:end_s3], ys[end_s2:end_s3])
        if split_c is not None
        else (np.empty(0), np.empty(0), np.empty(0))
    )

    if len(t1) < s1_deg_x + 1 or len(t2) < s2_deg_y + 1:
        return None, None

    for _ in range(BOOTSTRAP_RESAMPLES):
        idx1 = np.sort(rng.integers(0, len(t1), size=len(t1)))
        idx2 = np.sort(rng.integers(0, len(t2), size=len(t2)))
        fx1 = _fit_poly_huber_irls(t1[idx1], x1[idx1], s1_deg_x)
        fy1 = _fit_poly_huber_irls(t1[idx1], y1[idx1], 2)
        fx2 = _fit_poly_huber_irls(t2[idx2], x2[idx2], 1)
        fy2 = _fit_poly_huber_irls(t2[idx2], y2[idx2], s2_deg_y)
        if fx1 is None or fy1 is None or fx2 is None or fy2 is None:
            continue
        seg1 = _SegFit2D(fx1, fy1, np.empty(0), np.empty(0), 0.0, 1.0, len(t1), 0)
        seg2 = _SegFit2D(fx2, fy2, np.empty(0), np.empty(0), 0.0, 1.0, len(t2), 0)
        tb_b, _, _, _ = _find_closest_approach(seg1, seg2, t_b_center, step=0.1)
        tb_samples.append(_eff_to_orig_frame(knots, tb_b))

        if split_c is not None and t_c_center is not None and len(t3) >= 2:
            idx3 = np.sort(rng.integers(0, len(t3), size=len(t3)))
            fx3 = _fit_poly_huber_irls(t3[idx3], x3[idx3], 1)
            fy3 = _fit_poly_huber_irls(t3[idx3], y3[idx3], 1)
            if fx3 is not None and fy3 is not None:
                seg3 = _SegFit2D(fx3, fy3, np.empty(0), np.empty(0), 0.0, 1.0, len(t3), 0)
                tc_b, _, _, _ = _find_closest_approach(seg2, seg3, t_c_center, step=0.1)
                tc_samples.append(_eff_to_orig_frame(knots, tc_b))

    sig_b = round(float(np.std(tb_samples)), 4) if len(tb_samples) >= 5 else None
    sig_c = round(float(np.std(tc_samples)), 4) if len(tc_samples) >= 5 else None
    return sig_b, sig_c


def _observed_neighbors(track_frames: Sequence[int], frame_float: float) -> List[int]:
    f_round = int(round(frame_float))
    return [f for f in track_frames if abs(f - f_round) <= 1]


# ── Public Entry Point ──────────────────────────────────────────────────────
def analyse_track(
    ball_by_frame: Mapping[Any, Sequence[Mapping[str, Any]]],
    fps: float,
    corners: Mapping[str, Sequence[float]],
    batter_hand: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyse raw ball candidates and return events, evidence, track, bridge, and notes."""
    del batter_hand  # reserved for caller symmetry; event geometry is hand-agnostic
    fps_val = float(fps) if fps and float(fps) > 0 else 30.0
    H, _ = fit_ground_homography(corners)

    chain, v_notes = extract_best_track(ball_by_frame, corners)
    if not chain:
        return {
            "events": {"release": None, "bounce": None, "impact": None},
            "evidence": {"hypothesis": None, "dup_frames": 0},
            "observed": {
                "dup_frames": 0,
                "n_raw_frames": len(ball_by_frame),
                "n_track_points": 0,
                "n_missing_in_span": 0,
                "recall_in_span": 0.0,
            },
            "track": [],
            "bridge": [],
            "notes": v_notes,
        }

    track_obs, knots, dup_frames = _build_effective_time_axis(chain)
    notes = list(v_notes)
    if dup_frames > 0:
        notes.append(f"dup_frames={dup_frames}")

    rel_knot_idx = _find_release_knot_idx(knots)
    if rel_knot_idx > 0:
        notes.append(f"release_pruned_knots={rel_knot_idx}")

    ts = np.array([k.eff_t for k in knots], dtype=np.float64)
    xs = np.array([k.x for k in knots], dtype=np.float64)
    ys = np.array([k.y for k in knots], dtype=np.float64)
    n_knots = len(knots)
    n_fit = n_knots - rel_knot_idx

    track_frames = [int(pt["frame"]) for pt in track_obs]
    rel_knot = knots[rel_knot_idx]
    rel_orig_f = float(rel_knot.frames[0])
    rel_obs_nb = _observed_neighbors(track_frames, rel_orig_f)

    rel_event: Dict[str, Any] = {
        "frame": int(rel_knot.frames[0]),
        "subframe": round(rel_orig_f, 3),
        "timestamp_sec": round(rel_orig_f / fps_val, 4),
        "x": round(rel_knot.x, 2),
        "y": round(rel_knot.y, 2),
        "observed_neighbors": rel_obs_nb,
        "sigma_frames": None,
    }

    cache: Dict[Tuple[int, int, int, int], Optional[_SegFit2D]] = {}
    pen = math.log(max(4, 2 * max(n_fit, 2)))

    # ── H_a: No bounce (single smooth segment from release to end) ──
    s1_only = _fit_best_s1(ts, xs, ys, rel_knot_idx, n_knots, n_fit, cache)
    bic_a = (
        2.0 * s1_only.huber_sum / (BIC_SIGMA_PX ** 2) + s1_only.n_params * pen
        if s1_only is not None
        else float("inf")
    )

    # ── H_b: Bounce only (no contact) ──
    best_b: Optional[Dict[str, Any]] = None
    t_rel_eff = float(ts[rel_knot_idx])
    t_last_eff = float(ts[-1])
    b_lo_orig = rel_orig_f + MIN_S1_FRAMES
    b_hi_orig = float(knots[-1].frames[-1]) - MIN_POST_BOUNCE_FRAMES
    b_lo = max(t_rel_eff + 1.0, _orig_to_eff_frame(knots, b_lo_orig))
    b_hi = min(t_last_eff - 1.0, _orig_to_eff_frame(knots, b_hi_orig))

    if b_hi >= b_lo:
        grid_b = np.arange(b_lo, b_hi + 1e-6, GRID_STEP_FRAME)
        seen_splits_b: set[int] = set()
        for tb_grid in grid_b:
            split_b = int(np.searchsorted(ts, tb_grid, side="left"))
            split_b = max(rel_knot_idx + 3, min(n_knots - 2, split_b))
            if split_b in seen_splits_b:
                continue
            seen_splits_b.add(split_b)
            s1 = _fit_best_s1(ts, xs, ys, rel_knot_idx, split_b, n_fit, cache)
            s2 = _fit_best_s2(ts, xs, ys, split_b, n_knots, n_fit, cache)
            if s1 is None or s2 is None:
                continue
            tb_est, xb_est, yb_est, gap_b = _find_closest_approach(s1, s2, float(ts[split_b]))
            tb_orig = _eff_to_orig_frame(knots, tb_est)
            if not (b_lo_orig - 0.5 <= tb_orig <= b_hi_orig + 0.5):
                continue
            _, vy1 = s1.vel_xy(tb_est)
            _, vy2 = s2.vel_xy(tb_est)
            if not (vy1 > 0.0 and vy2 < 0.0):
                continue
            on_pitch, b_wx, b_wz = _is_on_pitch(H, xb_est, yb_est)
            if not on_pitch:
                continue
            bic_b = (
                2.0 * (s1.huber_sum + s2.huber_sum) / (BIC_SIGMA_PX ** 2)
                + (s1.n_params + s2.n_params + 1) * pen
                + 0.5 * (gap_b / BIC_SIGMA_PX) ** 2
            )
            if best_b is None or bic_b < best_b["bic"]:
                best_b = {
                    "bic": bic_b,
                    "split_b": split_b,
                    "s1": s1,
                    "s2": s2,
                    "tb_eff": tb_est,
                    "tb_orig": tb_orig,
                    "xb": xb_est,
                    "yb": yb_est,
                    "wx": b_wx,
                    "wz": b_wz,
                    "gap_px": gap_b,
                }

    # ── H_c: Bounce + Contact ──
    best_c: Optional[Dict[str, Any]] = None
    best_c_cand_rejected: Optional[Dict[str, Any]] = None

    if b_hi >= b_lo:
        grid_b = np.arange(b_lo, b_hi + 1e-6, GRID_STEP_FRAME)
        seen_splits_bc: set[Tuple[int, int]] = set()
        # Evaluate split_b partitions, then grid_c on 0.25-frame grid inside [t_b, t_b+12]
        unique_splits_b = sorted(
            {
                max(rel_knot_idx + 3, min(n_knots - 4, int(np.searchsorted(ts, tb_g, side="left"))))
                for tb_g in grid_b
            }
        )
        for split_b in unique_splits_b:
            s1 = _fit_best_s1(ts, xs, ys, rel_knot_idx, split_b, n_fit, cache)
            if s1 is None:
                continue
            tb_seed = float(ts[split_b])
            c_lo_eff = _orig_to_eff_frame(knots, _eff_to_orig_frame(knots, tb_seed) + 1.0)
            c_hi_eff = _orig_to_eff_frame(
                knots, _eff_to_orig_frame(knots, tb_seed) + MAX_CONTACT_AFTER_BOUNCE_FRAMES
            )
            c_lo_eff = max(float(ts[split_b + 1]), c_lo_eff)
            c_hi_eff = min(float(ts[-2]), c_hi_eff)
            if c_hi_eff < c_lo_eff:
                continue
            grid_c = np.arange(c_lo_eff, c_hi_eff + 1e-6, GRID_STEP_FRAME)
            for tc_grid in grid_c:
                split_c = int(np.searchsorted(ts, tc_grid, side="left"))
                split_c = max(split_b + 2, min(n_knots - 2, split_c))
                if (split_b, split_c) in seen_splits_bc:
                    continue
                seen_splits_bc.add((split_b, split_c))
                # Evaluate outgoing linear S3 on [split_c .. end_c] (up to 8 post-contact points)
                # against H_b on the exact same [rel_knot_idx .. end_c] horizon.
                end_c = min(n_knots, split_c + 8)
                n_local = end_c - rel_knot_idx
                pen_local = math.log(max(4, 2 * n_local))
                s2 = _fit_best_s2(ts, xs, ys, split_b, split_c, n_local, cache)
                s3 = _fit_seg_cached(ts, xs, ys, split_c, end_c, 1, 1, cache)
                s2_hb_local = _fit_best_s2(ts, xs, ys, split_b, end_c, n_local, cache)
                if s2 is None or s3 is None or s2_hb_local is None:
                    continue

                tb_est, xb_est, yb_est, gap_b = _find_closest_approach(s1, s2, float(ts[split_b]))
                tb_orig = _eff_to_orig_frame(knots, tb_est)
                if not (b_lo_orig - 0.5 <= tb_orig <= b_hi_orig + 0.5):
                    continue
                _, vy1 = s1.vel_xy(tb_est)
                _, vy2 = s2.vel_xy(tb_est)
                if not (vy1 > 0.0 and vy2 < 0.0):
                    continue
                on_pitch, b_wx, b_wz = _is_on_pitch(H, xb_est, yb_est)
                if not on_pitch:
                    continue

                tc_est, xc_est, yc_est, gap_c = _find_closest_approach(s2, s3, float(ts[split_c]))
                tc_orig = _eff_to_orig_frame(knots, tc_est)
                if not (0.5 <= (tc_orig - tb_orig) <= MAX_CONTACT_AFTER_BOUNCE_FRAMES + 0.5):
                    continue
                in_batter, c_wx, c_wz = _is_in_batter_region(H, xc_est, yc_est)
                if not in_batter:
                    continue

                # Avoid overfitting 2-point S3 (0 residual): floor S3 huber at S2-consistent scale
                s3_huber_eff = s3.huber_sum if s3.n_pts >= 3 else max(s3.huber_sum, 0.5 * (BIC_SIGMA_PX ** 2))
                bic_c_local = (
                    2.0 * (s1.huber_sum + s2.huber_sum + s3_huber_eff) / (BIC_SIGMA_PX ** 2)
                    + (s1.n_params + s2.n_params + s3.n_params + 2) * pen_local
                    + 0.5 * ((gap_b / BIC_SIGMA_PX) ** 2 + (gap_c / BIC_SIGMA_PX) ** 2)
                )
                bic_b_local = (
                    2.0 * (s1.huber_sum + s2_hb_local.huber_sum) / (BIC_SIGMA_PX ** 2)
                    + (s1.n_params + s2_hb_local.n_params + 1) * pen_local
                    + 0.5 * (gap_b / BIC_SIGMA_PX) ** 2
                )
                s1_local_a = _fit_best_s1(ts, xs, ys, rel_knot_idx, end_c, n_local, cache)
                bic_a_local = (
                    2.0 * s1_local_a.huber_sum / (BIC_SIGMA_PX ** 2) + s1_local_a.n_params * pen_local
                    if s1_local_a is not None
                    else float("inf")
                )
                local_margin = bic_b_local - bic_c_local

                ang, sp_ratio, comb_noise, kink_snr = _kink_metrics(
                    s2, s3, tc_est, ts[split_b:split_c], ts[split_c:end_c]
                )
                cand_info = {
                    "bic": bic_c_local,
                    "bic_norm": bic_c_local / max(1, n_local),
                    "bic_b_local": bic_b_local,
                    "bic_a_local": bic_a_local,
                    "local_margin": local_margin,
                    "split_b": split_b,
                    "split_c": split_c,
                    "end_c": end_c,
                    "s1": s1,
                    "s2": s2,
                    "s3": s3,
                    "tb_eff": tb_est,
                    "tb_orig": tb_orig,
                    "xb": xb_est,
                    "yb": yb_est,
                    "b_wx": b_wx,
                    "b_wz": b_wz,
                    "tc_eff": tc_est,
                    "tc_orig": tc_orig,
                    "xc": xc_est,
                    "yc": yc_est,
                    "c_wx": c_wx,
                    "c_wz": c_wz,
                    "gap_b": gap_b,
                    "gap_c": gap_c,
                    "angle_deg": ang,
                    "speed_ratio": sp_ratio,
                    "combined_noise_px": comb_noise,
                    "kink_snr": kink_snr,
                }
                if (
                    kink_snr >= KINK_NOISE_MULT
                    and local_margin >= H_C_MIN_BIC_MARGIN
                    and bic_c_local < bic_a_local
                ):
                    if best_c is None or cand_info["bic_norm"] < best_c["bic_norm"]:
                        best_c = cand_info
                else:
                    if best_c_cand_rejected is None or cand_info["bic_norm"] < best_c_cand_rejected["bic_norm"]:
                        best_c_cand_rejected = cand_info

    # ── Select Winning Hypothesis ──
    bic_b_val = best_b["bic"] if best_b is not None else float("inf")
    bic_c_val = best_c["bic"] if best_c is not None else float("inf")
    margin_bc = (
        best_c["local_margin"]
        if best_c is not None
        else (best_c_cand_rejected["local_margin"] if best_c_cand_rejected is not None else 0.0)
    )

    chosen_hyp = "H_a"
    if best_c is not None:
        chosen_hyp = "H_c"
    elif best_b is not None and bic_b_val < bic_a:
        chosen_hyp = "H_b"
        if best_c_cand_rejected is not None:
            if best_c_cand_rejected["kink_snr"] < KINK_NOISE_MULT:
                notes.append(f"rejected_H_c_low_kink_snr:{best_c_cand_rejected['kink_snr']:.2f}")
            else:
                notes.append(f"rejected_H_c_low_margin:{best_c_cand_rejected['local_margin']:.2f}")

    if chosen_hyp == "H_a" and best_b is None and best_c is None:
        notes.append("full_toss_or_no_bounce")

    bounce_event: Optional[Dict[str, Any]] = None
    impact_event: Optional[Dict[str, Any]] = None
    bridge_pts: List[Dict[str, Any]] = []

    if chosen_hyp == "H_b" and best_b is not None:
        sig_b, _ = _bootstrap_sigma_frames(
            ts, xs, ys, knots, rel_knot_idx, best_b["split_b"], None, None,
            best_b["s1"].fx.degree, best_b["s2"].fy.degree, best_b["tb_eff"], None,
        )
        bf_int = int(round(best_b["tb_orig"]))
        track_set = set(track_frames)
        bounce_event = {
            "frame": bf_int,
            "subframe": round(best_b["tb_orig"], 3),
            "timestamp_sec": round(best_b["tb_orig"] / fps_val, 4),
            "x": round(best_b["xb"], 2),
            "y": round(best_b["yb"], 2),
            "interpolated": bf_int not in track_set,
            "pitch_x_m": round(best_b["wx"], 3) if best_b["wx"] is not None else None,
            "pitch_z_m": round(best_b["wz"], 3) if best_b["wz"] is not None else None,
            "length_m": round(best_b["wz"], 3) if best_b["wz"] is not None else None,
            "observed_neighbors": _observed_neighbors(track_frames, best_b["tb_orig"]),
            "sigma_frames": sig_b,
        }
        bridge_pts = _sample_bridge(
            knots, track_set, rel_orig_f, best_b["tb_eff"], None, best_b["s1"], best_b["s2"], None
        )
    elif chosen_hyp == "H_c" and best_c is not None:
        sig_b, sig_c = _bootstrap_sigma_frames(
            ts, xs, ys, knots, rel_knot_idx, best_c["split_b"], best_c["split_c"], best_c["end_c"],
            best_c["s1"].fx.degree, best_c["s2"].fy.degree, best_c["tb_eff"], best_c["tc_eff"],
        )
        bf_int = int(round(best_c["tb_orig"]))
        cf_int = int(round(best_c["tc_orig"]))
        track_set = set(track_frames)
        bounce_event = {
            "frame": bf_int,
            "subframe": round(best_c["tb_orig"], 3),
            "timestamp_sec": round(best_c["tb_orig"] / fps_val, 4),
            "x": round(best_c["xb"], 2),
            "y": round(best_c["yb"], 2),
            "interpolated": bf_int not in track_set,
            "pitch_x_m": round(best_c["b_wx"], 3) if best_c["b_wx"] is not None else None,
            "pitch_z_m": round(best_c["b_wz"], 3) if best_c["b_wz"] is not None else None,
            "length_m": round(best_c["b_wz"], 3) if best_c["b_wz"] is not None else None,
            "observed_neighbors": _observed_neighbors(track_frames, best_c["tb_orig"]),
            "sigma_frames": sig_b,
        }
        impact_event = {
            "frame": cf_int,
            "subframe": round(best_c["tc_orig"], 3),
            "timestamp_sec": round(best_c["tc_orig"] / fps_val, 4),
            "x": round(best_c["xc"], 2),
            "y": round(best_c["yc"], 2),
            "source": "track_engine",
            "type": None,
            "observed_neighbors": _observed_neighbors(track_frames, best_c["tc_orig"]),
            "sigma_frames": sig_c,
        }
        bridge_pts = _sample_bridge(
            knots, track_set, rel_orig_f, best_c["tb_eff"], best_c["tc_eff"],
            best_c["s1"], best_c["s2"], best_c["s3"],
        )
    elif s1_only is not None:
        track_set = set(track_frames)
        bridge_pts = _sample_bridge(
            knots, track_set, rel_orig_f, None, None, s1_only, None, None
        )

    ev_src = best_c if chosen_hyp == "H_c" else (best_c or best_c_cand_rejected)
    evidence = {
        "hypothesis": chosen_hyp,
        "bic_a": round(bic_a, 3) if math.isfinite(bic_a) else None,
        "bic_b": round(bic_b_val, 3) if math.isfinite(bic_b_val) else None,
        "bic_c": round(bic_c_val, 3) if math.isfinite(bic_c_val) else None,
        "margin": round(margin_bc, 3) if math.isfinite(margin_bc) else None,
        "angle_deg": round(ev_src["angle_deg"], 2) if ev_src is not None else None,
        "speed_ratio": round(ev_src["speed_ratio"], 3) if ev_src is not None else None,
        "combined_noise_px": round(ev_src["combined_noise_px"], 3) if ev_src is not None else None,
        "kink_snr": round(ev_src["kink_snr"], 3) if ev_src is not None else None,
        "dup_frames": dup_frames,
    }

    span_lo = int(rel_knot.frames[0])
    span_hi = int(track_frames[-1])
    span_total = max(1, span_hi - span_lo + 1)
    obs_in_span = sum(1 for f in range(span_lo, span_hi + 1) if f in set(track_frames))
    observed = {
        "dup_frames": dup_frames,
        "n_raw_frames": len(ball_by_frame),
        "n_track_points": len(track_obs),
        "n_missing_in_span": span_total - obs_in_span,
        "recall_in_span": round(obs_in_span / span_total, 4),
    }

    return {
        "events": {
            "release": rel_event,
            "bounce": bounce_event,
            "impact": impact_event,
        },
        "evidence": evidence,
        "observed": observed,
        "track": track_obs,
        "bridge": bridge_pts,
        "notes": notes,
    }


def _sample_bridge(
    knots: Sequence[_Knot],
    track_set: set[int],
    rel_orig_f: float,
    tb_eff: Optional[float],
    tc_eff: Optional[float],
    s1: _SegFit2D,
    s2: Optional[_SegFit2D],
    s3: Optional[_SegFit2D],
) -> List[Dict[str, Any]]:
    """Sample fitted curves at missing frames between observed neighbours."""
    lo = int(round(rel_orig_f))
    hi = int(knots[-1].frames[-1])
    out: List[Dict[str, Any]] = []
    for f in range(lo, hi + 1):
        if f in track_set:
            continue
        t_eff = _orig_to_eff_frame(knots, float(f))
        if s2 is not None and tb_eff is not None and t_eff >= tb_eff:
            if s3 is not None and tc_eff is not None and t_eff >= tc_eff:
                seg_name = "S3"
                px, py = s3.eval_xy(t_eff)
            else:
                seg_name = "S2"
                px, py = s2.eval_xy(t_eff)
        else:
            seg_name = "S1"
            px, py = s1.eval_xy(t_eff)
        out.append(
            {
                "frame": int(f),
                "x": round(px, 2),
                "y": round(py, 2),
                "interpolated": True,
                "predicted": True,
                "segment": seg_name,
            }
        )
    return out
