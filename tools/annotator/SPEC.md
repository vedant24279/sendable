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


## 7. Annotation UI

### 7.1 Pure Helpers
- **Ghost Visibility (`src/lib/ghost.ts`)**:
  - `computeGhostVisible(s)` evaluates whether system predictions may be rendered or used to influence label state:
    $$\text{ghostVisible} = s.\text{ghostAllowed} \land \neg s.\text{blindToggle} \land (s.\text{overlays.ghostTrajectory} \lor s.\text{overlays.ghostEvents})$$
  - Store fields: `ghostAllowed` (boolean), `blindToggle` (boolean), `overlays.ghostTrajectory` and `overlays.ghostEvents` (booleans).
- **Pin Projection & Hit Testing (`src/lib/pins.ts`)**:
  - `pinsForFrame(label, frame, showAll)`: extracts key event pins (`release`, `bounce`, `impact`) either matching the active `frame` or all events when `showAll` is true.
  - `hitTestPin(pins, imgX, imgY, scale, radiusScreenPx = 10)`: calculates screen-space Euclidean distance from cursor to pins, returning the closest pin within `radiusScreenPx`.
- **Keyboard Action Router (`src/lib/hotkeys.ts`)**:
  - `keyToAction(ev)` maps keyboard events to discrete domain actions (`armTool`, `disarmTool`, `setLastVisible`, `setImpactType`, `undo`, `redo`, `saveDraft`, `finalize`, `nudgePin`, `selectPin`).
  - **Input Shield**: Ignores all single-key and modifier hotkeys when `targetTag` is `INPUT`, `TEXTAREA`, or `SELECT` to prevent interference while editing notes or metadata.

### 7.2 Viewer Interaction & Canvas Rendering (`src/components/Viewer.tsx`)
- **Tool Arming & Placement**:
  - Keys `R`, `B`, `H` arm `release`, `bounce`, and `impact` placement tools respectively.
  - While armed, canvas cursor switches to `crosshair` and status bar displays `"Tool: <tool> - click to place"`.
  - Left-clicking the canvas places the event at the current frame using un-zoomed original image coordinates $(x, y)$ rounded to 1 decimal place, then automatically disarms the tool.
  - Attempting to place `impact` without first selecting an impact type (or with type `none`) blocks placement and displays an inline warning banner: `"Choose impact type first (1-4)"`.
- **Pin Selection, Dragging & Nudging**:
  - When no tool is armed, clicking within 10 screen pixels of a pin selects it.
  - Dragging a selected pin moves it across the image in real time; changes are committed as a single undoable history entry upon mouse-up.
  - Clicking empty canvas space or pressing `Esc` deselects the pin.
  - Arrow keys with `Ctrl` nudge the selected pin by $\pm 1$ image pixel ($\pm 10$ pixels when holding `Shift`).
- **Canvas Rendering**:
  - Color-coded pin markers: Release (orange `#f97316`, `R`), Bounce (pink `#ec4899`, `B`), Impact (red `#ef4444`, `H`).
  - Active/selected pin is highlighted with an outer ring and renders a label badge showing its frame number and $(x, y)$ coordinates.
- **Loupe Magnifier**:
  - 8x nearest-neighbor magnification box rendered with center crosshair.
  - Positioned at an up-right offset `(cursor.x + 28, cursor.y - 28 - size)` and automatically flips downward or leftward if overflowing viewport boundaries.

### 7.3 Timeline Markers (`src/components/Timeline.tsx`)
- Displays distinct circular markers for human-annotated events: Release (`R`), Bounce (`B`), and Impact (`H`).
- Displays a prominent `END` badge on the timeline for `last_visible_frame`.
- System ghost markers are rendered only when `computeGhostVisible` is true and styled with translucent, dashed borders.

### 7.4 Control Panel (`src/components/LabelPanel.tsx`)
- **Status & Mode**: Displays real-time save state (`Idle`, `Saving...`, `Saved`, `Save Failed`), delivery annotation mode (`MANUAL` or `ASSISTED`), and status pill (`draft`, `final`, `flagged`).
- **Workflow Actions**:
  - `Save Draft` (`Ctrl+S`): forces an immediate save of the current draft.
  - `Finalize` (`Ctrl+Enter`): validates all requirements and transitions status to `final`.
  - `Flag`: displays an inline reason input, transitions status to `flagged`, and appends the note.
  - `Reopen Draft`: restores an already finalized delivery back to `draft`.
  - `Adopt System Release+Bounce`: one-click adoption of system release and bounce coordinates; hidden when ghost visibility is disabled.
