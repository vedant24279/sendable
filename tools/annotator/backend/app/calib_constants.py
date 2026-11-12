"""
Constants and world coordinate definitions for cricket pitch calibration.

Source of regulation dimensions:
    backend/pipeline/reconstruct3d/world_points.py
    (Derived from official Laws of Cricket: Law 6 - 22 yards between stump lines,
     popping creases 1.22 m in front of each stump line, return crease half-width 1.32 m).

Coordinate Frame:
    Origin: Middle stump base at STRIKER'S (batter's) end: (0.0, 0.0)
    pitch_x_m: Perpendicular across pitch, positive toward IMAGE-RIGHT
               (left return crease at -1.32 m, right return crease at +1.32 m).
    pitch_z_m: Along pitch length, positive toward the bowler (0.0 at striker's stump line).

Calibration Points:
    - bat_stump:  ( 0.00,  0.00)
    - bat_L:      (-1.32,  1.22)
    - bat_R:      (+1.32,  1.22)
    - bowl_L:     (-1.32, 18.90)  [20.12 - 1.22 = 18.90 m]
    - bowl_R:     (+1.32, 18.90)  [20.12 - 1.22 = 18.90 m]
    - bowl_stump: ( 0.00, 20.12)
"""

from __future__ import annotations
from typing import Dict, Tuple

# Regulation pitch dimensions in metres
PITCH_LENGTH_M: float = 20.12        # 22 yards between stump lines
POPPING_IN_FRONT_M: float = 1.22     # 4 ft in front of each stump line
RETURN_HALF_WIDTH_M: float = 1.32    # 4 ft 4 in half-width from center stump

# Bowler-end crease distance from striker's stump line (derived: 20.12 - 1.22 = 18.90 m)
BOWL_CREASE_Z_M: float = PITCH_LENGTH_M - POPPING_IN_FRONT_M

# World coordinates (pitch_x_m, pitch_z_m) for the 6 calibration points in metres
WORLD_CALIB_POINTS: Dict[str, Tuple[float, float]] = {
    "bat_stump":  (0.0, 0.0),
    "bat_L":      (-RETURN_HALF_WIDTH_M, POPPING_IN_FRONT_M),
    "bat_R":      (+RETURN_HALF_WIDTH_M, POPPING_IN_FRONT_M),
    "bowl_L":     (-RETURN_HALF_WIDTH_M, BOWL_CREASE_Z_M),
    "bowl_R":     (+RETURN_HALF_WIDTH_M, BOWL_CREASE_Z_M),
    "bowl_stump": (0.0, PITCH_LENGTH_M),
}

# The four corner points used for exact 4-point homography fitting
CORNER_NAMES: Tuple[str, str, str, str] = ("bat_L", "bat_R", "bowl_R", "bowl_L")

# All six required calibration point names
CALIB_POINT_NAMES: Tuple[str, ...] = (
    "bat_L",
    "bat_R",
    "bowl_L",
    "bowl_R",
    "bat_stump",
    "bowl_stump",
)

# Thresholds for stump residual error in pixels.
# NOTE: Because stump points are extrapolated 1.22 m beyond the creases,
# perspective and calibration errors are amplified at them; keep CALIB_WARN_PX = 4
# and CALIB_ERROR_PX = 12 as PROVISIONAL.
CALIB_WARN_PX: float = 4.0
CALIB_ERROR_PX: float = 12.0
