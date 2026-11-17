# Kink Events & Detection Recall Report: `dump_all_1`

- **Clips analysed (with dump + results)**: `57`
- **Final clips skipped (missing dump/results)**: `1` (c_f784a9d7)
- **Counts by ball colour**: `pink`=17, `red`=38, `white`=2
- **Counts by impact type**: `bat`=8, `none`=6, `pad`=36, `stumps`=7

## 1. Detection Recall by Ball Colour

| Ball Colour | n | Overall `[rel, last_vis]` | Before Impact | After Impact | Longest Gap Overall (med / max) | Gap `bnc±3` (med / max) | Gap `imp±3` (med / max) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `red` | 38 | 66.8% | 66.6% | 68.5% | 6.0 / 51 | 2.0 / 5 | 4.5 / 7 |
| `pink` | 17 | 92.9% | 94.9% | 91.7% | 1.0 / 14 | 0.0 / 1 | 1.0 / 5 |
| `white` | 2 | 11.1% | 7.3% | 15.0% | 24.5 / 34 | 5.5 / 7 | 5.0 / 7 |
| `ALL` | 57 | 72.8% | 72.9% | 74.6% | 5.0 / 51 | 1.0 / 7 | 3.0 / 7 |

## 2. Bounce & Impact: Piecewise Huber Fit vs Current System (`results.json`)

| Event (Slice) | Method | n | Found | Med `|Δt|` (f) | P90 `|Δt|` (f) | `≤0.5f` | `≤1f` | `≤2f` | Med Px | P90 Px |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Bounce (ALL) | Kink fit | 57 | 35/57 (61.4%) | 0.30 | 0.99 | 65.7% | 88.6% | 94.3% | 14.0 | 35.3 |
| Bounce (ALL) | Current system | 57 | 48/57 (84.2%) | 0.00 | 20.00 | 70.8% | 85.4% | 85.4% | 3.6 | 275.5 |
| Bounce (red) | Kink fit | 38 | 20/38 (52.6%) | 0.40 | 1.83 | 55.0% | 85.0% | 90.0% | 15.6 | 48.3 |
| Bounce (red) | Current system | 38 | 31/38 (81.6%) | 0.00 | 23.00 | 61.3% | 77.4% | 77.4% | 3.9 | 441.8 |
| Bounce (pink) | Kink fit | 17 | 15/17 (88.2%) | 0.25 | 0.67 | 80.0% | 93.3% | 100.0% | 7.0 | 17.9 |
| Bounce (pink) | Current system | 17 | 17/17 (100.0%) | 0.00 | 0.40 | 88.2% | 100.0% | 100.0% | 2.8 | 7.3 |
| Impact (`bat+pad`) | Kink fit | 44 | 22/44 (50.0%) | 0.47 | 2.10 | 50.0% | 72.7% | 81.8% | 29.4 | 47.0 |
| Impact (`bat+pad`) | Current system | 44 | 27/44 (61.4%) | 1.00 | 4.00 | 40.7% | 66.7% | 85.2% | 23.5 | 108.5 |
| Impact (`bat`) | Kink fit | 8 | 3/8 (37.5%) | 0.75 | 1.83 | 0.0% | 66.7% | 66.7% | 25.3 | 37.5 |
| Impact (`bat`) | Current system | 8 | 4/8 (50.0%) | 1.00 | 1.70 | 25.0% | 75.0% | 100.0% | 23.8 | 54.2 |
| Impact (`pad`) | Kink fit | 36 | 19/36 (52.8%) | 0.40 | 2.28 | 57.9% | 73.7% | 84.2% | 30.4 | 61.9 |
| Impact (`pad`) | Current system | 36 | 23/36 (63.9%) | 1.00 | 4.00 | 43.5% | 65.2% | 82.6% | 23.5 | 112.4 |
| Impact (`stumps`) | Kink fit | 7 | 2/7 (28.6%) | 2.15 | 2.83 | 0.0% | 0.0% | 50.0% | 17.3 | 24.7 |
| Impact (`stumps`) | Current system | 7 | 3/7 (42.9%) | 2.00 | 12.40 | 0.0% | 0.0% | 66.7% | 59.0 | 70.6 |

