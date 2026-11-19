# Baseline Evaluation Report: `track_1`

## 1. Run Info

- **Run name**: `track_1`
- **UTC time**: `2026-11-19T19:37:15Z`
- **Git commit**: `unknown`
- **Pipeline/worker dirty**: `False`
- **Legacy tracker folder**: `Zone-div_V8m`
- **Ball types in run**: `none`
- **Frame alignment**: `55/55` aligned (`0` mismatched excluded, `0` missing results)

## Conventions

- **As reported**: Compares `events.bounce` (`frame`, `x`, `y`, `zone`) in `results.json` directly against the human-labelled bounce centre. Note that the tracker writes the ball bounding-box bottom edge (`y2`) as `events.bounce.y`.
- **Centre vs centre**: Uses the system ball trajectory centre `(x, y)` at `events.bounce.frame` (preferring non-interpolated points; `approx` falls back to the nearest non-interpolated point within `±1` frame; `no_centre` if none exists), and projects both system centre and label centre through the ground-truth homography. Signed errors are `system - label` (`+dx` = right, `+dy` = lower on screen, `+pitch_z_m` = further down pitch toward bowling end).
- **Marker offset**: Signed pixel offset `as_reported_marker - label` (`dx`, `dy`), plus `dy / box_height` using the ball detection bounding-box `height` at `events.bounce.frame` from the detections CSV (expected `~ +0.5` when the marker sits at `y2` and both detect the same ball).
- **Zones**: `label_zone` is classified from the human bounce centre `pitch_z_m` through the GT homography (`Zone-div_V8m/zones.py` thresholds); `system_zone` is `events.bounce.zone` as reported; `system_zone_recomputed` is classified from the system trajectory centre pixel through the GT homography.

## 2. Headline Table (Overall)

| Metric | n | Value |
| --- | ---: | --- |
| Trajectory coverage `[release, impact]` (total / non-interp) | 49 | 75.5% / 75.5% |
| Trajectory coverage `[impact, last_visible]` (total / non-interp) | 49 | 61.0% / 61.0% |
| Release found rate | 55 | 55/55 (100.0%) |
| Release frame error (`0` / `±1` / `±2` frames) | 55 | 45.5% / 63.6% / 74.5% (med\|err\|=1.0, p90=4.0) |
| Release pixel distance (median / p90) | 55 | 7.1 px / 75.5 px |
| **Bounce — As reported**: found rate (excl. unclear) | 55 | 38/55 (69.1%) |
| **Bounce — As reported**: frame error (`0` / `±1` / `±2` frames) | 38 | 63.2% / 92.1% / 100.0% (med\|err\|=0.0, p90=1.0) |
| **Bounce — As reported**: pixel distance (median / p90) | 38 | 7.2 px / 25.2 px |
| **Bounce — As reported**: ground error in metres (median / p90) | 38 | 0.337 m / 0.896 m |
| **Bounce — As reported**: `pitch_z_m` error (signed mean / median abs) | 38 | 0.094 m / 0.329 m |
| **Bounce — As reported**: `pitch_x_m` error (signed mean / median abs) | 38 | -0.003 m / 0.015 m |
| **Bounce — As reported**: system `length_m` minus label `pitch_z_m` (signed mean / median) | 38 | 0.098 m / 0.102 m |
| **Bounce — As reported**: zone agreement | 38 | 84.2% |
| **Bounce — Centre vs centre**: centre availability (`exact` / `approx` / `no_centre`) | 38 | `35` / `3` / `0` |
| **Bounce — Centre vs centre**: frame error (`0` / `±1` / `±2` frames) | 38 | 63.2% / 92.1% / 100.0% (med\|err\|=0.0, p90=1.0) |
| **Bounce — Centre vs centre**: pixel distance (median / p90) | 38 | 3.3 px / 29.1 px |
| **Bounce — Centre vs centre**: signed `dx` (mean / median) | 38 | -0.26 px / -0.35 px |
| **Bounce — Centre vs centre**: signed `dy` (mean / median) | 38 | -4.25 px / -2.15 px |
| **Bounce — Centre vs centre**: ground error in metres (median / p90) | 38 | 0.150 m / 1.253 m |
| **Bounce — Centre vs centre**: `pitch_z_m` error (signed mean / median / median abs) | 38 | -0.255 m / -0.092 m / 0.148 m |
| **Bounce — Centre vs centre**: `pitch_x_m` error (signed mean / median / median abs) | 38 | -0.002 m / -0.002 m / 0.013 m |
| **Bounce — Centre vs centre**: recomputed zone agreement | 38 | 86.8% |
| **Bounce — Marker offset**: signed `dx` (`marker - label`, mean / median) | 38 | -0.55 px / 0.28 px |
| **Bounce — Marker offset**: signed `dy` (`marker - label`, mean / median) | 38 | 2.31 px / 2.25 px |
| **Bounce — Marker offset**: `dy / box_height` (median / mean) | 0 | — / — |
| Impact (`events.impact` non-null share) | 55 | 29/55 (52.7%) |
| Impact on contact clips (`events.impact` present) | 49 | 28/49 (57.1%) |
| Impact frame error (`0` / `±1` / `±2` frames) | 28 | 32.1% / 75.0% / 82.1% (signed mean=0.68, med\|err\|=1.0, p90=4.6) |
| Impact pixel distance (median / p90) | 28 | 33.9 px / 90.3 px |
| Deviation candidate (`events.deviation` present on contact clips) | 49 | 0/49 (0.0%) |
| Deviation vs Impact frame error (`0` / `±1` / `±2` frames) | 0 | — / — / — (med\|err\|=—, p90=—) |
| Deviation vs Impact pixel distance (median / p90) | 0 | — / — |
| Impact type accuracy | 49 | n/a (system provides no impact type) |
| False-marker rate on labelled `none` (impact / deviation) | 6 | 16.7% / 0.0% |
| LBW | 0 | n/a (not implemented in the system) |
| Runtime per clip (mean / median / p90) | 0 | — / — / — |

