# Release Rule Search — release_dump_1

- Final labelled clips with raw detections: **14**
- Rules evaluated: **27**

## Ranked Rules (In-Sample)

| Rank | Rule | Exact (0) | Within ±1 | Within ±2 | MAE (frames) | Scored |
|---:|---|---:|---:|---:|---:|---:|
| 1 | R1(K=2,T=0.065) | 7/14 | 12/14 | 14/14 | 0.64 | 14/14 |
| 2 | R1(K=2,T=0.075) | 7/14 | 12/14 | 14/14 | 0.64 | 14/14 |
| 3 | R1(K=3,T=0.065) | 7/14 | 12/14 | 14/14 | 0.64 | 14/14 |
| 4 | R1(K=3,T=0.075) | 7/14 | 12/14 | 14/14 | 0.64 | 14/14 |
| 5 | R1(K=4,T=0.065) | 7/14 | 12/14 | 14/14 | 0.64 | 14/14 |
| 6 | R1(K=4,T=0.075) | 7/14 | 12/14 | 14/14 | 0.64 | 14/14 |
| 7 | R4(K=2,T=0.065) | 7/14 | 12/14 | 14/14 | 0.64 | 14/14 |
| 8 | R4(K=2,T=0.075) | 7/14 | 12/14 | 14/14 | 0.64 | 14/14 |
| 9 | R4(K=3,T=0.065) | 7/14 | 12/14 | 14/14 | 0.64 | 14/14 |
| 10 | R4(K=3,T=0.075) | 7/14 | 12/14 | 14/14 | 0.64 | 14/14 |
| 11 | R4(K=4,T=0.065) | 7/14 | 12/14 | 14/14 | 0.64 | 14/14 |
| 12 | R4(K=4,T=0.075) | 7/14 | 12/14 | 14/14 | 0.64 | 14/14 |
| 13 | R1(K=2,T=0.045) | 6/14 | 12/14 | 14/14 | 0.71 | 14/14 |
| 14 | R1(K=2,T=0.055) | 6/14 | 12/14 | 14/14 | 0.71 | 14/14 |
| 15 | R1(K=3,T=0.045) | 6/14 | 12/14 | 14/14 | 0.71 | 14/14 |
| 16 | R1(K=3,T=0.055) | 6/14 | 12/14 | 14/14 | 0.71 | 14/14 |
| 17 | R1(K=4,T=0.045) | 6/14 | 12/14 | 14/14 | 0.71 | 14/14 |
| 18 | R1(K=4,T=0.055) | 6/14 | 12/14 | 14/14 | 0.71 | 14/14 |
| 19 | R4(K=2,T=0.045) | 6/14 | 12/14 | 14/14 | 0.71 | 14/14 |
| 20 | R4(K=2,T=0.055) | 6/14 | 12/14 | 14/14 | 0.71 | 14/14 |
| 21 | R4(K=3,T=0.045) | 6/14 | 12/14 | 14/14 | 0.71 | 14/14 |
| 22 | R4(K=3,T=0.055) | 6/14 | 12/14 | 14/14 | 0.71 | 14/14 |
| 23 | R4(K=4,T=0.045) | 6/14 | 12/14 | 14/14 | 0.71 | 14/14 |
| 24 | R4(K=4,T=0.055) | 6/14 | 12/14 | 14/14 | 0.71 | 14/14 |
| 25 | R2 | 3/14 | 8/14 | 11/14 | 1.79 | 14/14 |
| 26 | R0 | 4/14 | 6/14 | 8/14 | 1.93 | 14/14 |
| 27 | R3 | 4/14 | 6/14 | 7/14 | 10.79 | 14/14 |

## Leave-One-Out Cross-Validation (LOO)

| Candidate Set | Exact (0) | Within ±1 | Within ±2 | MAE (frames) | Threshold (>=11/14 ±1) |
|---|---:|---:|---:|---:|---|
| R1 | 6/14 | 12/14 | 14/14 | 0.71 | PASS |
| R4 | 6/14 | 12/14 | 14/14 | 0.71 | PASS |
| R1+R4 | 6/14 | 12/14 | 14/14 | 0.71 | PASS |
| ALL (R0..R4) | 6/14 | 12/14 | 14/14 | 0.71 | PASS |

### LOO Folds — R1