- **Impact type `none`** (`n=6`): no label impact event; current system emitted a false impact marker on `4/6` clips.

## 3. Gap Robustness (`k` Consecutive Deleted Frames)

| Event (Slice) | `k` | Method | n | Found | Med `|Δt|` (f) | P90 `|Δt|` (f) | Med Px | P90 Px |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Bounce (ALL) | 0 | Kink fit | 57 | 35/57 (61.4%) | 0.30 | 0.99 | 14.0 | 35.3 |
| Bounce (ALL) | 0 | Current frame surviving | 57 | 48/57 (84.2%) | 0.00 | 20.00 | 3.6 | 275.5 |
| Bounce (ALL) | 2 | Kink fit | 57 | 34/57 (59.6%) | 0.33 | 1.14 | 12.2 | 36.7 |
| Bounce (ALL) | 2 | Current frame surviving | 57 | 8/57 (14.0%) | 21.50 | 33.30 | 405.8 | 561.2 |
| Bounce (ALL) | 3 | Kink fit | 57 | 24/57 (42.1%) | 0.38 | 1.81 | 9.3 | 36.1 |
| Bounce (ALL) | 3 | Current frame surviving | 57 | 7/57 (12.3%) | 23.00 | 34.40 | 441.8 | 597.9 |
| Bounce (ALL) | 5 | Kink fit | 57 | 16/57 (28.1%) | 1.53 | 3.00 | 14.8 | 54.5 |
| Bounce (ALL) | 5 | Current frame surviving | 57 | 7/57 (12.3%) | 23.00 | 34.40 | 441.8 | 597.9 |
| Impact (`bat+pad`) | 0 | Kink fit | 44 | 22/44 (50.0%) | 0.47 | 2.10 | 29.4 | 47.0 |
| Impact (`bat+pad`) | 0 | Current vertex rule (I5b) | 44 | 27/44 (61.4%) | 1.00 | 4.00 | 23.5 | 108.1 |
| Impact (`bat+pad`) | 2 | Kink fit | 44 | 16/44 (36.4%) | 0.38 | 2.75 | 29.5 | 82.5 |
| Impact (`bat+pad`) | 2 | Current vertex rule (I5b) | 44 | 25/44 (56.8%) | 2.00 | 4.00 | 45.6 | 110.2 |
| Impact (`bat+pad`) | 3 | Kink fit | 44 | 16/44 (36.4%) | 0.50 | 2.75 | 30.9 | 83.1 |
| Impact (`bat+pad`) | 3 | Current vertex rule (I5b) | 44 | 24/44 (54.5%) | 2.00 | 4.00 | 60.8 | 111.2 |
| Impact (`bat+pad`) | 5 | Kink fit | 44 | 13/44 (29.5%) | 0.70 | 3.00 | 24.8 | 69.9 |
| Impact (`bat+pad`) | 5 | Current vertex rule (I5b) | 44 | 18/44 (40.9%) | 3.00 | 4.00 | 97.7 | 128.9 |

## 4. Clips Worse Than 1 Frame or 15 px (or Missed Fit)

Count: `54/57` clips.

