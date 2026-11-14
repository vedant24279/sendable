# Render v2 Inventory (`g1/render-v2`)

This document inventories the current video/overlay rendering pipeline across:
- [backend/pipeline/process.py](../backend/pipeline/process.py) (Pass 2, Pass 3, Pass 4, and `segments` bookkeeping)
- [backend/pipeline/bake_overlay.py](../backend/pipeline/bake_overlay.py) (`output_full.mp4` download compositor)
- [frontend/src/features/tracking/ResultsView.tsx](../frontend/src/features/tracking/ResultsView.tsx)
- [frontend/src/features/tracking/VideoPlayer.tsx](../frontend/src/features/tracking/VideoPlayer.tsx)
- [frontend/src/features/tracking/PitchOverlay.tsx](../frontend/src/features/tracking/PitchOverlay.tsx)
- `eval/runs/v2_1/c_3d27ed64/results.json` (`segments`, `events`, `trajectory`, and `trajectory_post`)

---

## 1. Segments in `output.mp4`

`output.mp4` contains **three** sequential segments (**Segment A**, **Segment B**, **Segment C**) written into a single OpenCV `VideoWriter` stream at the source clip's `fps` (`30.0` fps in `c_3d27ed64`), followed by an `ffmpeg` H.264 (`libx264`, `yuv420p`, `+faststart`) re-encode. No other video segments exist in `output.mp4` (though `PitchOverlay.tsx` and `bake_overlay.py` define `"before"` for `t < seg_a_start_sec` and `"after"` for `t >= seg_c_end_sec` as phase-router sentinels).

### Summary per Segment

| Segment | Pipeline Pass | What It Shows in `output.mp4` | Source Frame Range Logic | Playback Speed | Event Gating | `results.json` `segments.*` Keys (`c_3d27ed64` values) |
| --- | --- | --- | --- | --- | --- | --- |
| **Segment A** | **PASS 2** (`process.py` L910–L964) | Live-speed walkthrough with progressive ball markers (`release`, `bounce`, `deviation`) baked into the frames as each event occurs, plus fallback post-bounce polyline only when `deviation` is absent. *(Note: Pass 2 re-runs streaming detectors from frame 0 without `find_release_flight`, `[RELEASE OVERRIDE]`, or `finalize_deviation`, so baked Seg A markers reflect raw streaming state.)* | Loops `fnum` in `0 .. seg_a_end`, where:<br>`seg_a_end = min(dev_f + 30, total - 1)` if `have_dev`<br>else `min(bounce_f + 30, total - 1)` if `have_bounce`<br>else `total - 1`.<br>Skips writing frames before `seg_a_start_frame = max(0, release_f - 30)` if `have_release` else `0`.<br>Writes `seg_a_frames_written = seg_a_end - seg_a_start_frame + 1` frames (`0..52` = 53 frames on `c_3d27ed64`). | **1.0×** (`1` output frame per source frame at `fps`) | Always runs (ungated once `ball_count > 0`). Start frame gated on `have_release`; end frame gated on `have_dev` then `have_bounce`. Sub-timestamps gated on `have_release`, `have_release and have_bounce`, and `have_release and have_dev`. | `seg_a_start_sec` (`0.0`)<br>`seg_a_end_sec` (`1.7667`)<br>`seg_a_release_sec` (`0.1667`)<br>`seg_a_bounce_sec` (`0.5`)<br>`seg_a_deviation_sec` (`0.7333`) |
| **Segment B** | **PASS 3** (`process.py` L965–L1014) | Slow-motion replay of the delivery window (`release - 5` to `dev + 5`). `process.py` calls `_draw_progressive_overlays` with `big_fnum = seg_b_end + 10_000`, baking `release`, `bounce`, and `deviation` markers statically onto every frame of Seg B. Frontend SVG (`PitchOverlay.tsx`) and `bake_overlay.py` add stumps, pitching channel, growing `release -> bounce` parabola + `bounce -> deviation` line, and (in SVG) `PredictedPath` at `t >= seg_b_deviation_sec`. | `seg_b_start = max(0, release_f - 5)`<br>`seg_b_end = min(dev_f + 5, total - 1)` if `have_dev` else `seg_a_end`.<br>Writes `2` output frames per source frame (`seg_b_frames_written = 2 * (seg_b_end - seg_b_start + 1)`; on `c_3d27ed64`, source frames `0..27` -> 56 output frames). | **0.5×** (`for sub in (0, 1):` writes each source frame twice at `fps`) | Gated on `if have_release and have_bounce:`. If false, Seg B is skipped (`seg_b_frames_written = 0`, `seg_b_start_sec == seg_b_end_sec`, event keys `null`). `seg_b_deviation_sec` is additionally gated on `have_dev`. | `seg_b_start_sec` (`1.7667`)<br>`seg_b_end_sec` (`3.6333`)<br>`seg_b_release_sec` (`2.1`)<br>`seg_b_bounce_sec` (`2.7667`)<br>`seg_b_deviation_sec` (`3.2333`) |
| **Segment C** | **PASS 4** (`process.py` L449–L484, L1017–L1035) | Freeze-frame grabbed at `deviation_frame` (`dev_f`) with homography-projected pitch length zone bands (`YORKER`, `FULL`, `GOOD`, `SHORT`) drawn by `draw_zones(base, H_world, alpha=0.30, label=True)`. Frontend SVG (`PitchOverlay.tsx`) and `bake_overlay.py` animate the `release -> bounce -> deviation` trajectory at `0.5×` with a leading ball icon, followed by a `1.0 s` hold showing the bounce marker and (in SVG) `PredictedPath`. | Reads single source frame `max(0, deviation_frame)`.<br>`rel_to_dev_frames = max(1, deviation_frame - release_f)`<br>`anim_sec = 2.0 * rel_to_dev_frames / fps`<br>`hold_sec = 1.0`<br>Writes `n_total = max(8, int(round(fps * (anim_sec + hold_sec))))` copies of `base` (`64` output frames = `2.1333 s` on `c_3d27ed64`). | **0.0× video** (frozen frame) + **0.5× overlay sweep** (`2.0 * span / fps`) + **1.0 s hold** | Gated on `if have_release and have_bounce and have_dev:`. If false, Seg C is skipped and all `seg_c_*` keys are `null`. | `seg_c_start_sec` (`3.6333`)<br>`seg_c_rb_end_sec` (`4.3`)<br>`seg_c_bd_end_sec` (`4.7667`)<br>`seg_c_end_sec` (`5.7667`) |

