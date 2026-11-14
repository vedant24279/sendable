# Impact Rule Search — release_dump_1

- Final labelled clips with non-none impact & raw detections: **14**
- Rules evaluated: **31**

## Ranked Rules (In-Sample)

| Rank | Rule | Found | Exact (0) | Within ±1 | Within ±2 | MAE (frames) | Px Dist (med / p90) |
|---:|---|---:|---:|---:|---:|---:|---:|
| ref | SYSTEM(deviation) | 13/14 (92.9%) | 2/13 (14.3% of 14) | 6/13 (42.9% of 14) | 10/13 (71.4% of 14) | 3.23 | 55.0 / 108.2 |
| 1 | I5b(up=0.01,theta=20) | 12/14 (85.7%) | 7/12 (50.0% of 14) | 11/12 (78.6% of 14) | 12/12 (85.7% of 14) | 0.50 | 9.4 / 45.5 |
| 2 | I5b(up=0.01,theta=30) | 12/14 (85.7%) | 7/12 (50.0% of 14) | 11/12 (78.6% of 14) | 12/12 (85.7% of 14) | 0.50 | 9.4 / 45.5 |
| 3 | I5b(up=0.02,theta=20) | 12/14 (85.7%) | 7/12 (50.0% of 14) | 11/12 (78.6% of 14) | 12/12 (85.7% of 14) | 0.50 | 9.4 / 45.5 |
| 4 | I5b(up=0.02,theta=30) | 12/14 (85.7%) | 7/12 (50.0% of 14) | 11/12 (78.6% of 14) | 12/12 (85.7% of 14) | 0.50 | 9.4 / 45.5 |
| 5 | I6b(up=0.01,theta=20) | 13/14 (92.9%) | 7/13 (50.0% of 14) | 11/13 (78.6% of 14) | 12/13 (85.7% of 14) | 1.46 | 10.3 / 68.9 |
| 6 | I6b(up=0.01,theta=30) | 13/14 (92.9%) | 7/13 (50.0% of 14) | 11/13 (78.6% of 14) | 12/13 (85.7% of 14) | 1.46 | 10.3 / 68.9 |
| 7 | I6b(up=0.02,theta=20) | 13/14 (92.9%) | 7/13 (50.0% of 14) | 11/13 (78.6% of 14) | 12/13 (85.7% of 14) | 1.46 | 10.3 / 68.9 |
| 8 | I6b(up=0.02,theta=30) | 13/14 (92.9%) | 7/13 (50.0% of 14) | 11/13 (78.6% of 14) | 12/13 (85.7% of 14) | 1.46 | 10.3 / 68.9 |
| 9 | I5b(up=0.01,theta=45) | 10/14 (71.4%) | 7/10 (50.0% of 14) | 10/10 (71.4% of 14) | 10/10 (71.4% of 14) | 0.30 | 6.1 / 24.2 |
| 10 | I5b(up=0.02,theta=45) | 10/14 (71.4%) | 7/10 (50.0% of 14) | 10/10 (71.4% of 14) | 10/10 (71.4% of 14) | 0.30 | 6.1 / 24.2 |
| 11 | I6b(up=0.01,theta=45) | 11/14 (78.6%) | 7/11 (50.0% of 14) | 10/11 (71.4% of 14) | 10/11 (71.4% of 14) | 1.45 | 8.4 / 31.3 |
| 12 | I6b(up=0.02,theta=45) | 11/14 (78.6%) | 7/11 (50.0% of 14) | 10/11 (71.4% of 14) | 10/11 (71.4% of 14) | 1.45 | 8.4 / 31.3 |
| 13 | I5a(up=0.01,theta=30) | 12/14 (85.7%) | 5/12 (35.7% of 14) | 10/12 (71.4% of 14) | 11/12 (78.6% of 14) | 0.83 | 12.8 / 73.2 |
| 14 | I5a(up=0.02,theta=30) | 12/14 (85.7%) | 5/12 (35.7% of 14) | 10/12 (71.4% of 14) | 11/12 (78.6% of 14) | 0.83 | 12.8 / 73.2 |
| 15 | I5a(up=0.01,theta=20) | 12/14 (85.7%) | 5/12 (35.7% of 14) | 10/12 (71.4% of 14) | 11/12 (78.6% of 14) | 0.83 | 26.7 / 63.0 |
| 16 | I5a(up=0.02,theta=20) | 12/14 (85.7%) | 5/12 (35.7% of 14) | 10/12 (71.4% of 14) | 11/12 (78.6% of 14) | 0.83 | 26.7 / 63.0 |
| 17 | I6a(up=0.02,theta=30) | 13/14 (92.9%) | 5/13 (35.7% of 14) | 10/13 (71.4% of 14) | 11/13 (78.6% of 14) | 1.77 | 15.2 / 99.9 |
| 18 | I6a(up=0.02,theta=20) | 13/14 (92.9%) | 5/13 (35.7% of 14) | 10/13 (71.4% of 14) | 11/13 (78.6% of 14) | 1.77 | 38.3 / 97.7 |
| 19 | I2(max_turn) | 13/14 (92.9%) | 5/13 (35.7% of 14) | 9/13 (64.3% of 14) | 10/13 (71.4% of 14) | 1.46 | 23.5 / 182.9 |
| 20 | I5a(up=0.01,theta=45) | 10/14 (71.4%) | 5/10 (35.7% of 14) | 9/10 (64.3% of 14) | 9/10 (64.3% of 14) | 0.70 | 9.4 / 67.6 |
| 21 | I5a(up=0.02,theta=45) | 10/14 (71.4%) | 5/10 (35.7% of 14) | 9/10 (64.3% of 14) | 9/10 (64.3% of 14) | 0.70 | 9.4 / 67.6 |
| 22 | I6a(up=0.01,theta=45) | 11/14 (78.6%) | 5/11 (35.7% of 14) | 9/11 (64.3% of 14) | 9/11 (64.3% of 14) | 1.82 | 10.4 / 106.2 |
| 23 | I6a(up=0.02,theta=45) | 11/14 (78.6%) | 5/11 (35.7% of 14) | 9/11 (64.3% of 14) | 9/11 (64.3% of 14) | 1.82 | 10.4 / 106.2 |
| 24 | I6a(up=0.01,theta=30) | 13/14 (92.9%) | 4/13 (28.6% of 14) | 9/13 (64.3% of 14) | 10/13 (71.4% of 14) | 2.00 | 38.3 / 140.1 |
| 25 | I1(theta=45) | 13/14 (92.9%) | 4/13 (28.6% of 14) | 7/13 (50.0% of 14) | 8/13 (57.1% of 14) | 2.69 | 31.3 / 221.9 |
| 26 | I6a(up=0.01,theta=20) | 13/14 (92.9%) | 4/13 (28.6% of 14) | 7/13 (50.0% of 14) | 8/13 (57.1% of 14) | 2.85 | 53.0 / 186.0 |
| 27 | I1(theta=30) | 13/14 (92.9%) | 4/13 (28.6% of 14) | 6/13 (42.9% of 14) | 7/13 (50.0% of 14) | 2.85 | 113.9 / 221.9 |
| 28 | I4(last_seen) | 13/14 (92.9%) | 3/13 (21.4% of 14) | 5/13 (35.7% of 14) | 7/13 (50.0% of 14) | 4.15 | 113.6 / 373.3 |
| 29 | I1(theta=20) | 13/14 (92.9%) | 3/13 (21.4% of 14) | 5/13 (35.7% of 14) | 6/13 (42.9% of 14) | 3.08 | 131.0 / 221.9 |
| 30 | I3(speed_drop) | 12/14 (85.7%) | 1/12 (7.1% of 14) | 5/12 (35.7% of 14) | 6/12 (42.9% of 14) | 6.08 | 96.1 / 618.3 |
| 31 | I4(+1) | 13/14 (92.9%) | 0/13 (0.0% of 14) | 4/13 (28.6% of 14) | 6/13 (42.9% of 14) | 5.00 | 113.6 / 373.3 |

