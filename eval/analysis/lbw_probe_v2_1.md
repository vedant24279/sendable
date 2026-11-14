# LBW Projection Feasibility Probe (`v2_1`)

> **Note on Ground Truth**: All 14 labelled clips in `eval/labels` are **on-field LBW "out"** decisions (`lbw == "out"`, all pad impacts). This study is a **physics and calibration feasibility sanity check**, not an accuracy benchmark across out/not-out classes.

## 1. Overall Summary

| Metric | Value | Notes |
| :--- | :--- | :--- |
| Final labelled clips with `v2_1` results | `14` | All 14 clips have `lbw = "out"` |
| Image-left / world-side consistency | `14/14` (`100%`) | `bat_L` & `bowl_L` stay on world `-X` (`-1.32 m`); zero camera-side inversions (`wrong_side = 0`) |
| Camera poses solved (`calibrate.solve_pose`) | `14/14` (`100%`) | Coplanar 6-point PnP focal search over `500..15000 px` |
| Camera poses plausible (`height in [1, 15] m`, `dist in [5, 60] m`) | **`1/14` (`7.1%`)** | Only `c_69ba9415` (`f=10725 px`, `h=7.50 m`, `d=57.46 m`); the other 13 hit the `f=15000 px` ceiling (`d=65.1..81.3 m`) |
| Clips solved — System impact | `12/14` (`85.7%`) | `c_69ba9415` and `c_6e281881` skipped (`events.impact` is `null`) |
| Clips solved — Oracle impact (`>= 6` pts / all) | `13/14` (`14/14` incl. 5-pt `c_69ba9415`) | `c_6e281881` has 13 pts up to oracle impact f19; `c_69ba9415` has only 5 pre-bounce pts in `9..16` |
| **Share `HITTING` — System impact (`times = frame/fps`, `use_drag=False`)** | **`5/12` (`41.7%`)** | `4/12` (`33.3%`) when `times = (frame - release_frame)/fps` |
| **Share `HITTING` — System impact (`times = frame/fps`, `use_drag=True`)** | **`9/12` (`75.0%`)** | `6/12` (`50.0%`) when `times = (frame - release_frame)/fps` |
| **Share `HITTING` — Oracle impact (`times = frame/fps`, `use_drag=False`)** | **`6/13` (`46.2%`)** (`6/14` all) | `4/13` (`30.8%`) when `times = (frame - release_frame)/fps` |
| **Share `HITTING` — Oracle impact (`times = frame/fps`, `use_drag=True`)** | **`9/13` (`69.2%`)** (`9/14` all) | `6/13` (`46.2%`) when `times = (frame - release_frame)/fps` |

## 2. Main Per-Clip Table (`times = frame / fps`, `use_magnus=False`)

Stump-plane hitting box at `z = 0`: `|x| <= 0.114 + 0.036 = 0.150 m` and `0 <= y <= 0.711 + 0.036 = 0.747 m`. Values shown as `no_drag / drag` where both drag modes are run; Monte-Carlo columns (`MC hit%`, `std_x`, `std_y`) use 100 repeats (`seed=42`) with calibration perturbed by `N(0, 1.5 px)` and trajectory by `N(0, 2.0 px)`.

