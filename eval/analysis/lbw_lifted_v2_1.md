# Homography-Lifted Ballistic LBW Probe (`v2_1`)

> **Note on Ground Truth**: All 14 labelled clips in `eval/labels` are **on-field LBW "out"** decisions (`lbw == "out"`, all pad impacts). This evaluation tests whether a 4-corner ground homography ($H_g$) combined with a local vertical scale factor $L(X, Z)$ and a bounce-centred 8-parameter ballistic model fits the 2D ball tracks accurately and produces stable stump-plane projections.

## 1. Summary

| Metric | Value (12 system-impact clips) | Value (11 clips excl. `c_09a18d5f` bounce defect) | Gate / Notes |
| :--- | :--- | :--- | :--- |
| Total final labels (`lbw = "out"`) | `14` | `14` | All 14 labels are on-field outs |
| Clips solved (main system-impact run) | `12/14` (`85.7%`) | `11/14` | `c_69ba9415` & `c_6e281881` have `events.impact = null`; `c_6e281881` is solved in oracle-impact variants (`13/14`) |
| **Median fit RMS (px)** | **`7.48 px`** | **`7.00 px`** | Gate: `<= 3.00 px` (**FAIL**; min `3.43 px`, max `63.22 px`) |
| **Median bounce distance to label (m)** | **`0.267 m`** | **`0.222 m`** | Gate: `<= 0.250 m` (**FAIL**; 6/12 clips `<= 0.25 m`, min `0.115 m`) |
| **Clips with verdict agreeing in >= 85% of variants** | **`9/12` (`75.0%`)** | `8/11` (`72.7%`) | Gate: `>= 85.0%` (**FAIL**; `>= 7/8` variants = `87.5%`) |
| **Main run `HITTING` share (`k=0, e in [0.3, 0.8], system`)** | **`6/12` (`50.0%`)** | `6/11` (`54.5%`) | `|X_s| <= 0.150 m` and `0 <= h_s <= 0.747 m` |
| **Range of lateral stump position `X_s` (m)** | **`[-0.208, +0.160] m`** | `[-0.208, +0.160] m` | `10/12` within `+-0.150 m` (`c_41dd8473` at `+0.160 m`, `c_f51f593e` at `-0.208 m` outside) |

### HITTING Share Across All 8 Variants

| Variant ID | Drag `k` ($\text{s}^{-1}$) | `e` Bounds | Impact Source | Clips Solved | `HITTING` Count | `HITTING` Share |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `k0_e0308_sys` | `0.00` | `[0.30, 0.80]` | `system` | `12/14` | `6/12` | **`50.0%`** |
| `k0_e4565_sys` | `0.00` | `[0.45, 0.65]` | `system` | `12/14` | `7/12` | **`58.3%`** |
| `k15_e0308_sys` | `0.15` | `[0.30, 0.80]` | `system` | `12/14` | `7/12` | **`58.3%`** |
| `k15_e4565_sys` | `0.15` | `[0.45, 0.65]` | `system` | `12/14` | `8/12` | **`66.7%`** |
| `k0_e0308_ora` | `0.00` | `[0.30, 0.80]` | `oracle` | `13/14` | `6/13` | **`46.2%`** |
| `k0_e4565_ora` | `0.00` | `[0.45, 0.65]` | `oracle` | `13/14` | `7/13` | **`53.8%`** |
| `k15_e0308_ora` | `0.15` | `[0.30, 0.80]` | `oracle` | `13/14` | `7/13` | **`53.8%`** |
| `k15_e4565_ora` | `0.15` | `[0.45, 0.65]` | `oracle` | `13/14` | `8/13` | **`61.5%`** |

## 2. Per-Clip Table (Main Run + Variants + Monte-Carlo)

- **Main run**: `drag k = 0.0`, `e in [0.3, 0.8]`, `f in [0.55, 1.0]`, system impact (`v2_1`).
- **Arrival time**: reported as post-bounce travel time $\Delta t_s = t_s - t_b$ (and absolute clip timestamp $t_s$ in parentheses).
- **Margin (m)**: distance outside the `[|X_s| <= 0.150, 0 <= h_s <= 0.747]` hitting box (`0.000 m` when `HITTING`, with signed clearance inside shown in parentheses).