| Clip ID | Ball | Imp Type | Recall | Bnc Fit (`|Δt|` / px) | Bnc Sys (`|Δt|` / px) | Imp Fit (`|Δt|` / px) | Imp Sys (`|Δt|` / px) | Reason / Gaps |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| `c_0112a3f3` | `red` | `pad` | 18.6% | MISSED | MISSED | MISSED | MISSED | gap_b=5, gap_i=7, pre=None, post=None, out=None |
| `c_045513d5` | `red` | `pad` | 76.3% | MISSED | 0f / 3.0px | MISSED | 6f / 116.5px | gap_b=2, gap_i=5, pre=None, post=None, out=None |
| `c_0522189a` | `red` | `stumps` | 88.9% | 0.05f / 28.6px | 0f / 2.7px | 1.30f / 8.1px | 2f / 33.0px | gap_b=0, gap_i=4, pre=9, post=5, out=4 |
| `c_09650a59` | `red` | `pad` | 17.1% | MISSED | MISSED | MISSED | MISSED | gap_b=5, gap_i=7, pre=None, post=None, out=None |
| `c_09a18d5f` | `pink` | `pad` | 98.4% | 0.35f / 4.5px | 0f / 3.7px | 0.65f / 47.6px | 2f / 74.6px | gap_b=0, gap_i=1, pre=9, post=4, out=5 |
| `c_0e6d3a6d` | `red` | `pad` | 59.6% | MISSED | 0f / 3.9px | MISSED | 2f / 72.8px | gap_b=3, gap_i=3, pre=None, post=None, out=None |
| `c_0f711886` | `red` | `stumps` | 92.0% | 0.10f / 24.3px | 0f / 4.3px | 3.00f / 26.6px | 2f / 73.4px | gap_b=0, gap_i=5, pre=9, post=3, out=5 |
| `c_13f43606` | `pink` | `pad` | 97.5% | 0.20f / 5.2px | 0f / 0.6px | 0.40f / 22.7px | 0f / 1.1px | gap_b=0, gap_i=0, pre=9, post=3, out=6 |
| `c_1a22464f` | `red` | `pad` | 66.7% | MISSED | MISSED | MISSED | MISSED | gap_b=2, gap_i=6, pre=None, post=None, out=None |
| `c_1a3657dc` | `red` | `stumps` | 83.3% | MISSED | 20f / 167.6px | MISSED | MISSED | gap_b=3, gap_i=7, pre=None, post=None, out=None |
| `c_2c5d337b` | `red` | `bat` | 36.8% | MISSED | MISSED | MISSED | MISSED | gap_b=3, gap_i=6, pre=None, post=None, out=None |
| `c_314bf724` | `white` | `bat` | 25.0% | MISSED | MISSED | MISSED | MISSED | gap_b=7, gap_i=3, pre=None, post=None, out=None |
| `c_34f3913c` | `red` | `pad` | 93.3% | MISSED | 0f / 2.3px | MISSED | 2f / 29.0px | gap_b=3, gap_i=3, pre=None, post=None, out=None |
| `c_363e37eb` | `red` | `stumps` | 74.6% | 0.20f / 10.3px | 0f / 2.5px | MISSED | 15f / 59.0px | gap_b=1, gap_i=7, pre=12, post=2, out=None |
| `c_3d27ed64` | `pink` | `pad` | 98.2% | 0.20f / 5.0px | 0f / 3.1px | 1.10f / 30.4px | 1f / 31.0px | gap_b=1, gap_i=1, pre=9, post=2, out=6 |
| `c_3f1fc736` | `pink` | `pad` | 96.2% | 0.05f / 7.5px | 0f / 1.9px | 0.40f / 24.3px | 0f / 2.2px | gap_b=0, gap_i=2, pre=8, post=3, out=6 |
| `c_41dd8473` | `pink` | `pad` | 98.5% | 0.75f / 2.5px | 0f / 3.2px | 0.40f / 21.1px | 0f / 10.1px | gap_b=1, gap_i=1, pre=8, post=4, out=6 |
| `c_458266f0` | `red` | `pad` | 67.7% | MISSED | 0f / 3.1px | MISSED | 0f / 15.0px | gap_b=2, gap_i=3, pre=None, post=None, out=None |
| `c_46c688a4` | `red` | `bat` | 80.6% | 0.20f / 3.8px | 0f / 2.5px | 0.75f / 25.3px | 2f / 60.4px | gap_b=2, gap_i=2, pre=10, post=2, out=6 |
| `c_4af78565` | `red` | `bat` | 48.7% | 0.30f / 15.6px | 20f / 818.0px | 2.10f / 40.5px | MISSED | gap_b=2, gap_i=2, pre=5, post=2, out=2 |
| `c_4b4d9800` | `pink` | `pad` | 82.9% | 1.15f / 28.0px | 0f / 5.1px | 2.10f / 119.1px | MISSED | gap_b=0, gap_i=0, pre=10, post=4, out=6 |
| `c_5284da33` | `red` | `none` | 53.2% | 3.00f / 133.9px | 30f / 441.8px | n/a | none | gap_b=3, gap_i=None, pre=3, post=29, out=None |
| `c_542fca8b` | `pink` | `pad` | 88.1% | 0.10f / 18.9px | 0f / 9.6px | 0.30f / 35.7px | 1f / 3.3px | gap_b=1, gap_i=1, pre=9, post=3, out=3 |
| `c_58280133` | `red` | `pad` | 77.0% | 0.55f / 16.9px | 0f / 1.7px | 0.30f / 25.5px | 4f / 104.6px | gap_b=1, gap_i=7, pre=9, post=2, out=3 |
| `c_5ca2aea4` | `red` | `pad` | 77.9% | 0.45f / 1.4px | 27f / 451.1px | 0.35f / 16.9px | MISSED | gap_b=1, gap_i=1, pre=5, post=4, out=6 |
| `c_5cef27ce` | `pink` | `pad` | 92.3% | 0.25f / 14.2px | 0f / 1.1px | 0.55f / 35.7px | 0f / 3.5px | gap_b=0, gap_i=3, pre=17, post=5, out=3 |
| `c_5e5ea872` | `pink` | `pad` | 53.1% | 0.20f / 7.6px | 0f / 2.0px | MISSED | 0f / 10.4px | gap_b=1, gap_i=2, pre=9, post=2, out=None |
| `c_6017cc47` | `red` | `pad` | 77.3% | MISSED | 0f / 1.1px | MISSED | MISSED | gap_b=3, gap_i=3, pre=None, post=None, out=None |
| `c_60748b53` | `red` | `bat` | 54.8% | 0.60f / 15.5px | 0f / 5.4px | MISSED | 1f / 7.9px | gap_b=1, gap_i=4, pre=9, post=2, out=None |
| `c_62cb3c5e` | `red` | `pad` | 88.3% | 0.70f / 8.5px | 12f / 235.2px | 0.25f / 24.7px | MISSED | gap_b=2, gap_i=2, pre=8, post=2, out=6 |
| `c_639d3baa` | `pink` | `bat` | 96.7% | MISSED | 0f / 2.7px | MISSED | 1f / 39.7px | gap_b=1, gap_i=1, pre=None, post=None, out=None |
| `c_663067dc` | `pink` | `pad` | 95.1% | 0.20f / 4.6px | 0f / 2.6px | 0.05f / 28.4px | 0f / 5.5px | gap_b=0, gap_i=2, pre=18, post=5, out=4 |
| `c_69ba9415` | `red` | `pad` | 8.2% | MISSED | MISSED | MISSED | MISSED | gap_b=5, gap_i=7, pre=None, post=None, out=None |
| `c_6e281881` | `red` | `pad` | 50.0% | MISSED | 1f / 10.7px | MISSED | MISSED | gap_b=3, gap_i=5, pre=None, post=None, out=None |
| `c_75de2445` | `white` | `stumps` | 3.8% | MISSED | MISSED | MISSED | MISSED | gap_b=4, gap_i=7, pre=None, post=None, out=None |
| `c_77509418` | `red` | `pad` | 90.9% | 0.70f / 3.9px | 1f / 12.2px | 0.10f / 30.7px | 0f / 18.5px | gap_b=1, gap_i=1, pre=7, post=5, out=6 |
| `c_77d7834d` | `pink` | `pad` | 93.3% | 0.30f / 7.0px | 1f / 5.8px | 0.20f / 33.3px | 1f / 47.1px | gap_b=1, gap_i=2, pre=8, post=2, out=6 |
| `c_7f64dd0c` | `red` | `none` | 72.0% | 0.30f / 39.7px | 1f / 6.2px | n/a | FP | gap_b=0, gap_i=None, pre=11, post=5, out=None |
| `c_823ebcd1` | `red` | `bat` | 91.8% | 0.55f / 1.6px | 0f / 2.6px | 0.60f / 22.6px | 0f / 6.4px | gap_b=0, gap_i=1, pre=14, post=3, out=5 |
| `c_865b0a59` | `pink` | `pad` | 97.6% | 0.30f / 14.0px | 0f / 2.8px | 0.70f / 26.2px | 1f / 26.0px | gap_b=0, gap_i=1, pre=10, post=2, out=5 |
| `c_8e93d6d9` | `red` | `pad` | 73.5% | MISSED | 0f / 2.3px | MISSED | MISSED | gap_b=3, gap_i=2, pre=None, post=None, out=None |
| `c_a473c3f0` | `pink` | `pad` | 97.0% | 0.55f / 16.4px | 1f / 16.4px | 1.35f / 41.9px | 0f / 3.4px | gap_b=0, gap_i=1, pre=10, post=2, out=5 |
| `c_b0c1cf14` | `pink` | `pad` | 90.9% | 0.15f / 4.1px | 0f / 2.6px | 3.00f / 134.3px | 2f / 151.7px | gap_b=0, gap_i=1, pre=10, post=4, out=4 |
| `c_be3c00d2` | `red` | `pad` | 59.7% | MISSED | 41f / 445.1px | MISSED | MISSED | gap_b=3, gap_i=5, pre=None, post=None, out=None |
| `c_c1faf433` | `red` | `stumps` | 56.5% | 3.00f / 47.4px | 1f / 12.6px | MISSED | MISSED | gap_b=4, gap_i=4, pre=10, post=2, out=None |
| `c_c576b682` | `red` | `pad` | 67.3% | MISSED | 23f / 369.7px | MISSED | MISSED | gap_b=4, gap_i=7, pre=None, post=None, out=None |
| `c_c900737d` | `red` | `none` | 51.4% | 0.10f / 15.9px | 0f / 3.1px | n/a | FP | gap_b=0, gap_i=None, pre=10, post=6, out=None |
| `c_dd85ffc4` | `red` | `none` | 53.1% | 1.70f / 56.0px | 0f / 4.8px | n/a | FP | gap_b=3, gap_i=None, pre=9, post=6, out=None |
| `c_e4d991bf` | `red` | `pad` | 88.2% | MISSED | 0f / 3.6px | MISSED | 4f / 114.4px | gap_b=2, gap_i=4, pre=None, post=None, out=None |
| `c_e6b5e8a3` | `pink` | `pad` | 98.0% | MISSED | 0f / 2.5px | MISSED | 0f / 8.9px | gap_b=1, gap_i=1, pre=None, post=None, out=None |
| `c_f31728c7` | `pink` | `pad` | 88.1% | 0.30f / 3.4px | 0f / 4.0px | 3.00f / 41.4px | 4f / 43.7px | gap_b=0, gap_i=5, pre=15, post=3, out=2 |
| `c_f4592060` | `red` | `stumps` | 19.1% | MISSED | MISSED | MISSED | MISSED | gap_b=3, gap_i=7, pre=None, post=None, out=None |
| `c_f4e30475` | `red` | `pad` | 45.8% | MISSED | MISSED | MISSED | MISSED | gap_b=3, gap_i=6, pre=None, post=None, out=None |
| `c_fe67d2d6` | `red` | `bat` | 51.5% | 0.00f / 18.9px | 0f / 3.2px | MISSED | MISSED | gap_b=1, gap_i=5, pre=13, post=2, out=None |

