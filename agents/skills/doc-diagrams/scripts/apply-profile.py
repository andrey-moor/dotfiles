#!/usr/bin/env python3
"""Recolor diagram-design figures from the shipped palette to a saved profile.

Usage: apply-profile.py figure.html... [--profile NAME]

Every shipped semantic-role color the profile changes is replaced: hex values, and rgb()/rgba()
values whose RGB matches a shipped role at any alpha. Run it after drawing. The first run marks the file
with an apply-profile comment. When the profile reuses a shipped color, later runs leave that color alone,
because they cannot tell new shipped uses from the profile's own values. NAME defaults to the profile in the nearest .diagram-design marker above each figure.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from palette import applied_profile, color_maps, profile_name, recolor, with_marker  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("figures", nargs="+", type=Path)
    parser.add_argument("--profile", help="profile slug in ~/.diagram-design/profiles")
    args = parser.parse_args()
    for figure in args.figures:
        if not figure.is_file():
            print(f"apply-profile: not found: {figure}", file=sys.stderr)
            return 2
        name = profile_name(figure, args.profile)
        maps = color_maps(name)
        text = figure.read_text(encoding="utf-8")
        previous = applied_profile(text)
        if previous and previous != name:
            print(f"apply-profile: {figure} was recolored for profile {previous}; start again from the plugin template to use {name}", file=sys.stderr)
            return 1
        skip = maps[3] if previous == name else frozenset()
        recolored, counts = recolor(text, maps, skip)
        if name != "default":
            recolored = with_marker(recolored, name)
        if recolored != text:
            figure.write_text(recolored, encoding="utf-8")
        detail = ", ".join(f"{color} x{n}" for color, n in sorted(counts.items())) or "nothing to change"
        print(f"{figure}: profile {name}: {detail}")
        if skip:
            print(f"  note: the profile reuses shipped color(s) {', '.join(sorted(c if isinstance(c, str) else 'rgb(%d,%d,%d)' % c for c in skip))}; set new uses of them by hand")
    return 0


if __name__ == "__main__":
    sys.exit(main())
