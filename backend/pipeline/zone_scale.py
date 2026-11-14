"""Pitch zone scale mode switching ('legacy' vs 'laws').

Mutates the legacy `zones` module's `WORLD_COORDS` dict and `ZONES` list
in-place so callers that imported `ZONES` or `build_homography` by reference
(such as `zones_classify.py`) see the active scale immediately without
re-binding module attributes.
"""
from __future__ import annotations

import cv2
import numpy as np
import zones as _zones_mod  # noqa: E402

# Capture original legacy values once at first import so `apply("legacy")`
# restores them bit-for-bit.
_ORIG_HALF_WIDTH: float = float(_zones_mod.HALF_WIDTH)
_ORIG_BAT_CREASE_Y: float = float(_zones_mod.BAT_CREASE_Y)
_ORIG_BOWL_CREASE_Y: float = float(_zones_mod.BOWL_CREASE_Y)
_ORIG_BOWL_STUMP_Y: float = float(_zones_mod.BOWL_STUMP_Y)
_ORIG_WORLD_COORDS: dict[str, tuple[float, float]] = {
    k: (float(v[0]), float(v[1])) for k, v in _zones_mod.WORLD_COORDS.items()
}
_ORIG_ZONES: list[tuple[float, float, tuple[int, int, int], str]] = [
    (float(y0), float(y1), tuple(color), str(name))
    for (y0, y1, color, name) in _zones_mod.ZONES
]

# Laws of Cricket dimensions (metres from striker's middle-stump line):
#   stump-to-stump = 20.12 m (22 yd)
#   popping crease = 1.22 m (4 ft) in front of each stump line
#   popping-to-popping = 17.68 m -> bowler popping crease at y = 18.90 m
LAWS_HALF_WIDTH: float = 1.32
LAWS_BAT_CREASE_Y: float = 1.22
LAWS_BOWL_CREASE_Y: float = 18.90
LAWS_BOWL_STUMP_Y: float = 20.12

_CORNER_KEYS = ("bat_L", "bat_R", "bowl_L", "bowl_R")


def normalize_mode(mode: str | None) -> str:
    """Normalize a zone scale mode string ('laws' or 'legacy')."""
    if mode is not None and mode.strip().lower() == "laws":
        return "laws"
    return "legacy"


def apply(mode: str) -> str:
    """Apply `'legacy'` or `'laws'` pitch scale in-place on the `zones` module.

    Modifies `_zones_mod.WORLD_COORDS` and `_zones_mod.ZONES` in-place so the
    `dict` and `list` object identities never change.
    """
    norm = normalize_mode(mode)
    if norm == "laws":
        _zones_mod.HALF_WIDTH = LAWS_HALF_WIDTH
        _zones_mod.BAT_CREASE_Y = LAWS_BAT_CREASE_Y
        _zones_mod.BOWL_CREASE_Y = LAWS_BOWL_CREASE_Y
        _zones_mod.BOWL_STUMP_Y = LAWS_BOWL_STUMP_Y
        _zones_mod.WORLD_COORDS.update(
            {
                "bat_stump": (0.0, 0.0),
                "bat_L": (-LAWS_HALF_WIDTH, LAWS_BAT_CREASE_Y),
                "bat_R": (+LAWS_HALF_WIDTH, LAWS_BAT_CREASE_Y),
                "bowl_L": (-LAWS_HALF_WIDTH, LAWS_BOWL_CREASE_Y),
                "bowl_R": (+LAWS_HALF_WIDTH, LAWS_BOWL_CREASE_Y),
                "bowl_stump": (0.0, LAWS_BOWL_STUMP_Y),
            }
        )
        _zones_mod.ZONES[:] = [
            (y0, LAWS_BOWL_CREASE_Y if name == "SHORT" else y1, color, name)
            for (y0, y1, color, name) in _ORIG_ZONES
        ]
    else:
        _zones_mod.HALF_WIDTH = _ORIG_HALF_WIDTH
        _zones_mod.BAT_CREASE_Y = _ORIG_BAT_CREASE_Y
        _zones_mod.BOWL_CREASE_Y = _ORIG_BOWL_CREASE_Y
        _zones_mod.BOWL_STUMP_Y = _ORIG_BOWL_STUMP_Y
        _zones_mod.WORLD_COORDS.clear()
        _zones_mod.WORLD_COORDS.update(_ORIG_WORLD_COORDS)
        _zones_mod.ZONES[:] = list(_ORIG_ZONES)
    return norm


def markers_for_zones(markers: dict, mode: str) -> dict:
    """Return markers for `zones.build_homography`.

    In `'legacy'` mode, returns `markers` unchanged.
    In `'laws'` mode, returns a copy with `bat_stump` and `bowl_stump` derived
    from the four crease corners via the exact 4-point homography so that the
    6-point least-squares fit in `build_homography` equals the exact 4-corner
    homography.
    """
    if normalize_mode(mode) != "laws":
        return markers
    if not markers or not all(k in markers for k in _CORNER_KEYS):
        return dict(markers) if markers is not None else {}

    src_corners = np.array(
        [
            [-LAWS_HALF_WIDTH, LAWS_BAT_CREASE_Y],
            [+LAWS_HALF_WIDTH, LAWS_BAT_CREASE_Y],
            [-LAWS_HALF_WIDTH, LAWS_BOWL_CREASE_Y],
            [+LAWS_HALF_WIDTH, LAWS_BOWL_CREASE_Y],
        ],
        dtype=np.float32,
    )
    dst_corners = np.array(
        [[float(markers[k][0]), float(markers[k][1])] for k in _CORNER_KEYS],
        dtype=np.float32,
    )
    H_4pt, _ = cv2.findHomography(src_corners, dst_corners, method=0)
    if H_4pt is None:
        return dict(markers)

    stumps_world = np.array(
        [[[0.0, 0.0]], [[0.0, LAWS_BOWL_STUMP_Y]]], dtype=np.float32
    )
    stumps_px = cv2.perspectiveTransform(stumps_world, H_4pt).reshape(2, 2)

    out = dict(markers)
    out["bat_stump"] = (float(stumps_px[0, 0]), float(stumps_px[0, 1]))
    out["bowl_stump"] = (float(stumps_px[1, 0]), float(stumps_px[1, 1]))
    return out