| Clip | Fit RMS (px) | Rel Speed (km/h) | Fitted Bounce `(X_b, Z_b)` (m) | Bounce Dist (m) | Rise Angle (deg) | Arrival `dt_s (t_s)` (s) | `X_s` (m) | `h_s` (m) | Verdict | Margin (m) | Variant Agree | MC Hit % | MC `std(X_s, h_s)` (m) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `c_09a18d5f` | `63.22` | `92.5` | `(-0.299, 6.797)` | `0.558` | `7.22°` | `0.493s (0.660s)` | `+0.109` | `-0.330` | **`MISSING`** | `+0.330` | `8/8` (`100.0%`) | `0%` | `(0.015, 0.023)` |
| `c_13f43606` | `6.74` | `101.4` | `(-0.309, 6.065)` | `0.222` | `8.98°` | `0.224s (0.687s)` | `+0.035` | `+0.713` | **`HITTING`** | `0.000` (`-0.034`) | `6/8` (`75.0%`) | `100%` | `(0.014, 0.045)` |
| `c_3d27ed64` | `5.13` | `88.2` | `(+0.316, 5.802)` | `0.115` | `10.52°` | `0.243s (0.741s)` | `-0.008` | `+0.789` | **`MISSING`** | `+0.042` | `3/8` (`37.5%`) | `100%` | `(0.016, 0.045)` |
| `c_3f1fc736` | `3.43` | `129.8` | `(-0.271, 7.169)` | `0.173` | `6.57°` | `0.219s (0.648s)` | `+0.049` | `+0.591` | **`HITTING`** | `0.000` (`-0.101`) | `8/8` (`100.0%`) | `85%` | `(0.016, 0.070)` |
| `c_41dd8473` | `9.99` | `95.3` | `(-0.239, 6.794)` | `0.152` | `10.89°` | `0.259s (0.716s)` | `+0.160` | `+0.979` | **`MISSING`** | `+0.233` | `8/8` (`100.0%`) | `100%` | `(0.015, 0.029)` |
| `c_542fca8b` | `6.95` | `101.4` | `(+0.246, 5.619)` | `0.616` | `9.76°` | `0.214s (0.741s)` | `-0.029` | `+0.743` | **`HITTING`** | `0.000` (`-0.004`) | `8/8` (`100.0%`) | `100%` | `(0.016, 0.056)` |
| `c_5cef27ce` | `8.34` | `82.6` | `(-0.272, 3.983)` | `0.176` | `9.65°` | `0.184s (0.967s)` | `-0.143` | `+0.511` | **`HITTING`** | `0.000` (`-0.007`) | `8/8` (`100.0%`) | `54%` | `(0.014, 0.055)` |
| `c_5e5ea872` | `5.51` | `143.3` | `(-0.090, 5.965)` | `0.151` | `12.02°` | `0.259s (0.699s)` | `+0.149` | `+0.941` | **`MISSING`** | `+0.194` | `8/8` (`100.0%`) | `13%` | `(0.014, 0.113)` |
| `c_69ba9415` | — | — | — | — | — | — | — | — | **FAILED** (`missing_system_bounce`) | — | — | — | — |
| `c_6e281881` | — | — | — | — | — | — | — | — | **FAILED** (`missing_system_impact`) (oracle: RMS `4.97 px`, bdist `0.471 m`, `X_s=+0.168 m`, `h_s=+0.177 m`, `MISSING`) | — | — | — | — |
| `c_77d7834d` | `7.00` | `128.2` | `(-0.086, 6.588)` | `0.312` | `13.22°` | `0.270s (0.870s)` | `+0.105` | `+1.190` | **`MISSING`** | `+0.443` | `8/8` (`100.0%`) | `0%` | `(0.018, 0.102)` |
| `c_a473c3f0` | `9.16` | `158.5` | `(-0.308, 5.583)` | `0.639` | `4.47°` | `0.175s (0.622s)` | `-0.101` | `+0.286` | **`HITTING`** | `0.000` (`-0.049`) | `8/8` (`100.0%`) | `100%` | `(0.016, 0.017)` |
| `c_e6b5e8a3` | `9.26` | `160.8` | `(-0.025, 4.264)` | `0.356` | `8.43°` | `0.154s (0.645s)` | `+0.061` | `+0.515` | **`HITTING`** | `0.000` (`-0.089`) | `8/8` (`100.0%`) | `100%` | `(0.015, 0.057)` |
| `c_f51f593e` | `7.96` | `141.2` | `(-0.405, 7.044)` | `0.394` | `4.06°` | `0.198s (0.585s)` | `-0.208` | `+0.309` | **`MISSING`** | `+0.058` | `6/8` (`75.0%`) | `7%` | `(0.022, 0.057)` |

## 3. Side-by-Side Comparison with `reconstruct3d` Probe (`times = (frame - release)/fps`, `use_drag=False`)

