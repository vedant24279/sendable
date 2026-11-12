"""
Cricket pitch calibration geometry and homography estimation.

Implements exact 4-point homography estimation (image -> world in metres),
inverse homography (world -> image), stump residual calculation,
and pitch grid segment generation.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from app.calib_constants import (
    CALIB_POINT_NAMES,
    CORNER_NAMES,
    WORLD_CALIB_POINTS,
    PITCH_LENGTH_M,
    POPPING_IN_FRONT_M,
    BOWL_CREASE_Z_M,
    RETURN_HALF_WIDTH_M,
)


@dataclass
class FitResult:
    H: np.ndarray                 # 3x3 float64 homography mapping image (px) -> world (m)
    residual_px: Optional[float]  # RMS pixel distance for confirmed stumps; None if no stump confirmed
    H_inv: np.ndarray             # 3x3 float64 homography mapping world (m) -> image (px)

    def __getitem__(self, item: Union[int, str]) -> Any:
        if item == 0 or item == "H":
            return self.H
        if item == 1 or item == "residual_px":
            return self.residual_px
        if item == 2 or item == "H_inv":
            return self.H_inv
        raise KeyError(item)


def invert_homography(H: np.ndarray) -> np.ndarray:
    """
    Analytic 3x3 matrix inverse using adjugate matrix and determinant.
    Normalized such that H_inv[2, 2] == 1.0.
    """
    a, b, c = float(H[0, 0]), float(H[0, 1]), float(H[0, 2])
    d, e, f = float(H[1, 0]), float(H[1, 1]), float(H[1, 2])
    g, h, i = float(H[2, 0]), float(H[2, 1]), float(H[2, 2])

    A = e * i - f * h
    B = f * g - d * i
    C = d * h - e * g

    det = a * A + b * B + c * C
    if abs(det) < 1e-14:
        raise ValueError("Degenerate homography matrix (determinant close to zero)")

    inv = np.array([
        [A, c * h - b * i, b * f - c * e],
        [B, a * i - c * g, c * d - a * f],
        [C, b * g - a * h, a * e - b * d],
    ], dtype=np.float64) / det

    if abs(inv[2, 2]) > 1e-14:
        inv = inv / inv[2, 2]
    return inv


def fit_homography(
    points: Dict[str, Sequence[float]],
    stump_confirmed: Optional[Dict[str, bool]] = None,
) -> FitResult:
    """
    Fit an exact 4-point homography mapping image pixels (x, y) to ground world coordinates (X, Z).
    Computes residual_px as the RMS reprojection error over confirmed stumps only;
    returns None if no stump is confirmed. If stump_confirmed is None, computes over both stumps.
    """
    missing = [k for k in CALIB_POINT_NAMES if k not in points]
    if missing:
        raise ValueError(f"Missing required calibration points: {missing}")

    # Corner point correspondences: bat_L, bat_R, bowl_L, bowl_R
    corners = ("bat_L", "bat_R", "bowl_L", "bowl_R")
    A = np.zeros((8, 8), dtype=np.float64)
    b = np.zeros(8, dtype=np.float64)

    for idx, name in enumerate(corners):
        px, py = float(points[name][0]), float(points[name][1])
        wX, wZ = WORLD_CALIB_POINTS[name]
        r1 = 2 * idx
        r2 = r1 + 1

        A[r1, 0] = px
        A[r1, 1] = py
        A[r1, 2] = 1.0
        A[r1, 6] = -wX * px
        A[r1, 7] = -wX * py
        b[r1] = wX

        A[r2, 3] = px
        A[r2, 4] = py
        A[r2, 5] = 1.0
        A[r2, 6] = -wZ * px
        A[r2, 7] = -wZ * py
        b[r2] = wZ

    # Solve 8x8 linear system for H elements [h00, h01, h02, h10, h11, h12, h20, h21]
    try:
        sol = np.linalg.solve(A, b)
    except np.linalg.LinAlgError as e:
        raise ValueError(f"Could not solve homography: degenerate point configuration ({e})")

    H = np.array([
        [sol[0], sol[1], sol[2]],
        [sol[3], sol[4], sol[5]],
        [sol[6], sol[7], 1.0],
    ], dtype=np.float64)

    H_inv = invert_homography(H)

    # Project world stump positions to image space
    bat_stump_world = WORLD_CALIB_POINTS["bat_stump"]    # (0.0, 0.0)
    bowl_stump_world = WORLD_CALIB_POINTS["bowl_stump"]  # (0.0, 20.12)

    pred_bat_x, pred_bat_y = world_to_pixel(H, bat_stump_world[0], bat_stump_world[1], H_inv=H_inv)
    pred_bowl_x, pred_bowl_y = world_to_pixel(H, bowl_stump_world[0], bowl_stump_world[1], H_inv=H_inv)

    clicked_bat = points["bat_stump"]
    clicked_bowl = points["bowl_stump"]

    d_bat_sq = (float(clicked_bat[0]) - pred_bat_x) ** 2 + (float(clicked_bat[1]) - pred_bat_y) ** 2
    d_bowl_sq = (float(clicked_bowl[0]) - pred_bowl_x) ** 2 + (float(clicked_bowl[1]) - pred_bowl_y) ** 2

    residual_px: Optional[float]
    if stump_confirmed is None:
        residual_px = math.sqrt((d_bat_sq + d_bowl_sq) / 2.0)
    else:
        conf_bat = bool(stump_confirmed.get("bat_stump", False))
        conf_bowl = bool(stump_confirmed.get("bowl_stump", False))
        if conf_bat and conf_bowl:
            residual_px = math.sqrt((d_bat_sq + d_bowl_sq) / 2.0)
        elif conf_bat:
            residual_px = math.sqrt(d_bat_sq)
        elif conf_bowl:
            residual_px = math.sqrt(d_bowl_sq)
        else:
            residual_px = None

    return FitResult(H=H, residual_px=residual_px, H_inv=H_inv)


def pixel_to_world(H: np.ndarray, x: float, y: float) -> Tuple[float, float]:
    """Map image pixel (x, y) to world plane coordinates (pitch_x_m, pitch_z_m)."""
    px, py = float(x), float(y)
    w = H[2, 0] * px + H[2, 1] * py + H[2, 2]
    if abs(w) < 1e-12:
        raise ValueError("Point maps to infinity under homography")
    X = (H[0, 0] * px + H[0, 1] * py + H[0, 2]) / w
    Z = (H[1, 0] * px + H[1, 1] * py + H[1, 2]) / w
    return float(X), float(Z)


def world_to_pixel(
    H: np.ndarray,
    X: float,
    Z: float,
    H_inv: Optional[np.ndarray] = None,
) -> Tuple[float, float]:
    """Map world coordinates (pitch_x_m, pitch_z_m) to image pixel coordinates (x, y)."""
    if H_inv is None:
        H_inv = invert_homography(H)
    wX, wZ = float(X), float(Z)
    w = H_inv[2, 0] * wX + H_inv[2, 1] * wZ + H_inv[2, 2]
    if abs(w) < 1e-12:
        raise ValueError("World point maps to infinity in image space")
    x = (H_inv[0, 0] * wX + H_inv[0, 1] * wZ + H_inv[0, 2]) / w
    y = (H_inv[1, 0] * wX + H_inv[1, 1] * wZ + H_inv[1, 2]) / w
    return float(x), float(y)


def compute_stump_world_errors(
    points: Dict[str, Sequence[float]],
    H: Optional[np.ndarray] = None,
) -> Dict[str, float]:
    """
    Map the CLICKED bat_stump and bowl_stump pixels to pitch metres with pixel_to_world
    and compute signed errors against the expected world points:
      bat_stump (0.0, 0.0)    -> dx_bat = x - 0, dz_bat = z - 0
      bowl_stump (0.0, 20.12) -> dx_bowl = x - 0, dz_bowl = z - 20.12
    """
    if H is None:
        fit_res = fit_homography(points)
        H = fit_res.H

    clicked_bat = points["bat_stump"]
    clicked_bowl = points["bowl_stump"]

    x_bat, z_bat = pixel_to_world(H, float(clicked_bat[0]), float(clicked_bat[1]))
    x_bowl, z_bowl = pixel_to_world(H, float(clicked_bowl[0]), float(clicked_bowl[1]))

    return {
        "dx_bat": x_bat - 0.0,
        "dz_bat": z_bat - 0.0,
        "dx_bowl": x_bowl - 0.0,
        "dz_bowl": z_bowl - 20.12,
    }


def pitch_grid_segments(
    H: np.ndarray,
    spacing_m: float = 1.0,
) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """
    Generate image-pixel line segments for the full pitch rectangle and grid lines every spacing_m.
    Segments are returned as pairs of ((x1, y1), (x2, y2)) in pixel coordinates.
    """
    H_inv = invert_homography(H)
    segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []

    hw = RETURN_HALF_WIDTH_M  # 1.32 m
    len_m = PITCH_LENGTH_M    # 20.12 m

    def add_seg(wX1: float, wZ1: float, wX2: float, wZ2: float) -> None:
        p1 = world_to_pixel(H, wX1, wZ1, H_inv=H_inv)
        p2 = world_to_pixel(H, wX2, wZ2, H_inv=H_inv)
        segments.append((p1, p2))

    # 1. Pitch perimeter rectangle (from striker stump line Z=0 to bowler stump line Z=20.12)
    add_seg(-hw, 0.0, +hw, 0.0)        # Striker stump line
    add_seg(+hw, 0.0, +hw, len_m)      # Right return crease / pitch boundary
    add_seg(+hw, len_m, -hw, len_m)    # Bowler stump line
    add_seg(-hw, len_m, -hw, 0.0)      # Left return crease / pitch boundary

    # 2. Popping crease lines
    add_seg(-hw, POPPING_IN_FRONT_M, +hw, POPPING_IN_FRONT_M)  # Striker popping crease (1.22 m)
    add_seg(-hw, BOWL_CREASE_Z_M, +hw, BOWL_CREASE_Z_M)        # Bowler popping crease (18.90 m)

    # 3. Transverse grid lines across pitch every spacing_m
    z = spacing_m
    while z < len_m:
        # avoid duplicating popping creases if spacing matches closely
        if abs(z - POPPING_IN_FRONT_M) > 0.1 and abs(z - BOWL_CREASE_Z_M) > 0.1:
            add_seg(-hw, z, +hw, z)
        z += spacing_m

    # 4. Centerline along pitch
    add_seg(0.0, 0.0, 0.0, len_m)

    return segments


def _normalize_system_points(system_points: Any) -> Optional[Dict[str, Tuple[float, float]]]:
    if not system_points:
        return None
    res: Dict[str, Tuple[float, float]] = {}
    if isinstance(system_points, list):
        for item in system_points:
            if isinstance(item, dict) and "name" in item:
                res[item["name"]] = (float(item.get("x", 0.0)), float(item.get("y", 0.0)))
    elif isinstance(system_points, dict):
        for k, v in system_points.items():
            if isinstance(v, (list, tuple)) and len(v) >= 2:
                res[k] = (float(v[0]), float(v[1]))
            elif isinstance(v, dict) and "x" in v and "y" in v:
                res[k] = (float(v["x"]), float(v["y"]))
    return res if all(c in res for c in ("bat_L", "bat_R", "bowl_L", "bowl_R")) else None


def classify_source(
    points: Dict[str, Sequence[float]],
    system_points: Optional[Any],
) -> str:
    """
    Classify calibration source by comparing ONLY the four corner points
    ('bat_L', 'bat_R', 'bowl_L', 'bowl_R') against system corners:
    - 'manual': when there is no system calibration available
    - 'system_verified': when all 4 corners are within 0.05 px of system corners
    - 'system_adjusted': when system corners exist but one or more corners differ (> 0.05 px)
    """
    sys_pts = _normalize_system_points(system_points)
    if not sys_pts:
        return "manual"

    corners = ("bat_L", "bat_R", "bowl_L", "bowl_R")
    for name in corners:
        if name not in points or name not in sys_pts:
            return "system_adjusted"
        px, py = float(points[name][0]), float(points[name][1])
        sx, sy = sys_pts[name]
        dist = math.sqrt((px - sx) ** 2 + (py - sy) ** 2)
        if dist > 0.05:
            return "system_adjusted"

    return "system_verified"


def validate_calibration_geometry(
    points: Dict[str, Sequence[float]],
    width: Optional[float] = None,
    height: Optional[float] = None,
) -> List[str]:
    """
    Validate calibration points geometry.
    Returns a list of error message strings (empty if valid).
    """
    errors: List[str] = []

    # 1. All six points present
    missing = [k for k in CALIB_POINT_NAMES if k not in points]
    if missing:
        errors.append(f"Missing required calibration points: {missing}")
        return errors

    # 2. Coordinate bounds checks
    for name in CALIB_POINT_NAMES:
        pt = points[name]
        if len(pt) < 2:
            errors.append(f"Point {name} must have [x, y] coordinates")
            continue
        px, py = float(pt[0]), float(pt[1])
        if width is not None and not (0.0 <= px <= float(width)):
            errors.append(f"{name}.x ({px}) out of bounds [0, {width}]")
        if height is not None and not (0.0 <= py <= float(height)):
            errors.append(f"{name}.y ({py}) out of bounds [0, {height}]")

    if errors:
        return errors

    bat_L_x, bat_R_x = float(points["bat_L"][0]), float(points["bat_R"][0])
    bowl_L_x, bowl_R_x = float(points["bowl_L"][0]), float(points["bowl_R"][0])
    bat_stump_x = float(points["bat_stump"][0])
    bowl_stump_x = float(points["bowl_stump"][0])

    # 3. Horizontal ordering: bat_L.x < bat_R.x and bowl_L.x < bowl_R.x
    if bat_L_x >= bat_R_x:
        errors.append(f"bat_L.x ({bat_L_x}) must be strictly less than bat_R.x ({bat_R_x})")
    if bowl_L_x >= bowl_R_x:
        errors.append(f"bowl_L.x ({bowl_L_x}) must be strictly less than bowl_R.x ({bowl_R_x})")

    # 4. Stump horizontal position between left and right points
    if not (bat_L_x <= bat_stump_x <= bat_R_x):
        errors.append(
            f"bat_stump.x ({bat_stump_x}) must be between bat_L.x ({bat_L_x}) and bat_R.x ({bat_R_x})"
        )
    if not (bowl_L_x <= bowl_stump_x <= bowl_R_x):
        errors.append(
            f"bowl_stump.x ({bowl_stump_x}) must be between bowl_L.x ({bowl_L_x}) and bowl_R.x ({bowl_R_x})"
        )

    # 5. Convex non-degenerate quadrilateral and area > 2% of frame area
    corner_pts = [
        (float(points[name][0]), float(points[name][1]))
        for name in CORNER_NAMES  # bat_L, bat_R, bowl_R, bowl_L
    ]

    # Shoelace formula for area
    shoelace = 0.0
    for i in range(4):
        x1, y1 = corner_pts[i]
        x2, y2 = corner_pts[(i + 1) % 4]
        shoelace += (x1 * y2 - x2 * y1)
    quad_area = 0.5 * abs(shoelace)

    if width is not None and height is not None:
        min_area = 0.02 * float(width) * float(height)
        if quad_area <= min_area:
            errors.append(
                f"Calibration quadrilateral area ({quad_area:.1f} px^2) must be > 2% of frame area ({min_area:.1f} px^2)"
            )

    # Convexity: edge cross products must have strictly same sign
    crosses = []
    for i in range(4):
        p0 = corner_pts[i]
        p1 = corner_pts[(i + 1) % 4]
        p2 = corner_pts[(i + 2) % 4]
        v1 = (p1[0] - p0[0], p1[1] - p0[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        cp = v1[0] * v2[1] - v1[1] * v2[0]
        crosses.append(cp)

    is_convex = (all(c > 1e-4 for c in crosses) or all(c < -1e-4 for c in crosses))
    if not is_convex:
        errors.append("Calibration corner points (bat_L, bat_R, bowl_R, bowl_L) must form a strictly convex quadrilateral")

    return errors