| Clip | Pose RMS (px) | Focal (px) | Cam `h` / `dist` (m) | Plaus. | Fit RMS `nd/d` (px) | Speed `nd/d` (km/h) | Bounce `(x, z)` `nd` (m) | Bounce Err `nd/d` (m) | Sys `t_arr` `nd` (s) | Sys `(x, y)` `nd` (m) | Sys Out `nd` (m) | Sys Verdict `nd/d` | Ora `(x, y)` `nd` (m) | Ora Out `nd` (m) | Ora Verdict `nd/d` | MC Hit% `sys/ora` | MC `std_x` `sys` (m) | MC `std_y` `sys` (m) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `c_09a18d5f` | 0.82 | 15000 | 17.01 / 78.27 | NO | 5.61 / 5.70 | 119.5 / 138.2 | (-0.07, 6.55) | 0.26 / 0.26 | 0.640 | (+0.10, +0.69) | 0.000 | HITTING / HITTING | (+0.06, +0.94) | 0.189 | MISSING / MISSING | 100% / 4% | 0.012 | 0.043 |
| `c_13f43606` | 9.11 | 15000 | 8.73 / 65.09 | NO | 6.72 / 7.20 | 131.5 / 152.8 | (-0.30, 6.93) | 1.09 / 0.99 | 0.688 | (-0.02, +0.78) | 0.038 | MISSING / HITTING | (-0.02, +0.78) | 0.038 | MISSING / HITTING | 0% / 0% | 0.011 | 0.008 |
| `c_3d27ed64` | 6.61 | 15000 | 10.93 / 69.51 | NO | 5.57 / 6.35 | 128.7 / 147.1 | (+0.31, 6.35) | 0.66 / 0.58 | 0.708 | (+0.08, +0.66) | 0.000 | HITTING / HITTING | (+0.05, +0.65) | 0.000 | HITTING / HITTING | 100% / 100% | 0.009 | 0.007 |
| `c_3f1fc736` | 6.42 | 15000 | 10.92 / 69.51 | NO | 3.83 / 4.54 | 130.1 / 155.1 | (-0.26, 7.72) | 0.72 / 0.69 | 0.683 | (+0.07, +0.82) | 0.075 | MISSING / MISSING | (+0.07, +0.82) | 0.075 | MISSING / MISSING | 0% / 0% | 0.010 | 0.007 |
| `c_41dd8473` | 1.16 | 15000 | 16.23 / 81.28 | NO | 10.03 / 10.64 | 129.6 / 152.7 | (-0.20, 7.14) | 0.50 / 0.50 | 0.691 | (+0.15, +0.80) | 0.057 | MISSING / MISSING | (+0.15, +0.80) | 0.057 | MISSING / MISSING | 0% / 0% | 0.009 | 0.010 |
| `c_542fca8b` | 7.08 | 15000 | 10.78 / 68.30 | NO | 5.73 / 7.76 | 128.0 / 140.0 | (+0.25, 6.47) | 1.47 / 1.33 | 0.738 | (+0.01, +0.75) | 0.006 | MISSING / HITTING | (+0.05, +0.75) | 0.007 | MISSING / HITTING | 22% / 20% | 0.008 | 0.008 |
| `c_5cef27ce` | 7.52 | 15000 | 9.14 / 68.86 | NO | 9.32 / 10.64 | 94.3 / 104.2 | (-0.26, 4.53) | 0.72 / 0.47 | 0.985 | (-0.14, +0.61) | 0.000 | HITTING / HITTING | (-0.14, +0.61) | 0.000 | HITTING / HITTING | 95% / 95% | 0.007 | 0.006 |
| `c_5e5ea872` | 6.72 | 15000 | 10.93 / 69.70 | NO | 5.42 / 5.16 | 154.0 / 163.0 | (-0.11, 6.58) | 0.77 / 0.79 | 0.694 | (+0.12, +0.88) | 0.134 | MISSING / HITTING | (+0.12, +0.88) | 0.134 | MISSING / HITTING | 3% / 3% | 0.008 | 0.051 |
| `c_69ba9415` | 1.44 | 10725 | 7.50 / 57.46 | YES | — (6.24 ora) | — (73.7 ora) | (+0.38, 4.38)* | — (1.35 ora) | — | — | — | SKIP | (-0.06, -0.05) | 0.054 | MISSING / MISSING* | — / 31% | 0.028* | 0.242* |
| `c_6e281881` | 3.82 | 15000 | 11.87 / 69.34 | NO | — (2.93 ora) | — (135.7 ora) | (-0.07, 4.38)* | — (1.06 ora) | — | — | — | SKIP | (+0.09, +0.30) | 0.000 | HITTING / HITTING | — / 78% | 0.055* | 0.138* |
| `c_77d7834d` | 0.40 | 15000 | 16.96 / 78.12 | NO | 12.71 / 17.35 | 112.3 / 122.7 | (-0.10, 6.89) | 0.62 / 0.59 | 0.842 | (+0.10, +0.75) | 0.005 | MISSING / HITTING | (+0.09, +0.74) | 0.000 | HITTING / HITTING | 24% / 66% | 0.009 | 0.009 |
| `c_a473c3f0` | 8.92 | 15000 | 8.73 / 65.45 | NO | 4.87 / 4.79 | 145.1 / 151.0 | (-0.31, 6.84) | 1.90 / 1.86 | 0.653 | (-0.05, +0.58) | 0.000 | HITTING / HITTING | (-0.05, +0.58) | 0.000 | HITTING / HITTING | 99% / 99% | 0.021 | 0.068 |
| `c_e6b5e8a3` | 6.81 | 15000 | 10.93 / 68.89 | NO | 8.05 / 7.94 | 147.8 / 160.5 | (-0.04, 4.96) | 1.05 / 1.03 | 0.656 | (+0.08, +0.59) | 0.000 | HITTING / HITTING | (+0.08, +0.59) | 0.000 | HITTING / HITTING | 100% / 100% | 0.009 | 0.032 |
| `c_f51f593e` | 3.91 | 15000 | 12.45 / 79.72 | NO | 7.31 / 7.37 | 113.6 / 127.5 | (-0.39, 7.77) | 1.12 / 1.11 | 0.679 | (-0.09, +0.75) | 0.001 | MISSING / MISSING | (-0.09, +0.82) | 0.073 | MISSING / MISSING | 38% / 0% | 0.045 | 0.118 |

