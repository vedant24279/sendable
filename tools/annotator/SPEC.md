# Cricket Delivery Clip Annotator Specification

[SPEC]
1. Label schema v1 (one per clip): schema_version=1, clip_id, split ("dev"|"final"|null), annotator (str), mode ("assisted"|"blind"), status ("draft"|"final"|"flagged"), created_at, updated_at, ball_colour ("white"|"red"|"pink"), batter_hand ("right"|"left"), bowler_type ("pace"|"spin"), lighting ("bright"|"overcast"|"low"), release {frame,x,y}, bounce {frame,x,y}, impact {type:"bat"|"pad"|"stumps"|"none", frame, x, y} (frame/x/y null when type is "none"), last_visible_frame:int, lbw:null|"out"|"not_out_pitched_leg"|"not_out_impact_outside"|"not_out_missing"|"umpires_call", flags: list of "ball_not_visible"|"camera_moved"|"bad_calibration"|"unclear", notes:str. x,y are ORIGINAL video pixel coordinates (not screen coordinates), floats.
2. Validation rules: frames are ints within [0, frame_count-1]; x in [0,width], y in [0,height]; release.frame < bounce.frame; bounce.frame <= impact.frame when impact exists; impact.frame <= last_visible_frame when impact exists; lbw may be non-null only when impact.type == "pad"; if impact.type == "none" then impact frame/x/y must be null. A status "final" label must have release, bounce, impact (type at least), last_visible_frame, ball_colour, batter_hand filled; "draft" may be partial.
3. Later UI requirements (not for this prompt): frame-exact stepping with prefetch; zoom to 8x + loupe; arrow-key 1px nudge of selected point; hotkeys R/B/H/E place release/bounce/impact/end, 1-4 choose impact type, Z/Y undo/redo, Ctrl+S save, Space play at 0.25x; timeline with event ticks and frames where the system found the ball; ghost overlay of the system's prediction from results.json; calibration overlay (pitch rectangle and stump positions); BLIND mode for split=final: ghost hidden until the label is saved as final (lock-then-reveal); second-pass labels stored as separate annotator names with a diff report; progress dashboard; scoring panel.
[/SPEC]

## 4. Prefill Shape

The endpoint `GET /api/clips/{id}/prefill` returns the system's detected events, trajectory points, and pitch calibration normalised to the following JSON structure:

```json
{
  "clip_id": "03ef03b1",
  "events": {
    "release": {
      "frame": 2,
      "x": 776.0,
      "y": 456.0,
      "timestamp_sec": 0.0667
    },
    "bounce": {
      "frame": 12,
      "x": 850.0,
      "y": 546.0,
      "timestamp_sec": 0.4,
      "zone": "SHORT",
      "length_m": 8.777,
      "grid_cell": [55, 4]
    },
    "impact": null,
    "deviation": {
      "frame": 19,
      "x": 913.0,
      "y": 352.0,
      "timestamp_sec": 0.6333
    }
  },
  "trajectory": [
    {
      "frame": 2,
      "x": 776.0,
      "y": 456.0,
      "conf": 0.7999,
      "interpolated": false
    }
  ],
  "calibration": [
    { "name": "bat_L", "x": 778.0, "y": 434.0 },
    { "name": "bat_R", "x": 1083.0, "y": 430.0 },
    { "name": "bat_stump", "x": 936.0, "y": 426.0 },
    { "name": "bowl_L", "x": 739.0, "y": 764.0 },
    { "name": "bowl_R", "x": 1115.0, "y": 768.0 },
    { "name": "bowl_stump", "x": 922.0, "y": 784.0 }
  ]
}
```

### Notes on Prefill Fields:
- `events`: Contains `release`, `bounce`, `impact`, and `deviation`. Every event field is nullable (`null` if absent from results.json).
- `trajectory`: Array of ball detection points with `frame` (int), `x` (float), `y` (float), `conf` (float, nullable), and `interpolated` (boolean).
- `calibration`: Pitch landmarks normalised from results.json into an array of `{ "name": str, "x": float, "y": float }`.


## 5. Viewer Architecture and Controls

### 5.1 Viewport Transformation
- **Coordinate System**: All overlays and annotations map to ORIGINAL video pixel coordinates `[0..width, 0..height]` (floats).
- **Transformation Formula**:
  - `screen.x = image.x * scale + offsetX`
  - `screen.y = image.y * scale + offsetY`
  - Inverted: `image.x = (screen.x - offsetX) / scale`, `image.y = (screen.y - offsetY) / scale`
- **Scale Constraints**: Clamped to `[0.1, 16.0]`. When `scale >= 2.0`, canvas `imageSmoothingEnabled` is disabled for crisp nearest-neighbour inspection.
- **Centering & Fitting**: `F` key fits the full delivery frame into the container maintaining aspect ratio; `G` resets zoom to 1:1 pixel scale (100%).
- **Zooming**: Mouse wheel zooms centered exactly at the cursor point, keeping the image pixel under the cursor fixed.

### 5.2 Frame Cache & Prefetching
- **Decode Guarantee**: Backend decodes frames sequentially with OpenCV and serves JPEGs (quality 92).
- **Client Cache**: Frontend maintains an LRU cache of up to 60 `ImageBitmap` instances per delivery clip.
- **Strict Frame Display**: The viewer never displays a frame index other than the currently selected frame. If a frame is decoding/fetching, a clean loading placeholder is displayed.
- **Prefetch Window**: Upon every frame step, background prefetching automatically loads frames `[n - 3 .. n + 10]`.
- **Clip Switching**: Pending frame fetches are immediately aborted via `AbortController` when switching clips.

