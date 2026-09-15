#!/usr/bin/env python3
"""Run diagram-design's checks on figures drawn under a saved profile.

Usage: check-figure.py figure.html... [--profile NAME]

Runs the plugin's self_check.py; verify-geometry.py with label masks up to 20px tall, because the
presentation type ramp draws 16px masks that the plugin's 14px limit would skip; verify-motion.py for
step-mode figures; and lint-skin.py, with each color finding judged against the profile instead of
the shipped palette. It also fails when a shipped color that the profile changes is still in the file.
Exit 1 on any finding.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from palette import COLOR, applied_profile, color_maps, plugin_root, profile_colors, profile_name, recolor, rgb  # noqa: E402

PRESENTATION_MASK_MAX_H = 20.0
# Every "path:line: ..." line is a finding; none may be dropped for failing to parse its category.
LINT_LINE = re.compile(r"^(?P<where>.+?:\d+): (?P<rest>.+)$")


def run(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr).strip()


def geometry(plugin: Path, figure: Path) -> tuple[list[str], int]:
    spec = importlib.util.spec_from_file_location("verify_geometry", plugin / "scripts/verify-geometry.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("MASK_MIN_W", "MASK_MAX_W", "MASK_MIN_H", "MASK_MAX_H", "parse_rects", "check"):
        if not hasattr(module, name):
            raise SystemExit(f"check-figure: verify-geometry.py no longer defines {name}; update check-figure.py")
    module.MASK_MAX_H = PRESENTATION_MASK_MAX_H
    rects = module.parse_rects(figure.read_text(encoding="utf-8"))
    masks = sum(1 for r in rects if module.MASK_MIN_W <= r.w <= module.MASK_MAX_W and module.MASK_MIN_H <= r.h <= module.MASK_MAX_H)
    return list(module.check(figure)), masks


def skin(plugin: Path, figure: Path, hexes: set, triples: set) -> tuple[list[str], int]:
    code, output = run([sys.executable, str(plugin / "scripts/lint-skin.py"), str(figure)])
    parsed = [LINT_LINE.match(line) for line in output.splitlines()]
    parsed = [m for m in parsed if m]
    if code != 0 and not parsed:
        return [f"lint-skin.py failed without findings: {output[-300:]}"], 0
    findings, accepted = [], 0
    for match in parsed:
        if match["rest"].startswith("color: "):
            value = COLOR.search(match["rest"])
            if value and (value.group(0).lower() in hexes or rgb(value.group(0).replace(" ", "")) in triples):
                accepted += 1
                continue
        findings.append(match.group(0))
    return findings, accepted


def check(plugin: Path, figure: Path, explicit_profile: str | None) -> list[str]:
    findings: list[str] = []
    name = profile_name(figure, explicit_profile)
    code, output = run([sys.executable, str(plugin / "skills/diagram-design/scripts/self_check.py"), str(figure)])
    if code != 0:
        findings.append(f"self_check: {output}")
    geometry_findings, masks = geometry(plugin, figure)
    findings.extend(f"geometry: {line}" for line in geometry_findings)
    text = figure.read_text(encoding="utf-8")
    motion = "not a step-mode figure"
    if "data-motion-root" in text:
        code, output = run([sys.executable, str(plugin / "scripts/verify-motion.py"), str(figure)])
        motion = "ok" if code == 0 else "failed"
        if code != 0:
            findings.append(f"motion: {output}")
    hexes, triples = profile_colors(name)
    skin_findings, accepted = skin(plugin, figure, hexes, triples)
    findings.extend(f"skin: {line}" for line in skin_findings)
    maps = color_maps(name)
    previous = applied_profile(text)
    if previous and previous != name:
        findings.append(f"palette: the file was recolored for profile {previous}, not {name}")
    _, leftover = recolor(text, maps, skip=maps[3])
    if leftover:
        findings.append(f"palette: shipped colors still present ({', '.join(sorted(leftover))}); run apply-profile.py")
    print(f"{figure}: profile {name}; {masks} label mask(s) checked; motion {motion}; "
          f"{accepted} profile color(s) accepted; {len(findings)} finding(s)")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("figures", nargs="+", type=Path)
    parser.add_argument("--profile", help="profile slug in ~/.diagram-design/profiles")
    args = parser.parse_args()
    plugin = plugin_root()
    failed = False
    for figure in args.figures:
        if not figure.is_file():
            print(f"check-figure: not found: {figure}", file=sys.stderr)
            return 2
        for finding in check(plugin, figure, args.profile):
            print(f"  {finding}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