- **Validation Issues List**: Lists blocking errors and non-blocking warnings with one-click jump to the relevant frame.
- **Events Table**: Tabular view of Release, Bounce, Impact, and Last Visible frames and coordinates with `Go` (jump to frame) and `✕` (clear event) buttons.
- **Metadata Fields**: Dropdowns and inputs for `split`, `ball_colour`, `batter_hand`, `bowler_type`, `lighting`, 1-4 impact buttons, conditional `lbw` dropdown (enabled for pad impact), flags checkboxes, and notes textarea.

### 7.5 Top Bar, Safety & Progression
- **Annotator Identification**: Reads annotator name from URL query parameter `?annotator=` (default: `vedant`).
- **Progress Counter**: Tracks finalized deliveries: `Final: x / N`.
- **Auto-Advance**: Checkbox (enabled by default) automatically selects the next non-final clip upon finalizing.
- **Dirty Safety**: `window.beforeunload` listener alerts the user if attempting to leave or reload with unsaved modifications or while a save is in flight.

## 8. Ground-Truth Calibration

### 8.1 World Coordinates & Pitch Regulation
The ground-truth calibration model establishes metric planar homography between pixel coordinates and the 3D ground plane ($Y = 0$).
- **Source of Regulation Dimensions**: [`backend/pipeline/reconstruct3d/world_points.py`](file:///c:/Users/vedan/Desktop/Internship/sendable/backend/pipeline/reconstruct3d/world_points.py) derived from official Laws of Cricket (Law 6):
  - Pitch length stump-to-stump: `PITCH_LENGTH_M = 20.12` ($22\text{ yards}$).
  - Popping crease in front of stumps: `POPPING_IN_FRONT_M = 1.22` ($4\text{ ft}$).
  - Return crease half-width from middle stump: `RETURN_HALF_WIDTH_M = 1.32` ($4\text{ ft } 4\text{ in}$).
  - Distance between popping creases: $20.12 - 2 \times 1.22 = 17.68\text{ m}$ ($58\text{ ft}$).
- **Coordinate Axes**:
  - `pitch_x_m`: Perpendicular across the pitch, positive toward **IMAGE-RIGHT** (left return crease at $-1.32\text{ m}$, right return crease at $+1.32\text{ m}$).
  - `pitch_z_m`: Along pitch length, positive toward the bowler ($0.0\text{ m}$ at the striker's stump line).
- **World Points $(X, Z)$ in Metres**:
  - `bat_stump`: $(0.0, 0.0)$
  - `bat_L`: $(-1.32, 1.22)$
  - `bat_R`: $(+1.32, 1.22)$
  - `bowl_L`: $(-1.32, 18.90)$ (derived as $20.12 - 1.22 = 18.90\text{ m}$)
  - `bowl_R`: $(+1.32, 18.90)$ (derived as $20.12 - 1.22 = 18.90\text{ m}$)
  - `bowl_stump`: $(0.0, 20.12)$

> [!WARNING]
> **Known Issue with Legacy Zones**: `zones.py` in `Zone-div_V8m` and `Zone-div(final)` uses $19.68\text{ m}$ between popping creases (which inflates pitch length to $22.12\text{ m}$ instead of the regulation $20.12\text{ m}$ / $17.68\text{ m}$ popping crease separation). Its `length_m` and length-zone boundaries are consequently inflated; the annotator does not use it.

### 8.2 Data Model (`calibration_gt`)
Additive optional field on `Label`:
```json
{
  "calibration_gt": {
    "points": {
      "bat_L": [x, y],
      "bat_R": [x, y],
      "bowl_L": [x, y],
      "bowl_R": [x, y],
      "bat_stump": [x, y],
      "bowl_stump": [x, y]
    },
    "source": "system_verified | system_adjusted | manual",
    "residual_px": 0.0,
    "updated_at": "ISO-8601 string"
  }
}
```

### 8.3 Geometry & Error Thresholds
- **Exact 4-Point Homography**: Solves $8\times8$ linear system for $H_{\text{img} \to \text{world}}$ from the four corners (`bat_L`, `bat_R`, `bowl_L`, `bowl_R`).
- **Stump Reprojection Residual (`residual_px`)**:
  - Middle stumps (`bat_stump` at $(0, 0)$ and `bowl_stump` at $(0, 20.12)$) are reprojected into image space via $H^{-1}$.
  - Root-Mean-Square (RMS) pixel reprojection distance:
    $$\text{residual\_px} = \sqrt{\frac{d_{\text{bat\_stump}}^2 + d_{\text{bowl\_stump}}^2}{2}}$$
- **Provisional Thresholds**:
  - `CALIB_WARN_PX = 4.0`: residual $> 4.0\text{ px}$ generates a non-blocking validation warning.
  - `CALIB_ERROR_PX = 12.0`: residual $> 12.0\text{ px}$ generates a blocking validation error.
  - *Note*: Because stump points sit extrapolated $1.22\text{ m}$ beyond the crease line, perspective errors are naturally amplified at them; these thresholds are provisional.
- **Backend Recomputation**: On every `PUT`, the backend recomputes `residual_px` using `fit_homography`. If the client value differs by $> 0.01\text{ px}$ (or is missing), the backend overwrites it.

### 8.4 Validation Constraints
- **Bounds**: All 6 points must fall within $[0, \text{width}] \times [0, \text{height}]$.
- **Convexity & Area**: The 4 corner points (`bat_L`, `bat_R`, `bowl_R`, `bowl_L`) must form a strictly convex quadrilateral with area $> 2\%$ of the frame area.
- **Horizontal Ordering**:
  - `bat_L.x < bat_R.x` and `bowl_L.x < bowl_R.x`.
  - `bat_stump.x` must be bounded between `bat_L.x` and `bat_R.x`.
  - `bowl_stump.x` must be bounded between `bowl_L.x` and `bowl_R.x`.
- **Status "final" Requirements**:
  In addition to earlier requirements, a label with `status: "final"` strictly requires:
  - `calibration_gt` is non-null.
  - `split` is non-null (`"dev"` or `"final"`).
  - `bowler_type` is non-null (`"pace"` or `"spin"`).
  - `lighting` is non-null (`"bright"`, `"overcast"`, or `"low"`).
  - When `impact.type === "pad"`, `lbw` must be non-null.

- **Bad Calibration Flag Exception**:
  A calibration residual above `CALIB_ERROR_PX` (12.0 px) is treated as a blocking validation error only when the label does NOT contain the flag `"bad_calibration"`. When `"bad_calibration"` is set, it is downgraded to a non-blocking warning.

## 9. Calibration UI

### 9.1 Mode & Controls
- **Toggle Mode**: Keyboard shortcut `C` toggles Calibration Mode on/off (ignored inside form inputs/selects). Also accessible via the `📐 Calibration (C)` toolbar button and "Open calibration" issue links.
- **Tool Disarming**: Entering Calibration Mode disarms all event placement tools (`R`, `B`, `H`, `E`).
- **Handle Selection**: `Tab` and `Shift+Tab` cycle forward and backward through the six calibration handles (`bat_L`, `bat_R`, `bowl_L`, `bowl_R`, `bat_stump`, `bowl_stump`).
- **Fine Adjustment**: `Ctrl+Arrow` nudges the selected calibration handle by $1.0\text{ px}$; `Ctrl+Shift+Arrow` nudges by $0.1\text{ px}$.

### 9.2 Canvas Overlays
- **Handles**: Six draggable circular handles color-coded by role (`bat_L`: cyan, `bat_R`: blue, `bowl_L`: emerald, `bowl_R`: green, `bat_stump`: amber, `bowl_stump`: purple). The active handle is ringed with a white outer border.
- **Click-to-Place Sequence**: Clicking empty canvas space places the currently selected point (or the first missing point) and automatically advances selection to the next missing handle.
- **Pitch Rectangle & 1 m Grid**: Projected onto the canvas using $H$ when the 4 corners are placed; 1 m grid lines rendered as thin semi-transparent lines ($22\%$ opacity).
- **Predicted Stump Positions**: Homography-projected middle stump locations rendered as dashed hollow circles alongside clicked stump points to expose reprojection gaps.
- **Loupe Magnifier**: Always active in calibration mode; pressing `L` cycles magnification through `8x -> 16x -> off`.

### 9.3 Calibration Panel (`src/components/CalibrationPanel.tsx`)
- Replaces the event table in the side panel while in Calibration Mode.
- Shows real-time stump residual error badge (green $< 4\text{ px}$, amber $4-12\text{ px}$, red $> 12\text{ px}$) and source badge (`system_verified`, `system_adjusted`, or `manual`).
- **Stump Check Readout**: Displays longitudinal $Z$ coordinates projected from clicked stump pixels:
  `Stump check: bat end Z = x.xx m (expected 0.00) | bowl end Z = x.xx m (expected 20.12)`.
- **Table of Points**: Lists all 6 landmarks with $(x, y)$ coordinates, `Go` (center & 4x zoom), and `Clear` buttons.
- **Batch Actions**: "Accept system calibration", "Reset to system", and "Clear all".
- **Guidance & Hints**: Instructs annotators on finding the true ground base below the middle stump and checking first/last frames for camera movement.

### 9.4 Metric Readouts & Clip List Badges
- **Status Bar Metric Readout**: When calibration is valid, the bottom status bar displays real-time cursor ground-plane position in metres: `pitch_x_m: +x.xx m, pitch_z_m: +z.xx m`.
- **Events Table Pitch Column**: Key Events table includes a `Pitch pos` column showing projected metric positions $(X, Z)\text{ m}$ for Release, Bounce, and Impact.
- **Clip List Calibration Badge**: Clips with `calibration_gt` display a purple `C` badge in the clip list.
- **Sorting**: Clip list supports sorting "By system residual (high to low)" based on prefill `system_residual_px`.

## 10. Derived Stumps & Stump Confirmation

Measurements on 79 delivery clips revealed that clicked stump points are frequently noisy (batter-end points scatter $\pm 0.5\text{ m}$ with outliers up to $2\text{ m}$; bowler-end points sit on average $0.45\text{ m}$ short; stump bases are frequently occluded by the batter or umpire), whereas the four pitch corners fit the pitch dimensions reliably.

To eliminate false-positive calibration error blocks while retaining high-precision metric ground-plane homography, ground-truth calibration is **corner-driven**:

### 10.1 Data Model
`calibration_gt` includes an additive field `stump_confirmed`:
```json
{
  "calibration_gt": {
    "points": { ... },
    "source": "system_verified | system_adjusted | manual",
    "residual_px": null,
    "stump_confirmed": {
      "bat_stump": false,
      "bowl_stump": false
    },
    "updated_at": "ISO-8601 string"
  }
}
```
- **Old Label Compatibility**: When `stump_confirmed` is omitted (or loaded from legacy schema v1 labels), both stumps default to `false`.

### 10.2 Dynamic Stump Derivation & Confirmation
- **Homography Fitting**: Homography matrix $H$ is computed strictly from the 4 corner landmarks (`bat_L`, `bat_R`, `bowl_L`, `bowl_R`).
- **Unconfirmed (Derived) Stumps**: When a stump is unconfirmed, its coordinates automatically track the exact homography prediction:
  - `bat_stump = round1(world_to_pixel(H, 0.0, 0.0))`
  - `bowl_stump = round1(world_to_pixel(H, 0.0, 20.12))`
  Moving, nudging, or resetting any corner automatically re-derives all unconfirmed stumps.
- **Stump Confirmation**: Manually placing, dragging, or nudging a stump handle marks that stump as `confirmed` (`stump_confirmed[name] = true`). A confirmed stump retains its clicked location when pitch corners are adjusted.
- **Unconfirm Action**: Each stump row in `CalibrationPanel` provides an "Unconfirm (derive again)" button that snaps the stump back to the homography projection and marks it unconfirmed.

### 10.3 Residual Calculation
- `residual_px` is computed as the RMS reprojection error **over confirmed stumps only**:
  - Both confirmed: $\text{residual\_px} = \sqrt{(d_{\text{bat}}^2 + d_{\text{bowl}}^2) / 2}$
  - One confirmed: $\text{residual\_px} = d_{\text{confirmed}}$
  - Neither confirmed: $\text{residual\_px} = \text{null}$
- **Validation Rules**: `CALIB_WARN_PX` and `CALIB_ERROR_PX` thresholds apply strictly when `residual_px` is non-null. When no stump is confirmed, `residual_px: null` allows finalizing without artificial residual blocks.

### 10.4 System Calibration Actions & Source Classification
- **Accept system calibration**: Copies the 4 system corners and derives both stumps with `stump_confirmed = { bat_stump: false, bowl_stump: false }`.
- **Reset to system**: Copies all six system points with both stumps unconfirmed (`stump_confirmed = { bat_stump: false, bowl_stump: false }`).
- **Source Classification**: Compares **only the 4 corner points** against system points. Moving or deriving stump points does not alter the source classification between `system_verified` and `system_adjusted`.

## 11. In-App Video Library & Recents

Replaces the single static folder model with an in-app, user-managed video library residing outside the repository.

### 11.1 Directory Structure & Storage
- **Root Directory**: Configured via `ANNOTATOR_LIBRARY_DIR` environment variable; defaults to `<home>/CricketAnnotator/library` (`Path.home() / "CricketAnnotator" / "library"`). Never stored inside the git repository.
- **Videos Subdirectory**: `videos/<clip_id><ext>` storing renamed files. Client filenames are never used as on-disk paths.
- **Whitelisted Video Extensions**: `.mp4`, `.mov`, `.mkv`, `.avi`, `.m4v`, `.webm`.
- **Catalog File**: `library.json` using atomic temporary file replacement on save.

### 11.2 Catalog Entry Schema
```json
{
  "clip_id": "c_a1b2c3d4",
  "display_name": "match_delivery_01.mp4",
  "sha256": "a1b2c3d4e5...",
  "size_bytes": 1048576,
  "added_at": "ISO-8601 string",
  "last_opened_at": "ISO-8601 string",
  "hidden": false,
  "fps": 30.0,
  "frame_count": 92,
  "width": 1920,
  "height": 1080,
  "warnings": []
}
```
- **Clip ID**: Formatted as `"c_" + sha256[:8]`. If the 8-character prefix collides with an existing clip with a different hash, uses 12 hex characters (`"c_" + sha256[:12]`).
- **Warnings**:
  - `low_fps`: `fps < 25`
  - `low_res`: `height < 720`
  - `short`: `frame_count < 20`
  - `long`: `frame_count > 300`

### 11.3 Upload & Ingestion
- `POST /api/library/upload?name=<filename>`: Streams raw binary body (no multipart form dependency).
- **Size Limits**: Enforces `ANNOTATOR_MAX_UPLOAD_MB` (default 2048 MB); returns HTTP 413 if exceeded.
- **Validation**: Rejects unsupported extensions (HTTP 415) and empty bodies (HTTP 400).
- **Deduplication**: If `sha256` already exists in `library.json`, cleans up upload temp file, un-hides the entry (`hidden = false`), updates `last_opened_at`, and returns `{ "status": "duplicate", "entry": ... }`.
- **Integrity**: Decodes sequentially with OpenCV. If 0 frames or corrupt, deletes the video file and returns HTTP 422 with zero leftover files.

### 11.4 Endpoints
- `GET /api/library/recents?limit=20`: Returns non-hidden entries sorted by `last_opened_at desc` (fallback `added_at desc`), joined with `label_status`.
- `GET /api/library`: Returns all non-hidden entries joined with `label_status`.
- `GET /api/library/info`: Returns `{ "folder": str, "count": int }`.
- `POST /api/library/{clip_id}/opened`: Updates `last_opened_at` timestamp.
- `POST /api/library/{clip_id}/hide`: Flags `hidden = true` (video and label persist on disk).
- `GET /api/clips`: Aggregates library clips (`pool: "library"`) and debug manifest clips (`pool: "debug"`).
- `GET /api/clips/{clip_id}/prefill`: Returns empty events, empty trajectory, and `calibration: null` for library clips.
