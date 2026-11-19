# Track Engine Offline Evaluation (`track_1` vs `lbw_ui_3`)

- Clips evaluated: `55` (`red`: `38`, `pink`: `17`)
- Score report: `C:\Users\vedan\Desktop\Internship\sendable\eval\reports\track_1.md`

## Comparison (`track_1` vs `lbw_ui_3`)

| Run / Slice | Rel Found / ±1f | Bnc Found / ±1f / Ctr(m) | Imp Found / ±1f | False Imp (none) |
| --- | --- | --- | --- | --- |
| `track_1` ALL | 55/55 (100.0%) / 63.6% | 38/55 (69.1%) / 92.1% / 0.150m | 28/49 (57.1%) / 75.0% | 1/6 (16.7%) |
| `lbw_ui_3` ALL | 55/55 (100.0%) / 83.6% | 48/55 (87.3%) / 85.4% / 0.136m | 30/49 (61.2%) / 60.0% | 4/6 (66.7%) |
| `track_1` red | 38/38 (100.0%) / 55.3% | 21/38 (55.3%) / 95.2% / 0.164m | 13/32 (40.6%) / 61.5% | 1/6 (16.7%) |
| `lbw_ui_3` red | 38/38 (100.0%) / 78.9% | 31/38 (81.6%) / 77.4% / 0.157m | 14/32 (43.8%) / 35.7% | 4/6 (66.7%) |
| `track_1` pink | 17/17 (100.0%) / 82.4% | 17/17 (100.0%) / 88.2% / 0.100m | 15/17 (88.2%) / 86.7% | 0/0 |
| `lbw_ui_3` pink | 17/17 (100.0%) / 94.1% | 17/17 (100.0%) / 100.0% / 0.102m | 16/17 (94.1%) / 81.2% | 0/0 |

## Gap Robustness Test

| Event | Setting / k | Found / n | Med |err| (f) | p90 |err| (f) |
| --- | --- | ---: | ---: | ---: |
| bounce | `lbw_ui_3` (k=0) | 48/55 | 0.00 | 20.00 |
| bounce | engine k=0 | 38/55 | 0.30 | 1.20 |
| bounce | engine k=2 | 35/55 | 0.75 | 2.56 |
| bounce | engine k=3 | 29/55 | 1.50 | 2.97 |
| bounce | engine k=5 | 21/55 | 2.80 | 3.70 |
| impact | `lbw_ui_3` (k=0) | 30/49 | 1.00 | 4.00 |
| impact | engine k=0 | 28/49 | 0.88 | 4.46 |
| impact | engine k=2 | 24/49 | 1.17 | 5.69 |
| impact | engine k=3 | 24/49 | 1.10 | 5.69 |
| impact | engine k=5 | 12/49 | 2.50 | 5.39 |