## Leave-One-Out Cross-Validation (LOO)

| Candidate Set | Found | Exact (0) | Within ±1 | Within ±2 | MAE (frames) | Px Dist (med / p90) |
|---|---:|---:|---:|---:|---:|---:|
| I1 (theta) | 13/14 (92.9%) | 3/13 (21.4% of 14) | 6/13 (42.9% of 14) | 7/13 (50.0% of 14) | 2.92 | 113.9 / 221.9 |
| I4 (+1 vs last_seen) | 13/14 (92.9%) | 3/13 (21.4% of 14) | 5/13 (35.7% of 14) | 7/13 (50.0% of 14) | 4.15 | 113.6 / 373.3 |
| I5a (up, theta) | 12/14 (85.7%) | 3/12 (21.4% of 14) | 9/12 (64.3% of 14) | 11/12 (78.6% of 14) | 1.08 | 46.6 / 73.2 |
| I5b (up, theta) | 12/14 (85.7%) | 7/12 (50.0% of 14) | 11/12 (78.6% of 14) | 12/12 (85.7% of 14) | 0.50 | 9.4 / 45.5 |
| I5 (I5a + I5b) | 12/14 (85.7%) | 7/12 (50.0% of 14) | 11/12 (78.6% of 14) | 12/12 (85.7% of 14) | 0.50 | 9.4 / 45.5 |
| I6a (up, theta) | 13/14 (92.9%) | 3/13 (21.4% of 14) | 9/13 (64.3% of 14) | 11/13 (78.6% of 14) | 2.00 | 47.1 / 99.9 |
| I6b (up, theta) | 13/14 (92.9%) | 7/13 (50.0% of 14) | 11/13 (78.6% of 14) | 12/13 (85.7% of 14) | 1.46 | 10.3 / 68.9 |
| I6 (I6a + I6b) | 13/14 (92.9%) | 7/13 (50.0% of 14) | 11/13 (78.6% of 14) | 12/13 (85.7% of 14) | 1.46 | 10.3 / 68.9 |
| ALL (I1..I6) | 12/14 (85.7%) | 7/12 (50.0% of 14) | 11/12 (78.6% of 14) | 12/12 (85.7% of 14) | 0.50 | 9.4 / 45.5 |

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

