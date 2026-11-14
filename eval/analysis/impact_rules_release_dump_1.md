# Impact Rule Search — release_dump_1

- Final labelled clips with non-none impact & raw detections: **14**
- Rules evaluated: **7**

## Ranked Rules (In-Sample)

| Rank | Rule | Found | Exact (0) | Within ±1 | Within ±2 | MAE (frames) | Px Dist (med / p90) |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | I2(max_turn) | 13/14 (92.9%) | 5/13 (35.7% of 14) | 9/13 (64.3% of 14) | 10/13 (71.4% of 14) | 1.46 | 23.5 / 182.9 |
| 2 | I1(theta=45) | 13/14 (92.9%) | 4/13 (28.6% of 14) | 7/13 (50.0% of 14) | 8/13 (57.1% of 14) | 2.69 | 31.3 / 221.9 |
| 3 | I1(theta=30) | 13/14 (92.9%) | 4/13 (28.6% of 14) | 6/13 (42.9% of 14) | 7/13 (50.0% of 14) | 2.85 | 113.9 / 221.9 |
| 4 | I4(last_seen) | 13/14 (92.9%) | 3/13 (21.4% of 14) | 5/13 (35.7% of 14) | 7/13 (50.0% of 14) | 4.15 | 113.6 / 373.3 |
| 5 | I1(theta=20) | 13/14 (92.9%) | 3/13 (21.4% of 14) | 5/13 (35.7% of 14) | 6/13 (42.9% of 14) | 3.08 | 131.0 / 221.9 |
| 6 | I3(speed_drop) | 12/14 (85.7%) | 1/12 (7.1% of 14) | 5/12 (35.7% of 14) | 6/12 (42.9% of 14) | 6.08 | 96.1 / 618.3 |
| 7 | I4(+1) | 13/14 (92.9%) | 0/13 (0.0% of 14) | 4/13 (28.6% of 14) | 6/13 (42.9% of 14) | 5.00 | 113.6 / 373.3 |

## Leave-One-Out Cross-Validation (LOO)

| Candidate Set | Found | Exact (0) | Within ±1 | Within ±2 | MAE (frames) | Px Dist (med / p90) |
|---|---:|---:|---:|---:|---:|---:|
| I1 (theta) | 13/14 (92.9%) | 3/13 (21.4% of 14) | 6/13 (42.9% of 14) | 7/13 (50.0% of 14) | 2.92 | 113.9 / 221.9 |
| I4 (+1 vs last_seen) | 13/14 (92.9%) | 3/13 (21.4% of 14) | 5/13 (35.7% of 14) | 7/13 (50.0% of 14) | 4.15 | 113.6 / 373.3 |
| ALL (I1..I4) | 13/14 (92.9%) | 5/13 (35.7% of 14) | 9/13 (64.3% of 14) | 10/13 (71.4% of 14) | 1.46 | 23.5 / 182.9 |

### LOO Folds — I1 (theta)

| Clip | Ball | Label | Chosen Rule | Pred | Err (rule - label) | Px Dist |
|---|---|---:|---|---:|---:|---:|
| c_09a18d5f | pink | 17 | I1(theta=45) | 5 | -12 | 209.4 |
| c_13f43606 | pink | 18 | I1(theta=45) | 18 | 0 | 1.3 |
| c_3d27ed64 | pink | 19 | I1(theta=45) | 20 | +1 | 31.3 |
| c_3f1fc736 | pink | 19 | I1(theta=45) | 19 | 0 | 2.5 |
| c_41dd8473 | pink | 19 | I1(theta=45) | 14 | -5 | 230.5 |
| c_542fca8b | pink | 21 | I1(theta=45) | 20 | -1 | 3.7 |
| c_5cef27ce | pink | 29 | I1(theta=45) | 24 | -5 | 154.3 |
| c_5e5ea872 | pink | 17 | I1(theta=30) | 14 | -3 | 148.5 |
| c_69ba9415 | red | 23 | I1(theta=45) | NA | NA | NA |
| c_6e281881 | red | 19 | I1(theta=45) | 17 | -2 | 113.9 |
| c_77d7834d | pink | 23 | I1(theta=45) | 18 | -5 | 225.1 |
| c_a473c3f0 | pink | 17 | I1(theta=45) | 14 | -3 | 131.0 |
| c_e6b5e8a3 | pink | 17 | I1(theta=45) | 17 | 0 | 8.4 |
| c_f51f593e | red | 18 | I1(theta=45) | 19 | +1 | 23.5 |