## 3. Comparison with Release-Zeroed Times (`times = (frame - release_frame) / fps`)

In `trajectory_fit.ball_positions_at_times`, `p0` and `v0` represent the ball state at `t = 0`, with `p0[2]` bounded to `[15.0, 25.0] m`. When raw `times = frame / fps` is passed, `t = 0` is video frame 0 (`release_frame` frames before release), which hits the `p0[2] <= 25.0 m` ceiling on late-release or high-speed clips (`c_542fca8b`, `c_5e5ea872`, `c_77d7834d`, `c_e6b5e8a3`). Zeroing `t = 0` at `release_frame` (matching `trajectory_fit.py` lines 635 & 657) yields:

| Clip | Rel Frame | Sys Fit RMS `nd/d` (px) | Sys Speed `nd/d` (km/h) | Sys Bounce Err `nd/d` (m) | Sys `(x, y)` `nd` (m) | Sys `(x, y)` `d` (m) | Sys Verdict `nd/d` | Ora `(x, y)` `nd` (m) | Ora Verdict `nd/d` | MC Hit% `sys/ora` | MC `std_x / std_y` `sys` (m) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `c_09a18d5f` | 4 | 5.61 / 5.70 | 120.0 / 133.4 | 0.26 / 0.26 | (+0.10, +0.69) | (+0.09, +0.70) | HITTING / HITTING | (+0.06, +0.94) | MISSING / MISSING | 100% / 3% | 0.012 / 0.043 |
| `c_13f43606` | 4 | 6.72 / 7.16 | 132.0 / 151.4 | 1.09 / 1.01 | (-0.02, +0.78) | (-0.04, +0.75) | MISSING / HITTING | (-0.02, +0.78) | MISSING / HITTING | 0% / 0% | 0.011 / 0.008 |
| `c_3d27ed64` | 5 | 5.57 / 6.10 | 129.3 / 147.1 | 0.66 / 0.63 | (+0.08, +0.66) | (+0.09, +0.64) | HITTING / HITTING | (+0.05, +0.65) | HITTING / HITTING | 100% / 100% | 0.010 / 0.009 |
| `c_3f1fc736` | 3 | 3.83 / 4.54 | 130.5 / 150.3 | 0.72 / 0.69 | (+0.07, +0.82) | (+0.05, +0.80) | MISSING / MISSING | (+0.07, +0.82) | MISSING / MISSING | 0% / 0% | 0.010 / 0.007 |
| `c_41dd8473` | 5 | 10.03 / 10.64 | 130.3 / 145.9 | 0.50 / 0.50 | (+0.15, +0.80) | (+0.14, +0.79) | MISSING / MISSING | (+0.15, +0.80) | MISSING / MISSING | 0% / 0% | 0.009 / 0.010 |
| `c_542fca8b` | 5 | 5.28 / 5.89 | 137.2 / 159.1 | 1.53 / 1.47 | (+0.02, +0.76) | (+0.04, +0.73) | MISSING / HITTING | (+0.06, +0.81) | MISSING / HITTING | 3% / 42% | 0.008 / 0.008 |
| `c_5cef27ce` | 4 | 9.28 / 10.39 | 98.3 / 115.8 | 0.78 / 0.63 | (-0.14, +0.61) | (-0.16, +0.57) | HITTING / MISSING | (-0.14, +0.61) | HITTING / MISSING | 86% / 86% | 0.007 / 0.006 |
| `c_5e5ea872` | 3 | 3.72 / 4.14 | 181.3 / 181.3 | 0.86 / 0.82 | (+0.10, +0.97) | (+0.10, +0.77) | MISSING / MISSING | (+0.10, +0.97) | MISSING / MISSING | 0% / 0% | 0.008 / 0.019 |
| `c_69ba9415` | 9 | — | — | — | — | — | SKIP | (-1.00, -0.42) | MISSING / MISSING | — / 0% | — |
| `c_6e281881` | 5 | — | — | — | — | — | SKIP | (+0.07, +0.32) | HITTING / HITTING | — / 95% | — |
| `c_77d7834d` | 9 | 6.18 / 6.18 | 140.6 / 160.1 | 0.54 / 0.55 | (+0.08, +0.81) | (+0.07, +0.81) | MISSING / MISSING | (+0.04, +1.16) | MISSING / MISSING | 0% / 0% | 0.008 / 0.045 |
| `c_a473c3f0` | 4 | 4.87 / 4.79 | 148.4 / 145.0 | 1.90 / 1.86 | (-0.05, +0.56) | (-0.03, +0.70) | HITTING / HITTING | (-0.05, +0.56) | HITTING / HITTING | 99% / 99% | 0.038 / 0.125 |
| `c_e6b5e8a3` | 5 | 7.31 / 7.24 | 181.1 / 181.2 | 1.08 / 1.05 | (+0.06, +0.75) | (+0.07, +0.61) | MISSING / HITTING | (+0.06, +0.75) | MISSING / HITTING | 69% / 69% | 0.008 / 0.021 |
| `c_f51f593e` | 3 | 7.31 / 7.37 | 114.1 / 124.4 | 1.12 / 1.11 | (-0.09, +0.75) | (-0.09, +0.76) | MISSING / MISSING | (-0.09, +0.82) | MISSING / MISSING | 38% / 0% | 0.045 / 0.118 |