### LOO Folds — I5a (up, theta)

| Clip | Ball | Label | Chosen Rule | Pred | Err (rule - label) | Px Dist |
|---|---|---:|---|---:|---:|---:|
| c_09a18d5f | pink | 17 | I5a(up=0.01,theta=30) | 19 | +2 | 74.3 |
| c_13f43606 | pink | 18 | I5a(up=0.01,theta=20) | 17 | -1 | 46.2 |
| c_3d27ed64 | pink | 19 | I5a(up=0.01,theta=30) | 19 | 0 | 8.9 |
| c_3f1fc736 | pink | 19 | I5a(up=0.01,theta=30) | 16 | -3 | 106.2 |
| c_41dd8473 | pink | 19 | I5a(up=0.01,theta=30) | 18 | -1 | 63.3 |
| c_542fca8b | pink | 21 | I5a(up=0.01,theta=20) | 19 | -2 | 53.0 |
| c_5cef27ce | pink | 29 | I5a(up=0.01,theta=30) | 28 | -1 | 15.2 |
| c_5e5ea872 | pink | 17 | I5a(up=0.01,theta=20) | 16 | -1 | 60.4 |
| c_69ba9415 | red | 23 | I5a(up=0.01,theta=30) | NA | NA | NA |
| c_6e281881 | red | 19 | I5a(up=0.01,theta=30) | NA | NA | NA |
| c_77d7834d | pink | 23 | I5a(up=0.01,theta=30) | 24 | +1 | 47.1 |
| c_a473c3f0 | pink | 17 | I5a(up=0.01,theta=30) | 17 | 0 | 2.9 |
| c_e6b5e8a3 | pink | 17 | I5a(up=0.01,theta=30) | 17 | 0 | 8.4 |
| c_f51f593e | red | 18 | I5a(up=0.01,theta=30) | 17 | -1 | 38.3 |

