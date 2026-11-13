/**
 * Label validation layer mirroring backend schema.py validation rules.
 */

import { Label, LabelStatus } from './labelModel';
import { CALIB_WARN_PX, CALIB_ERROR_PX } from './calibConstants';
import { validateCalibrationGeometry } from './calibration';

export interface Issue {
  path: string;
  message: string;
  severity: 'error' | 'warning';
}

export interface ClipDimensions {
  frame_count?: number;
  width?: number;
  height?: number;
}

/**
 * Validates a label against schema.py constraints and clip dimensions.
 * Returns an array of Issues.
 */
export function validateLabel(
  label: Label,
  meta?: ClipDimensions | null,
  forStatus?: LabelStatus
): Issue[] {
  const issues: Issue[] = [];

  // 1. schema_version must be 1
  if (label.schema_version !== 1) {
    issues.push({
      path: 'schema_version',
      message: 'schema_version must be 1',
      severity: 'error',
    });
  }

  // 2. Impact type none check
  if (label.impact && label.impact.type === 'none') {
    if (
      label.impact.frame != null ||
      label.impact.x != null ||
      label.impact.y != null
    ) {
      issues.push({
        path: 'impact',
        message: "When impact.type is 'none', frame, x, and y must all be null",
        severity: 'error',
      });
    }
  }

  // 3. LBW rule: lbw may be non-null only when impact.type == 'pad'
  if (label.lbw != null) {
    if (!label.impact || label.impact.type !== 'pad') {
      issues.push({
        path: 'lbw',
        message: `lbw may be non-null only when impact.type == 'pad', got impact type '${label.impact?.type}'`,
        severity: 'error',
      });
    }
  }

  // 4. Frame order checks
  // release.frame < bounce.frame
  if (label.release && label.bounce) {
    if (label.release.frame >= label.bounce.frame) {
      issues.push({
        path: 'release.frame',
        message: `release.frame (${label.release.frame}) must be strictly less than bounce.frame (${label.bounce.frame})`,
        severity: 'error',
      });
    }
  }

  // bounce.frame <= impact.frame when impact exists and has a frame
  if (label.bounce && label.impact && label.impact.frame != null) {
    if (label.bounce.frame > label.impact.frame) {
      issues.push({
        path: 'impact.frame',
        message: `bounce.frame (${label.bounce.frame}) must be <= impact.frame (${label.impact.frame})`,
        severity: 'error',
      });
    }
  }

  // impact.frame <= last_visible_frame when impact exists and has a frame
  if (label.impact && label.impact.frame != null && label.last_visible_frame != null) {
    if (label.impact.frame > label.last_visible_frame) {
      issues.push({
        path: 'last_visible_frame',
        message: `impact.frame (${label.impact.frame}) must be <= last_visible_frame (${label.last_visible_frame})`,
        severity: 'error',
      });
    }
  }

  // release.frame <= last_visible_frame when release and last_visible_frame exist (from schema.py line 131)
  if (label.release && label.last_visible_frame != null) {
    if (label.release.frame > label.last_visible_frame) {
      issues.push({
        path: 'last_visible_frame',
        message: `release.frame (${label.release.frame}) must be <= last_visible_frame (${label.last_visible_frame})`,
        severity: 'error',
      });
    }
  }

  // 5. Dimensional bounds validation if context is provided
  const fc = meta?.frame_count;
  const w = meta?.width;
  const h = meta?.height;

  const checkFrame = (f: number, path: string, name: string) => {
    if (fc != null && fc > 0) {
      if (!Number.isInteger(f) || f < 0 || f >= fc) {
        issues.push({
          path,
          message: `${name} frame ${f} out of bounds [0, ${fc - 1}]`,
          severity: 'error',
        });
      }
    }
  };

  const checkXY = (x: number, y: number, basePath: string, name: string) => {
    if (w != null && (x < 0.0 || x > w)) {
      issues.push({
        path: `${basePath}.x`,
        message: `${name} x coordinate ${x} out of bounds [0, ${w}]`,
        severity: 'error',
      });
    }
    if (h != null && (y < 0.0 || y > h)) {
      issues.push({
        path: `${basePath}.y`,
        message: `${name} y coordinate ${y} out of bounds [0, ${h}]`,
        severity: 'error',
      });
    }
  };

  if (label.release) {
    checkFrame(label.release.frame, 'release.frame', 'release');
    checkXY(label.release.x, label.release.y, 'release', 'release');
  }

  if (label.bounce) {
    checkFrame(label.bounce.frame, 'bounce.frame', 'bounce');
    checkXY(label.bounce.x, label.bounce.y, 'bounce', 'bounce');
  }

  if (label.impact && label.impact.frame != null) {
    checkFrame(label.impact.frame, 'impact.frame', 'impact');
    if (label.impact.x != null && label.impact.y != null) {
      checkXY(label.impact.x, label.impact.y, 'impact', 'impact');
    }
  }

  if (label.last_visible_frame != null) {
    checkFrame(label.last_visible_frame, 'last_visible_frame', 'last_visible_frame');
  }

  // 6. Required fields for status "final"
  const targetStatus = forStatus ?? label.status;
  if (targetStatus === 'final') {
    if (!label.annotator || !label.annotator.trim()) {
      issues.push({
        path: 'annotator',
        message: "annotator is required for status 'final'",
        severity: 'error',
      });
    }
    if (!label.release) {
      issues.push({
        path: 'release',
        message: "release is required for status 'final'",
        severity: 'error',
      });
    }
    if (!label.bounce) {
      issues.push({
        path: 'bounce',
        message: "bounce is required for status 'final'",
        severity: 'error',
      });
    }
    if (!label.impact) {
      issues.push({
        path: 'impact',
        message: "impact is required for status 'final'",
        severity: 'error',
      });
    } else if (label.impact.type !== 'none') {
      if (
        label.impact.frame == null ||
        label.impact.x == null ||
        label.impact.y == null
      ) {
        issues.push({
          path: 'impact',
          message: `impact frame, x, and y are required when impact.type is '${label.impact.type}' in status 'final'`,
          severity: 'error',
        });
      }
    }
    if (label.last_visible_frame == null) {
      issues.push({
        path: 'last_visible_frame',
        message: "last_visible_frame is required for status 'final'",
        severity: 'error',
      });
    }
    if (!label.ball_colour) {
      issues.push({
        path: 'ball_colour',
        message: "ball_colour is required for status 'final'",
        severity: 'error',
      });
    }
    if (!label.batter_hand) {
      issues.push({
        path: 'batter_hand',
        message: "batter_hand is required for status 'final'",
        severity: 'error',
      });
    }
    if (!label.calibration_gt) {
      issues.push({
        path: 'calibration_gt',
        message: "calibration_gt is required for status 'final'",
        severity: 'error',
      });
    }
    if (!label.bowler_type) {
      issues.push({
        path: 'bowler_type',
        message: "bowler_type is required for status 'final'",
        severity: 'error',
      });
    }
    if (!label.lighting) {
      issues.push({
        path: 'lighting',
        message: "lighting is required for status 'final'",
        severity: 'error',
      });
    }
    if (label.impact?.type === 'pad' && label.lbw == null) {
      issues.push({
        path: 'lbw',
        message: "lbw is required for status 'final' when impact.type is 'pad'",
        severity: 'error',
      });
    }
  }

  // 7. Calibration geometry validation & residual checks
  if (label.calibration_gt) {
    const geomErrors = validateCalibrationGeometry(label.calibration_gt.points, w, h);
    for (const err of geomErrors) {
      issues.push({
        path: 'calibration_gt',
        message: err,
        severity: 'error',
      });
    }

    if (label.calibration_gt.residual_px != null) {
      const res = label.calibration_gt.residual_px;
      const hasBadCalibFlag = label.flags?.includes('bad_calibration');
      if (res > CALIB_ERROR_PX) {
        if (hasBadCalibFlag) {
          issues.push({
            path: 'calibration_gt.residual_px',
            message: `Calibration residual (${res.toFixed(2)} px) exceeds error limit (${CALIB_ERROR_PX} px), flagged as bad_calibration`,
            severity: 'warning',
          });
        } else {
          issues.push({
            path: 'calibration_gt.residual_px',
            message: `Calibration residual (${res.toFixed(2)} px) exceeds maximum error limit (${CALIB_ERROR_PX} px)`,
            severity: 'error',
          });
        }
      } else if (res > CALIB_WARN_PX) {
        issues.push({
          path: 'calibration_gt.residual_px',
          message: `Calibration residual (${res.toFixed(2)} px) exceeds warning threshold (${CALIB_WARN_PX} px)`,
          severity: 'warning',
        });
      }
    }
  }

  // 8. Non-blocking warnings
  // Warning: release frame later than frame 20
  if (label.release && label.release.frame > 20) {
    issues.push({
      path: 'release.frame',
      message: `Release frame (${label.release.frame}) is unusually late (> frame 20)`,
      severity: 'warning',
    });
  }

  // Warning: bounce within 3 frames of release
  if (label.release && label.bounce) {
    const diff = label.bounce.frame - label.release.frame;
    if (diff >= 0 && diff <= 3) {
      issues.push({
        path: 'bounce.frame',
        message: `Bounce frame (${label.bounce.frame}) is within 3 frames of release (${label.release.frame})`,
        severity: 'warning',
      });
    }
  }

  // Warning: last_visible_frame < bounce frame
  if (label.bounce && label.last_visible_frame != null) {
    if (label.last_visible_frame < label.bounce.frame) {
      issues.push({
        path: 'last_visible_frame',
        message: `Last visible frame (${label.last_visible_frame}) is before bounce frame (${label.bounce.frame})`,
        severity: 'warning',
      });
    }
  }

  return issues;
}