## 4. Failed / Implausible Clips & Reasons

### 4.1 Trajectory / Impact Failures
- **`c_69ba9415`**:
  - **System impact**: Skipped — `events.impact` is `null` (and `events.bounce` is `null`).
  - **Oracle impact**: Trajectory in `v2_1/c_69ba9415/results.json` contains only **5 pre-bounce points** (frames `[9, 10, 11, 15, 16]`), terminating before the labelled bounce (frame 19) and labelled impact (frame 23). Fitting 9 parameters to 5 pre-bounce points has no post-bounce observability (`y = -0.05 m` / `-0.42 m` at `z = 0`).
- **`c_6e281881`**:
  - **System impact**: Skipped — `events.impact` is `null` (Rule I5b found no post-bounce vertex with `>= 20 deg` kink).
  - **Oracle impact**: Succeeds (`13` points in frames `5..17` spanning the bounce at frame 16 up to labelled impact frame 19), giving `fit_rms = 2.91 px` and classifying as **`HITTING`** (`x = +0.09 m, y = +0.30 m`).

### 4.2 Camera Pose Plausibility Flags (`height in [1, 15] m`, `distance in [5, 60] m`)
- **`c_09a18d5f`**: Implausible (`focal = 15000 px`, `height = 17.01 m`, `dist_behind = 78.27 m`) — height 17.01 m outside [1, 15] m; distance 78.27 m outside [5, 60] m.
- **`c_13f43606`**: Implausible (`focal = 15000 px`, `height = 8.73 m`, `dist_behind = 65.09 m`) — distance 65.09 m outside [5, 60] m.
- **`c_3d27ed64`**: Implausible (`focal = 15000 px`, `height = 10.93 m`, `dist_behind = 69.51 m`) — distance 69.51 m outside [5, 60] m.
- **`c_3f1fc736`**: Implausible (`focal = 15000 px`, `height = 10.92 m`, `dist_behind = 69.51 m`) — distance 69.51 m outside [5, 60] m.
- **`c_41dd8473`**: Implausible (`focal = 15000 px`, `height = 16.23 m`, `dist_behind = 81.28 m`) — height 16.23 m outside [1, 15] m; distance 81.28 m outside [5, 60] m.
- **`c_542fca8b`**: Implausible (`focal = 15000 px`, `height = 10.78 m`, `dist_behind = 68.30 m`) — distance 68.30 m outside [5, 60] m.
- **`c_5cef27ce`**: Implausible (`focal = 15000 px`, `height = 9.14 m`, `dist_behind = 68.86 m`) — distance 68.86 m outside [5, 60] m.
- **`c_5e5ea872`**: Implausible (`focal = 15000 px`, `height = 10.93 m`, `dist_behind = 69.70 m`) — distance 69.70 m outside [5, 60] m.
- **`c_6e281881`**: Implausible (`focal = 15000 px`, `height = 11.87 m`, `dist_behind = 69.34 m`) — distance 69.34 m outside [5, 60] m.
- **`c_77d7834d`**: Implausible (`focal = 15000 px`, `height = 16.96 m`, `dist_behind = 78.12 m`) — height 16.96 m outside [1, 15] m; distance 78.12 m outside [5, 60] m.
- **`c_a473c3f0`**: Implausible (`focal = 15000 px`, `height = 8.73 m`, `dist_behind = 65.45 m`) — distance 65.45 m outside [5, 60] m.
- **`c_e6b5e8a3`**: Implausible (`focal = 15000 px`, `height = 10.93 m`, `dist_behind = 68.89 m`) — distance 68.89 m outside [5, 60] m.
- **`c_f51f593e`**: Implausible (`focal = 15000 px`, `height = 12.45 m`, `dist_behind = 79.72 m`) — distance 79.72 m outside [5, 60] m.

## 5. Key Feasibility Findings

1. **Lateral (`x`) projection is strong across all solved clips**: Every single solved clip (`12/12` system, `13/13` valid oracle) lands horizontally in-line with the stumps at `z = 0` (`|x| in [0.01, 0.15] m <= 0.150 m`), with tight Monte-Carlo lateral spread (`std_x` median `~0.014 m`).
2. **Vertical (`y`) height at the stumps is the sole cause of `MISSING` classifications**: Every `MISSING` verdict on a valid track is a narrow over-the-top miss (`y in [0.75, 0.97] m` vs the `0.747 m` top-of-stumps limit; several miss by only `3–55 mm`).
3. **Root cause is coplanar 6-point focal-length degeneracy**: Because all 6 calibration points lie on `Y = 0`, `solve_pose` runs to the `f = 15000 px` search boundary on 13/14 clips (`distance = 65–81 m` behind bowler's stumps), flattening perspective and biasing the post-bounce vertical pitch angle upward.