### LOO Folds — I5b (up, theta)

| Clip | Ball | Label | Chosen Rule | Pred | Err (rule - label) | Px Dist |
|---|---|---:|---|---:|---:|---:|
| c_09a18d5f | pink | 17 | I5b(up=0.01,theta=20) | 19 | +2 | 74.3 |
| c_13f43606 | pink | 18 | I5b(up=0.01,theta=20) | 18 | 0 | 1.3 |
| c_3d27ed64 | pink | 19 | I5b(up=0.01,theta=20) | 20 | +1 | 31.3 |
| c_3f1fc736 | pink | 19 | I5b(up=0.01,theta=20) | 19 | 0 | 2.5 |
| c_41dd8473 | pink | 19 | I5b(up=0.01,theta=20) | 19 | 0 | 10.3 |
| c_542fca8b | pink | 21 | I5b(up=0.01,theta=20) | 20 | -1 | 3.7 |
| c_5cef27ce | pink | 29 | I5b(up=0.01,theta=20) | 29 | 0 | 3.5 |
| c_5e5ea872 | pink | 17 | I5b(up=0.01,theta=20) | 17 | 0 | 10.4 |
| c_69ba9415 | red | 23 | I5b(up=0.01,theta=20) | NA | NA | NA |
| c_6e281881 | red | 19 | I5b(up=0.01,theta=20) | NA | NA | NA |
| c_77d7834d | pink | 23 | I5b(up=0.01,theta=20) | 24 | +1 | 47.1 |
| c_a473c3f0 | pink | 17 | I5b(up=0.01,theta=20) | 17 | 0 | 2.9 |
| c_e6b5e8a3 | pink | 17 | I5b(up=0.01,theta=20) | 17 | 0 | 8.4 |
| c_f51f593e | red | 18 | I5b(up=0.01,theta=20) | 19 | +1 | 23.5 |

### LOO Folds — I5 (I5a + I5b)

| Clip | Ball | Label | Chosen Rule | Pred | Err (rule - label) | Px Dist |
|---|---|---:|---|---:|---:|---:|
| c_09a18d5f | pink | 17 | I5b(up=0.01,theta=20) | 19 | +2 | 74.3 |
| c_13f43606 | pink | 18 | I5b(up=0.01,theta=20) | 18 | 0 | 1.3 |
| c_3d27ed64 | pink | 19 | I5b(up=0.01,theta=20) | 20 | +1 | 31.3 |
| c_3f1fc736 | pink | 19 | I5b(up=0.01,theta=20) | 19 | 0 | 2.5 |
| c_41dd8473 | pink | 19 | I5b(up=0.01,theta=20) | 19 | 0 | 10.3 |
| c_542fca8b | pink | 21 | I5b(up=0.01,theta=20) | 20 | -1 | 3.7 |
| c_5cef27ce | pink | 29 | I5b(up=0.01,theta=20) | 29 | 0 | 3.5 |
| c_5e5ea872 | pink | 17 | I5b(up=0.01,theta=20) | 17 | 0 | 10.4 |
| c_69ba9415 | red | 23 | I5b(up=0.01,theta=20) | NA | NA | NA |
| c_6e281881 | red | 19 | I5b(up=0.01,theta=20) | NA | NA | NA |
| c_77d7834d | pink | 23 | I5b(up=0.01,theta=20) | 24 | +1 | 47.1 |
| c_a473c3f0 | pink | 17 | I5b(up=0.01,theta=20) | 17 | 0 | 2.9 |
| c_e6b5e8a3 | pink | 17 | I5b(up=0.01,theta=20) | 17 | 0 | 8.4 |
| c_f51f593e | red | 18 | I5b(up=0.01,theta=20) | 19 | +1 | 23.5 |

### LOO Folds — I6a (up, theta)

