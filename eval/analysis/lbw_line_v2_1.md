# Line-Only LBW Prediction (`lbw_line_1`)

> **Sanity check, not an accuracy measure.** All 14 labelled clips are on-field LBW **"out"** decisions (all pad impacts). Only the LINE is evaluated: height at the stumps is not recoverable from the single camera. The expected outcome is mostly `OUT_LINE` / `HITTING`; anything else is a sign of a geometry or event problem, not of a wrong decision.

Clips with labels and `lbw_line_1` results: `14`; line prediction computed: `11`; not computable: `3`. Batch `lbw` blocks stored in results.json: `11` (equal to a recomputation with `batter_hand=right`: `11`); results.json without an `lbw` key: `3` (`c_09a18d5f, c_69ba9415, c_6e281881`).

## 1. Per-clip results (labelled batter hand)

| Clip | Hand | Pitch `(X, Z)` m | Pitch side / verdict | Impact `X` m | Impact side / verdict | `X_s` m | σ m | Wickets | Margin m | Stable | Slope pts flag | Overall |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `c_09a18d5f` | right | — | — | — | — | — | — | — | — | — | — | **not computed** (bounce frame 4 not after release frame 4) |
| `c_13f43606` | right | `(-0.330, 5.85)` | off / `outside_off` | `-0.060` | centre / `in_line` | `-0.003` | `0.037` | `HITTING` | `-0.111` | yes | ok | `OUT_LINE` |
| `c_3d27ed64` | right | `(+0.341, 5.59)` | leg / `outside_leg` | `+0.181` | leg / `outside_leg` | `+0.147` | `0.027` | `UMPIRES_CALL` | `+0.033` | **no** | ok | `NOT_OUT_LINE` |
| `c_3f1fc736` | right | `(-0.279, 6.93)` | off / `outside_off` | `+0.036` | centre / `in_line` | `+0.084` | `0.033` | `HITTING` | `-0.030` | **no** | ok | `OUT_LINE` |
| `c_41dd8473` | right | `(-0.291, 6.55)` | off / `outside_off` | `+0.151` | leg / `outside_leg` | `+0.212` | `0.042` | `MISSING` | `+0.098` | yes | ok | `NOT_OUT_LINE` |
| `c_542fca8b` | right | `(+0.268, 5.38)` | leg / `outside_leg` | `+0.044` | centre / `in_line` | `-0.008` | `0.035` | `HITTING` | `-0.107` | yes | ok | `NOT_OUT_LINE` |
| `c_5cef27ce` | right | `(-0.331, 3.87)` | off / `outside_off` | `-0.004` | centre / `in_line` | `+0.077` | `0.052` | `HITTING` | `-0.037` | **no** | ok | `OUT_LINE` |
| `c_5e5ea872` | right | `(-0.094, 5.72)` | centre / `in_line` | `-0.017` | centre / `in_line` | `-0.001` | `0.017` | `HITTING` | `-0.114` | yes | ok | `OUT_LINE` |
| `c_69ba9415` | left | — | — | — | — | — | — | — | — | — | — | **not computed** (no impact event) |
| `c_6e281881` | right | — | — | — | — | — | — | — | — | — | — | **not computed** (no impact event) |
| `c_77d7834d` | right | `(-0.123, 6.34)` | off / `outside_off` | `+0.103` | centre / `in_line` | `+0.121` | `0.020` | `UMPIRES_CALL` | `+0.007` | **no** | ok | `UMPIRES_CALL` |
| `c_a473c3f0` | right | `(-0.364, 5.34)` | off / `outside_off` | `-0.123` | off / `umpires_call` | `-0.078` | `0.030` | `HITTING` | `-0.036` | **no** | ok | `UMPIRES_CALL` |
| `c_e6b5e8a3` | right | `(-0.047, 4.01)` | centre / `in_line` | `-0.059` | centre / `in_line` | `-0.059` | `0.052` | `HITTING` | `-0.056` | **no** | flag | `OUT_LINE` |
| `c_f51f593e` | right | `(-0.410, 6.81)` | off / `outside_off` | `-0.277` | off / `outside_off` | `-0.259` | `0.021` | `MISSING` | `+0.145` | yes | ok | `NOT_OUT_LINE` |

## 2. Verdict counts (labelled hand)

Computed clips: `11`.