| Metric (12 system-impact clips) | `reconstruct3d` Probe (release-zeroed, no drag) | Homography-Lifted Ballistic Fit (`k=0`, `e in [0.3, 0.8]`) | Change / Interpretation |
| :--- | :---: | :---: | :--- |
| **Median Fit RMS (px)** | `5.89 px` (`3.72–10.03 px`) | `7.48 px` (`7.00 px` excl. `c_09a18d5f`) | `reconstruct3d` has 9 free parameters (unconstrained 3D initial state + free bounce time); lifted model anchors `t_b` within `+-1` frame of system bounce and `(X_b, Z_b)` within `+-0.25 m` |
| **Median Bounce Distance to Label (m)** | `0.821 m` (`0.257–1.898 m`) | **`0.267 m`** (`0.222 m` excl. `c_09a18d5f`; min `0.115 m`) | **`3.1x` reduction (`0.821 m -> 0.267 m`)**: anchoring `(X_b, Z_b)` to the exact 4-corner ground homography eliminates the `0.5–1.9 m` longitudinal bounce drift of PnP |
| **`HITTING` Share** | `4/12` (`33.3%`) | **`6/12` (`50.0%`)** (`46.2%–66.7%` across all 8 variants) | `9/12` (`75.0%`) clips have `100%` (`8/8`) variant agreement; `HITTING` share spans `46.2%–66.7%` vs `33.3%–75.0%` in `reconstruct3d` |

### Per-Clip Comparison (`reconstruct3d` Release-Zeroed No-Drag vs Homography-Lifted Main)

| Clip | `reconstruct3d` Fit RMS (px) | Lifted Fit RMS (px) | `reconstruct3d` Bounce Dist (m) | Lifted Bounce Dist (m) | `reconstruct3d` Verdict | Lifted Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `c_09a18d5f` | `5.61` | `63.22` | `0.257` | `0.558` | `HITTING` | **`MISSING`** |
| `c_13f43606` | `6.72` | `6.74` | `1.091` | `0.222` | `MISSING` | **`HITTING`** |
| `c_3d27ed64` | `5.57` | `5.13` | `0.658` | `0.115` | `HITTING` | **`MISSING`** |
| `c_3f1fc736` | `3.83` | `3.43` | `0.725` | `0.173` | `MISSING` | **`HITTING`** |
| `c_41dd8473` | `10.03` | `9.99` | `0.504` | `0.152` | `MISSING` | **`MISSING`** |
| `c_542fca8b` | `5.28` | `6.95` | `1.530` | `0.616` | `MISSING` | **`HITTING`** |
| `c_5cef27ce` | `9.28` | `8.34` | `0.782` | `0.176` | `HITTING` | **`HITTING`** |
| `c_5e5ea872` | `3.72` | `5.51` | `0.860` | `0.151` | `MISSING` | **`MISSING`** |
| `c_69ba9415` | — | — | — | — | — | **FAILED** (`missing_system_bounce`) |
| `c_6e281881` | — | — | — | — | — | **FAILED** (`missing_system_impact`) |
| `c_77d7834d` | `6.18` | `7.00` | `0.536` | `0.312` | `MISSING` | **`MISSING`** |
| `c_a473c3f0` | `4.87` | `9.16` | `1.898` | `0.639` | `HITTING` | **`HITTING`** |
| `c_e6b5e8a3` | `7.32` | `9.26` | `1.082` | `0.356` | `MISSING` | **`HITTING`** |
| `c_f51f593e` | `7.31` | `7.96` | `1.117` | `0.394` | `MISSING` | **`MISSING`** |

## 4. Failed and Defective Clips (with Reasons)

- **`c_69ba9415`** (`missing_system_bounce` in both system and oracle runs): `events.bounce` and `events.impact` are both `null` in `v2_1/results.json`, and `trajectory` only contains 5 pre-bounce detections in frames `9..16` (before `label.bounce.frame = 18`), so no bounce frame or post-bounce segment is available.
- **`c_6e281881`** (`missing_system_impact` in system-impact run): `events.impact` is `null` in `v2_1/results.json` (`events.release.frame = 5`, `events.bounce.frame = 16`). In the **oracle-impact** variants (`label.impact.frame = 19`, 13 points), the lifted fit succeeds with `fit_rms = 4.97 px`, `bounce_dist = 0.471 m`, `X_s = +0.168 m`, `h_s = +0.177 m`, verdict `MISSING` (`4/4` oracle variants agree).
- **`c_09a18d5f`** (upstream bounce frame defect: `sys_bounce_frame(4)==sys_release_frame(4) (true bounce f=12)`): In `v2_1/results.json`, the legacy streaming bounce detector fired prematurely at frame `4`, and `release_flight` also moved `events.release.frame` to `4`. Because the model constrains $t_b$ within $\pm 1$ frame of `events.bounce.frame = 4` while the actual pitch bounce in the trajectory occurs at frame `12`, the fit cannot bend at frame `12`, yielding `fit_rms = 63.22 px` and `bounce_dist = 0.558 m`.

## 5. Decision

**DECISION: FAIL (median fit RMS = 7.48 px > 3.00 px (even excluding c_09a18d5f's f=4 bounce defect, 11-clip median is 7.00 px > 3.00 px); median bounce distance = 0.267 m > 0.25 m (11-clip median excluding c_09a18d5f is 0.222 m); verdict stability = 9/12 (75.0%) < 85.0% of clips agreeing in >= 85% of variants)**
