# Baseline Evaluation Report: `lbw_ui_3`

## 1. Run Info

- **Run name**: `lbw_ui_3`
- **UTC time**: `2026-11-17T13:36:45Z`
- **Git commit**: `8ce0cd4bdb3d995c35543c65e55f3d055b8968bd`
- **Pipeline/worker dirty**: `True`
- **Legacy tracker folder**: `Zone-div_V8m`
- **Ball types in run**: `pink, red, white`
- **Frame alignment**: `57/57` aligned (`0` mismatched excluded, `1` missing results)

## Conventions

- **As reported**: Compares `events.bounce` (`frame`, `x`, `y`, `zone`) in `results.json` directly against the human-labelled bounce centre. Note that the tracker writes the ball bounding-box bottom edge (`y2`) as `events.bounce.y`.
- **Centre vs centre**: Uses the system ball trajectory centre `(x, y)` at `events.bounce.frame` (preferring non-interpolated points; `approx` falls back to the nearest non-interpolated point within `±1` frame; `no_centre` if none exists), and projects both system centre and label centre through the ground-truth homography. Signed errors are `system - label` (`+dx` = right, `+dy` = lower on screen, `+pitch_z_m` = further down pitch toward bowling end).
- **Marker offset**: Signed pixel offset `as_reported_marker - label` (`dx`, `dy`), plus `dy / box_height` using the ball detection bounding-box `height` at `events.bounce.frame` from the detections CSV (expected `~ +0.5` when the marker sits at `y2` and both detect the same ball).
- **Zones**: `label_zone` is classified from the human bounce centre `pitch_z_m` through the GT homography (`Zone-div_V8m/zones.py` thresholds); `system_zone` is `events.bounce.zone` as reported; `system_zone_recomputed` is classified from the system trajectory centre pixel through the GT homography.

## 2. Headline Table (Overall)

| Metric | n | Value |
| --- | ---: | --- |
| Trajectory coverage `[release, impact]` (total / non-interp) | 51 | 72.8% / 72.8% |
| Trajectory coverage `[impact, last_visible]` (total / non-interp) | 51 | 54.2% / 54.2% |
| Release found rate | 57 | 56/57 (98.2%) |
| Release frame error (`0` / `±1` / `±2` frames) | 56 | 58.9% / 82.1% / 85.7% (med\|err\|=0.0, p90=4.5) |
| Release pixel distance (median / p90) | 56 | 3.2 px / 55.0 px |
| **Bounce — As reported**: found rate (excl. unclear) | 57 | 48/57 (84.2%) |
| **Bounce — As reported**: frame error (`0` / `±1` / `±2` frames) | 48 | 70.8% / 85.4% / 85.4% (med\|err\|=0.0, p90=20.0) |
| **Bounce — As reported**: pixel distance (median / p90) | 48 | 8.3 px / 273.2 px |
| **Bounce — As reported**: ground error in metres (median / p90) | 48 | 0.360 m / 4.321 m |
| **Bounce — As reported**: `pitch_z_m` error (signed mean / median abs) | 48 | -0.578 m / 0.360 m |
| **Bounce — As reported**: `pitch_x_m` error (signed mean / median abs) | 48 | -0.136 m / 0.011 m |
| **Bounce — As reported**: system `length_m` minus label `pitch_z_m` (signed mean / median) | 48 | 0.350 m / 0.272 m |
| **Bounce — As reported**: zone agreement | 41 | 85.4% |
| **Bounce — Centre vs centre**: centre availability (`exact` / `approx` / `no_centre`) | 48 | `46` / `0` / `2` |
| **Bounce — Centre vs centre**: frame error (`0` / `±1` / `±2` frames) | 48 | 70.8% / 85.4% / 85.4% (med\|err\|=0.0, p90=20.0) |
| **Bounce — Centre vs centre**: pixel distance (median / p90) | 46 | 3.4 px / 92.0 px |
| **Bounce — Centre vs centre**: signed `dx` (mean / median) | 46 | 3.77 px / -1.30 px |
| **Bounce — Centre vs centre**: signed `dy` (mean / median) | 46 | -14.59 px / -2.05 px |
| **Bounce — Centre vs centre**: ground error in metres (median / p90) | 46 | 0.136 m / 1.795 m |
| **Bounce — Centre vs centre**: `pitch_z_m` error (signed mean / median / median abs) | 46 | -0.750 m / -0.092 m / 0.135 m |
| **Bounce — Centre vs centre**: `pitch_x_m` error (signed mean / median / median abs) | 46 | 0.038 m / -0.008 m / 0.011 m |
| **Bounce — Centre vs centre**: recomputed zone agreement | 46 | 84.8% |
| **Bounce — Marker offset**: signed `dx` (`marker - label`, mean / median) | 48 | -22.46 px / -1.55 px |
| **Bounce — Marker offset**: signed `dy` (`marker - label`, mean / median) | 48 | -9.87 px / 5.50 px |
| **Bounce — Marker offset**: `dy / box_height` (median / mean) | 48 | 0.375 / -1.166 |
| Impact (`events.impact` non-null share) | 57 | 34/57 (59.6%) |
| Impact on contact clips (`events.impact` present) | 51 | 30/51 (58.8%) |
| Impact frame error (`0` / `±1` / `±2` frames) | 30 | 36.7% / 60.0% / 83.3% (signed mean=1.53, med\|err\|=1.0, p90=4.0) |
| Impact pixel distance (median / p90) | 30 | 27.5 px / 105.6 px |
| Deviation candidate (`events.deviation` present on contact clips) | 51 | 43/51 (84.3%) |
| Deviation vs Impact frame error (`0` / `±1` / `±2` frames) | 43 | 11.6% / 39.5% / 62.8% (med\|err\|=2.0, p90=21.4) |
| Deviation vs Impact pixel distance (median / p90) | 43 | 53.0 px / 303.9 px |
| Impact type accuracy | 51 | n/a (system provides no impact type) |
| False-marker rate on labelled `none` (impact / deviation) | 6 | 66.7% / 100.0% |
| LBW | 0 | n/a (not implemented in the system) |
| Runtime per clip (mean / median / p90) | 57 | 14.05 s / 12.62 s / 20.45 s |