### LOO Folds — I4 (+1 vs last_seen)

| Clip | Ball | Label | Chosen Rule | Pred | Err (rule - label) | Px Dist |
|---|---|---:|---|---:|---:|---:|
| c_09a18d5f | pink | 17 | I4(last_seen) | 17 | 0 | 6.6 |
| c_13f43606 | pink | 18 | I4(last_seen) | 19 | +1 | 45.6 |
| c_3d27ed64 | pink | 19 | I4(last_seen) | 21 | +2 | 50.4 |
| c_3f1fc736 | pink | 19 | I4(last_seen) | 27 | +8 | 268.0 |
| c_41dd8473 | pink | 19 | I4(last_seen) | 27 | +8 | 204.5 |
| c_542fca8b | pink | 21 | I4(last_seen) | 30 | +9 | 450.3 |
| c_5cef27ce | pink | 29 | I4(last_seen) | 29 | 0 | 3.5 |
| c_5e5ea872 | pink | 17 | I4(last_seen) | 18 | +1 | 42.5 |
| c_69ba9415 | red | 23 | I4(last_seen) | NA | NA | NA |
| c_6e281881 | red | 19 | I4(last_seen) | 17 | -2 | 113.9 |
| c_77d7834d | pink | 23 | I4(last_seen) | 23 | 0 | 1.7 |
| c_a473c3f0 | pink | 17 | I4(last_seen) | 20 | +3 | 113.6 |
| c_e6b5e8a3 | pink | 17 | I4(last_seen) | 29 | +12 | 399.6 |
| c_f51f593e | red | 18 | I4(last_seen) | 26 | +8 | 231.0 |

### LOO Folds — ALL (I1..I4)

| Clip | Ball | Label | Chosen Rule | Pred | Err (rule - label) | Px Dist |
|---|---|---:|---|---:|---:|---:|
| c_09a18d5f | pink | 17 | I2(max_turn) | 12 | -5 | 195.9 |
| c_13f43606 | pink | 18 | I2(max_turn) | 18 | 0 | 1.3 |
| c_3d27ed64 | pink | 19 | I2(max_turn) | 20 | +1 | 31.3 |
| c_3f1fc736 | pink | 19 | I2(max_turn) | 19 | 0 | 2.5 |
| c_41dd8473 | pink | 19 | I2(max_turn) | 18 | -1 | 63.3 |
| c_542fca8b | pink | 21 | I2(max_turn) | 20 | -1 | 3.7 |
| c_5cef27ce | pink | 29 | I2(max_turn) | 29 | 0 | 3.5 |
| c_5e5ea872 | pink | 17 | I2(max_turn) | 17 | 0 | 10.4 |
| c_69ba9415 | red | 23 | I2(max_turn) | NA | NA | NA |
| c_6e281881 | red | 19 | I2(max_turn) | 17 | -2 | 113.9 |
| c_77d7834d | pink | 23 | I2(max_turn) | 18 | -5 | 225.1 |
| c_a473c3f0 | pink | 17 | I2(max_turn) | 14 | -3 | 131.0 |
| c_e6b5e8a3 | pink | 17 | I2(max_turn) | 17 | 0 | 8.4 |
| c_f51f593e | red | 18 | I2(max_turn) | 19 | +1 | 23.5 |

## Per-Clip Signed Errors (`rule - label`) — Best 3 Rules

