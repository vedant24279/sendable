# Post-Impact Coverage — `release_dump_1`

- Interval: inclusive frames `[labelled_impact_frame .. last_visible_frame]`.
- Outliers: raw detections whose distance to the nearest detection in the adjacent detected frames is `> 0.2 * W` on both sides.

## Per-Clip Post-Impact Coverage

| Clip | Ball | Impact (`L`) | Last Visible | Frames | Raw Det Frames | Raw Coverage | Longest Gap | Outliers (`>0.2W`) | `results.json` Traj Frames | `results.json` Coverage | `results.json` Last Frame |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `c_09a18d5f` | `pink` | 17 | 62 | 46 | 45/46 | 97.8% | 1 | 0 | 5/46 | 10.9% | 22 |
| `c_13f43606` | `pink` | 18 | 43 | 26 | 25/26 | 96.2% | 1 | 0 | 8/26 | 30.8% | 25 |
| `c_3d27ed64` | `pink` | 19 | 60 | 42 | 42/42 | 100.0% | 0 | 0 | 9/42 | 21.4% | 27 |
| `c_3f1fc736` | `pink` | 19 | 55 | 37 | 37/37 | 100.0% | 0 | 0 | 8/37 | 21.6% | 26 |
| `c_41dd8473` | `pink` | 19 | 70 | 52 | 52/52 | 100.0% | 0 | 0 | 7/52 | 13.5% | 25 |
| `c_542fca8b` | `pink` | 21 | 46 | 26 | 23/26 | 88.5% | 1 | 0 | 3/26 | 11.5% | 25 |
| `c_5cef27ce` | `pink` | 29 | 69 | 41 | 36/41 | 87.8% | 3 | 0 | 2/41 | 4.9% | 33 |
| `c_5e5ea872` | `pink` | 17 | 34 | 18 | 4/18 | 22.2% | 14 | 0 | 2/18 | 11.1% | 18 |
| `c_69ba9415` | `red` | 23 | 67 | 45 | 0/45 | 0.0% | 45 | 0 | 0/45 | 0.0% | 16 |
| `c_6e281881` | `red` | 19 | 33 | 15 | 1/15 | 6.7% | 13 | 0 | 1/15 | 6.7% | 32 |
| `c_77d7834d` | `pink` | 23 | 38 | 16 | 16/16 | 100.0% | 0 | 0 | 8/16 | 50.0% | 30 |
| `c_a473c3f0` | `pink` | 17 | 35 | 19 | 18/19 | 94.7% | 1 | 0 | 8/19 | 42.1% | 25 |
| `c_e6b5e8a3` | `pink` | 17 | 52 | 36 | 36/36 | 100.0% | 0 | 0 | 7/36 | 19.4% | 23 |
| `c_f51f593e` | `red` | 18 | 64 | 47 | 45/47 | 95.7% | 1 | 0 | 6/47 | 12.8% | 24 |
| **Mean / Total** | — | — | — | **466** | **380/466** | **77.8%** (med 95.9%) | max 45 | **0** | **74/466** | **18.3%** (med 13.1%) | — |
