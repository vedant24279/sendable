# Lift Geometry Sanity Check (`eval/labels` final clips)

Method: 4-corner ground homography `fit_homography` (`app/calib.py`), mapping impact pixel `(x_ball, y_ball)` via `H` to `X_ball`, evaluating `Hg(X_ball, Z)` and local scale `L = b * cos(theta)` with `sin(theta) = min(a/b, 0.9)` (`lbw_lifted.hg_project_and_scales`), and height `h = (y_ground - y_ball) / L`.

## 1. Bowled Clips (`impact.type == "stumps"`, `Z = 0.0 m`, `n = 8`)

- **Share inside `[-0.1, 0.85] m`**: `8/8` (`100.0%`)
- **Share inside `[0.0, 0.75] m`**: `8/8` (`100.0%`)
- **Mean `h`**: `0.489 m`
- **Std `h`**: `0.182 m` (population `ddof=0`; sample `ddof=1`: `0.194 m`)

| Clip ID | Colour | Label `(x, y)` | `X_ball` (m) | `y_ground` (px) | `L` (px/m) | `a / b` | `h` (m) | In `[-0.1, 0.85]` |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| `c_0522189a` | red | (951.8, 286.0) | -0.045 | 380.3 | 145.7 | 0.098 | **0.648** | yes |
| `c_0f711886` | red | (960.8, 419.6) | +0.078 | 452.7 | 148.9 | 0.098 | **0.222** | yes |
| `c_1a3657dc` | red | (947.1, 389.0) | -0.011 | 454.4 | 149.4 | 0.098 | **0.438** | yes |
| `c_363e37eb` | red | (949.7, 362.3) | +0.003 | 452.9 | 148.5 | 0.098 | **0.610** | yes |
| `c_75de2445` | white | (946.1, 279.0) | -0.095 | 317.0 | 82.8 | 0.166 | **0.459** | yes |
| `c_c1faf433` | red | (978.1, 294.9) | +0.116 | 396.2 | 151.1 | 0.161 | **0.671** | yes |
| `c_f4592060` | red | (948.1, 282.8) | -0.084 | 380.2 | 146.1 | 0.098 | **0.666** | yes |
| `c_f784a9d7` | white | (969.0, 298.4) | +0.025 | 316.6 | 92.2 | 0.163 | **0.197** | yes |

## 2. Pad Clips (`impact.type == "pad"`, `n = 36`)

| Assumed `Z_i` (m) | `n` | Median `h` (m) | `p10` (m) | `p90` (m) | Min / Max (m) | Share `< 0.65 m` |
| ---: | ---: | ---: | ---: | ---: | :---: | ---: |
| 1.0 | 36 | 0.448 | 0.225 | 0.671 | 0.033 / 0.728 | 31/36 (86.1%) |
| 0.4 | 36 | 0.379 | 0.144 | 0.599 | -0.043 / 0.665 | 35/36 (97.2%) |
| 1.6 | 36 | 0.514 | 0.305 | 0.754 | 0.110 / 0.838 | 26/36 (72.2%) |

## 3. Conclusion

All 8 bowled (`stumps`) clips lie within `[0.197, 0.671] m` (mean `0.489 m`, std `0.182 m`), validating the homography lift scale `L` at `Z = 0`. Across all 36 `pad` clips at `Z_i = 1.0 m`, median impact height is `0.448 m` (`p10 = 0.225 m`, `p90 = 0.671 m`), with `31/36` (`86.1%`) below `0.65 m`.
