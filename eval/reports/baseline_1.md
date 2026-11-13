# Baseline Evaluation Report: `baseline_1`

## 1. Run Info

- **Run name**: `baseline_1`
- **UTC time**: `2026-11-13T09:09:26Z`
- **Git commit**: `4a37964415d0a482d84e6fc1b6af6c6f03678ae4`
- **Pipeline/worker dirty**: `False`
- **Legacy tracker folder**: `Zone-div_V8m`
- **Ball types in run**: `pink, red`
- **Frame alignment**: `14/14` aligned (`0` mismatched excluded, `0` missing results)

## 2. Headline Table (Overall)

| Metric | n | Value |
| --- | ---: | --- |
| Trajectory coverage `[release, impact]` (total / non-interp) | 14 | 88.5% / 88.5% |
| Trajectory coverage `[impact, last_visible]` (total / non-interp) | 14 | 18.3% / 18.3% |
| Release found rate | 14 | 14/14 (100.0%) |
| Release frame error (`0` / `±1` / `±2` frames) | 14 | 28.6% / 42.9% / 57.1% (med\|err\|=2.0, p90=4.0) |
| Release pixel distance (median / p90) | 14 | 68.8 px / 181.6 px |
| Bounce found rate (excl. unclear) | 14 | 13/14 (92.9%) |
| Bounce frame error (`0` / `±1` / `±2` frames) | 13 | 69.2% / 92.3% / 92.3% (med\|err\|=0.0, p90=1.0) |
| Bounce pixel distance (median / p90) | 13 | 10.4 px / 21.9 px |
| Bounce ground error in metres (median / p90) | 13 | 0.472 m / 0.697 m |
| Bounce `pitch_z_m` error (signed mean / median abs) | 13 | 0.443 m / 0.457 m |
| Bounce `pitch_x_m` error (signed mean / median abs) | 13 | -0.035 m / 0.011 m |
| System `length_m` minus labelled `pitch_z_m` (signed mean / median) | 13 | 0.999 m / 0.971 m |
| Bounce zone agreement | 13 | 53.8% |
| Impact (`events.impact` non-null share) | 14 | 0/14 (0.0%) |
| Deviation candidate (`events.deviation` present on contact clips) | 14 | 13/14 (92.9%) |
| Deviation vs Impact frame error (`0` / `±1` / `±2` frames) | 13 | 15.4% / 46.2% / 76.9% (med\|err\|=2.0, p90=3.0) |
| Deviation vs Impact pixel distance (median / p90) | 13 | 55.0 px / 108.2 px |
| Impact type accuracy | 14 | n/a (system provides no impact type) |
| False-marker rate on labelled `none` (impact / deviation) | 0 | — / — |
| LBW | 0 | n/a (not implemented in the system) |
| Runtime per clip (mean / median / p90) | 14 | 8.62 s / 8.78 s / 10.36 s |

## 3. Detail Tables

### 3.1 Breakdown by Ball Colour

| Slice | n (valid / clear) | Cov `[rel,imp]` | Release Found | Rel `±1f` | Rel Med px | Bounce Found | Bnc `±1f` | Bnc Med m | Dev on Contact | Dev `±1f` | Dev Med px | Runtime Med |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `pink` | 11 / 11 | 94.2% (n=11) | 11/11 | 36.4% | 122.9 | 11/11 | 90.9% | 0.375 | 11/11 | 54.5% | 39.1 | 8.10s |
| `red` | 3 / 3 | 67.9% (n=3) | 3/3 | 66.7% | 2.3 | 2/3 | 100.0% | 0.492 | 2/3 | 0.0% | 107.2 | 10.41s |
| `white` | 0 / 0 | — (n=0) | 0/0 | — | — | 0/0 | — | — | 0/0 | — | — | — |

### 3.2 Breakdown by Split (`dev` / `final` / `none`)

| Slice | n (valid / clear) | Cov `[rel,imp]` | Release Found | Rel `±1f` | Rel Med px | Bounce Found | Bnc `±1f` | Bnc Med m | Dev on Contact | Dev `±1f` | Dev Med px | Runtime Med |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `dev` | 4 / 4 | 96.7% (n=4) | 4/4 | 75.0% | 5.4 | 4/4 | 100.0% | 0.424 | 4/4 | 50.0% | 48.5 | 8.02s |
| `final` | 0 / 0 | — (n=0) | 0/0 | — | — | 0/0 | — | — | 0/0 | — | — | — |
| `none` | 10 / 10 | 85.3% (n=10) | 10/10 | 30.0% | 112.2 | 9/10 | 88.9% | 0.472 | 9/10 | 44.4% | 55.0 | 8.94s |

### 3.3 Per-Clip Detail Table