## 3. Detail Tables

### 3.1 Breakdown by Ball Colour

| Slice | n (valid / clear) | Cov `[rel,imp]` | Release Found | Rel `±1f` | Rel Med px | Bounce Found | Bnc `±1f` | Bnc Med m (rep / ctr) | Dev on Contact | Dev `±1f` | Dev Med px | Runtime Med |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `pink` | 17 / 17 | 92.1% (n=17) | 17/17 | 94.1% | 13.8 | 17/17 | 100.0% | 0.270 / 0.102 | 17/17 | 47.1% | 40.3 | 10.54s |
| `red` | 38 / 38 | 66.6% (n=32) | 38/38 | 78.9% | 2.3 | 31/38 | 77.4% | 0.499 / 0.157 | 26/32 | 34.6% | 54.4 | 14.36s |
| `white` | 2 / 2 | 7.1% (n=2) | 1/2 | 0.0% | 190.1 | 0/2 | — | — / — | 0/2 | — | — | 6.46s |

### 3.2 Breakdown by Split (`dev` / `final` / `none`)

| Slice | n (valid / clear) | Cov `[rel,imp]` | Release Found | Rel `±1f` | Rel Med px | Bounce Found | Bnc `±1f` | Bnc Med m (rep / ctr) | Dev on Contact | Dev `±1f` | Dev Med px | Runtime Med |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `dev` | 4 / 4 | 95.0% (n=4) | 4/4 | 100.0% | 5.4 | 4/4 | 100.0% | 0.424 / 0.093 | 4/4 | 50.0% | 48.5 | 9.66s |
| `final` | 0 / 0 | — (n=0) | 0/0 | — | — | 0/0 | — | — / — | 0/0 | — | — | — |
| `none` | 53 / 53 | 70.9% (n=47) | 52/53 | 80.8% | 3.2 | 44/53 | 84.1% | 0.360 / 0.142 | 39/47 | 38.5% | 53.0 | 12.64s |

### 3.3 Per-Clip Detail Table