| Clip | Ball | Label | Chosen Rule | Pred | Err (rule - label) | Px Dist |
|---|---|---:|---|---:|---:|---:|
| c_09a18d5f | pink | 17 | I6a(up=0.02,theta=30) | 19 | +2 | 74.3 |
| c_13f43606 | pink | 18 | I6a(up=0.02,theta=20) | 17 | -1 | 46.2 |
| c_3d27ed64 | pink | 19 | I6a(up=0.02,theta=30) | 19 | 0 | 8.9 |
| c_3f1fc736 | pink | 19 | I6a(up=0.02,theta=30) | 16 | -3 | 106.2 |
| c_41dd8473 | pink | 19 | I6a(up=0.02,theta=30) | 18 | -1 | 63.3 |
| c_542fca8b | pink | 21 | I6a(up=0.02,theta=20) | 19 | -2 | 53.0 |
| c_5cef27ce | pink | 29 | I6a(up=0.02,theta=30) | 28 | -1 | 15.2 |
| c_5e5ea872 | pink | 17 | I6a(up=0.02,theta=20) | 16 | -1 | 60.4 |
| c_69ba9415 | red | 23 | I6a(up=0.02,theta=30) | NA | NA | NA |
| c_6e281881 | red | 19 | I6a(up=0.02,theta=30) | 32 | +13 | 617.4 |
| c_77d7834d | pink | 23 | I6a(up=0.02,theta=30) | 24 | +1 | 47.1 |
| c_a473c3f0 | pink | 17 | I6a(up=0.02,theta=30) | 17 | 0 | 2.9 |
| c_e6b5e8a3 | pink | 17 | I6a(up=0.02,theta=30) | 17 | 0 | 8.4 |
| c_f51f593e | red | 18 | I6a(up=0.02,theta=30) | 17 | -1 | 38.3 |

### LOO Folds — I6b (up, theta)

| Clip | Ball | Label | Chosen Rule | Pred | Err (rule - label) | Px Dist |
|---|---|---:|---|---:|---:|---:|
| c_09a18d5f | pink | 17 | I6b(up=0.01,theta=20) | 19 | +2 | 74.3 |
| c_13f43606 | pink | 18 | I6b(up=0.01,theta=20) | 18 | 0 | 1.3 |
| c_3d27ed64 | pink | 19 | I6b(up=0.01,theta=20) | 20 | +1 | 31.3 |
| c_3f1fc736 | pink | 19 | I6b(up=0.01,theta=20) | 19 | 0 | 2.5 |
| c_41dd8473 | pink | 19 | I6b(up=0.01,theta=20) | 19 | 0 | 10.3 |
| c_542fca8b | pink | 21 | I6b(up=0.01,theta=20) | 20 | -1 | 3.7 |
| c_5cef27ce | pink | 29 | I6b(up=0.01,theta=20) | 29 | 0 | 3.5 |
| c_5e5ea872 | pink | 17 | I6b(up=0.01,theta=20) | 17 | 0 | 10.4 |
| c_69ba9415 | red | 23 | I6b(up=0.01,theta=20) | NA | NA | NA |
| c_6e281881 | red | 19 | I6b(up=0.01,theta=20) | 32 | +13 | 617.4 |
| c_77d7834d | pink | 23 | I6b(up=0.01,theta=20) | 24 | +1 | 47.1 |
| c_a473c3f0 | pink | 17 | I6b(up=0.01,theta=20) | 17 | 0 | 2.9 |
| c_e6b5e8a3 | pink | 17 | I6b(up=0.01,theta=20) | 17 | 0 | 8.4 |
| c_f51f593e | red | 18 | I6b(up=0.01,theta=20) | 19 | +1 | 23.5 |

### LOO Folds — I6 (I6a + I6b)