## 5. Per-Clip Table

| Clip ID | Ball | Imp Type | Recall (All / Bef / Aft) | Gaps (All / B±3 / I±3) | Bnc Fit (`|Δt|` / px) | Bnc Sys (`|Δt|` / px) | Imp Fit (`|Δt|` / px) | Imp Sys (`|Δt|` / px) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `c_0112a3f3` | `red` | `pad` | 18.6% / 57.1% / 0.0% | 34 / 5 / 7 | MISSED | MISSED | MISSED | MISSED |
| `c_045513d5` | `red` | `pad` | 76.3% / 78.9% / 73.7% | 5 / 2 / 5 | MISSED | 0f / 3.0px | MISSED | 6f / 116.5px |
| `c_0522189a` | `red` | `stumps` | 88.9% / 88.9% / 88.9% | 4 / 0 / 4 | 0.05f / 28.6px | 0f / 2.7px | 1.30f / 8.1px | 2f / 33.0px |
| `c_09650a59` | `red` | `pad` | 17.1% / 43.8% / 0.0% | 33 / 5 / 7 | MISSED | MISSED | MISSED | MISSED |
| `c_09a18d5f` | `pink` | `pad` | 98.4% / 100.0% / 97.8% | 1 / 0 / 1 | 0.35f / 4.5px | 0f / 3.7px | 0.65f / 47.6px | 2f / 74.6px |
| `c_0e6d3a6d` | `red` | `pad` | 59.6% / 86.7% / 48.6% | 4 / 3 / 3 | MISSED | 0f / 3.9px | MISSED | 2f / 72.8px |
| `c_0f711886` | `red` | `stumps` | 92.0% / 73.7% / 98.2% | 6 / 0 / 5 | 0.10f / 24.3px | 0f / 4.3px | 3.00f / 26.6px | 2f / 73.4px |
| `c_13f43606` | `pink` | `pad` | 97.5% / 100.0% / 96.0% | 1 / 0 / 0 | 0.20f / 5.2px | 0f / 0.6px | 0.40f / 22.7px | 0f / 1.1px |
| `c_1a22464f` | `red` | `pad` | 66.7% / 68.8% / 64.3% | 7 / 2 / 6 | MISSED | MISSED | MISSED | MISSED |
| `c_1a3657dc` | `red` | `stumps` | 83.3% / 72.2% / 88.1% | 9 / 3 / 7 | MISSED | 20f / 167.6px | MISSED | MISSED |
| `c_2c5d337b` | `red` | `bat` | 36.8% / 82.4% / 0.0% | 24 / 3 / 6 | MISSED | MISSED | MISSED | MISSED |
| `c_3089a3bb` | `red` | `none` | 77.8% / — / — | 6 / 2 / — | 0.35f / 14.9px | 0f / 3.7px | n/a | FP |
| `c_314bf724` | `white` | `bat` | 25.0% / 6.2% / 50.0% | 15 / 7 / 3 | MISSED | MISSED | MISSED | MISSED |
| `c_34f3913c` | `red` | `pad` | 93.3% / 83.3% / 100.0% | 3 / 3 / 3 | MISSED | 0f / 2.3px | MISSED | 2f / 29.0px |
| `c_363e37eb` | `red` | `stumps` | 74.6% / 80.0% / 72.5% | 18 / 1 / 7 | 0.20f / 10.3px | 0f / 2.5px | MISSED | 15f / 59.0px |
| `c_3d27ed64` | `pink` | `pad` | 98.2% / 93.3% / 100.0% | 1 / 1 / 1 | 0.20f / 5.0px | 0f / 3.1px | 1.10f / 30.4px | 1f / 31.0px |
| `c_3f1fc736` | `pink` | `pad` | 96.2% / 87.5% / 100.0% | 2 / 0 / 2 | 0.05f / 7.5px | 0f / 1.9px | 0.40f / 24.3px | 0f / 2.2px |
| `c_41dd8473` | `pink` | `pad` | 98.5% / 93.8% / 100.0% | 1 / 1 / 1 | 0.75f / 2.5px | 0f / 3.2px | 0.40f / 21.1px | 0f / 10.1px |
| `c_458266f0` | `red` | `pad` | 67.7% / 86.7% / 50.0% | 5 / 2 / 3 | MISSED | 0f / 3.1px | MISSED | 0f / 15.0px |
| `c_46c688a4` | `red` | `bat` | 80.6% / 77.8% / 84.6% | 3 / 2 / 2 | 0.20f / 3.8px | 0f / 2.5px | 0.75f / 25.3px | 2f / 60.4px |
| `c_4af78565` | `red` | `bat` | 48.7% / 39.1% / 62.5% | 7 / 2 / 2 | 0.30f / 15.6px | 20f / 818.0px | 2.10f / 40.5px | MISSED |
| `c_4b4d9800` | `pink` | `pad` | 82.9% / 100.0% / 66.7% | 3 / 0 / 0 | 1.15f / 28.0px | 0f / 5.1px | 2.10f / 119.1px | MISSED |
| `c_4cfd824c` | `red` | `none` | 57.1% / — / — | 8 / 1 / — | 0.65f / 3.0px | 1f / 9.3px | n/a | none |
| `c_5284da33` | `red` | `none` | 53.2% / — / — | 10 / 3 / — | 3.00f / 133.9px | 30f / 441.8px | n/a | none |
| `c_542fca8b` | `pink` | `pad` | 88.1% / 88.2% / 88.0% | 1 / 1 / 1 | 0.10f / 18.9px | 0f / 9.6px | 0.30f / 35.7px | 1f / 3.3px |
| `c_58280133` | `red` | `pad` | 77.0% / 65.0% / 82.9% | 9 / 1 / 7 | 0.55f / 16.9px | 0f / 1.7px | 0.30f / 25.5px | 4f / 104.6px |
| `c_5ca2aea4` | `red` | `pad` | 77.9% / 39.3% / 96.6% | 13 / 1 / 1 | 0.45f / 1.4px | 27f / 451.1px | 0.35f / 16.9px | MISSED |
| `c_5cef27ce` | `pink` | `pad` | 92.3% / 100.0% / 87.5% | 3 / 0 / 3 | 0.25f / 14.2px | 0f / 1.1px | 0.55f / 35.7px | 0f / 3.5px |
| `c_5e5ea872` | `pink` | `pad` | 53.1% / 93.3% / 17.6% | 14 / 1 / 2 | 0.20f / 7.6px | 0f / 2.0px | MISSED | 0f / 10.4px |
| `c_6017cc47` | `red` | `pad` | 77.3% / 77.3% / 77.3% | 5 / 3 / 3 | MISSED | 0f / 1.1px | MISSED | MISSED |
| `c_60748b53` | `red` | `bat` | 54.8% / 86.7% / 25.0% | 6 / 1 / 4 | 0.60f / 15.5px | 0f / 5.4px | MISSED | 1f / 7.9px |
| `c_62cb3c5e` | `red` | `pad` | 88.3% / 76.5% / 93.0% | 3 / 2 / 2 | 0.70f / 8.5px | 12f / 235.2px | 0.25f / 24.7px | MISSED |
| `c_639d3baa` | `pink` | `bat` | 96.7% / 93.3% / 100.0% | 1 / 1 / 1 | MISSED | 0f / 2.7px | MISSED | 1f / 39.7px |
| `c_663067dc` | `pink` | `pad` | 95.1% / 96.3% / 94.1% | 2 / 0 / 2 | 0.20f / 4.6px | 0f / 2.6px | 0.05f / 28.4px | 0f / 5.5px |
| `c_69ba9415` | `red` | `pad` | 8.2% / 29.4% / 0.0% | 51 / 5 / 7 | MISSED | MISSED | MISSED | MISSED |
| `c_6e281881` | `red` | `pad` | 50.0% / 86.7% / 7.7% | 14 / 3 / 5 | MISSED | 1f / 10.7px | MISSED | MISSED |
| `c_75de2445` | `white` | `stumps` | 3.8% / 8.0% / 0.0% | 34 / 4 / 7 | MISSED | MISSED | MISSED | MISSED |
| `c_77509418` | `red` | `pad` | 90.9% / 87.5% / 92.9% | 1 / 1 / 1 | 0.70f / 3.9px | 1f / 12.2px | 0.10f / 30.7px | 0f / 18.5px |
| `c_77d7834d` | `pink` | `pad` | 93.3% / 86.7% / 100.0% | 2 / 1 / 2 | 0.30f / 7.0px | 1f / 5.8px | 0.20f / 33.3px | 1f / 47.1px |
| `c_7f64dd0c` | `red` | `none` | 72.0% / — / — | 4 / 0 / — | 0.30f / 39.7px | 1f / 6.2px | n/a | FP |
| `c_823ebcd1` | `red` | `bat` | 91.8% / 80.0% / 97.9% | 3 / 0 / 1 | 0.55f / 1.6px | 0f / 2.6px | 0.60f / 22.6px | 0f / 6.4px |
| `c_865b0a59` | `pink` | `pad` | 97.6% / 100.0% / 96.2% | 1 / 0 / 1 | 0.30f / 14.0px | 0f / 2.8px | 0.70f / 26.2px | 1f / 26.0px |
| `c_8e93d6d9` | `red` | `pad` | 73.5% / 66.7% / 78.9% | 4 / 3 / 2 | MISSED | 0f / 2.3px | MISSED | MISSED |
| `c_a473c3f0` | `pink` | `pad` | 97.0% / 100.0% / 94.4% | 1 / 0 / 1 | 0.55f / 16.4px | 1f / 16.4px | 1.35f / 41.9px | 0f / 3.4px |
| `c_b0c1cf14` | `pink` | `pad` | 90.9% / 94.1% / 80.0% | 1 / 0 / 1 | 0.15f / 4.1px | 0f / 2.6px | 3.00f / 134.3px | 2f / 151.7px |
| `c_be3c00d2` | `red` | `pad` | 59.7% / 68.8% / 56.9% | 13 / 3 / 5 | MISSED | 41f / 445.1px | MISSED | MISSED |
| `c_c1faf433` | `red` | `stumps` | 56.5% / 72.2% / 0.0% | 6 / 4 / 4 | 3.00f / 47.4px | 1f / 12.6px | MISSED | MISSED |
| `c_c576b682` | `red` | `pad` | 67.3% / 58.8% / 71.1% | 11 / 4 / 7 | MISSED | 23f / 369.7px | MISSED | MISSED |
| `c_c900737d` | `red` | `none` | 51.4% / — / — | 17 / 0 / — | 0.10f / 15.9px | 0f / 3.1px | n/a | FP |
| `c_dd85ffc4` | `red` | `none` | 53.1% / — / — | 7 / 3 / — | 1.70f / 56.0px | 0f / 4.8px | n/a | FP |
| `c_e4d991bf` | `red` | `pad` | 88.2% / 75.0% / 94.3% | 4 / 2 / 4 | MISSED | 0f / 3.6px | MISSED | 4f / 114.4px |
| `c_e6b5e8a3` | `pink` | `pad` | 98.0% / 92.9% / 100.0% | 1 / 1 / 1 | MISSED | 0f / 2.5px | MISSED | 0f / 8.9px |
| `c_f31728c7` | `pink` | `pad` | 88.1% / 90.9% / 86.5% | 5 / 0 / 5 | 0.30f / 3.4px | 0f / 4.0px | 3.00f / 41.4px | 4f / 43.7px |
| `c_f4592060` | `red` | `stumps` | 19.1% / 3.6% / 42.1% | 20 / 3 / 7 | MISSED | MISSED | MISSED | MISSED |
| `c_f4e30475` | `red` | `pad` | 45.8% / 50.0% / 0.0% | 5 / 3 / 6 | MISSED | MISSED | MISSED | MISSED |
| `c_f51f593e` | `red` | `pad` | 95.2% / 87.5% / 97.8% | 1 / 1 / 1 | 0.20f / 14.3px | 0f / 3.7px | 0.20f / 9.7px | 1f / 23.5px |
| `c_fe67d2d6` | `red` | `bat` | 51.5% / 66.7% / 11.1% | 6 / 1 / 5 | 0.00f / 18.9px | 0f / 3.2px | MISSED | MISSED |