## 3. Detail Tables

### 3.1 Breakdown by Ball Colour

| Slice | n (valid / clear) | Cov `[rel,imp]` | Release Found | Rel `±1f` | Rel Med px | Bounce Found | Bnc `±1f` | Bnc Med m (rep / ctr) | Dev on Contact | Dev `±1f` | Dev Med px | Runtime Med |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `pink` | 17 / 17 | 93.0% (n=17) | 17/17 | 82.4% | 13.1 | 17/17 | 88.2% | 0.203 / 0.100 | 0/17 | — | — | — |
| `red` | 38 / 38 | 66.2% (n=32) | 38/38 | 55.3% | 6.1 | 21/38 | 95.2% | 0.400 / 0.164 | 0/32 | — | — | — |
| `white` | 0 / 0 | — (n=0) | 0/0 | — | — | 0/0 | — | — / — | 0/0 | — | — | — |

### 3.2 Breakdown by Split (`dev` / `final` / `none`)

| Slice | n (valid / clear) | Cov `[rel,imp]` | Release Found | Rel `±1f` | Rel Med px | Bounce Found | Bnc `±1f` | Bnc Med m (rep / ctr) | Dev on Contact | Dev `±1f` | Dev Med px | Runtime Med |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `dev` | 4 / 4 | 96.7% (n=4) | 4/4 | 100.0% | 7.7 | 4/4 | 100.0% | 0.366 / 0.072 | 0/4 | — | — | — |
| `final` | 0 / 0 | — (n=0) | 0/0 | — | — | 0/0 | — | — / — | 0/0 | — | — | — |
| `none` | 51 / 51 | 73.6% (n=45) | 51/51 | 60.8% | 7.1 | 34/51 | 91.2% | 0.337 / 0.154 | 0/45 | — | — | — |