| Clip | Ball | Label | Chosen Rule | Pred | Err (rule - label) | Px Dist |
|---|---|---:|---|---:|---:|---:|
| c_09a18d5f | pink | 17 | I6b(up=0.01,theta=20) | 19 | +2 | 74.3 |
| c_13f43606 | pink | 18 | I6b(up=0.01,theta=20) | 18 | 0 | 1.3 |
| c_3d27ed64 | pink | 19 | I6b(up=0.01,theta=20) | 20 | +1 | 31.3 |
| c_3f1fc736 | pink | 19 | I6b(up=0.01,theta=20) | 19 | 0 | 2.5 |
| c_41dd8473 | pink | 19 | I6b(up=0.01,theta=20) | 19 | 0 | 10.3 |
| c_542fca8b | pink | 21 | I6b(up=0.01,theta=20) | 20 | -1 | 3.7 |
| c_5cef27ce | pink | 29 | I6b(up=0.01,theta=20) | 29 | 0 | 3.5 |
| c_5e5ea872 | pink | 17 | I6b(up=0.01,theta=20) | 17 | 0 | 10.4 |
| c_69ba9415 | red | 23 | I6b(up=0.01,theta=20) | NA | NA | NA |
| c_6e281881 | red | 19 | I6b(up=0.01,theta=20) | 32 | +13 | 617.4 |
| c_77d7834d | pink | 23 | I6b(up=0.01,theta=20) | 24 | +1 | 47.1 |
| c_a473c3f0 | pink | 17 | I6b(up=0.01,theta=20) | 17 | 0 | 2.9 |
| c_e6b5e8a3 | pink | 17 | I6b(up=0.01,theta=20) | 17 | 0 | 8.4 |
| c_f51f593e | red | 18 | I6b(up=0.01,theta=20) | 19 | +1 | 23.5 |

### LOO Folds — ALL (I1..I6)

| Clip | Ball | Label | Chosen Rule | Pred | Err (rule - label) | Px Dist |
|---|---|---:|---|---:|---:|---:|
| c_09a18d5f | pink | 17 | I5b(up=0.01,theta=20) | 19 | +2 | 74.3 |
| c_13f43606 | pink | 18 | I5b(up=0.01,theta=20) | 18 | 0 | 1.3 |
| c_3d27ed64 | pink | 19 | I5b(up=0.01,theta=20) | 20 | +1 | 31.3 |
| c_3f1fc736 | pink | 19 | I5b(up=0.01,theta=20) | 19 | 0 | 2.5 |
| c_41dd8473 | pink | 19 | I5b(up=0.01,theta=20) | 19 | 0 | 10.3 |
| c_542fca8b | pink | 21 | I5b(up=0.01,theta=20) | 20 | -1 | 3.7 |
| c_5cef27ce | pink | 29 | I5b(up=0.01,theta=20) | 29 | 0 | 3.5 |
| c_5e5ea872 | pink | 17 | I5b(up=0.01,theta=20) | 17 | 0 | 10.4 |
| c_69ba9415 | red | 23 | I5b(up=0.01,theta=20) | NA | NA | NA |
| c_6e281881 | red | 19 | I5b(up=0.01,theta=20) | NA | NA | NA |
| c_77d7834d | pink | 23 | I5b(up=0.01,theta=20) | 24 | +1 | 47.1 |
| c_a473c3f0 | pink | 17 | I5b(up=0.01,theta=20) | 17 | 0 | 2.9 |
| c_e6b5e8a3 | pink | 17 | I5b(up=0.01,theta=20) | 17 | 0 | 8.4 |
| c_f51f593e | red | 18 | I5b(up=0.01,theta=20) | 19 | +1 | 23.5 |

## Per-Clip Signed Errors (`rule - label`) — Best 3 Rules

| Clip | Ball | Label | I5b(up=0.01,theta=20) | I5b(up=0.01,theta=30) | I5b(up=0.02,theta=20) | I6b(up=0.01,theta=20) | I5b(up=0.01,theta=45) |
|---|---|---:|---:|---:|---:|---:|---:|
| c_09a18d5f | pink | 17 | +2 | +2 | +2 | +2 | NA |
| c_13f43606 | pink | 18 | 0 | 0 | 0 | 0 | 0 |
| c_3d27ed64 | pink | 19 | +1 | +1 | +1 | +1 | +1 |
| c_3f1fc736 | pink | 19 | 0 | 0 | 0 | 0 | 0 |
| c_41dd8473 | pink | 19 | 0 | 0 | 0 | 0 | 0 |
| c_542fca8b | pink | 21 | -1 | -1 | -1 | -1 | -1 |
| c_5cef27ce | pink | 29 | 0 | 0 | 0 | 0 | 0 |
| c_5e5ea872 | pink | 17 | 0 | 0 | 0 | 0 | 0 |
| c_69ba9415 | red | 23 | NA | NA | NA | NA | NA |
| c_6e281881 | red | 19 | NA | NA | NA | +13 | NA |
| c_77d7834d | pink | 23 | +1 | +1 | +1 | +1 | NA |
| c_a473c3f0 | pink | 17 | 0 | 0 | 0 | 0 | 0 |
| c_e6b5e8a3 | pink | 17 | 0 | 0 | 0 | 0 | 0 |
| c_f51f593e | red | 18 | +1 | +1 | +1 | +1 | +1 |