---

## 2. Markers and Overlays by Renderer and Segment

| Marker / Overlay | Segment | `process.py` (`output.mp4`) | `bake_overlay.py` (`output_full.mp4` download) | Frontend SVG (`PitchOverlay.tsx` / `ResultsView.tsx`) |
| --- | --- | --- | --- | --- |
| **Release marker** | **Seg A** | Baked progressively when `fnum >= release.release_frame` via `overlay_ball_image` (`_draw_progressive_overlays` L240–L243, using re-run streaming detector). | Baked progressively when `t >= seg_a_release_sec` via `_draw_ball_marker` (L308–L310) for all `ball_type`s. | `<BallMarker>` when `currentTime >= seg_a_release_sec` (`BallMarkers` L460, L465), **only for `ballType === "white"`** (skipped for `"red"`/`"pink"` at L451) when `showBallMarkers` is On. |
| | **Seg B** | Baked statically on **all** frames (`big_fnum >= release.release_frame`) via `overlay_ball_image` (L240–L243, L985). | Baked statically on **all** frames of Seg B via `_draw_ball_marker` (L365). | Static `<BallMarker>` on **all** frames of Seg B (L475), **only for `ballType === "white"`** when `showBallMarkers` is On. |
| | **Seg C** | Not drawn (`_run_segment_c` L449–L484). | Not drawn as static marker (only traveling ball during sweep, L350–L358). | Not drawn as static marker (only traveling `<BallMarker>` inside `Parabolas` L263–L273, L290–L293). |
| **Bounce marker** | **Seg A** | Baked progressively when `fnum >= bf` via `overlay_ball_image` (L244–L247, streaming detector). | Baked progressively when `t >= seg_a_bounce_sec` via `_draw_ball_marker` (L311–L313). | Progressive `<BallMarker>` when `currentTime >= seg_a_bounce_sec` (L461, L466), **only for `"white"`**. |
| | **Seg B** | Baked statically on **all** frames (`big_fnum >= bf`) via `overlay_ball_image` (L244–L247). | Baked statically on **all** frames of Seg B via `_draw_ball_marker` (L366). | Static `<BallMarker>` on **all** frames of Seg B (L476), **only for `"white"`**. |
| | **Seg C** | Not drawn. | Baked during the 1 s hold (`t >= seg_c_bd_end_sec`) via `_draw_ball_marker` (L369–L371). | `<BallMarker>` during the 1 s hold (`currentTime >= seg_c_bd_end_sec`, L484–L485), **only for `"white"`**. |
| **Deviation marker** | **Seg A** | Baked progressively when `fnum >= dev_f` via `trajectory.draw_direction_change_markers` (L249, streaming detector). | Baked progressively when `t >= seg_a_deviation_sec` via `_draw_ball_marker` (L314–L316). | Progressive `<BallMarker>` when `currentTime >= seg_a_deviation_sec` (L462, L467), **only for `"white"`**. |
| | **Seg B** | Baked statically on **all** frames (`big_fnum`) via `trajectory.draw_direction_change_markers` (L249, L983). | Baked statically on **all** frames of Seg B via `_draw_ball_marker` (L367). | Static `<BallMarker>` on **all** frames of Seg B (L477), **only for `"white"`**. |
| | **Seg C** | Not drawn. | Not drawn. | Not drawn. |
| **Impact marker (`events.impact`, new)** | **Seg A / B / C** | **Not drawn** (`_vertex_impact` is only serialized to `results.json["events"]["impact"]` at L1169–L1177). | **Not drawn** (`ev.get("impact")` is never read). | **Not drawn** (`result.events.impact` is not read in `PitchOverlay.tsx` or `ResultsView.tsx`). |
| **Trajectory line** (`release -> bounce`, `bounce -> contact`, `trajectory_post`) | **Seg A** | Only when `bounce` exists and `deviation` is absent (`not have_dev_now`), bakes `trajectory.draw_post_bounce_path` (L223–L234). `draw_parabolas` is a no-op. `trajectory_post` not drawn. | Not drawn (`_progress` returns `(0.0, 0.0)`). | Not drawn (`Parabolas` returns `null` in `"segA"`, L230). |
| | **Seg B** | Fallback `draw_post_bounce_path` up to `big_fnum` only when `not have_dev_now`. `rel_to_bounce_progress` & `bounce_to_dev_progress` are computed (L998–L1002) but deleted unused in `_draw_progressive_overlays` (L212–L213). `trajectory_post` not drawn. | Growing quadratic parabola `release -> bounce` (`_draw_parabola_segment`, width 16, alpha 0.40) over `[seg_b_release_sec, seg_b_bounce_sec]`, then straight line `bounce -> deviation` (width 13, alpha 0.70) over `[seg_b_bounce_sec, seg_b_deviation_sec]` (L326–L348). `trajectory_post` not drawn. | Growing SVG `<polyline>` for `release -> bounce` (width 16, opacity 0.40) and `bounce -> deviation` (width 13, opacity 0.70) driven by `parabolaProgress` (`Parabolas` L223–L289) when `showParabola` is On. `trajectory_post` not drawn. |
| | **Seg C** | Not drawn (`_run_segment_c` deletes parabola inputs at L477–L478). | Sweeps `release -> bounce` (`[seg_c_start_sec, seg_c_rb_end_sec]`) and `bounce -> deviation` (`[seg_c_rb_end_sec, seg_c_bd_end_sec]`) with leading `_draw_ball_marker`, then holds full line for `1.0 s` (L326–L358). `trajectory_post` not drawn. | Sweeps `release -> bounce` and `bounce -> deviation` with leading `<BallMarker>` (`Parabolas` L263–L293), then holds for `1.0 s`. `trajectory_post` not drawn. |
| **Predicted path** (dashed LBW line + hit/miss circle) | **Seg A** | Not drawn. | Not drawn (`PredictedPath` is missing from `bake_overlay.py`). | Not drawn (`PredictedPath` returns `null` in `"segA"`, L331). |
| | **Seg B** | Not drawn. | **Not drawn** (never ported to `bake_overlay.py`). | Drawn by `PredictedPath` (L324–L434) when `showPrediction` is On and `bd >= 1` (`currentTime >= seg_b_deviation_sec`). |
| | **Seg C** | Not drawn. | **Not drawn** (never ported to `bake_overlay.py`). | Drawn by `PredictedPath` (L324–L434) when `showPrediction` is On and `bd >= 1` (`currentTime >= seg_c_bd_end_sec`, during 1 s hold). |
| **Stumps & pitching line** | **Seg A** | Not drawn (`_draw_stumps_overlay` at L378–L394 is dead code). | Not drawn (`_compose_frame` returns early at L317). | **Drawn** across all of Seg A (`StumpSet` and `PitchingLine` at `PitchOverlay.tsx` L536, L540–L541 are not phase-gated). |
| | **Seg B & C** | Not drawn (`_draw_stumps_overlay` is never called). | Drawn via `_draw_stump_set` (bat & bowl) and `_draw_pitching_line` (L323, L360–L361). | Drawn via `<StumpSet>` (bat & bowl) and `<PitchingLine>` when `showStumps` / `showPitchingLine` are On (L536, L540–L541). |
| **Zone bands / Pitch map** (`YORKER`, `FULL`, `GOOD`, `SHORT`) | **Seg A & B** | Not drawn. | Not drawn. | Not drawn in video overlay (`ResultsView.tsx` L263–L270 shows a text badge in the Bounce card). |
| | **Seg C** | **Baked into frozen frame** via `draw_zones(base, H_world, alpha=0.30, label=True)` in `_run_segment_c` (L468–L470). *(No separate 2D mini-map inset exists; the homography-warped zone bands on the pitch are the pitch map.)* | Inherited from `output.mp4` frames during Seg C. | Inherited from `output.mp4` video stream during Seg C. |