| Stage | Counts |
| :--- | :--- |
| Pitching | `in_line`: 2, `outside_leg`: 2, `outside_off`: 7 |
| Impact | `in_line`: 7, `outside_leg`: 2, `outside_off`: 1, `umpires_call`: 1 |
| Wickets | `HITTING`: 7, `MISSING`: 2, `UMPIRES_CALL`: 2 |
| Overall | `NOT_OUT_LINE`: 4, `OUT_LINE`: 5, `UMPIRES_CALL`: 2 |

Wickets shares: `HITTING` 7/11 (`63.6%`), `UMPIRES_CALL` 2/11 (`18.2%`), `MISSING` 2/11 (`18.2%`).

Mean σ (wickets lateral uncertainty): `0.033 m` (min `0.017`, max `0.052`).

### Verdicts that are not stable (`|margin| <= 2σ`): `6/11`

| Clip | Wickets | `X_s` m | Margin m | 2σ m | Overall |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `c_3d27ed64` | `UMPIRES_CALL` | `+0.147` | `+0.033` | `0.055` | `NOT_OUT_LINE` |
| `c_3f1fc736` | `HITTING` | `+0.084` | `-0.030` | `0.066` | `OUT_LINE` |
| `c_5cef27ce` | `HITTING` | `+0.077` | `-0.037` | `0.103` | `OUT_LINE` |
| `c_77d7834d` | `UMPIRES_CALL` | `+0.121` | `+0.007` | `0.041` | `UMPIRES_CALL` |
| `c_a473c3f0` | `HITTING` | `-0.078` | `-0.036` | `0.061` | `UMPIRES_CALL` |
| `c_e6b5e8a3` | `HITTING` | `-0.059` | `-0.056` | `0.104` | `OUT_LINE` |

## 3. `X_s` versus the homography-lifted probe

Reference: `X_s_m` (main run, `k=0`, `e in [0.3, 0.8]`, system impact) of `lbw_lifted_v2_1.csv`. Agreement threshold: `5 cm`.

| Clip | Line `X_s` m | Lifted `X_s` m | Δ m | `X_i` m | Slope term `ΔX` m | Slope pts | Agrees |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `c_13f43606` | `-0.003` | `+0.035` | `-0.038` | `-0.060` | `+0.057` | ok | yes |
| `c_3d27ed64` | `+0.147` | `-0.008` | `+0.155` | `+0.181` | `-0.033` | ok | **no** |
| `c_3f1fc736` | `+0.084` | `+0.050` | `+0.035` | `+0.036` | `+0.048` | ok | yes |
| `c_41dd8473` | `+0.212` | `+0.160` | `+0.052` | `+0.151` | `+0.060` | ok | **no** |
| `c_542fca8b` | `-0.008` | `-0.029` | `+0.021` | `+0.044` | `-0.052` | ok | yes |
| `c_5cef27ce` | `+0.077` | `-0.143` | `+0.220` | `-0.004` | `+0.081` | ok | **no** |
| `c_5e5ea872` | `-0.001` | `+0.149` | `-0.150` | `-0.017` | `+0.016` | ok | **no** |
| `c_77d7834d` | `+0.121` | `+0.105` | `+0.016` | `+0.103` | `+0.018` | ok | yes |
| `c_a473c3f0` | `-0.078` | `-0.101` | `+0.022` | `-0.123` | `+0.045` | ok | yes |
| `c_e6b5e8a3` | `-0.059` | `+0.061` | `-0.120` | `-0.059` | `+0.000` | flag | **no** |
| `c_f51f593e` | `-0.259` | `-0.208` | `-0.051` | `-0.277` | `+0.018` | ok | **no** |

Within `5 cm`: `5/11`; median |Δ| `0.051 m`, max |Δ| `0.220 m`.

Clips differing by more than 5 cm: `c_3d27ed64` (+0.155 m), `c_41dd8473` (+0.052 m), `c_5cef27ce` (+0.220 m), `c_5e5ea872` (-0.150 m), `c_e6b5e8a3` (-0.120 m), `c_f51f593e` (-0.051 m).

### Why the clips differ

Two model differences explain the gaps. (a) The line model takes the post-bounce lateral slope directly from the post-bounce points and always extrapolates from a pad `1.0 m` from the stump line (post-bounce along-pitch speed `0.85` x pre-bounce); the lifted fit ties the post-bounce lateral velocity to the pre-bounce one (times `f`) and its time to the stumps follows from a poorly determined `f`/height, so its bounce→stumps time differs from the line model's (see the frame columns). (b) `events.impact` is a trajectory vertex and can be one frame after the labelled impact, i.e. on the post-contact deflection, which changes `X_i` and the slope.