## Clips Still Wrong for Each of the Best 3 Rules

### I5b(up=0.01,theta=20)
- Missed (2): `c_69ba9415` (red: label=23, pred=None), `c_6e281881` (red: label=19, pred=None)
- Outside ±1 (1): `c_09a18d5f` (pink: label=17, pred=19, err=+2, px=74.3)
- Off by ±1 (4): `c_3d27ed64` (pink: label=19, pred=20, err=+1, px=31.3), `c_542fca8b` (pink: label=21, pred=20, err=-1, px=3.7), `c_77d7834d` (pink: label=23, pred=24, err=+1, px=47.1), `c_f51f593e` (red: label=18, pred=19, err=+1, px=23.5)

### I5b(up=0.01,theta=30)
- Missed (2): `c_69ba9415` (red: label=23, pred=None), `c_6e281881` (red: label=19, pred=None)
- Outside ±1 (1): `c_09a18d5f` (pink: label=17, pred=19, err=+2, px=74.3)
- Off by ±1 (4): `c_3d27ed64` (pink: label=19, pred=20, err=+1, px=31.3), `c_542fca8b` (pink: label=21, pred=20, err=-1, px=3.7), `c_77d7834d` (pink: label=23, pred=24, err=+1, px=47.1), `c_f51f593e` (red: label=18, pred=19, err=+1, px=23.5)

### I5b(up=0.02,theta=20)
- Missed (2): `c_69ba9415` (red: label=23, pred=None), `c_6e281881` (red: label=19, pred=None)
- Outside ±1 (1): `c_09a18d5f` (pink: label=17, pred=19, err=+2, px=74.3)
- Off by ±1 (4): `c_3d27ed64` (pink: label=19, pred=20, err=+1, px=31.3), `c_542fca8b` (pink: label=21, pred=20, err=-1, px=3.7), `c_77d7834d` (pink: label=23, pred=24, err=+1, px=47.1), `c_f51f593e` (red: label=18, pred=19, err=+1, px=23.5)

### I6b(up=0.01,theta=20)
- Missed (1): `c_69ba9415` (red: label=23, pred=None)
- Outside ±1 (2): `c_09a18d5f` (pink: label=17, pred=19, err=+2, px=74.3), `c_6e281881` (red: label=19, pred=32, err=+13, px=617.4)
- Off by ±1 (4): `c_3d27ed64` (pink: label=19, pred=20, err=+1, px=31.3), `c_542fca8b` (pink: label=21, pred=20, err=-1, px=3.7), `c_77d7834d` (pink: label=23, pred=24, err=+1, px=47.1), `c_f51f593e` (red: label=18, pred=19, err=+1, px=23.5)

### I5b(up=0.01,theta=45)
- Missed (4): `c_09a18d5f` (pink: label=17, pred=None), `c_69ba9415` (red: label=23, pred=None), `c_6e281881` (red: label=19, pred=None), `c_77d7834d` (pink: label=23, pred=None)
- Outside ±1: none
- Off by ±1 (3): `c_3d27ed64` (pink: label=19, pred=20, err=+1, px=31.3), `c_542fca8b` (pink: label=21, pred=20, err=-1, px=3.7), `c_f51f593e` (red: label=18, pred=19, err=+1, px=23.5)
