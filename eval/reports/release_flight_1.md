# Baseline Evaluation Report: `release_flight_1`

## 1. Run Info

- **Run name**: `release_flight_1`
- **UTC time**: `2026-11-14T01:00:48Z`
- **Git commit**: `bc388874b67450f94e70b8c2ec8724702e21643c`
- **Pipeline/worker dirty**: `True`
- **Legacy tracker folder**: `Zone-div_V8m`
- **Ball types in run**: `pink, red`
- **Frame alignment**: `14/14` aligned (`0` mismatched excluded, `0` missing results)

## Conventions

- **As reported**: Compares `events.bounce` (`frame`, `x`, `y`, `zone`) in `results.json` directly against the human-labelled bounce centre. Note that the tracker writes the ball bounding-box bottom edge (`y2`) as `events.bounce.y`.
- **Centre vs centre**: Uses the system ball trajectory centre `(x, y)` at `events.bounce.frame` (preferring non-interpolated points; `approx` falls back to the nearest non-interpolated point within `±1` frame; `no_centre` if none exists), and projects both system centre and label centre through the ground-truth homography. Signed errors are `system - label` (`+dx` = right, `+dy` = lower on screen, `+pitch_z_m` = further down pitch toward bowling end).
- **Marker offset**: Signed pixel offset `as_reported_marker - label` (`dx`, `dy`), plus `dy / box_height` using the ball detection bounding-box `height` at `events.bounce.frame` from the detections CSV (expected `~ +0.5` when the marker sits at `y2` and both detect the same ball).
- **Zones**: `label_zone` is classified from the human bounce centre `pitch_z_m` through the GT homography (`Zone-div_V8m/zones.py` thresholds); `system_zone` is `events.bounce.zone` as reported; `system_zone_recomputed` is classified from the system trajectory centre pixel through the GT homography.

## 2. Headline Table (Overall)

| Metric | n | Value |
| --- | ---: | --- |
| Trajectory coverage `[release, impact]` (total / non-interp) | 14 | 86.2% / 86.2% |
| Trajectory coverage `[impact, last_visible]` (total / non-interp) | 14 | 18.3% / 18.3% |
| Release found rate | 14 | 14/14 (100.0%) |
| Release frame error (`0` / `±1` / `±2` frames) | 14 | 50.0% / 85.7% / 100.0% (med\|err\|=0.5, p90=1.7) |
| Release pixel distance (median / p90) | 14 | 12.2 px / 22.5 px |
| **Bounce — As reported**: found rate (excl. unclear) | 14 | 13/14 (92.9%) |
| **Bounce — As reported**: frame error (`0` / `±1` / `±2` frames) | 13 | 69.2% / 92.3% / 92.3% (med\|err\|=0.0, p90=1.0) |
| **Bounce — As reported**: pixel distance (median / p90) | 13 | 10.4 px / 21.9 px |
| **Bounce — As reported**: ground error in metres (median / p90) | 13 | 0.472 m / 0.697 m |
| **Bounce — As reported**: `pitch_z_m` error (signed mean / median abs) | 13 | 0.443 m / 0.457 m |
| **Bounce — As reported**: `pitch_x_m` error (signed mean / median abs) | 13 | -0.035 m / 0.011 m |
| **Bounce — As reported**: system `length_m` minus label `pitch_z_m` (signed mean / median) | 13 | 0.999 m / 0.971 m |
| **Bounce — As reported**: zone agreement | 13 | 53.8% |
| **Bounce — Centre vs centre**: centre availability (`exact` / `approx` / `no_centre`) | 13 | `13` / `0` / `0` |
| **Bounce — Centre vs centre**: frame error (`0` / `±1` / `±2` frames) | 13 | 69.2% / 92.3% / 92.3% (med\|err\|=0.0, p90=1.0) |
| **Bounce — Centre vs centre**: pixel distance (median / p90) | 13 | 3.2 px / 15.3 px |
| **Bounce — Centre vs centre**: signed `dx` (mean / median) | 13 | -5.97 px / -1.80 px |
| **Bounce — Centre vs centre**: signed `dy` (mean / median) | 13 | 2.41 px / 1.90 px |
| **Bounce — Centre vs centre**: ground error in metres (median / p90) | 13 | 0.102 m / 0.381 m |
| **Bounce — Centre vs centre**: `pitch_z_m` error (signed mean / median / median abs) | 13 | 0.099 m / 0.062 m / 0.102 m |
| **Bounce — Centre vs centre**: `pitch_x_m` error (signed mean / median / median abs) | 13 | -0.035 m / -0.009 m / 0.010 m |
| **Bounce — Centre vs centre**: recomputed zone agreement | 13 | 100.0% |
| **Bounce — Marker offset**: signed `dx` (`marker - label`, mean / median) | 13 | -5.97 px / -1.80 px |
| **Bounce — Marker offset**: signed `dy` (`marker - label`, mean / median) | 13 | 10.48 px / 10.20 px |
| **Bounce — Marker offset**: `dy / box_height` (median / mean) | 13 | 0.639 / 0.673 |
| Impact (`events.impact` non-null share) | 14 | 0/14 (0.0%) |
| Deviation candidate (`events.deviation` present on contact clips) | 14 | 13/14 (92.9%) |
| Deviation vs Impact frame error (`0` / `±1` / `±2` frames) | 13 | 15.4% / 46.2% / 76.9% (med\|err\|=2.0, p90=3.0) |
| Deviation vs Impact pixel distance (median / p90) | 13 | 55.0 px / 108.2 px |
| Impact type accuracy | 14 | n/a (system provides no impact type) |
| False-marker rate on labelled `none` (impact / deviation) | 0 | — / — |
| LBW | 0 | n/a (not implemented in the system) |
| Runtime per clip (mean / median / p90) | 14 | 9.13 s / 8.96 s / 11.45 s |

