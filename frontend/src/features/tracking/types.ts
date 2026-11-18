// Mirror of backend results.json (spec §7). Backend JSON is the source of truth.

export type MarkerName =
  | "bat_L" | "bat_R" | "bowl_L" | "bowl_R"
  | "bat_stump" | "bowl_stump";

// Polygon vertices (clockwise from bowler-end left, which is bottom-left
// when the camera is behind the bowler).
export const POLYGON_ORDER: MarkerName[] = [
  "bowl_L", "bowl_R", "bat_R", "bat_L",
];

// Stand-alone single-point markers (the middle-stump bases).
export const STUMP_MARKERS: MarkerName[] = ["bat_stump", "bowl_stump"];

export const MARKER_ORDER: MarkerName[] = [...POLYGON_ORDER, ...STUMP_MARKERS];

export const MARKER_LABELS: Record<MarkerName, string> = {
  bat_L:  "Batter's side · LEFT return crease (where popping crease meets the LEFT return crease at the batter's end)",
  bat_R:  "Batter's side · RIGHT return crease (where popping crease meets the RIGHT return crease at the batter's end)",
  bowl_L: "Bowler's side · LEFT return crease (where popping crease meets the LEFT return crease at the bowler's end)",
  bowl_R: "Bowler's side · RIGHT return crease (where popping crease meets the RIGHT return crease at the bowler's end)",
  bat_stump:  "Batter's end middle stump base (place at the foot of the middle stump at the batter's end)",
  bowl_stump: "Bowler's end middle stump base (place at the foot of the middle stump at the bowler's end)",
};

export const MARKER_SHORT_LABELS: Record<MarkerName, string> = {
  bat_L:  "Batter's side · Left return crease",
  bat_R:  "Batter's side · Right return crease",
  bowl_L: "Bowler's side · Left return crease",
  bowl_R: "Bowler's side · Right return crease",
  bat_stump:  "Batter's end middle stump base",
  bowl_stump: "Bowler's end middle stump base",
};

export type Calibration = Record<MarkerName, [number, number]>;

export type JobStatus = "queued" | "processing" | "done" | "failed" | "cancelled";

export interface JobProgress { frame: number; total: number; percent: number; }

export interface JobRecord {
  job_id: string;
  status: JobStatus;
  progress: JobProgress | null;
  error: { code: string; message: string } | null;
}

export type Zone = "YORKER" | "FULL" | "GOOD" | "SHORT";

export interface ReleaseEvent {
  frame: number; timestamp_sec: number; x: number; y: number;
}

export interface BounceEvent extends ReleaseEvent {
  interpolated: boolean;
  zone: Zone | null;
  length_m: number | null;
  grid_cell: [number, number] | null;
}

export interface ImpactEvent extends ReleaseEvent {
  source?: string | null;
  type?: string | null;
  reason?: string;
}

export interface TrajectoryPoint {
  frame: number; x: number; y: number;
  interpolated: boolean; conf: number | null;
}

export interface TrajectoryPostPoint {
  frame: number;
  x: number;
  y: number;
  conf?: number | null;
}

// Line-only LBW block (backend/pipeline/lbw_line.py). Geometry is computed in
// Python; the frontend only draws the integer pixels it is given.
export type LbwOverall = "OUT_LINE" | "NOT_OUT_LINE" | "UMPIRES_CALL" | "NO_IMPACT";
export type LbwSide = "off" | "leg" | "centre" | null;
export type LbwPitchingVerdict =
  | "in_line" | "outside_off" | "outside_leg" | "outside_side_unknown";
export type LbwImpactVerdict = LbwPitchingVerdict | "umpires_call";
export type LbwWicketsVerdict = "HITTING" | "UMPIRES_CALL" | "MISSING";
export type LbwPixel = [number, number] | null;

export interface LbwPixels {
  stump_base_left: LbwPixel;
  stump_base_right: LbwPixel;
  stump_top_offset_px: number | null;
  pitching: LbwPixel;
  impact_ground: LbwPixel;
  wickets_centre: LbwPixel;
  wickets_left: LbwPixel;
  wickets_right: LbwPixel;
  impact_left: LbwPixel;
  impact_right: LbwPixel;
}

export interface LbwResult {
  mode: "line";
  batter_hand: "right" | "left" | null;
  pitching: { x: number; z: number; side: LbwSide; verdict: LbwPitchingVerdict };
  impact: { x: number; side: LbwSide; verdict: LbwImpactVerdict };
  wickets: {
    x: number;
    sigma: number;
    sigma_stat?: number;
    verdict: LbwWicketsVerdict;
    margin_m: number;
    stable: boolean;
  };
  height: null;
  overall: LbwOverall;
  notes: string[];
  slope_flag: boolean;
  pixels?: LbwPixels;
}

