"""
Scan and display filename_meta parsing results for library entries or a text file of filenames.

Usage:
    python scan_names.py
    python scan_names.py --names names.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple

_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.library import load_library_catalog  # noqa: E402
from filename_meta import parse_filename_meta  # noqa: E402


def scan_names(names: List[str]) -> Tuple[List[Tuple[str, Optional[str], Optional[str]]], List[str]]:
    rows: List[Tuple[str, Optional[str], Optional[str]]] = []
    unparsed: List[str] = []

    for name in names:
        parsed = parse_filename_meta(name)
        decision = parsed["reference_decision"]
        colour = parsed["ball_colour_hint"]
        rows.append((name, decision, colour))
        if decision is None:
            unparsed.append(name)

    return rows, unparsed


def format_report(names: List[str]) -> str:
    if not names:
        return "No filenames found to scan."

    rows, unparsed = scan_names(names)
    name_width = max(len("Filename"), *(len(r[0]) for r in rows))
    dec_width = max(len("Decision"), 8)
    col_width = max(len("Ball Colour"), 11)

    lines: List[str] = []
    header = f"{'Filename':<{name_width}}  {'Decision':<{dec_width}}  {'Ball Colour':<{col_width}}"
    lines.append(header)
    lines.append("-" * len(header))

    for name, decision, colour in rows:
        dec_str = decision if decision is not None else "-"
        col_str = colour if colour is not None else "-"
        lines.append(f"{name:<{name_width}}  {dec_str:<{dec_width}}  {col_str:<{col_width}}")

    lines.append("")
    lines.append(f"Total scanned: {len(rows)} | Unparsed decision: {len(unparsed)}")
    if unparsed:
        lines.append("Could not parse decision:")
        for u in unparsed:
            lines.append(f"  - {u}")

    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Parse reference decision and ball colour hints from video filenames."
    )
    parser.add_argument(
        "--names",
        type=Path,
        default=None,
        help="Path to a text file with one filename per line (defaults to scanning the library).",
    )
    args = parser.parse_args(argv)

    names: List[str] = []
    if args.names is not None:
        if not args.names.is_file():
            print(f"Error: file not found: {args.names}", file=sys.stderr)
            return 1
        with open(args.names, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    names.append(stripped)
    else:
        catalog = load_library_catalog()
        for clip_id, entry in catalog.items():
            names.append(str(entry.get("display_name") or clip_id))

    print(format_report(names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