| Clip ID | Ball | Split | Unclear | Rel Err (f / px) | As-rep Bnc (f / px / m) | Centre vs Centre (`status`: `dx`,`dy` / px / m) | Marker Offset (`dx`,`dy` / `dy/h`) | `pitch_z` Err rep/ctr (m) | Zone (`lbl` -> `rep` / `recomp`) | Impact Err (f / px) | Dev vs Imp (f / px) | Runtime (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: |
| `c_0112a3f3` | `red` | `none` | `no` | -1f / 18.5px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | 11.28 |
| `c_045513d5` | `red` | `none` | `no` | 0f / 1.6px | 0f / 10.0px / 0.589m | `exact`: 0.0,3.0 / 3.0px / 0.178m | 0.0,10.0 / 0.77 | 0.589 / 0.178 | `FULL` -> `GOOD` / `GOOD` | 6f / 116.5px | 2f / 40.9px | 11.94 |
| `c_0522189a` | `red` | `none` | `no` | 0f / 1.0px | 0f / 4.1px / 0.227m | `exact`: -1.6,-2.2 / 2.7px / 0.134m | -1.6,3.8 / 0.32 | 0.227 / -0.133 | `GOOD` -> `GOOD` / `GOOD` | -2f / 33.0px | -3f / 53.7px | 11.81 |
| `c_09650a59` | `red` | `none` | `no` | 4f / 55.8px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | 9.11 |
| `c_09a18d5f` | `pink` | `none` | `no` | 2f / 22.7px | 0f / 5.2px / 0.140m | `exact`: -3.2,-1.9 / 3.7px / 0.070m | -3.2,4.1 / 0.37 | 0.139 / -0.067 | `GOOD` -> `GOOD` / `GOOD` | 2f / 74.6px | 0f / 7.1px | 10.54 |
| `c_0e6d3a6d` | `red` | `none` | `no` | 0f / 2.7px | 0f / 3.5px / 0.097m | `exact`: -2.7,-2.8 / 3.9px / 0.121m | -2.7,2.2 / 0.22 | 0.095 / -0.119 | `FULL` -> `FULL` / `FULL` | 2f / 72.8px | 10f / 338.7px | 10.03 |
| `c_0f711886` | `red` | `none` | `no` | 0f / 1.8px | 0f / 10.2px / 0.603m | `exact`: -0.7,4.2 / 4.3px / 0.249m | -0.7,10.2 / 0.85 | 0.603 / 0.249 | `FULL` -> `GOOD` / `FULL` | 2f / 73.4px | 2f / 73.4px | 17.35 |
| `c_13f43606` | `pink` | `none` | `no` | 0f / 19.9px | 0f / 8.1px / 0.375m | `exact`: 0.6,0.1 / 0.6px / 0.006m | 0.6,8.1 / 0.54 | 0.375 / 0.005 | `FULL` -> `GOOD` / `FULL` | 0f / 1.1px | 2f / 81.4px | 8.44 |
| `c_1a22464f` | `red` | `none` | `no` | 0f / 1.1px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | 9.95 |
| `c_1a3657dc` | `red` | `none` | `no` | 0f / 0.9px | 20f / 163.9px / 8.442m | `exact`: -109.4,-127.0 / 167.6px / 8.817m | -109.4,-122.0 / -12.20 | -8.405 / -8.781 | `FULL` -> `—` / `PAST_BAT_CREASE` | none | 24f / 217.4px | 13.88 |
| `c_2c5d337b` | `red` | `none` | `no` | 0f / 1.6px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | 12.24 |
| `c_3089a3bb` | `red` | `none` | `no` | 0f / 1.6px | 0f / 4.2px / 0.182m | `exact`: -3.0,-2.1 / 3.7px / 0.133m | -3.0,2.9 / 0.29 | 0.181 / -0.132 | `GOOD` -> `GOOD` / `GOOD` | present (no-contact) | present (no-contact) | 12.64 |
| `c_314bf724` | `white` | `none` | `no` | 15f / 190.1px | missed | missed | missed | — / — | `GOOD` -> `—` / `—` | none | none | 4.15 |
| `c_34f3913c` | `red` | `none` | `no` | 0f / 2.2px | 0f / 7.9px / 0.530m | `exact`: 1.4,1.8 / 2.3px / 0.123m | 1.4,7.8 / 0.65 | 0.530 / 0.123 | `FULL` -> `FULL` / `FULL` | 2f / 29.0px | 3f / 34.9px | 13.96 |
| `c_363e37eb` | `red` | `none` | `no` | 1f / 4.7px | 0f / 5.2px / 0.308m | `exact`: -1.5,-2.0 / 2.5px / 0.125m | -1.5,5.0 / 0.38 | 0.308 / -0.125 | `FULL` -> `FULL` / `FULL` | 15f / 59.0px | 15f / 59.0px | 17.34 |
| `c_3d27ed64` | `pink` | `dev` | `no` | 0f / 2.2px | 0f / 5.9px / 0.236m | `exact`: -1.9,-2.4 / 3.1px / 0.102m | -1.9,5.6 / 0.37 | 0.235 / -0.102 | `FULL` -> `FULL` / `FULL` | 1f / 31.0px | 3f / 81.0px | 11.30 |
| `c_3f1fc736` | `pink` | `none` | `no` | -1f / 9.8px | 0f / 8.5px / 0.345m | `exact`: -1.1,-1.6 / 1.9px / 0.066m | -1.1,8.4 / 0.44 | 0.345 / -0.066 | `GOOD` -> `GOOD` / `GOOD` | 0f / 2.2px | 2f / 84.8px | 11.70 |
| `c_41dd8473` | `pink` | `none` | `no` | 1f / 15.0px | 0f / 3.8px / 0.125m | `exact`: -1.8,-2.7 / 3.2px / 0.102m | -1.8,3.3 / 0.27 | 0.125 / -0.102 | `GOOD` -> `GOOD` / `GOOD` | 0f / 10.1px | 1f / 17.1px | 14.61 |
| `c_458266f0` | `red` | `none` | `no` | 0f / 2.8px | 0f / 6.3px / 0.230m | `exact`: -2.3,-2.1 / 3.1px / 0.083m | -2.3,5.9 / 0.39 | 0.230 / -0.082 | `FULL` -> `FULL` / `FULL` | 0f / 15.0px | 1f / 9.6px | 8.84 |
| `c_46c688a4` | `red` | `none` | `no` | 0f / 1.9px | 0f / 2.9px / 0.172m | `exact`: -1.1,-2.3 / 2.5px / 0.148m | -1.1,2.7 / 0.27 | 0.172 / -0.147 | `GOOD` -> `GOOD` / `GOOD` | 2f / 60.4px | -1f / 28.9px | 11.35 |
| `c_4af78565` | `red` | `none` | `no` | 14f / 109.3px | 20f / 818.0px / 5.247m | `no_centre` | -818.0,-0.8 / -0.06 | -0.475 / — | `FULL` -> `—` / `—` | none | 0f / 2.5px | 11.28 |
| `c_4b4d9800` | `pink` | `none` | `no` | 1f / 15.5px | 0f / 2.9px / 0.130m | `exact`: 0.0,-5.1 / 5.1px / 0.230m | 0.0,2.9 / 0.18 | 0.130 / -0.230 | `FULL` -> `FULL` / `FULL` | none | 2f / 118.9px | 8.93 |
| `c_4cfd824c` | `red` | `none` | `no` | 0f / 0.4px | -1f / 7.6px / 0.098m | `exact`: -7.5,-5.5 / 9.3px / 0.335m | -7.5,1.5 / 0.12 | 0.086 / -0.331 | `FULL` -> `FULL` / `FULL` | none | present (no-contact) | 12.62 |
| `c_5284da33` | `red` | `none` | `no` | 39f / 445.7px | 30f / 440.7px / 7.831m | `exact`: 430.2,-100.7 / 441.8px / 8.204m | 430.2,-95.7 / -9.57 | -7.063 / -7.467 | `FULL` -> `—` / `PAST_BAT_CREASE` | none | present (no-contact) | 14.38 |
| `c_542fca8b` | `pink` | `none` | `no` | 0f / 10.7px | 0f / 22.2px / 0.912m | `exact`: 3.6,8.9 / 9.6px / 0.373m | 3.6,21.9 / 0.84 | 0.912 / 0.373 | `FULL` -> `FULL` / `FULL` | -1f / 3.3px | -1f / 4.2px | 10.58 |
| `c_58280133` | `red` | `none` | `no` | 0f / 2.1px | 0f / 6.8px / 0.417m | `exact`: -1.6,0.6 / 1.7px / 0.039m | -1.6,6.6 / 0.55 | 0.417 / 0.038 | `GOOD` -> `GOOD` / `GOOD` | 4f / 104.6px | 4f / 104.6px | 15.92 |
| `c_5ca2aea4` | `red` | `none` | `no` | 19f / 105.4px | 27f / 449.8px / 9.156m | `no_centre` | -433.3,-120.6 / -12.06 | -8.624 / — | `FULL` -> `—` / `—` | none | 1f / 25.6px | 17.68 |
| `c_5cef27ce` | `pink` | `dev` | `no` | -1f / 8.5px | 0f / 11.8px / 0.594m | `exact`: -0.7,0.8 / 1.1px / 0.041m | -0.7,11.8 / 0.56 | 0.594 / 0.040 | `FULL` -> `FULL` / `FULL` | 0f / 3.5px | -1f / 15.2px | 15.75 |
| `c_5e5ea872` | `pink` | `dev` | `no` | 0f / 2.3px | 0f / 6.0px / 0.253m | `exact`: 0.3,-2.0 / 2.0px / 0.085m | 0.3,6.0 / 0.40 | 0.253 / -0.085 | `FULL` -> `GOOD` / `FULL` | 0f / 10.4px | 0f / 16.1px | 7.06 |
| `c_6017cc47` | `red` | `none` | `no` | -1f / 14.6px | 0f / 4.9px / 0.174m | `exact`: 0.2,-1.1 / 1.1px / 0.039m | 0.2,4.9 / 0.41 | 0.174 / -0.039 | `FULL` -> `FULL` / `FULL` | none | 2f / 53.0px | 14.34 |
| `c_60748b53` | `red` | `none` | `no` | 1f / 12.3px | 0f / 5.8px / 0.203m | `exact`: -4.7,-2.6 / 5.4px / 0.162m | -4.7,3.4 / 0.28 | 0.201 / -0.160 | `FULL` -> `FULL` / `FULL` | -1f / 7.9px | 0f / 24.3px | 12.57 |
| `c_62cb3c5e` | `red` | `none` | `no` | 0f / 1.5px | 12f / 233.9px / 3.924m | `exact`: 225.9,-65.5 / 235.2px / 4.233m | 225.9,-60.5 / -6.72 | -3.633 / -3.963 | `FULL` -> `—` / `YORKER` | none | 23f / 581.6px | 17.89 |
| `c_639d3baa` | `pink` | `none` | `no` | 1f / 16.4px | 0f / 5.4px / 0.243m | `exact`: -0.7,-2.6 / 2.7px / 0.117m | -0.7,5.4 / 0.34 | 0.243 / -0.117 | `FULL` -> `FULL` / `FULL` | 1f / 39.7px | 2f / 55.2px | 8.14 |
| `c_663067dc` | `pink` | `none` | `no` | 0f / 3.2px | 0f / 5.4px / 0.207m | `exact`: -0.1,-2.6 / 2.6px / 0.100m | -0.1,5.4 / 0.36 | 0.207 / -0.100 | `FULL` -> `FULL` / `FULL` | 0f / 5.5px | 3f / 40.3px | 11.67 |
| `c_69ba9415` | `red` | `none` | `no` | 2f / 36.1px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | 11.93 |
| `c_6e281881` | `red` | `none` | `no` | 0f / 2.3px | -1f / 15.1px / 0.512m | `exact`: -8.6,6.4 / 10.7px / 0.269m | -8.6,12.4 / 1.03 | 0.509 / 0.264 | `FULL` -> `FULL` / `FULL` | none | 24f / 159.4px | 13.47 |
| `c_75de2445` | `white` | `none` | `no` | missed | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | 8.78 |
| `c_77509418` | `red` | `none` | `no` | 0f / 0.8px | 1f / 10.1px / 0.065m | `exact`: -10.1,-6.8 / 12.2px / 0.421m | -10.1,0.2 / 0.01 | 0.006 / -0.417 | `GOOD` -> `GOOD` / `GOOD` | 0f / 18.5px | 1f / 52.0px | 17.29 |
| `c_77d7834d` | `pink` | `none` | `no` | 0f / 13.8px | -1f / 9.6px / 0.270m | `exact`: -5.5,1.9 / 5.8px / 0.071m | -5.5,7.9 / 0.66 | 0.267 / 0.062 | `GOOD` -> `GOOD` / `GOOD` | 1f / 47.1px | 2f / 79.6px | 8.95 |
| `c_7f64dd0c` | `red` | `none` | `no` | 0f / 1.4px | -1f / 12.2px / 0.761m | `exact`: 0.3,6.2 / 6.2px / 0.388m | 0.3,12.2 / 1.11 | 0.761 / 0.388 | `FULL` -> `FULL` / `FULL` | present (no-contact) | present (no-contact) | 14.75 |
| `c_823ebcd1` | `red` | `none` | `no` | 0f / 2.7px | 0f / 8.4px / 0.518m | `exact`: -0.9,2.4 / 2.6px / 0.148m | -0.9,8.4 / 0.70 | 0.517 / 0.148 | `FULL` -> `FULL` / `FULL` | 0f / 6.4px | 0f / 6.4px | 20.65 |
| `c_865b0a59` | `pink` | `none` | `no` | -1f / 33.7px | 0f / 10.6px / 0.434m | `exact`: 2.5,1.3 / 2.8px / 0.056m | 2.5,10.3 / 0.61 | 0.434 / 0.055 | `FULL` -> `FULL` / `FULL` | 1f / 26.0px | 1f / 20.5px | 9.53 |
| `c_8e93d6d9` | `red` | `none` | `no` | 0f / 1.0px | 0f / 3.7px / 0.170m | `exact`: 0.0,-2.3 / 2.3px / 0.106m | 0.0,3.7 / 0.31 | 0.170 / -0.106 | `FULL` -> `FULL` / `FULL` | none | 6f / 325.5px | 9.45 |
| `c_a473c3f0` | `pink` | `dev` | `no` | 1f / 14.4px | -1f / 20.8px / 0.723m | `exact`: -14.3,8.1 / 16.4px / 0.396m | -14.3,15.1 / 1.08 | 0.719 / 0.389 | `FULL` -> `FULL` / `FULL` | 0f / 3.4px | 3f / 114.1px | 8.01 |
| `c_b0c1cf14` | `pink` | `none` | `no` | 0f / 5.7px | 0f / 6.4px / 0.282m | `exact`: 0.4,-2.6 / 2.6px / 0.115m | 0.4,6.4 / 0.38 | 0.282 / -0.115 | `FULL` -> `GOOD` / `FULL` | 2f / 151.7px | -1f / 8.7px | 6.14 |
| `c_be3c00d2` | `red` | `none` | `no` | 0f / 1.5px | 41f / 444.6px / 3.098m | `exact`: -443.6,-36.5 / 445.1px / 3.169m | -443.6,-30.5 / -2.54 | -0.867 / -1.073 | `GOOD` -> `—` / `FULL` | none | 49f / 599.6px | 19.06 |
| `c_c1faf433` | `red` | `none` | `no` | 0f / 1.4px | -1f / 18.1px / 0.574m | `exact`: 9.2,8.6 / 12.6px / 0.321m | 9.2,15.6 / 1.11 | 0.571 / 0.316 | `FULL` -> `GOOD` / `FULL` | none | -2f / 60.8px | 16.17 |
| `c_c576b682` | `red` | `none` | `no` | -1f / 6.2px | 23f / 365.1px / 12.919m | `exact`: 142.3,-341.2 / 369.7px / 13.133m | 142.3,-336.2 / -33.62 | -12.873 / -13.087 | `FULL` -> `—` / `PAST_BAT_CREASE` | none | 27f / 333.8px | 28.08 |
| `c_c900737d` | `red` | `none` | `no` | 0f / 1.0px | 0f / 3.3px / 0.169m | `exact`: -2.0,-2.4 / 3.1px / 0.157m | -2.0,2.6 / 0.26 | 0.168 / -0.156 | `GOOD` -> `GOOD` / `FULL` | present (no-contact) | present (no-contact) | 20.31 |
| `c_dd85ffc4` | `red` | `none` | `no` | 0f / 3.3px | 0f / 9.4px / 0.499m | `exact`: -4.6,1.2 / 4.8px / 0.076m | -4.6,8.2 / 0.63 | 0.498 / 0.071 | `FULL` -> `FULL` / `FULL` | present (no-contact) | present (no-contact) | 23.59 |
| `c_e4d991bf` | `red` | `none` | `no` | 0f / 2.5px | 0f / 3.6px / 0.164m | `exact`: -2.6,-2.5 / 3.6px / 0.167m | -2.6,2.5 / 0.25 | 0.163 / -0.166 | `FULL` -> `FULL` / `FULL` | 4f / 114.4px | 1f / 30.6px | 27.10 |
| `c_e6b5e8a3` | `pink` | `none` | `no` | 1f / 22.1px | 0f / 11.5px / 0.489m | `exact`: -0.1,2.5 / 2.5px / 0.107m | -0.1,11.5 / 0.64 | 0.489 / 0.107 | `FULL` -> `FULL` / `FULL` | 0f / 8.9px | 1f / 39.1px | 16.67 |
| `c_f31728c7` | `pink` | `none` | `no` | 0f / 1.6px | 0f / 7.5px / 0.270m | `exact`: -1.6,-3.7 / 4.0px / 0.137m | -1.6,7.3 / 0.35 | 0.270 / -0.137 | `FULL` -> `FULL` / `FULL` | 4f / 43.7px | 4f / 43.7px | 19.68 |
| `c_f4592060` | `red` | `none` | `no` | 40f / 172.5px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | 26.42 |
| `c_f4e30475` | `red` | `none` | `no` | 5f / 54.2px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | -8f / 61.0px | 19.69 |
| `c_f51f593e` | `red` | `none` | `no` | 0f / 1.5px | 0f / 10.4px / 0.472m | `exact`: -1.9,3.2 / 3.7px / 0.149m | -1.9,10.2 / 0.73 | 0.472 / 0.148 | `GOOD` -> `GOOD` / `GOOD` | 1f / 23.5px | 2f / 55.0px | 24.79 |
| `c_f784a9d7` | `white` | `none` | `no` | missed | missed | missed | missed | — / — | `—` -> `—` / `—` | none | none | — |
| `c_fe67d2d6` | `red` | `none` | `no` | 3f / 26.3px | 0f / 8.7px / 0.518m | `exact`: -2.1,2.4 / 3.2px / 0.148m | -2.1,8.4 / 0.76 | 0.518 / 0.148 | `FULL` -> `FULL` / `FULL` | none | 1f / 19.8px | 19.27 |

### 3.4 Bounce Zone Agreement & Confusion Matrix (Recomputed from System Centre)

Thresholds loaded at runtime from `backend/worker/legacy/Zone-div_V8m/zones.py`: `YORKER`: `[0.00, 2.00) m`, `FULL`: `[2.00, 6.00) m`, `GOOD`: `[6.00, 8.00) m`, `SHORT`: `[8.00, 20.90) m`

- **System zone (as reported) agreement**: `35/41` (85.4%)
- **System zone (recomputed from system centre) agreement**: `39/46` (84.8%)

| Labelled \\ System Recomputed | `YORKER` | `FULL` | `GOOD` | `SHORT` | `PAST_BAT_CREASE` |
| --- | ---: | ---: | ---: | ---: | ---: |
| **`YORKER`** | 0 | 0 | 0 | 0 | 0 |
| **`FULL`** | 1 | 29 | 1 | 0 | 3 |
| **`GOOD`** | 0 | 2 | 10 | 0 | 0 |
| **`SHORT`** | 0 | 0 | 0 | 0 | 0 |
| **`PAST_BAT_CREASE`** | 0 | 0 | 0 | 0 | 0 |

### 3.5 Calibration Quality of the Labels

- **Total clips scored**: `58`
- **Both stumps derived (`0` confirmed)**: `0`
- **One stump confirmed (`1` confirmed)**: `0`
- **Both stumps confirmed (`2` confirmed)**: `58`
- **Homography `residual_px` (n=58)**: mean=1.25 px, max=3.99 px

### 3.6 Clips Flagged `unclear`

Clips with the `unclear` flag are included in Release metrics, excluded from Bounce and Impact tolerance/error tables, and listed below:

_No clips had the `unclear` flag in this run._

## 4. Worst 5 Clips per Metric

### Release Frame Error (frames)
1. `c_f4592060` (`red`, split=`none`): **40**
2. `c_5284da33` (`red`, split=`none`): **39**
3. `c_5ca2aea4` (`red`, split=`none`): **19**
4. `c_314bf724` (`white`, split=`none`): **15**
5. `c_4af78565` (`red`, split=`none`): **14**

### Release Pixel Distance (px)
1. `c_5284da33` (`red`, split=`none`): **445.7**
2. `c_314bf724` (`white`, split=`none`): **190.1**
3. `c_f4592060` (`red`, split=`none`): **172.5**
4. `c_4af78565` (`red`, split=`none`): **109.3**
5. `c_5ca2aea4` (`red`, split=`none`): **105.4**

### Bounce Frame Error (frames, excl. unclear)
1. `c_be3c00d2` (`red`, split=`none`): **41**
2. `c_5284da33` (`red`, split=`none`): **30**
3. `c_5ca2aea4` (`red`, split=`none`): **27**
4. `c_c576b682` (`red`, split=`none`): **23**
5. `c_1a3657dc` (`red`, split=`none`): **20**

### Bounce Ground Error (m, excl. unclear)
1. `c_c576b682` (`red`, split=`none`): **12.919**
2. `c_5ca2aea4` (`red`, split=`none`): **9.156**
3. `c_1a3657dc` (`red`, split=`none`): **8.442**
4. `c_5284da33` (`red`, split=`none`): **7.831**
5. `c_4af78565` (`red`, split=`none`): **5.247**

### Deviation vs Impact Frame Error (frames, excl. unclear)
1. `c_be3c00d2` (`red`, split=`none`): **49**
2. `c_c576b682` (`red`, split=`none`): **27**
3. `c_1a3657dc` (`red`, split=`none`): **24**
4. `c_6e281881` (`red`, split=`none`): **24**
5. `c_62cb3c5e` (`red`, split=`none`): **23**

### Deviation vs Impact Pixel Distance (px, excl. unclear)
1. `c_be3c00d2` (`red`, split=`none`): **599.6**
2. `c_62cb3c5e` (`red`, split=`none`): **581.6**
3. `c_0e6d3a6d` (`red`, split=`none`): **338.7**
4. `c_c576b682` (`red`, split=`none`): **333.8**
5. `c_8e93d6d9` (`red`, split=`none`): **325.5**

## 5. Caveats

- **Small sample sizes**: The current baseline evaluation set has a small number of final clips; percentile estimates (`p90`) and subgroup breakdowns (`ball_colour`, `split`) have high variance until more clips are annotated.
- **Labels made blind to the pipeline**: Ground-truth labels (`release`, `bounce`, `impact`, `calibration_gt`) were annotated independently in the annotator UI without inspecting pipeline predictions.
- **30 fps temporal resolution limits**: At ~30 fps (~33.3 ms per frame), a fast delivery travels ~0.9–1.2 m between consecutive frames. A 1-frame sampling difference near bounce or impact naturally introduces 0.5–1.2 m of along-pitch distance difference even when pixel localization is accurate.
- **Legacy `zones.py` length bug (`19.68 m` vs `17.68 m`)**: The legacy tracker sets `BOWL_CREASE_Y = 1.22 + 19.68 = 20.90 m` instead of the regulation `1.22 + 17.68 = 18.90 m` (`calib_constants.py`), systematically inflating `system.bounce.length_m` relative to true `pitch_z_m`.