## 3. Detail Tables

### 3.1 Breakdown by Ball Colour

| Slice | n (valid / clear) | Cov `[rel,imp]` | Release Found | Rel `±1f` | Rel Med px | Bounce Found | Bnc `±1f` | Bnc Med m (rep / ctr) | Dev on Contact | Dev `±1f` | Dev Med px | Runtime Med |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `pink` | 11 / 11 | 91.2% (n=11) | 11/11 | 90.9% | 13.8 | 11/11 | 90.9% | 0.375 / 0.102 | 11/11 | 54.5% | 39.1 | 8.08s |
| `red` | 3 / 3 | 67.9% (n=3) | 3/3 | 66.7% | 2.3 | 2/3 | 100.0% | 0.492 / 0.209 | 2/3 | 0.0% | 107.2 | 11.64s |
| `white` | 0 / 0 | — (n=0) | 0/0 | — | — | 0/0 | — | — / — | 0/0 | — | — | — |

### 3.2 Breakdown by Split (`dev` / `final` / `none`)

| Slice | n (valid / clear) | Cov `[rel,imp]` | Release Found | Rel `±1f` | Rel Med px | Bounce Found | Bnc `±1f` | Bnc Med m (rep / ctr) | Dev on Contact | Dev `±1f` | Dev Med px | Runtime Med |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `dev` | 4 / 4 | 95.0% (n=4) | 4/4 | 100.0% | 5.4 | 4/4 | 100.0% | 0.424 / 0.093 | 4/4 | 50.0% | 48.5 | 8.09s |
| `final` | 0 / 0 | — (n=0) | 0/0 | — | — | 0/0 | — | — / — | 0/0 | — | — | — |
| `none` | 10 / 10 | 82.7% (n=10) | 10/10 | 80.0% | 14.4 | 9/10 | 88.9% | 0.472 / 0.107 | 9/10 | 44.4% | 55.0 | 9.25s |

### 3.3 Per-Clip Detail Table