| Clip | Ball | Label | Chosen Rule | Pred | Err (rule - label) |
|---|---|---:|---|---:|---:|
| c_09a18d5f | pink | 2 | R1(K=2,T=0.065) | 4 | +2 |
| c_13f43606 | pink | 4 | R1(K=2,T=0.065) | 4 | 0 |
| c_3d27ed64 | pink | 5 | R1(K=2,T=0.065) | 5 | 0 |
| c_3f1fc736 | pink | 4 | R1(K=2,T=0.065) | 3 | -1 |
| c_41dd8473 | pink | 4 | R1(K=2,T=0.065) | 5 | +1 |
| c_542fca8b | pink | 5 | R1(K=2,T=0.045) | 6 | +1 |
| c_5cef27ce | pink | 5 | R1(K=2,T=0.065) | 4 | -1 |
| c_5e5ea872 | pink | 3 | R1(K=2,T=0.065) | 3 | 0 |
| c_69ba9415 | red | 7 | R1(K=2,T=0.065) | 9 | +2 |
| c_6e281881 | red | 5 | R1(K=2,T=0.065) | 5 | 0 |
| c_77d7834d | pink | 9 | R1(K=2,T=0.065) | 9 | 0 |
| c_a473c3f0 | pink | 3 | R1(K=2,T=0.065) | 4 | +1 |
| c_e6b5e8a3 | pink | 4 | R1(K=2,T=0.065) | 5 | +1 |
| c_f51f593e | red | 3 | R1(K=2,T=0.065) | 3 | 0 |

### LOO Folds — R4

| Clip | Ball | Label | Chosen Rule | Pred | Err (rule - label) |
|---|---|---:|---|---:|---:|
| c_09a18d5f | pink | 2 | R4(K=2,T=0.065) | 4 | +2 |
| c_13f43606 | pink | 4 | R4(K=2,T=0.065) | 4 | 0 |
| c_3d27ed64 | pink | 5 | R4(K=2,T=0.065) | 5 | 0 |
| c_3f1fc736 | pink | 4 | R4(K=2,T=0.065) | 3 | -1 |
| c_41dd8473 | pink | 4 | R4(K=2,T=0.065) | 5 | +1 |
| c_542fca8b | pink | 5 | R4(K=2,T=0.045) | 6 | +1 |
| c_5cef27ce | pink | 5 | R4(K=2,T=0.065) | 4 | -1 |
| c_5e5ea872 | pink | 3 | R4(K=2,T=0.065) | 3 | 0 |
| c_69ba9415 | red | 7 | R4(K=2,T=0.065) | 9 | +2 |
| c_6e281881 | red | 5 | R4(K=2,T=0.065) | 5 | 0 |
| c_77d7834d | pink | 9 | R4(K=2,T=0.065) | 9 | 0 |
| c_a473c3f0 | pink | 3 | R4(K=2,T=0.065) | 4 | +1 |
| c_e6b5e8a3 | pink | 4 | R4(K=2,T=0.065) | 5 | +1 |
| c_f51f593e | red | 3 | R4(K=2,T=0.065) | 3 | 0 |

### LOO Folds — R1+R4

| Clip | Ball | Label | Chosen Rule | Pred | Err (rule - label) |
|---|---|---:|---|---:|---:|
| c_09a18d5f | pink | 2 | R1(K=2,T=0.065) | 4 | +2 |
| c_13f43606 | pink | 4 | R1(K=2,T=0.065) | 4 | 0 |
| c_3d27ed64 | pink | 5 | R1(K=2,T=0.065) | 5 | 0 |
| c_3f1fc736 | pink | 4 | R1(K=2,T=0.065) | 3 | -1 |
| c_41dd8473 | pink | 4 | R1(K=2,T=0.065) | 5 | +1 |
| c_542fca8b | pink | 5 | R1(K=2,T=0.045) | 6 | +1 |
| c_5cef27ce | pink | 5 | R1(K=2,T=0.065) | 4 | -1 |
| c_5e5ea872 | pink | 3 | R1(K=2,T=0.065) | 3 | 0 |
| c_69ba9415 | red | 7 | R1(K=2,T=0.065) | 9 | +2 |
| c_6e281881 | red | 5 | R1(K=2,T=0.065) | 5 | 0 |
| c_77d7834d | pink | 9 | R1(K=2,T=0.065) | 9 | 0 |
| c_a473c3f0 | pink | 3 | R1(K=2,T=0.065) | 4 | +1 |
| c_e6b5e8a3 | pink | 4 | R1(K=2,T=0.065) | 5 | +1 |
| c_f51f593e | red | 3 | R1(K=2,T=0.065) | 3 | 0 |

### LOO Folds — ALL (R0..R4)

