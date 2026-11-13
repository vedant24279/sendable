"""
Extract reference decision and ball colour hints from video display names.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

_SEP_RE = re.compile(r"[_\-.\s]+")
_EXT_RE = re.compile(r"\.[a-zA-Z0-9]{1,5}$")
_BALL_COLOURS = {"white", "red", "pink"}


def _extract_stem(display_name: str) -> str:
    base = Path(display_name.strip()).name
    if not base:
        return ""
    if _EXT_RE.search(Path(base).suffix):
        return Path(base).stem
    return base


def parse_filename_meta(display_name: str) -> Dict[str, Optional[str]]:
    """
    Parse the stem of display_name (case-insensitive), treating '_', '-', '.',
    and space as identical word separators.

    Rules:
    - "not out" / "notout" / "not_out" -> reference_decision = "not_out" (checked first)
    - Otherwise whole word "out" -> reference_decision = "out"
    - If both "not out" (or "notout") and a separate "out" word appear -> null
    - Otherwise -> null
    - Ball colour hint: whole word "white" | "red" | "pink" (unique), else null
    - source_group defaults to null
    """
    stem = _extract_stem(display_name).lower()
    tokens = [t for t in _SEP_RE.split(stem) if t]

    has_not_out = False
    has_separate_out = False

    i = 0
    n = len(tokens)
    while i < n:
        if tokens[i] == "notout":
            has_not_out = True
            i += 1
        elif i + 1 < n and tokens[i] == "not" and tokens[i + 1] == "out":
            has_not_out = True
            i += 2
        elif tokens[i] == "out":
            has_separate_out = True
            i += 1
        else:
            i += 1

    reference_decision: Optional[str]
    if has_not_out and has_separate_out:
        reference_decision = None
    elif has_not_out:
        reference_decision = "not_out"
    elif has_separate_out:
        reference_decision = "out"
    else:
        reference_decision = None

    found_colours = {t for t in tokens if t in _BALL_COLOURS}
    ball_colour_hint: Optional[str] = next(iter(found_colours)) if len(found_colours) == 1 else None

    return {
        "reference_decision": reference_decision,
        "ball_colour_hint": ball_colour_hint,
        "source_group": None,
    }
