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