| Clip | Ball | Label | Chosen Rule | Pred | Err (rule - label) |
|---|---|---:|---|---:|---:|
| c_09a18d5f | pink | 2 | R1(K=2,T=0.065) | 4 | +2 |
| c_13f43606 | pink | 4 | R1(K=2,T=0.065) | 4 | 0 |
| c_3d27ed64 | pink | 5 | R1(K=2,T=0.065) | 5 | 0 |
| c_3f1fc736 | pink | 4 | R1(K=2,T=0.065) | 3 | -1 |
| c_41dd8473 | pink | 4 | R1(K=2,T=0.065) | 5 | +1 |
| c_542fca8b | pink | 5 | R1(K=2,T=0.045) | 6 | +1 |
| c_5cef27ce | pink | 5 | R1(K=2,T=0.065) | 4 | -1 |
| c_5e5ea872 | pink | 3 | R1(K=2,T=0.065) | 3 | 0 |
| c_69ba9415 | red | 7 | R1(K=2,T=0.065) | 9 | +2 |
| c_6e281881 | red | 5 | R1(K=2,T=0.065) | 5 | 0 |
| c_77d7834d | pink | 9 | R1(K=2,T=0.065) | 9 | 0 |
| c_a473c3f0 | pink | 3 | R1(K=2,T=0.065) | 4 | +1 |
| c_e6b5e8a3 | pink | 4 | R1(K=2,T=0.065) | 5 | +1 |
| c_f51f593e | red | 3 | R1(K=2,T=0.065) | 3 | 0 |

## Per-Clip Signed Errors (`rule - label`) — Best 3 Rules

| Clip | Ball | Label | R1(K=2,T=0.065) | R1(K=2,T=0.075) | R1(K=3,T=0.065) |
|---|---|---:|---:|---:|---:|
| c_09a18d5f | pink | 2 | +2 | +2 | +2 |
| c_13f43606 | pink | 4 | 0 | 0 | 0 |
| c_3d27ed64 | pink | 5 | 0 | 0 | 0 |
| c_3f1fc736 | pink | 4 | -1 | -1 | -1 |
| c_41dd8473 | pink | 4 | +1 | +1 | +1 |
| c_542fca8b | pink | 5 | 0 | 0 | 0 |
| c_5cef27ce | pink | 5 | -1 | -1 | -1 |
| c_5e5ea872 | pink | 3 | 0 | 0 | 0 |
| c_69ba9415 | red | 7 | +2 | +2 | +2 |
| c_6e281881 | red | 5 | 0 | 0 | 0 |
| c_77d7834d | pink | 9 | 0 | 0 | 0 |
| c_a473c3f0 | pink | 3 | +1 | +1 | +1 |
| c_e6b5e8a3 | pink | 4 | +1 | +1 | +1 |
| c_f51f593e | red | 3 | 0 | 0 | 0 |

## Clips Still Wrong for Each of the Best 3 Rules

### R1(K=2,T=0.065)
- Outside ±1 (2): `c_09a18d5f` (pink: label=2, pred=4, err=+2), `c_69ba9415` (red: label=7, pred=9, err=+2)
- Off by ±1 (5): `c_3f1fc736` (pink: label=4, pred=3, err=-1), `c_41dd8473` (pink: label=4, pred=5, err=+1), `c_5cef27ce` (pink: label=5, pred=4, err=-1), `c_a473c3f0` (pink: label=3, pred=4, err=+1), `c_e6b5e8a3` (pink: label=4, pred=5, err=+1)

### R1(K=2,T=0.075)
- Outside ±1 (2): `c_09a18d5f` (pink: label=2, pred=4, err=+2), `c_69ba9415` (red: label=7, pred=9, err=+2)
- Off by ±1 (5): `c_3f1fc736` (pink: label=4, pred=3, err=-1), `c_41dd8473` (pink: label=4, pred=5, err=+1), `c_5cef27ce` (pink: label=5, pred=4, err=-1), `c_a473c3f0` (pink: label=3, pred=4, err=+1), `c_e6b5e8a3` (pink: label=4, pred=5, err=+1)

### R1(K=3,T=0.065)
- Outside ±1 (2): `c_09a18d5f` (pink: label=2, pred=4, err=+2), `c_69ba9415` (red: label=7, pred=9, err=+2)
- Off by ±1 (5): `c_3f1fc736` (pink: label=4, pred=3, err=-1), `c_41dd8473` (pink: label=4, pred=5, err=+1), `c_5cef27ce` (pink: label=5, pred=4, err=-1), `c_a473c3f0` (pink: label=3, pred=4, err=+1), `c_e6b5e8a3` (pink: label=4, pred=5, err=+1)