| Clip ID | Ball | Split | Unclear | Rel Err (f / px) | As-rep Bnc (f / px / m) | Centre vs Centre (`status`: `dx`,`dy` / px / m) | Marker Offset (`dx`,`dy` / `dy/h`) | `pitch_z` Err rep/ctr (m) | Zone (`lbl` -> `rep` / `recomp`) | Dev vs Imp (f / px) | Runtime (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: |
| `c_09a18d5f` | `pink` | `none` | `no` | 2f / 22.7px | -8f / 48.3px / 0.539m | `exact`: -46.2,8.1 / 46.9px / 0.383m | -46.2,14.1 / 1.18 | 0.457 / 0.253 | `GOOD` -> `GOOD` / `GOOD` | 0f / 7.1px | 10.19 |
| `c_13f43606` | `pink` | `none` | `no` | 0f / 19.9px | 0f / 8.1px / 0.375m | `exact`: 0.6,0.1 / 0.6px / 0.006m | 0.6,8.1 / 0.54 | 0.375 / 0.005 | `FULL` -> `GOOD` / `FULL` | 2f / 81.4px | 7.72 |
| `c_3d27ed64` | `pink` | `dev` | `no` | 0f / 2.2px | 0f / 5.9px / 0.236m | `exact`: -1.9,-2.4 / 3.1px / 0.102m | -1.9,5.6 / 0.37 | 0.235 / -0.102 | `FULL` -> `GOOD` / `FULL` | 3f / 81.0px | 9.32 |
| `c_3f1fc736` | `pink` | `none` | `no` | -1f / 9.8px | 0f / 8.5px / 0.345m | `exact`: -1.1,-1.6 / 1.9px / 0.066m | -1.1,8.4 / 0.44 | 0.345 / -0.066 | `GOOD` -> `SHORT` / `GOOD` | 2f / 84.8px | 8.60 |
| `c_41dd8473` | `pink` | `none` | `no` | 1f / 15.0px | 0f / 3.8px / 0.125m | `exact`: -1.8,-2.7 / 3.2px / 0.102m | -1.8,3.3 / 0.27 | 0.125 / -0.102 | `GOOD` -> `GOOD` / `GOOD` | 1f / 17.1px | 9.89 |
| `c_542fca8b` | `pink` | `none` | `no` | 0f / 10.7px | 0f / 22.2px / 0.912m | `exact`: 3.6,8.9 / 9.6px / 0.373m | 3.6,21.9 / 0.84 | 0.912 / 0.373 | `FULL` -> `GOOD` / `FULL` | -1f / 4.2px | 7.91 |
| `c_5cef27ce` | `pink` | `dev` | `no` | -1f / 8.5px | 0f / 11.8px / 0.594m | `exact`: -0.7,0.8 / 1.1px / 0.041m | -0.7,11.8 / 0.56 | 0.594 / 0.040 | `FULL` -> `FULL` / `FULL` | -1f / 15.2px | 10.74 |
| `c_5e5ea872` | `pink` | `dev` | `no` | 0f / 2.3px | 0f / 6.0px / 0.253m | `exact`: 0.3,-2.0 / 2.0px / 0.085m | 0.3,6.0 / 0.40 | 0.253 / -0.085 | `FULL` -> `GOOD` / `FULL` | 0f / 16.1px | 6.65 |
| `c_69ba9415` | `red` | `none` | `no` | 2f / 36.1px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | 11.01 |
| `c_6e281881` | `red` | `none` | `no` | 0f / 2.3px | -1f / 15.1px / 0.512m | `exact`: -8.6,6.4 / 10.7px / 0.269m | -8.6,12.4 / 1.03 | 0.509 / 0.264 | `FULL` -> `FULL` / `FULL` | 24f / 159.4px | 12.29 |
| `c_77d7834d` | `pink` | `none` | `no` | 0f / 13.8px | -1f / 9.6px / 0.270m | `exact`: -5.5,1.9 / 5.8px / 0.071m | -5.5,7.9 / 0.66 | 0.267 / 0.062 | `GOOD` -> `GOOD` / `GOOD` | 2f / 79.6px | 6.99 |
| `c_a473c3f0` | `pink` | `dev` | `no` | 1f / 14.4px | -1f / 20.8px / 0.723m | `exact`: -14.3,8.1 / 16.4px / 0.396m | -14.3,15.1 / 1.08 | 0.719 / 0.389 | `FULL` -> `GOOD` / `FULL` | 3f / 114.1px | 6.86 |
| `c_e6b5e8a3` | `pink` | `none` | `no` | 1f / 22.1px | 0f / 11.5px / 0.489m | `exact`: -0.1,2.5 / 2.5px / 0.107m | -0.1,11.5 / 0.64 | 0.489 / 0.107 | `FULL` -> `FULL` / `FULL` | 1f / 39.1px | 8.08 |
| `c_f51f593e` | `red` | `none` | `no` | 0f / 1.5px | 0f / 10.4px / 0.472m | `exact`: -1.9,3.2 / 3.7px / 0.149m | -1.9,10.2 / 0.73 | 0.472 / 0.148 | `GOOD` -> `GOOD` / `GOOD` | 2f / 55.0px | 11.64 |

### 3.4 Bounce Zone Agreement & Confusion Matrix (Recomputed from System Centre)

Thresholds loaded at runtime from `backend/worker/legacy/Zone-div_V8m/zones.py`: `YORKER`: `[0.00, 2.00) m`, `FULL`: `[2.00, 6.00) m`, `GOOD`: `[6.00, 8.00) m`, `SHORT`: `[8.00, 20.90) m`

- **System zone (as reported) agreement**: `7/13` (53.8%)
- **System zone (recomputed from system centre) agreement**: `13/13` (100.0%)

| Labelled \\ System Recomputed | `YORKER` | `FULL` | `GOOD` | `SHORT` |
| --- | ---: | ---: | ---: | ---: |
| **`YORKER`** | 0 | 0 | 0 | 0 |
| **`FULL`** | 0 | 8 | 0 | 0 |
| **`GOOD`** | 0 | 0 | 5 | 0 |
| **`SHORT`** | 0 | 0 | 0 | 0 |

### 3.5 Calibration Quality of the Labels

- **Total clips scored**: `14`
- **Both stumps derived (`0` confirmed)**: `0`
- **One stump confirmed (`1` confirmed)**: `0`
- **Both stumps confirmed (`2` confirmed)**: `14`
- **Homography `residual_px` (n=14)**: mean=0.92 px, max=3.26 px

### 3.6 Clips Flagged `unclear`

Clips with the `unclear` flag are included in Release metrics, excluded from Bounce and Impact tolerance/error tables, and listed below:

_No clips had the `unclear` flag in this run._

## 4. Worst 5 Clips per Metric

### Release Frame Error (frames)
1. `c_09a18d5f` (`pink`, split=`none`): **2**
2. `c_69ba9415` (`red`, split=`none`): **2**
3. `c_3f1fc736` (`pink`, split=`none`): **-1**
4. `c_41dd8473` (`pink`, split=`none`): **1**
5. `c_5cef27ce` (`pink`, split=`dev`): **-1**

### Release Pixel Distance (px)
1. `c_69ba9415` (`red`, split=`none`): **36.1**
2. `c_09a18d5f` (`pink`, split=`none`): **22.7**
3. `c_e6b5e8a3` (`pink`, split=`none`): **22.1**
4. `c_13f43606` (`pink`, split=`none`): **19.9**
5. `c_41dd8473` (`pink`, split=`none`): **15.0**

### Bounce Frame Error (frames, excl. unclear)
1. `c_09a18d5f` (`pink`, split=`none`): **-8**
2. `c_6e281881` (`red`, split=`none`): **-1**
3. `c_77d7834d` (`pink`, split=`none`): **-1**
4. `c_a473c3f0` (`pink`, split=`dev`): **-1**
5. `c_13f43606` (`pink`, split=`none`): **0**

### Bounce Ground Error (m, excl. unclear)
1. `c_542fca8b` (`pink`, split=`none`): **0.912**
2. `c_a473c3f0` (`pink`, split=`dev`): **0.723**
3. `c_5cef27ce` (`pink`, split=`dev`): **0.594**
4. `c_09a18d5f` (`pink`, split=`none`): **0.539**
5. `c_6e281881` (`red`, split=`none`): **0.512**

### Deviation vs Impact Frame Error (frames, excl. unclear)
1. `c_6e281881` (`red`, split=`none`): **24**
2. `c_3d27ed64` (`pink`, split=`dev`): **3**
3. `c_a473c3f0` (`pink`, split=`dev`): **3**
4. `c_13f43606` (`pink`, split=`none`): **2**
5. `c_3f1fc736` (`pink`, split=`none`): **2**

### Deviation vs Impact Pixel Distance (px, excl. unclear)
1. `c_6e281881` (`red`, split=`none`): **159.4**
2. `c_a473c3f0` (`pink`, split=`dev`): **114.1**
3. `c_3f1fc736` (`pink`, split=`none`): **84.8**
4. `c_13f43606` (`pink`, split=`none`): **81.4**
5. `c_3d27ed64` (`pink`, split=`dev`): **81.0**

## 5. Caveats

- **Small sample sizes**: The current baseline evaluation set has a small number of final clips; percentile estimates (`p90`) and subgroup breakdowns (`ball_colour`, `split`) have high variance until more clips are annotated.
- **Labels made blind to the pipeline**: Ground-truth labels (`release`, `bounce`, `impact`, `calibration_gt`) were annotated independently in the annotator UI without inspecting pipeline predictions.
- **30 fps temporal resolution limits**: At ~30 fps (~33.3 ms per frame), a fast delivery travels ~0.9–1.2 m between consecutive frames. A 1-frame sampling difference near bounce or impact naturally introduces 0.5–1.2 m of along-pitch distance difference even when pixel localization is accurate.
- **Legacy `zones.py` length bug (`19.68 m` vs `17.68 m`)**: The legacy tracker sets `BOWL_CREASE_Y = 1.22 + 19.68 = 20.90 m` instead of the regulation `1.22 + 17.68 = 18.90 m` (`calib_constants.py`), systematically inflating `system.bounce.length_m` relative to true `pitch_z_m`.