| Clip | Ball | Label | I2(max_turn) | I1(theta=45) | I1(theta=30) |
|---|---|---:|---:|---:|---:|
| c_09a18d5f | pink | 17 | -5 | -12 | -12 |
| c_13f43606 | pink | 18 | 0 | 0 | 0 |
| c_3d27ed64 | pink | 19 | +1 | +1 | 0 |
| c_3f1fc736 | pink | 19 | 0 | 0 | 0 |
| c_41dd8473 | pink | 19 | -1 | -5 | -5 |
| c_542fca8b | pink | 21 | -1 | -1 | -1 |
| c_5cef27ce | pink | 29 | 0 | -5 | -5 |
| c_5e5ea872 | pink | 17 | 0 | 0 | -3 |
| c_69ba9415 | red | 23 | NA | NA | NA |
| c_6e281881 | red | 19 | -2 | -2 | -2 |
| c_77d7834d | pink | 23 | -5 | -5 | -5 |
| c_a473c3f0 | pink | 17 | -3 | -3 | -3 |
| c_e6b5e8a3 | pink | 17 | 0 | 0 | 0 |
| c_f51f593e | red | 18 | +1 | +1 | +1 |

## Clips Still Wrong for Each of the Best 3 Rules

### I2(max_turn)
- Missed (1): `c_69ba9415` (red: label=23, pred=None)
- Outside ±1 (4): `c_09a18d5f` (pink: label=17, pred=12, err=-5, px=195.9), `c_6e281881` (red: label=19, pred=17, err=-2, px=113.9), `c_77d7834d` (pink: label=23, pred=18, err=-5, px=225.1), `c_a473c3f0` (pink: label=17, pred=14, err=-3, px=131.0)
- Off by ±1 (4): `c_3d27ed64` (pink: label=19, pred=20, err=+1, px=31.3), `c_41dd8473` (pink: label=19, pred=18, err=-1, px=63.3), `c_542fca8b` (pink: label=21, pred=20, err=-1, px=3.7), `c_f51f593e` (red: label=18, pred=19, err=+1, px=23.5)

### I1(theta=45)
- Missed (1): `c_69ba9415` (red: label=23, pred=None)
- Outside ±1 (6): `c_09a18d5f` (pink: label=17, pred=5, err=-12, px=209.4), `c_41dd8473` (pink: label=19, pred=14, err=-5, px=230.5), `c_5cef27ce` (pink: label=29, pred=24, err=-5, px=154.3), `c_6e281881` (red: label=19, pred=17, err=-2, px=113.9), `c_77d7834d` (pink: label=23, pred=18, err=-5, px=225.1), `c_a473c3f0` (pink: label=17, pred=14, err=-3, px=131.0)
- Off by ±1 (3): `c_3d27ed64` (pink: label=19, pred=20, err=+1, px=31.3), `c_542fca8b` (pink: label=21, pred=20, err=-1, px=3.7), `c_f51f593e` (red: label=18, pred=19, err=+1, px=23.5)

### I1(theta=30)
- Missed (1): `c_69ba9415` (red: label=23, pred=None)
- Outside ±1 (7): `c_09a18d5f` (pink: label=17, pred=5, err=-12, px=209.4), `c_41dd8473` (pink: label=19, pred=14, err=-5, px=230.5), `c_5cef27ce` (pink: label=29, pred=24, err=-5, px=154.3), `c_5e5ea872` (pink: label=17, pred=14, err=-3, px=148.5), `c_6e281881` (red: label=19, pred=17, err=-2, px=113.9), `c_77d7834d` (pink: label=23, pred=18, err=-5, px=225.1), `c_a473c3f0` (pink: label=17, pred=14, err=-3, px=131.0)
- Off by ±1 (2): `c_542fca8b` (pink: label=21, pred=20, err=-1, px=3.7), `c_f51f593e` (red: label=18, pred=19, err=+1, px=23.5)