| Clip ID | Ball | Split | Unclear | Rel Err (f / px) | Bnc Err (f / px / m) | `pitch_z` Err (m) | `pitch_x` Err (m) | `sys.length - lbl.z` (m) | Zone (`lbl` -> `sys`) | Dev vs Imp (f / px) | Runtime (s) |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | ---: |
| `c_09a18d5f` | `pink` | `none` | `no` | -2f / 101.5px | -8f / 48.3px / 0.539m | 0.457 | -0.286 | 1.095 | `GOOD` -> `GOOD` | 0f / 7.1px | 9.48 |
| `c_13f43606` | `pink` | `none` | `no` | -4f / 188.3px | 0f / 8.1px / 0.375m | 0.375 | 0.003 | 0.971 | `FULL` -> `GOOD` | 2f / 81.4px | 7.55 |
| `c_3d27ed64` | `pink` | `dev` | `no` | 0f / 2.2px | 0f / 5.9px / 0.236m | 0.235 | -0.012 | 0.794 | `FULL` -> `GOOD` | 3f / 81.0px | 9.16 |
| `c_3f1fc736` | `pink` | `none` | `no` | -1f / 9.8px | 0f / 8.5px / 0.345m | 0.345 | -0.006 | 1.040 | `GOOD` -> `SHORT` | 2f / 84.8px | 8.40 |
| `c_41dd8473` | `pink` | `none` | `no` | -3f / 122.9px | 0f / 3.8px / 0.125m | 0.125 | -0.011 | 0.775 | `GOOD` -> `GOOD` | 1f / 17.1px | 9.60 |
| `c_542fca8b` | `pink` | `none` | `no` | -3f / 158.1px | 0f / 22.2px / 0.912m | 0.912 | 0.017 | 1.478 | `FULL` -> `GOOD` | -1f / 4.2px | 7.63 |
| `c_5cef27ce` | `pink` | `dev` | `no` | -1f / 8.5px | 0f / 11.8px / 0.594m | 0.594 | -0.004 | 1.000 | `FULL` -> `FULL` | -1f / 15.2px | 10.24 |
| `c_5e5ea872` | `pink` | `dev` | `no` | 0f / 2.3px | 0f / 6.0px / 0.253m | 0.253 | 0.001 | 0.821 | `FULL` -> `GOOD` | 0f / 16.1px | 6.27 |
| `c_69ba9415` | `red` | `none` | `no` | 2f / 36.1px | missed | — | — | — | `FULL` -> `—` | none | 9.52 |
| `c_6e281881` | `red` | `none` | `no` | 0f / 2.3px | -1f / 15.1px / 0.512m | 0.509 | -0.048 | 0.824 | `FULL` -> `FULL` | 24f / 159.4px | 10.45 |
| `c_77d7834d` | `pink` | `none` | `no` | -4f / 173.9px | -1f / 9.6px / 0.270m | 0.267 | -0.034 | 0.898 | `GOOD` -> `GOOD` | 2f / 79.6px | 7.01 |
| `c_a473c3f0` | `pink` | `dev` | `no` | -3f / 185.0px | -1f / 20.8px / 0.723m | 0.719 | -0.073 | 1.252 | `FULL` -> `GOOD` | 3f / 114.1px | 6.88 |
| `c_e6b5e8a3` | `pink` | `none` | `no` | -4f / 171.8px | 0f / 11.5px / 0.489m | 0.489 | 0.000 | 0.877 | `FULL` -> `FULL` | 1f / 39.1px | 8.10 |
| `c_f51f593e` | `red` | `none` | `no` | 0f / 1.5px | 0f / 10.4px / 0.472m | 0.472 | -0.002 | 1.166 | `GOOD` -> `GOOD` | 2f / 55.0px | 10.41 |

### 3.4 Bounce Zone Confusion Matrix (Labelled Zone Rows vs System Zone Columns)

Thresholds loaded at runtime from `backend/worker/legacy/Zone-div_V8m/zones.py`: `YORKER`: `[0.00, 2.00) m`, `FULL`: `[2.00, 6.00) m`, `GOOD`: `[6.00, 8.00) m`, `SHORT`: `[8.00, 20.90) m`

| Labelled \\ System | `YORKER` | `FULL` | `GOOD` | `SHORT` |
| --- | ---: | ---: | ---: | ---: |
| **`YORKER`** | 0 | 0 | 0 | 0 |
| **`FULL`** | 0 | 3 | 5 | 0 |
| **`GOOD`** | 0 | 0 | 4 | 1 |
| **`SHORT`** | 0 | 0 | 0 | 0 |

Zone agreement: `7/13` (53.8%)

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
1. `c_13f43606` (`pink`, split=`none`): **-4**
2. `c_77d7834d` (`pink`, split=`none`): **-4**
3. `c_e6b5e8a3` (`pink`, split=`none`): **-4**
4. `c_41dd8473` (`pink`, split=`none`): **-3**
5. `c_542fca8b` (`pink`, split=`none`): **-3**

### Release Pixel Distance (px)
1. `c_13f43606` (`pink`, split=`none`): **188.3**
2. `c_a473c3f0` (`pink`, split=`dev`): **185.0**
3. `c_77d7834d` (`pink`, split=`none`): **173.9**
4. `c_e6b5e8a3` (`pink`, split=`none`): **171.8**
5. `c_542fca8b` (`pink`, split=`none`): **158.1**

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