### 5.3 Overlays
- **Calibration Overlay**:
  - Boundary polygon: `bowl_L -> bowl_R -> bat_R -> bat_L` closed path.
  - Stumps: Labelled markers for `bat_stump` and `bowl_stump`.
  - Always visible when toggled, unaffected by blind mode.
- **Ghost Trajectory**:
  - Solid dots for detected points, hollow dots for interpolated points.
  - Current-frame detection is highlighted with a distinct outer ring.
  - Gated by `ghostAllowed` (hidden in blind mode).
- **Ghost Events**:
  - Coloured pins for `Release`, `Bounce`, `Deviation`, and `Impact`.
  - Pin visibility is configurable to show only the active frame event or all clip events.
  - Gated by `ghostAllowed`.

### 5.4 Navigation & Loupe
- **8x Loupe Magnifier**: 160x160 px window at 8x magnification with center crosshair. Toggled via `L` or active while holding `Alt`.
- **Timeline**: Visual tick track indicating detected vs. interpolated ball detections per frame, event markers, and interactive scrub handle.
- **Playback**: Space bar toggles smooth 0.25x slow-motion playback.
- **Reserved Keys**: Hotkeys `R`, `B`, `H`, `E`, `Z`, `Y`, and digits `1-4` are strictly reserved for subsequent annotation tools.

## 6. Label Logic

### 6.1 State Model & Pure Operations (`src/lib/labelModel.ts`)
- **Schema Alignment**: Types directly match `tools/annotator/backend/app/schema.py` (`schema_version=1`, `clip_id`, `split`, `annotator`, `mode`, `status`, `created_at`, `updated_at`, `ball_colour`, `batter_hand`, `bowler_type`, `lighting`, `release`, `bounce`, `impact`, `last_visible_frame`, `lbw`, `flags`, `notes`).
- **Precision**: Original pixel coordinates $(x, y)$ are rounded to 1 decimal place. Frame numbers are rounded to integers.
- **Preconditions & Constraints**:
  - Placing impact coordinates requires an existing non-none impact type (`bat`, `pad`, `stumps`). Placing without a type or with type `none` throws a descriptive `Error`.
  - Setting impact type to `none` forces impact `frame`, `x`, and `y` to `null`.
  - Switching impact type away from `pad` resets `lbw` to `null`.
- **Mode Tracking**:
  - Newly initialized labels start in `blind` mode.
  - Any edit made while `ghostVisible` is `true` escalates mode to `assisted` permanently.
- **System Event Adoption**:
  - `adoptSystemEvents` copies system-detected `release` and `bounce` only; `impact` remains untouched.
  - Mode is set to `assisted`.

### 6.2 Validation Rules (`src/lib/validate.ts`)
Validates labels against `schema.py` constraints and clip dimension metadata, returning an array of `{ path, message, severity: "error" | "warning" }`.
- **Strict Errors**:
  - `schema_version` must equal 1.
  - When `impact.type === 'none'`, coordinates must all be null.
  - `lbw` may only be set when `impact.type === 'pad'`.
  - Ordering: `release.frame < bounce.frame`, `bounce.frame <= impact.frame`, `impact.frame <= last_visible_frame`, `release.frame <= last_visible_frame`.
  - Bounds: frames must be integers $\in [0, \text{frame\_count} - 1]$; $(x, y)$ coordinates must be within $[0, \text{width}] \times [0, \text{height}]$.
  - Status `final` requirements: `annotator` (non-empty), `release`, `bounce`, `impact` (including coordinates when not `none`), `last_visible_frame`, `ball_colour`, and `batter_hand` must be filled.
- **Non-blocking Warnings**:
  - `release.frame > 20`: unusually late release.
  - `bounce.frame - release.frame <= 3`: rapid bounce within 3 frames of release.
  - `last_visible_frame < bounce.frame`: last visible frame positioned prior to bounce.

### 6.3 History Management (`src/lib/history.ts`)
- Generic `HistoryStack<T>` managing linear undo/redo history.
- Capped at 200 entries to bound memory consumption; evicts oldest past states on overflow.
- Branching actions clear the future redo stack.

### 6.4 Store & Autosave (`src/labelStore.ts`)
- **State**: `{ label, savedLabel, dirty, saveState, saveError, issues, canUndo, canRedo }`.
- **Autosave Engine**:
  - 1500 ms debounced autosave runs exclusively when status is `draft`.
  - Monotonic revision counter ensures in-flight network saves never overwrite newer local modifications.
  - Switching delivery clips immediately flushes any pending draft autosave before loading the next clip.
  - Save errors transition `saveState` to `"error"` while preserving `dirty: true`.
- **Lifecycle Actions**:
  - `load`: fetches remote label or creates `emptyLabel`, resets history stack.
  - `apply`: pushes to history, recomputes validation issues, marks dirty, and schedules autosave.
  - `finalize`: runs validation for `final`; halts without network call if any error issues exist; warnings do not block submission.
  - `flag`: updates status to `"flagged"` and appends note.
  - `reopen`: restores status from `"final"` to `"draft"`.