---

## 3. Where Segment Speeds Are Set & Exact Code Locations to Remove Segment A and Slow Segment B to `0.35×`

### Where Speeds Are Set Today

1. **Segment A (`1.0×`)**:
   - [backend/pipeline/process.py](../backend/pipeline/process.py#L936-L963): `for fnum in range(0, seg_a_end + 1):` calls `out_writer.write(frame)` once per source frame (`1` output frame per `1` source frame at `fps`).
   - [backend/pipeline/process.py](../backend/pipeline/process.py#L1041-L1058): `seg_a_end_sec` and `seg_a_*_sec` divide frame counts directly by `fps`.
2. **Segment B (`0.5×`)**:
   - [backend/pipeline/process.py](../backend/pipeline/process.py#L990-L1013): Inside `for fnum in range(seg_b_start, seg_b_end + 1):`, the inner loop `for sub in (0, 1):` writes each frame **twice** (`2` output frames per source frame = `0.5×` speed).
   - [backend/pipeline/process.py](../backend/pipeline/process.py#L1062-L1068): Event timestamps multiply source-frame offsets by `2 / fps`:
     - `seg_b_release_sec = round(seg_a_end_sec + 5 * 2 / fps, 4)`
     - `seg_b_bounce_sec = round(seg_a_end_sec + (bounce_f - release_f + 5) * 2 / fps, 4)`
     - `seg_b_deviation_sec = round(seg_a_end_sec + (dev_f - release_f + 5) * 2 / fps, 4)`
     *(Note: hardcoding `5` assumes `release_f >= 5`; when `release_f < 5`, `release_f - seg_b_start` is `release_f < 5`, so `5 * 2 / fps` is off by `(5 - release_f) * 2 / fps`.)*
3. **Segment C (`0.5×` sweep + `1.0 s` hold)**:
   - [backend/pipeline/process.py](../backend/pipeline/process.py#L479-L483): `anim_sec = 2.0 * rel_to_dev_frames / fps` and `hold_sec = 1.0` determine `n_total = max(8, int(round(fps * (anim_sec + hold_sec))))`.
   - [backend/pipeline/process.py](../backend/pipeline/process.py#L1073-L1079): `rb_anim = 2.0 * (bounce_f - release_f) / fps`, `bd_anim = 2.0 * (dev_f - bounce_f) / fps`, and `+ 1.0` for `seg_c_end_sec`.
4. **Browser Video Player User Speed Control**:
   - [frontend/src/features/tracking/VideoPlayer.tsx](../frontend/src/features/tracking/VideoPlayer.tsx#L33-L51) and [L135-L140](../frontend/src/features/tracking/VideoPlayer.tsx#L135-L140): `SPEEDS = [0.25, 0.5, 1, 1.5, 2]` sets `videoRef.current.playbackRate`.

### Exact Code Locations to Remove Segment A and Slow Segment B to `0.35×`

1. **[backend/pipeline/process.py](../backend/pipeline/process.py#L916-L964) (Pass 2 / Segment A removal)**:
   - Replace the Pass 2 video-read/render loop with a lightweight CSV-logging loop over `detections_by_frame` (no `out_writer.write(frame)` in Pass 2), setting `seg_a_frames_written = 0` (`seg_a_end_sec = 0.0`, `seg_a_release_sec = seg_a_bounce_sec = seg_a_deviation_sec = None`).
2. **[backend/pipeline/process.py](../backend/pipeline/process.py#L965-L1014) (Pass 3 / Segment B at `0.35×`)**:
   - Define `_SEG_B_SPEED = 0.35` (`1 / 0.35 = 20 / 7 ≈ 2.8571` output frames per source frame).
   - For source frame index `k = fnum - seg_b_start` (`0 <= k <= seg_b_end - seg_b_start`), compute the exact output frame range `out_start = round(k / _SEG_B_SPEED)` to `out_end = round((k + 1) / _SEG_B_SPEED)` and write `out_end - out_start` frames (`2` or `3` frames per step, averaging `20 / 7` frames per source frame).
   - Extend `seg_b_end` through the end of `trajectory_post_points` (or `min((impact_f or dev_f) + 5, total - 1)` when `trajectory_post_points` is empty) so the post-impact path is included in Segment B.
   - If `not (have_release and have_bounce)`, fall back to writing the clip frames so `output.mp4` is never empty when Segment A is gone.
3. **[backend/pipeline/process.py](../backend/pipeline/process.py#L1041-L1098) (`segments` timestamp calculation)**:
   - Set `seg_b_start_sec = 0.0` (since `seg_a_end_sec = 0.0`).
   - Use actual `lead_b = release_f - seg_b_start` (fixing the `release_f < 5` offset bug) and map any source frame `f` in Segment B to output seconds via `seg_b_start_sec + round((f - seg_b_start) / _SEG_B_SPEED) / fps`:
     - `seg_b_release_sec = round(round((release_f - seg_b_start) / _SEG_B_SPEED) / fps, 4)`
     - `seg_b_bounce_sec = round(round((bounce_f - seg_b_start) / _SEG_B_SPEED) / fps, 4)`
     - `seg_b_impact_sec = round(round((impact_f - seg_b_start) / _SEG_B_SPEED) / fps, 4)` (and `seg_b_deviation_sec` for backward compatibility).
4. **[frontend/src/features/tracking/ResultsView.tsx](../frontend/src/features/tracking/ResultsView.tsx#L88-L92)**:
   - Read seek-bar marker times from `segs?.seg_b_release_sec`, `segs?.seg_b_bounce_sec`, and `segs?.seg_b_impact_sec ?? segs?.seg_b_deviation_sec` instead of `segs?.seg_a_*_sec`.
5. **[frontend/src/features/tracking/PitchOverlay.tsx](../frontend/src/features/tracking/PitchOverlay.tsx#L152-L178) & [backend/pipeline/bake_overlay.py](../backend/pipeline/bake_overlay.py#L251-L274)**:
   - Remove the `"segA"` phase branch (or keep `seg_a_start_sec: 0.0, seg_a_end_sec: 0.0` as no-op compatibility keys so `t >= 0` immediately routes to `"segB"`). Because `parabolaProgress` / `_progress` linearly interpolate between `seg_b_release_sec`, `seg_b_bounce_sec`, and `seg_b_deviation_sec`, updating those timestamps in `results.json` automatically slows the overlay growth in Segment B to `0.35×`.

---

## 4. How the Frontend Uses `segments` & What Breaks If Segment A Is Removed from `results.json`

### Current Frontend Usage of `segments`

1. **[ResultsView.tsx](../frontend/src/features/tracking/ResultsView.tsx#L88-L116)**:
   - Reads `segs = result.segments` and populates seek-bar `markers` for `<VideoPlayer>` using **only** `seg_a_*`:
     - `releaseT = segs?.seg_a_release_sec ?? result.events.release?.timestamp_sec`
     - `bounceT = segs?.seg_a_bounce_sec ?? result.events.bounce?.timestamp_sec`
     - `deviationT = segs?.seg_a_deviation_sec ?? result.events.deviation?.timestamp_sec`
2. **[VideoPlayer.tsx](../frontend/src/features/tracking/VideoPlayer.tsx#L102-L116) & [L268-L285](../frontend/src/features/tracking/VideoPlayer.tsx#L268-L285)**:
   - Does not inspect `result.segments` directly. It renders `markers` at `(m.time / duration) * 100%` on the timeline and emits `currentTime` at 60 Hz via `requestAnimationFrame` to `ResultsView` -> `PitchOverlay`.
3. **[PitchOverlay.tsx](../frontend/src/features/tracking/PitchOverlay.tsx#L152-L189)**:
   - `currentPhase(t, segs)` (L154–L160) checks:
     1. `if (t < segs.seg_a_start_sec) return "before";`
     2. `if (t < segs.seg_a_end_sec) return "segA";`
     3. `if (t < segs.seg_b_end_sec) return "segB";`
     4. `if (segs.seg_c_end_sec != null && t < segs.seg_c_end_sec) return "segC";`
     5. `return "after";`
   - `parabolaProgress(t, segs)` (L164–L189) returns `{ rb: 0, bd: 0 }` in `"before"`/`"segA"`, uses `seg_b_release_sec` / `seg_b_bounce_sec` / `seg_b_deviation_sec` in `"segB"`, and uses `seg_c_start_sec` / `seg_c_rb_end_sec` / `seg_c_bd_end_sec` in `"segC"`.
   - `Parabolas` (L229–L232) and `PredictedPath` (L330–L334) return `null` when `phase === "before" || phase === "segA"`.
   - `BallMarkers` (L459–L488) uses `seg_a_*_sec` in `"segA"`, draws all markers statically in `"segB"`, and uses `seg_c_bd_end_sec` in `"segC"`.

### What Breaks If `seg_a_*` Keys Are Removed from `results.json`

1. **`bake_overlay.py` crashes with `KeyError`**: `_phase(t, segs)` at [bake_overlay.py L252–L253](../backend/pipeline/bake_overlay.py#L252-L253) indexes `segs["seg_a_start_sec"]` and `segs["seg_a_end_sec"]` directly, throwing `KeyError: 'seg_a_start_sec'` when downloading `output_full.mp4`.
2. **`ResultsView.tsx` seek-bar markers point to wrong timestamps**: At [ResultsView.tsx L89–L91](../frontend/src/features/tracking/ResultsView.tsx#L89-L91), `segs?.seg_a_release_sec ?? result.events.release?.timestamp_sec` falls back to `events.*.timestamp_sec` (`1.0×` source-video timestamps `frame / fps`), which do not match the `0.35×` Segment B timestamps in `output.mp4`.
3. **Frontend TypeScript compilation (`types.ts` / `PitchOverlay.tsx`)**: Removing `seg_a_*` from the JSON contract without updating `TrackingResult["segments"]` and `currentPhase` breaks `tsc` type-checking on `segs.seg_a_start_sec` / `segs.seg_a_end_sec`. *(Keeping `seg_a_start_sec: 0.0, seg_a_end_sec: 0.0` as zero-length compatibility fields or updating `types.ts`, `PitchOverlay.tsx`, `ResultsView.tsx`, and `bake_overlay.py` together avoids all three issues.)*

---

## 5. Where `trajectory_post` and `events.impact` Can Be Drawn in Each Renderer

1. **Video Generator ([backend/pipeline/process.py](../backend/pipeline/process.py))**:
   - **Recommended clean separation**: Stop baking ball markers and polylines into `output.mp4` during Pass 3 so `output.mp4` contains only the `0.35×` video frames (Pass 3 / Seg B) and the frozen `draw_zones` pitch map frame (Pass 4 / Seg C).
   - **Event & segment plumbing in `process.py`**:
     - Define effective contact event `_contact_f = _vertex_impact["frame"] if _vertex_impact is not None else dev_f` and `_contact_pt = (_vertex_impact["x"], _vertex_impact["y"]) if _vertex_impact is not None else ((dev_changes[0][1], dev_changes[0][2]) if have_dev else None)`.
     - In Pass 3 (L968–L1014): extend `seg_b_end` to `trajectory_post_points[-1]["frame"]` when `trajectory_post_points` is non-empty (else `min(_contact_f + 5, total - 1)` when contact exists, else `min(bounce_f + 30, total - 1)`).
     - In Pass 4 (`_run_segment_c`, L449–L484, L1018–L1035): freeze at `_contact_f` (`impact.frame` when available, else `dev_f`), and include the post-impact sweep duration `post_anim = 2.0 * (post_end_f - _contact_f) / fps` in `anim_sec` when `trajectory_post_points` is non-empty.
     - In `segments_obj` (L1060–L1098): emit `seg_b_impact_sec`, `seg_b_post_end_sec`, `seg_c_bi_end_sec`, and `seg_c_post_end_sec` (while keeping `seg_b_deviation_sec` and `seg_c_bd_end_sec` populated with the contact timestamp so existing consumers work seamlessly).
2. **Download Compositor ([backend/pipeline/bake_overlay.py](../backend/pipeline/bake_overlay.py))**:
   - **`_progress(t, segs, phase)` (L260–L285)**: Return `(rb, bi, post)` where:
     - `rb` progresses `0 -> 1` over `[seg_b_release_sec, seg_b_bounce_sec]` in Seg B (and `[seg_c_start_sec, seg_c_rb_end_sec]` in Seg C).
     - `bi` (`bounce -> impact/deviation`) progresses `0 -> 1` over `[seg_b_bounce_sec, seg_b_impact_sec]` in Seg B (and `[seg_c_rb_end_sec, seg_c_bd_end_sec]` in Seg C).
     - `post` (`impact -> last trajectory_post point`) progresses `0 -> 1` over `[seg_b_impact_sec, seg_b_post_end_sec]` in Seg B (and `[seg_c_bd_end_sec, seg_c_post_end_sec]` in Seg C).
   - **`_compose_frame(frame, t, segs, results, ball_type)` (L290–L372)**:
     - Select `contact = ev.get("impact") or ev.get("deviation")` and `traj_post = results.get("trajectory_post") or []`.
     - Draw `bounce -> contact` with `_draw_parabola_segment` using `bi`.
     - When `traj_post` is non-empty and `post > 0`, build the post-impact polyline from `[(contact["x"], contact["y"])] + [(p["x"], p["y"]) for p in traj_post]` up to fractional progress `post` and render it via `_draw_parabola_segment(frame, post_pts, trail_bgr, 11, 0.75)`.
     - Draw `_draw_ball_marker` in Seg B **progressively** as each event timestamp is reached (`t >= seg_b_release_sec` for `release`, `t >= seg_b_bounce_sec` for `bounce`, `t >= seg_b_impact_sec` for `contact`).
     - Port `PredictedPath` (`_draw_predicted_path`) to `_compose_frame` when `bi >= 1` so downloads match the screen.
3. **Frontend SVG ([frontend/src/features/tracking/PitchOverlay.tsx](../frontend/src/features/tracking/PitchOverlay.tsx) & [ResultsView.tsx](../frontend/src/features/tracking/ResultsView.tsx))**:
   - **`parabolaProgress(t, segs)` (L164–L189)**: Return `{ rb, bd, post }` using `seg_b_impact_sec ?? seg_b_deviation_sec` and `seg_b_post_end_sec` / `seg_c_post_end_sec`.
   - **`Parabolas` (L223–L296)**:
     - Use `const contact = result.events.impact ?? result.events.deviation;` for `bdPath`.
     - When `result.trajectory_post?.length` and `post > 0`, slice/interpolate `[{ x: contact.x, y: contact.y }, ...result.trajectory_post]` by `post` and render a `<polyline>` ( plus advance `ballPos` along `trajectory_post` in Seg C when `0 < post < 1`).
   - **`PredictedPath` (L324–L434)**: Use `const contact = result.events.impact ?? result.events.deviation;` instead of `deviation` so the LBW projection extrapolates `bounce -> impact` to the batter stump plane once `bd >= 1`.
   - **`BallMarkers` (L443–L491)**:
     - Remove `if (ballType === "red" || ballType === "pink") return null;`.
     - In `"segB"`, reveal `release` at `currentTime >= segs.seg_b_release_sec`, `bounce` at `currentTime >= segs.seg_b_bounce_sec`, and `contact` (`impact ?? deviation`) at `currentTime >= (segs.seg_b_impact_sec ?? segs.seg_b_deviation_sec)`.
   - **`ResultsView.tsx` (L88–L116, L237–L301)**: Use `seg_b_*` timestamps for timeline markers and show `Impact` in `EventCards`.

---

## 6. Duplicated Drawing Paths and What Can Be Deleted

| Duplicated Element | Locations in Codebase | Issue / Conflict | What Can Be Deleted |
| --- | --- | --- | --- |
| **1. Event ball markers (`release`, `bounce`, `deviation`)** | 1. `process.py`: `_draw_progressive_overlays` (L239–L249) + unused `_draw_bounce_marker_at` (L397–L414)<br>2. `PitchOverlay.tsx`: `BallMarkers` (L443–L491)<br>3. `bake_overlay.py`: `_compose_frame` (L308–L316, L365–L371) | `process.py` bakes `17 px` ball markers + legacy `draw_direction_change_markers` into `output.mp4` for **all** ball types (and in Seg B bakes all 3 markers from the very first frame via `big_fnum`). `PitchOverlay.tsx` suppresses SVG markers for `red`/`pink` (L451) but double-draws on `white`. `bake_overlay.py` draws `21 px` markers on top of `output.mp4` for **all** ball types, double-baking markers in downloads. | Delete marker baking in `process.py` (`_draw_progressive_overlays` L185–L250 and `_draw_bounce_marker_at` L397–L414) and delete the `if (ballType === "red" \|\| ballType === "pink") return null;` guard in `PitchOverlay.tsx` L451. |
| **2. Stumps & wicket-to-wicket channel (`StumpSet` / `PitchingLine`)** | 1. `process.py`: `_draw_stumps_at` (L276–L338), `_draw_stump_line` (L341–L375), `_draw_stumps_overlay` (L378–L394)<br>2. `PitchOverlay.tsx`: `StumpSet` (L63–L103), `PitchingLine` (L105–L128)<br>3. `bake_overlay.py`: `_draw_stump_set` (L149–L178), `_draw_pitching_line` (L180–L205) | `_draw_stumps_overlay` in `process.py` is **100% dead code** (never called anywhere) and uses `_STUMP_HEIGHT_M = 0.71` vs `0.65` in `PitchOverlay.tsx` and `bake_overlay.py`. | Delete `_draw_stumps_at`, `_draw_stump_line`, and `_draw_stumps_overlay` (L276–L394) in `process.py` (retaining only the constants `_STUMP_HEIGHT_M` and `_RETURN_CREASE_M` used by Pass 1 stump/bat-zone height math). |
| **3. Constrained quadratic parabola fit (`release -> bounce`)** | 1. `process.py`: `_fit_constrained_quadratic_k` (L417–L436), `_point_on_constrained_quadratic` (L439–L443), unused import `draw_release_to_bounce_parabola` (L48), and unused progress math in Pass 3/4 (L971–L974, L986–L987, L997–L1010, L1028–L1032)<br>2. `PitchOverlay.tsx`: `fitConstrainedQuadratic` & `pointOnQuad` (L194–L221)<br>3. `bake_overlay.py`: `_fit_kxky` & `_point_on_quad` (L214–L234) | `process.py` computes `rb_prog`, `bd_prog`, and `rel_to_bounce_pts` in Pass 3 & Pass 4, passes them to `_draw_progressive_overlays` / `_run_segment_c`, and immediately `del`s them unused (L212–L213, L477–L478). | Delete `_fit_constrained_quadratic_k`, `_point_on_constrained_quadratic`, the unused `visualizer` import (L48), and the unused parabola arguments in `process.py`. |
| **4. Post-bounce fallback polyline** | 1. `process.py`: `trajectory.draw_post_bounce_path` call in `_draw_progressive_overlays` (L224–L234)<br>2. `PitchOverlay.tsx` / `bake_overlay.py`: `Parabolas` / `_compose_frame` | `process.py` bakes a raw polyline into `output.mp4` only when `not have_dev_now` (and in Seg B draws the entire post-bounce path statically from frame 0 because `up_to_frame=big_fnum`). | Delete `_draw_progressive_overlays` in `process.py` and let `PitchOverlay.tsx` and `bake_overlay.py` draw the growing post-bounce / post-impact polyline from `results.json`. |

---

## 7. Proposed Minimal Ordered Change List

| Order | Change Description | Files Touched | Estimated Size |
| ---: | --- | --- | --- |
| **1** | **Remove Segment A, slow Segment B to `0.35×`, and clean up dead/duplicate baking in `process.py`**:<br>- Replace Pass 2 video write with CSV-only logging (`seg_a_frames_written = 0`, `seg_a_start_sec = 0.0`, `seg_a_end_sec = 0.0`).<br>- In Pass 3 (Seg B), write clean video frames (no baked markers) at `0.35×` (`round((k+1)/0.35) - round(k/0.35)` repeats per source frame) from `max(0, release_f - 5)` through the end of `trajectory_post` (or `contact_f + 5`).<br>- In Pass 4 (Seg C), freeze at `impact_f` (fallback `dev_f`), bake `draw_zones` pitch map, and include `post_anim` in the `0.5×` sweep duration.<br>- Emit `seg_b_impact_sec`, `seg_b_post_end_sec`, `seg_c_bi_end_sec`, and `seg_c_post_end_sec` in `results.json["segments"]`.<br>- Delete dead helpers (`_draw_progressive_overlays`, `_draw_stumps_at`, `_draw_stump_line`, `_draw_stumps_overlay`, `_draw_bounce_marker_at`, `_fit_constrained_quadratic_k`, `_point_on_constrained_quadratic`). | `backend/pipeline/process.py` | `+70 / -260` lines |
| **2** | **Update frontend types, progressive Seg B markers, impact + `trajectory_post` line, and C freeze-frame sweep**:<br>- Add optional `impact` / `trajectory_post` and new `segments` fields to `TrackingResult` in `types.ts`.<br>- In `PitchOverlay.tsx`: remove the `ballType === "red" \|\| "pink"` early return in `BallMarkers`; reveal `release`, `bounce`, and `impact` (`impact ?? deviation`) progressively at their `seg_b_*_sec` timestamps in Seg B; extend `parabolaProgress` and `Parabolas` to grow `release -> bounce -> impact` and `trajectory_post` with the ball in Seg B (at `0.35×`) and sweep + hold in Seg C; anchor `PredictedPath` at `impact ?? deviation`.<br>- In `ResultsView.tsx`: point timeline seek markers at `seg_b_release_sec`, `seg_b_bounce_sec`, and `seg_b_impact_sec ?? seg_b_deviation_sec`, and show `Impact` in `EventCards`. | `frontend/src/features/tracking/types.ts`<br>`frontend/src/features/tracking/PitchOverlay.tsx`<br>`frontend/src/features/tracking/ResultsView.tsx` | `+95 / -45` lines |
| **3** | **Sync `bake_overlay.py` so downloaded `output_full.mp4` matches on-screen rendering**:<br>- Update `_progress` and `_compose_frame` to reveal `release`, `bounce`, and `impact ?? deviation` progressively in Seg B (`t >= seg_b_*_sec`) instead of statically.<br>- Draw `bounce -> (impact ?? deviation)` and the growing `trajectory_post` polyline in Seg B and Seg C.<br>- Port `PredictedPath` (`_draw_predicted_path`) into `_compose_frame` when `bi >= 1` so the downloaded MP4 matches the review screen. | `backend/pipeline/bake_overlay.py` | `+85 / -25` lines |
| **4** | **Add/update tests for `0.35×` Segment B timing, Segment A removal, and overlay bake parity**:<br>- Unit test `segments` timestamps (`seg_a_end_sec == 0.0`, `seg_b_*_sec` at `0.35×`, `seg_c_*_sec` with `impact` and `trajectory_post`) and `bake_full_overlay` with `events.impact` + `trajectory_post`. | `backend/tests/test_pipeline_isolation.py` (or `test_render_v2.py`) | `+60 / -10` lines |
