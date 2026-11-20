# Direct-Lift Height Extrapolation Analysis

Method: Post-bounce `Z(t)` linearly interpolated between labelled `Z_b` (bounce via `H`) and `Z_i`, lateral `X(t)` solved from `Hg(X, Z(t))` (`u = x_pixel`), `h(t) = (y_ground - y_pixel) / L`, fit `h(t) = h0 + v*t - 4.905*t^2` (`>= 4` pts) else linear, extrapolate to `t_s = t_i + Z_i / vz` with `vz = factor * (Z_b - Z_i) / (t_i - t_b)`.

## 1. Bowled (`stumps`, `n = 8` total: `6` red, `2` white) Validation

Notes: `c_f784a9d7` (white) has no `dump_all_1` file; `c_1a3657dc` and `c_f4592060` (red) have `0` post-bounce detections in `(t_b, t_i - k]`; `c_c1faf433` drops out at `k = 3`.

| `vz_factor` | Cut `k` | `n` | Med `|h_err|` (m) | Max `|h_err|` (m) | Med `|X_err|` (m) | Max `|X_err|` (m) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.00 | 1 | 5 | 0.229 | 0.709 | 0.025 | 0.152 |
| 1.00 | 2 | 5 | 0.300 | 0.709 | 0.048 | 0.152 |
| 1.00 | 3 | 4 | 0.323 | 0.709 | 0.048 | 0.152 |
| 0.85 | 1 | 5 | 0.259 | 0.776 | 0.023 | 0.183 |
| 0.85 | 2 | 5 | 0.265 | 0.776 | 0.046 | 0.183 |
| 0.85 | 3 | 4 | 0.333 | 0.776 | 0.035 | 0.183 |

### Per-Clip Validation (`vz_factor = 1.00`, `k = 1`) & Direct Stump Points (`Z_i = 0`)

| Clip ID | Colour | `n_pts` | `frames_left` | `h_obs` (m) | `h_pred` (m) | `|h_err|` (m) | `X_obs` (m) | `X_pred` (m) | `|X_err|` (m) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `c_0522189a` | red | 6 | 2 | 0.648 | 0.877 | 0.229 | -0.044 | -0.069 | 0.025 |
| `c_0f711886` | red | 4 | 5 | 0.222 | 0.931 | 0.709 | +0.075 | +0.053 | 0.021 |
| `c_363e37eb` | red | 3 | 4 | 0.610 | 0.310 | 0.300 | -0.001 | -0.075 | 0.074 |
| `c_75de2445` | white | 3 | 6 | 0.459 | 0.481 | 0.022 | -0.091 | +0.061 | 0.152 |
| `c_c1faf433` | red | 3 | 1 | 0.671 | 0.843 | 0.172 | +0.096 | +0.094 | 0.002 |
| `c_1a3657dc` | red | — | — | 0.438 | — | — | -0.012 | — | — |
| `c_f4592060` | red | — | — | 0.666 | — | — | -0.079 | — | — |
| `c_f784a9d7` | white | — | — | 0.197 | — | — | +0.025 | — | — |

## 2. Pad Clips (`n = 36` red/pink, all on-field OUT)

| `Z_i` (m) | `vz_factor` | `n` | `h_s` med (`p10`, `p90`) m | `X_s` med (`p10`, `p90`) m | HITTING (`|X|<=0.15`, `0<=h<=0.75`) | Flips vs `(1.0, 0.85)` |
| ---: | ---: | ---: | --- | --- | ---: | ---: |
| 0.4 | 0.85 | 36 | 0.405 (0.133, 0.613) | +0.001 (-0.102, +0.185) | 29/36 (80.6%) | 6/36 (16.7%) |
| 0.4 | 1.00 | 36 | 0.399 (0.131, 0.606) | +0.002 (-0.103, +0.185) | 29/36 (80.6%) | 6/36 (16.7%) |
| 1.0 | 0.85 | 36 | 0.548 (0.269, 0.771) | +0.015 (-0.087, +0.188) | 25/36 (69.4%) | 0/36 (0.0%) |
| 1.0 | 1.00 | 36 | 0.534 (0.254, 0.750) | +0.006 (-0.092, +0.187) | 26/36 (72.2%) | 1/36 (2.8%) |
| 1.6 | 0.85 | 36 | 0.798 (0.447, 1.022) | +0.063 (-0.089, +0.237) | 14/36 (38.9%) | 11/36 (30.6%) |
| 1.6 | 1.00 | 36 | 0.762 (0.427, 0.956) | +0.046 (-0.078, +0.217) | 15/36 (41.7%) | 10/36 (27.8%) |

- **Overall verdict stability across all 6 `(Z_i, vz_factor)` pairs**: `17/36` (`47.2%`) clips flip verdict across at least one setting (`Z_i` sensitivity dominates; changing `vz_factor` alone at `Z_i = 1.0 m` flips `1/36` = `2.8%`).