| Clip | Impact frame sys / label | Line `X_s` | Line `X_s` (labelled impact) | Lifted `X_s` | Lifted `X_s` (oracle impact) | Line frames bounce→stumps | Lifted frames bounce→stumps | Cause (differs > 5 cm) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `c_13f43606` | 18 / 18 | `-0.003` | `+0.001` | `+0.035` | `+0.035` | `4.9` | `6.7` | — |
| `c_3d27ed64` | 20 / 19 | `+0.147` | `+0.056` | `-0.008` | `-0.028` | `5.8` | `7.3` | system impact +1 frame vs label; lifted bounce→stumps time differs by +1.4 frames; still +0.084 m apart with the labelled impact (lateral slope model) |
| `c_3f1fc736` | 19 / 19 | `+0.084` | `+0.091` | `+0.050` | `+0.050` | `6.9` | `6.6` | — |
| `c_41dd8473` | 19 / 19 | `+0.212` | `+0.152` | `+0.160` | `+0.160` | `6.7` | `7.8` | lifted bounce→stumps time differs by +1.1 frames |
| `c_542fca8b` | 20 / 21 | `-0.008` | `+0.037` | `-0.029` | `+0.060` | `4.9` | `6.4` | — |
| `c_5cef27ce` | 29 / 29 | `+0.077` | `+0.076` | `-0.143` | `-0.143` | `7.4` | `5.5` | lifted bounce→stumps time differs by -1.9 frames; still +0.219 m apart with the labelled impact (lateral slope model) |
| `c_5e5ea872` | 17 / 17 | `-0.001` | `+0.010` | `+0.149` | `+0.149` | `4.9` | `7.8` | lifted bounce→stumps time differs by +2.9 frames; still -0.140 m apart with the labelled impact (lateral slope model) |
| `c_77d7834d` | 24 / 23 | `+0.121` | `+0.001` | `+0.105` | `+0.094` | `7.7` | `8.1` | — |
| `c_a473c3f0` | 17 / 17 | `-0.078` | `-0.077` | `-0.101` | `-0.101` | `4.7` | `5.3` | — |
| `c_e6b5e8a3` | 17 / 17 | `-0.059` | `-0.065` | `+0.061` | `+0.061` | `2.8` | `4.6` | lifted bounce→stumps time differs by +1.9 frames; still -0.126 m apart with the labelled impact (lateral slope model); slope flag (<3 points): slope set to 0 |
| `c_f51f593e` | 19 / 18 | `-0.259` | `-0.101` | `-0.208` | `+0.022` | `7.8` | `5.9` | system impact +1 frame vs label; lifted bounce→stumps time differs by -1.9 frames; still -0.123 m apart with the labelled impact (lateral slope model) |

## 4. Second pass: `batter_hand = None`

Computed clips: `11`. Sides are `None`; the leg-side pitching rule cannot apply.

| Stage | Counts |
| :--- | :--- |
| Pitching | `in_line`: 2, `outside_side_unknown`: 9 |
| Impact | `in_line`: 7, `outside_side_unknown`: 3, `umpires_call`: 1 |
| Wickets | `HITTING`: 7, `MISSING`: 2, `UMPIRES_CALL`: 2 |
| Overall | `NOT_OUT_LINE`: 3, `OUT_LINE`: 6, `UMPIRES_CALL`: 2 |

Clips whose overall verdict changes when the hand is unknown: `c_542fca8b`. Clips whose `X_s` changes: none (X_s does not depend on the hand).

## 5. Clips without a line prediction

- `c_09a18d5f`: bounce frame 4 not after release frame 4.
- `c_69ba9415`: no impact event.
- `c_6e281881`: no impact event.

## 6. Assumptions to confirm

- `OFF_SIDE_IS_IMAGE_LEFT_FOR_RIGHT_HANDER = True` in `backend/pipeline/lbw_line.py` (off side for a right-hander is the image left, `X < 0`). **To be confirmed by the user**; all off/leg logic depends only on this constant. Data check on these 11 computed labelled-out clips: pitching verdicts are `in_line` 2, `outside_leg` 2, `outside_off` 7 with the current value and `in_line` 2, `outside_leg` 7, `outside_off` 2 with it flipped (overall `{'NOT_OUT_LINE': 8, 'OUT_LINE': 3}`). Pitching outside leg cannot be out, so the flipped value would call most of these on-field outs not out; this supports the current value but does not prove it.
- Release assumed `19.5 m` from the stump line; post-bounce along-pitch speed `0.85 x` pre-bounce; pad `1.0 m` (σ `0.6 m`) from the stump line.
- Height is not evaluated; the impact type is not classified (pad assumed).