### 3.3 Per-Clip Detail Table

| Clip ID | Ball | Split | Unclear | Rel Err (f / px) | As-rep Bnc (f / px / m) | Centre vs Centre (`status`: `dx`,`dy` / px / m) | Marker Offset (`dx`,`dy` / `dy/h`) | `pitch_z` Err rep/ctr (m) | Zone (`lbl` -> `rep` / `recomp`) | Impact Err (f / px) | Dev vs Imp (f / px) | Runtime (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: |
| `c_0112a3f3` | `red` | `none` | `no` | -1f / 18.5px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | — |
| `c_045513d5` | `red` | `none` | `no` | 0f / 1.6px | 0f / 13.0px / 0.754m | `exact`: 1.0,3.0 / 3.2px / 0.178m | -1.8,12.8 / — | 0.754 / 0.178 | `FULL` -> `GOOD` / `GOOD` | 6f / 110.2px | none | — |
| `c_0522189a` | `red` | `none` | `no` | 3f / 44.7px | 0f / 1.5px / 0.067m | `exact`: -0.6,-2.2 / 2.3px / 0.133m | 1.1,1.1 / — | 0.066 / -0.133 | `GOOD` -> `GOOD` / `GOOD` | -1f / 33.6px | none | — |
| `c_09650a59` | `red` | `none` | `no` | 0f / 1.4px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | — |
| `c_09a18d5f` | `pink` | `none` | `no` | 1f / 31.9px | 0f / 2.7px / 0.090m | `exact`: -2.2,-1.9 / 2.9px / 0.068m | -0.7,-2.6 / — | -0.090 / -0.066 | `GOOD` -> `GOOD` / `GOOD` | 1f / 54.8px | none | — |
| `c_0e6d3a6d` | `red` | `none` | `no` | 0f / 2.7px | -1f / 5.4px / 0.072m | `exact`: -5.7,-2.8 / 6.4px / 0.126m | -5.2,-1.5 / — | -0.061 / -0.119 | `FULL` -> `FULL` / `FULL` | 2f / 77.0px | none | — |
| `c_0f711886` | `red` | `none` | `no` | 0f / 1.8px | 0f / 10.8px / 0.640m | `exact`: -0.7,4.2 / 4.3px / 0.249m | 0.9,10.8 / — | 0.640 / 0.249 | `FULL` -> `GOOD` / `FULL` | 3f / 81.3px | none | — |
| `c_13f43606` | `pink` | `none` | `no` | -1f / 18.8px | 0f / 5.4px / 0.167m | `exact`: 0.6,0.1 / 0.6px / 0.006m | 4.1,3.6 / — | 0.166 / 0.005 | `FULL` -> `GOOD` / `FULL` | 0f / 22.3px | none | — |
| `c_1a22464f` | `red` | `none` | `no` | 0f / 1.1px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | — |
| `c_1a3657dc` | `red` | `none` | `no` | 2f / 9.9px | 0f / 4.7px / 0.108m | `exact`: -1.4,1.0 / 1.7px / 0.062m | -4.4,1.7 / — | 0.105 / 0.061 | `FULL` -> `FULL` / `FULL` | 6f / 80.6px | none | — |
| `c_2c5d337b` | `red` | `none` | `no` | 4f / 6.0px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | — |
| `c_3089a3bb` | `red` | `none` | `no` | 3f / 36.2px | 0f / 2.8px / 0.160m | `approx`: -12.0,-16.1 / 20.1px / 1.023m | -1.2,2.6 / — | 0.160 / -1.020 | `GOOD` -> `GOOD` / `GOOD` | present (no-contact) | none | — |
| `c_34f3913c` | `red` | `none` | `no` | 2f / 7.1px | 0f / 8.3px / 0.551m | `exact`: 2.4,1.8 / 3.0px / 0.124m | 1.7,8.1 / — | 0.551 / 0.123 | `FULL` -> `FULL` / `FULL` | 1f / 18.9px | none | — |
| `c_363e37eb` | `red` | `none` | `no` | 3f / 7.8px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | — |
| `c_3d27ed64` | `pink` | `dev` | `no` | 1f / 6.9px | 0f / 3.8px / 0.033m | `exact`: -1.9,-1.4 / 2.4px / 0.060m | -3.8,-0.6 / — | -0.025 / -0.059 | `FULL` -> `FULL` / `FULL` | 1f / 31.8px | none | — |
| `c_3f1fc736` | `pink` | `none` | `no` | 0f / 4.9px | 0f / 5.2px / 0.209m | `exact`: -0.1,-1.6 / 1.6px / 0.066m | 1.2,5.1 / — | 0.209 / -0.066 | `GOOD` -> `GOOD` / `GOOD` | -1f / 13.5px | none | — |
| `c_41dd8473` | `pink` | `none` | `no` | 0f / 2.2px | 1f / 3.2px / 0.092m | `exact`: 5.2,-9.7 / 11.0px / 0.370m | 2.1,2.4 / — | 0.091 / -0.368 | `GOOD` -> `GOOD` / `GOOD` | 0f / 20.9px | none | — |
| `c_458266f0` | `red` | `none` | `no` | 0f / 2.8px | 0f / 16.7px / 0.275m | `exact`: -2.3,-2.1 / 3.1px / 0.083m | 15.4,-6.6 / — | -0.259 / -0.082 | `FULL` -> `FULL` / `FULL` | none | none | — |
| `c_46c688a4` | `red` | `none` | `no` | 2f / 12.7px | 0f / 6.7px / 0.400m | `exact`: -1.1,-2.3 / 2.5px / 0.148m | -2.4,-6.2 / — | -0.400 / -0.147 | `GOOD` -> `GOOD` / `GOOD` | 1f / 28.1px | none | — |
| `c_4af78565` | `red` | `none` | `no` | 13f / 92.7px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | — |
| `c_4b4d9800` | `pink` | `none` | `no` | -3f / 113.0px | -2f / 12.6px / 0.569m | `exact`: 12.0,-30.1 / 32.4px / 1.372m | 0.4,-12.6 / — | -0.569 / -1.370 | `FULL` -> `FULL` / `FULL` | 4f / 127.6px | none | — |
| `c_4cfd824c` | `red` | `none` | `no` | 0f / 0.4px | -1f / 13.7px / 0.664m | `exact`: -6.5,-5.5 / 8.5px / 0.334m | -8.3,-11.0 / — | -0.662 / -0.331 | `FULL` -> `FULL` / `FULL` | none | none | — |
| `c_5284da33` | `red` | `none` | `no` | 31f / 266.0px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | — |
| `c_542fca8b` | `pink` | `none` | `no` | -1f / 22.5px | 0f / 19.8px / 0.820m | `exact`: 4.6,8.9 / 10.0px / 0.373m | 2.1,19.7 / — | 0.820 / 0.373 | `FULL` -> `FULL` / `FULL` | 0f / 34.2px | none | — |
| `c_58280133` | `red` | `none` | `no` | 0f / 1.9px | -1f / 27.0px / 1.665m | `exact`: -8.6,-21.4 / 23.1px / 1.385m | -8.3,-25.6 / — | -1.664 / -1.384 | `GOOD` -> `FULL` / `FULL` | -6f / 120.0px | none | — |
| `c_5ca2aea4` | `red` | `none` | `no` | 18f / 90.7px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | — |
| `c_5cef27ce` | `pink` | `dev` | `no` | -1f / 8.5px | 0f / 11.5px / 0.578m | `exact`: 0.3,0.8 / 0.9px / 0.041m | -0.3,11.5 / — | 0.578 / 0.041 | `FULL` -> `FULL` / `FULL` | 0f / 34.8px | none | — |
| `c_5e5ea872` | `pink` | `dev` | `no` | 0f / 2.3px | 0f / 4.8px / 0.153m | `exact`: 0.3,-2.0 / 2.0px / 0.085m | 3.2,3.6 / — | 0.152 / -0.085 | `FULL` -> `FULL` / `FULL` | 0f / 11.4px | none | — |
| `c_6017cc47` | `red` | `none` | `no` | -1f / 14.6px | 0f / 1.6px / 0.055m | `exact`: 0.2,-1.1 / 1.1px / 0.039m | 0.2,1.5 / — | 0.055 / -0.039 | `FULL` -> `FULL` / `FULL` | 0f / 34.4px | none | — |
| `c_60748b53` | `red` | `none` | `no` | 0f / 0.4px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | — |
| `c_62cb3c5e` | `red` | `none` | `no` | 2f / 16.5px | 1f / 7.4px / 0.399m | `exact`: 5.9,-2.5 / 6.4px / 0.151m | 3.4,6.6 / — | 0.398 / -0.147 | `FULL` -> `FULL` / `FULL` | 0f / 20.4px | none | — |
| `c_639d3baa` | `pink` | `none` | `no` | 0f / 5.5px | 1f / 18.1px / 0.203m | `approx`: -0.7,-2.6 / 2.7px / 0.117m | 17.7,3.9 / — | 0.174 / -0.117 | `FULL` -> `FULL` / `FULL` | none | none | — |
| `c_663067dc` | `pink` | `none` | `no` | 0f / 3.2px | 0f / 2.4px / 0.080m | `exact`: -0.1,-2.6 / 2.6px / 0.100m | 1.2,2.1 / — | 0.080 / -0.100 | `FULL` -> `FULL` / `FULL` | 1f / 24.4px | none | — |
| `c_69ba9415` | `red` | `none` | `no` | 2f / 36.2px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | — |
| `c_6e281881` | `red` | `none` | `no` | 0f / 2.3px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | — |
| `c_77509418` | `red` | `none` | `no` | 0f / 0.8px | 1f / 4.6px / 0.030m | `exact`: -10.1,-6.8 / 12.2px / 0.421m | -4.6,0.1 / — | 0.006 / -0.417 | `GOOD` -> `GOOD` / `GOOD` | 0f / 32.1px | none | — |
| `c_77d7834d` | `pink` | `none` | `no` | -1f / 14.9px | 0f / 3.0px / 0.063m | `exact`: 1.5,-5.1 / 5.3px / 0.175m | 2.5,1.8 / — | 0.061 / -0.175 | `GOOD` -> `GOOD` / `GOOD` | 1f / 34.2px | none | — |
| `c_7f64dd0c` | `red` | `none` | `no` | 7f / 38.1px | 0f / 24.5px / 1.505m | `exact`: 0.3,3.2 / 3.2px / 0.201m | 2.8,24.3 / — | 1.505 / 0.201 | `FULL` -> `FULL` / `FULL` | none | none | — |
| `c_823ebcd1` | `red` | `none` | `no` | 0f / 2.7px | -1f / 2.8px / 0.172m | `approx`: -5.9,-44.6 / 45.0px / 2.862m | -0.4,-2.8 / — | -0.172 / -2.862 | `FULL` -> `FULL` / `YORKER` | -1f / 7.2px | none | — |
| `c_865b0a59` | `pink` | `none` | `no` | -2f / 52.7px | 0f / 22.6px / 0.850m | `exact`: 2.5,2.3 / 3.4px / 0.098m | 10.2,20.2 / — | 0.848 / 0.097 | `FULL` -> `FULL` / `FULL` | 1f / 23.7px | none | — |
| `c_8e93d6d9` | `red` | `none` | `no` | 0f / 1.0px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | — |
| `c_a473c3f0` | `pink` | `dev` | `no` | 0f / 13.1px | 0f / 22.3px / 1.003m | `exact`: -2.3,6.1 / 6.5px / 0.291m | -7.0,21.2 / — | 1.003 / 0.290 | `FULL` -> `FULL` / `FULL` | 1f / 50.1px | none | — |
| `c_b0c1cf14` | `pink` | `none` | `no` | -1f / 30.4px | 0f / 2.0px / 0.015m | `exact`: 1.4,-2.6 / 3.0px / 0.115m | 1.9,0.2 / — | 0.011 / -0.115 | `FULL` -> `FULL` / `FULL` | -2f / 81.8px | none | — |
| `c_be3c00d2` | `red` | `none` | `no` | 0f / 1.5px | missed | missed | missed | — / — | `GOOD` -> `—` / `—` | none | none | — |
| `c_c1faf433` | `red` | `none` | `no` | 0f / 1.4px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | — |
| `c_c576b682` | `red` | `none` | `no` | -1f / 6.2px | -1f / 28.3px / 0.548m | `exact`: 7.3,35.8 / 36.5px / 1.202m | -23.8,15.2 / — | 0.524 / 1.201 | `FULL` -> `GOOD` / `GOOD` | none | none | — |
| `c_c900737d` | `red` | `none` | `no` | 0f / 1.0px | 0f / 7.0px / 0.437m | `exact`: -2.0,-2.4 / 3.1px / 0.157m | 1.9,6.8 / — | 0.436 / -0.156 | `GOOD` -> `GOOD` / `FULL` | none | none | — |
| `c_dd85ffc4` | `red` | `none` | `no` | 0f / 3.0px | 2f / 46.6px / 2.580m | `exact`: 24.4,-34.8 / 42.5px / 2.186m | 22.4,-40.8 / — | -2.575 / -2.180 | `FULL` -> `YORKER` / `FULL` | none | none | — |
| `c_e4d991bf` | `red` | `none` | `no` | 3f / 40.2px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | — |
| `c_e6b5e8a3` | `pink` | `none` | `no` | -3f / 94.8px | -1f / 18.0px / 0.720m | `exact`: -0.1,-0.5 / 0.5px / 0.021m | -6.0,16.9 / — | 0.720 / -0.021 | `FULL` -> `FULL` / `FULL` | 1f / 73.9px | none | — |
| `c_f31728c7` | `pink` | `none` | `no` | 0f / 1.6px | -2f / 40.0px / 0.820m | `exact`: -12.6,-24.7 / 27.7px / 0.925m | -33.9,-21.3 / — | -0.793 / -0.921 | `FULL` -> `FULL` / `FULL` | none | none | — |
| `c_f4592060` | `red` | `none` | `no` | 39f / 172.2px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | — |
| `c_f4e30475` | `red` | `none` | `no` | 4f / 52.5px | missed | missed | missed | — / — | `FULL` -> `—` / `—` | none | none | — |
| `c_f51f593e` | `red` | `none` | `no` | 0f / 1.5px | 0f / 14.8px / 0.658m | `exact`: -0.9,3.2 / 3.3px / 0.148m | -3.8,14.2 / — | 0.658 / 0.148 | `GOOD` -> `GOOD` / `GOOD` | 0f / 13.2px | none | — |
| `c_fe67d2d6` | `red` | `none` | `no` | 3f / 26.3px | -1f / 2.1px / 0.084m | `exact`: -2.1,-2.6 / 3.3px / 0.164m | -1.6,1.3 / — | 0.083 / -0.163 | `FULL` -> `FULL` / `FULL` | none | none | — |

### 3.4 Bounce Zone Agreement & Confusion Matrix (Recomputed from System Centre)

Thresholds loaded at runtime from `backend/worker/legacy/Zone-div_V8m/zones.py`: `YORKER`: `[0.00, 2.00) m`, `FULL`: `[2.00, 6.00) m`, `GOOD`: `[6.00, 8.00) m`, `SHORT`: `[8.00, 20.90) m`

- **System zone (as reported) agreement**: `32/38` (84.2%)
- **System zone (recomputed from system centre) agreement**: `33/38` (86.8%)

| Labelled \\ System Recomputed | `YORKER` | `FULL` | `GOOD` | `SHORT` |
| --- | ---: | ---: | ---: | ---: |
| **`YORKER`** | 0 | 0 | 0 | 0 |
| **`FULL`** | 1 | 24 | 2 | 0 |
| **`GOOD`** | 0 | 2 | 9 | 0 |
| **`SHORT`** | 0 | 0 | 0 | 0 |

### 3.5 Calibration Quality of the Labels

- **Total clips scored**: `55`
- **Both stumps derived (`0` confirmed)**: `0`
- **One stump confirmed (`1` confirmed)**: `0`
- **Both stumps confirmed (`2` confirmed)**: `55`
- **Homography `residual_px` (n=55)**: mean=1.28 px, max=3.99 px

### 3.6 Clips Flagged `unclear`

Clips with the `unclear` flag are included in Release metrics, excluded from Bounce and Impact tolerance/error tables, and listed below:

_No clips had the `unclear` flag in this run._

## 4. Worst 5 Clips per Metric

### Release Frame Error (frames)
1. `c_f4592060` (`red`, split=`none`): **39**
2. `c_5284da33` (`red`, split=`none`): **31**
3. `c_5ca2aea4` (`red`, split=`none`): **18**
4. `c_4af78565` (`red`, split=`none`): **13**
5. `c_7f64dd0c` (`red`, split=`none`): **7**

### Release Pixel Distance (px)
1. `c_5284da33` (`red`, split=`none`): **266.0**
2. `c_f4592060` (`red`, split=`none`): **172.2**
3. `c_4b4d9800` (`pink`, split=`none`): **113.0**
4. `c_e6b5e8a3` (`pink`, split=`none`): **94.8**
5. `c_4af78565` (`red`, split=`none`): **92.7**

### Bounce Frame Error (frames, excl. unclear)
1. `c_4b4d9800` (`pink`, split=`none`): **-2**
2. `c_dd85ffc4` (`red`, split=`none`): **2**
3. `c_f31728c7` (`pink`, split=`none`): **-2**
4. `c_0e6d3a6d` (`red`, split=`none`): **-1**
5. `c_41dd8473` (`pink`, split=`none`): **1**

### Bounce Ground Error (m, excl. unclear)
1. `c_dd85ffc4` (`red`, split=`none`): **2.580**
2. `c_58280133` (`red`, split=`none`): **1.665**
3. `c_7f64dd0c` (`red`, split=`none`): **1.505**
4. `c_a473c3f0` (`pink`, split=`dev`): **1.003**
5. `c_865b0a59` (`pink`, split=`none`): **0.850**

### Deviation vs Impact Frame Error (frames, excl. unclear)
- _No scored clips_

### Deviation vs Impact Pixel Distance (px, excl. unclear)
- _No scored clips_

## 5. Caveats

- **Small sample sizes**: The current baseline evaluation set has a small number of final clips; percentile estimates (`p90`) and subgroup breakdowns (`ball_colour`, `split`) have high variance until more clips are annotated.
- **Labels made blind to the pipeline**: Ground-truth labels (`release`, `bounce`, `impact`, `calibration_gt`) were annotated independently in the annotator UI without inspecting pipeline predictions.
- **30 fps temporal resolution limits**: At ~30 fps (~33.3 ms per frame), a fast delivery travels ~0.9–1.2 m between consecutive frames. A 1-frame sampling difference near bounce or impact naturally introduces 0.5–1.2 m of along-pitch distance difference even when pixel localization is accurate.
- **Legacy `zones.py` length bug (`19.68 m` vs `17.68 m`)**: The legacy tracker sets `BOWL_CREASE_Y = 1.22 + 19.68 = 20.90 m` instead of the regulation `1.22 + 17.68 = 18.90 m` (`calib_constants.py`), systematically inflating `system.bounce.length_m` relative to true `pitch_z_m`.