export interface TrackingResult {
  schema_version: 1;
  job_id: string;
  /** Ball type used for this job — drives per-ball marker/trajectory colouring
   *  in the frontend overlay. May be absent on older cached results.json files. */
  ball_type?: BallType;
  video: {
    filename: string; fps: number; frame_count: number;
    width: number; height: number; duration_sec: number;
  };
  outputs: {
    annotated_video_url: string;
    csv_url: string;
    first_frame_url: string;
  };
  calibration: Calibration;
  events: {
    release: ReleaseEvent | null;
    bounce: BounceEvent | null;
    impact?: ImpactEvent | null;
    deviation: ReleaseEvent | null;
  };
  trajectory: TrajectoryPoint[];
  trajectory_post?: TrajectoryPostPoint[];
  /** Present only when the job ran with TRACKER_LBW_MODE=line and an impact was found. */
  lbw?: LbwResult | null;
  segments: {
    render_mode?: string;
    seg_a_start_sec: number;
    seg_a_end_sec: number;
    seg_a_release_sec: number | null;
    seg_a_bounce_sec: number | null;
    seg_a_deviation_sec: number | null;
    seg_b_start_sec: number;
    seg_b_end_sec: number;
    seg_b_release_sec: number | null;
    seg_b_bounce_sec: number | null;
    seg_b_impact_sec?: number | null;
    seg_b_deviation_sec: number | null;
    seg_b_post_end_sec?: number | null;
    speed_b?: number;
    seg_post_end_frame?: number | null;
    seg_c_start_sec: number | null;
    seg_c_rb_end_sec: number | null;
    seg_c_bi_end_sec?: number | null;
    seg_c_bd_end_sec: number | null;
    seg_c_post_end_sec?: number | null;
    seg_c_end_sec: number | null;
  };
  stats: {
    frames_with_ball: number;
    frames_interpolated: number;
    detection_rate: number;
    processing_time_sec: number;
  };
}

export interface FirstFrameResponse {
  upload_id: string;
  filename: string;
  width: number;
  height: number;
  duration_sec: number;
  first_frame_url: string;
}

export type BallType = "white" | "red" | "pink";

export interface JobListItem {
  job_id: string;
  filename: string | null;
  status: JobStatus;
  created_at: number;
  zone: Zone | null;
  first_frame_url: string | null;
  has_feedback?: boolean;
}

export type EventVerdict = "correct" | "wrong" | "unsure";
export type TrackingQuality = "smooth" | "jumpy" | "lost";
export type OverlayAlignment = "good" | "slightly_off" | "way_off";
export type WhatWentWrong =
  | "wrong_frame" | "wrong_zone_color" | "wrong_position"
  | "not_the_ball" | "missed_entirely";

export interface DeliveryFeedback {
  per_event: {
    release: EventVerdict | null;
    bounce: EventVerdict | null;
    deviation: EventVerdict | null;
  };
  tracking_quality: TrackingQuality | null;
  overlay_alignment: OverlayAlignment | null;
  what_went_wrong: WhatWentWrong[];
  comment: string;
  overall_stars: number;
}

// Spec §10 error code → UI message
export const ERROR_MESSAGES: Record<string, string> = {
  INVALID_VIDEO: "This file couldn't be read as a video. Try MP4 (H.264).",
  VIDEO_TOO_LARGE: "Videos up to 500 MB are supported. Trim to one delivery.",
  VIDEO_TOO_LONG: "Clips must be 30 seconds or shorter. Trim to one delivery.",
  INVALID_BALL_TYPE: "Pick white or red ball before analyzing.",
  INVALID_CALIBRATION: "Calibration points look wrong — re-place the 4 markers.",
  MODEL_LOAD_FAILED: "Analysis engine unavailable. Try again shortly.",
  NO_BALL_DETECTED:
    "No ball was detected. Check lighting/angle and that the ball is visible.",
  HOMOGRAPHY_FAILED:
    "Pitch markers couldn't form a valid layout — re-place them.",
  ENCODING_FAILED: "Processing finished but the video couldn't be saved. Try again.",
  CANCELLED: "Cancelled.",
  INTERNAL: "Something went wrong. Try again.",
};

export const ZONE_COLORS: Record<Zone, string> = {
  YORKER: "#FFFF00",
  FULL: "#64C8E6",
  GOOD: "#32FF00",
  SHORT: "#FF0000",
};
