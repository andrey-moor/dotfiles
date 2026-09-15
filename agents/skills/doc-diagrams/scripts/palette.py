"""Palette helpers shared by apply-profile.py and check-figure.py.

A profile is a copy of diagram-design's style guide with different values in the light column of
its "### Semantic roles" table. Colors are mapped role by role from the shipped guide to the profile.
"""
from __future__ import annotations

import re
from pathlib import Path

HOME = Path.home()
CLAUDE_CACHE = HOME / ".claude/plugins/cache/diagram-design/diagram-design"
COPILOT_PLUGIN = HOME / ".copilot/installed-plugins/_direct/cathrynlavery--diagram-design"
PROFILES = HOME / ".diagram-design/profiles"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
ROLE_ROW = re.compile(r"^\|\s*`([A-Za-z0-9-]+)`\s*\|[^|]*\|\s*`([^`]+)`")
# One pattern for both syntaxes, so a single pass never recolors its own output.
COLOR = re.compile(
    r"(?P<hex>#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F]))"
    r"|(?P<rgb>rgba?\(\s*(?P<r>\d+)\s*,\s*(?P<g>\d+)\s*,\s*(?P<b>\d+)\s*(?P<a>,\s*[\d.]+\s*)?\))"
)
MARKER = re.compile(r"<!--\s*apply-profile:\s*([a-z0-9-]+)\s*-->")


def plugin_root() -> Path:
    """Newest cached Claude Code install, else the Copilot CLI install."""
    def version_key(path: Path) -> list:
        return [(0, int(part)) if part.isdigit() else (1, part) for part in re.split(r"[.-]", path.name)]

    cached = sorted((p for p in CLAUDE_CACHE.glob("*") if p.is_dir()), key=version_key)
    for candidate in cached[-1:] + [COPILOT_PLUGIN]:
        if (candidate / "scripts/verify-geometry.py").is_file():
            return candidate
    raise SystemExit("diagram-design plugin not found; install it first (see the doc-diagrams skill)")


def normalize(value: str) -> str | None:
    """Lowercase 6-digit hex, or rgb()/rgba() without spaces; None if not a color."""
    value = value.strip().lower().replace(" ", "")
    if re.fullmatch(r"#[0-9a-f]{3}", value):
        return "#" + "".join(ch * 2 for ch in value[1:])
    if re.fullmatch(r"#[0-9a-f]{6}", value):
        return value
    match = COLOR.fullmatch(value)
    if match and match.group("rgb"):
        r, g, b = (int(match.group(k)) for k in "rgb")
        alpha = (match.group("a") or "").lstrip(",")
        return f"rgba({r},{g},{b},{float(alpha):g})" if alpha else f"rgb({r},{g},{b})"
    return None


def rgb(value: str) -> tuple[int, int, int] | None:
    value = normalize(value) or ""
    if value.startswith("#"):
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    match = COLOR.fullmatch(value)
    return tuple(int(match.group(k)) for k in "rgb") if match and match.group("rgb") else None


def light_roles(guide: Path) -> dict[str, str]:
    roles: dict[str, str] = {}
    unreadable: list[str] = []
    inside = False
    for line in guide.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            inside = line.strip().lower() == "### semantic roles"
            continue
        match = ROLE_ROW.match(line) if inside else None
        if match:
            value = normalize(match.group(2))
            if value is None:
                unreadable.append(f"{match.group(1)} = {match.group(2)}")
            else:
                roles[match.group(1).lower()] = value
    if unreadable:
        raise SystemExit(f"{guide}: color value(s) are not hex or rgb(a): {'; '.join(unreadable)}")
    if not roles:
        raise SystemExit(f"no '### Semantic roles' table in {guide}")
    return roles


def profile_name(figure: Path, explicit: str | None) -> str:
    name = explicit
    if name is None:
        for folder in [figure.resolve().parent, *figure.resolve().parents]:
            marker = folder / ".diagram-design"
            if marker.is_file():
                match = re.fullmatch(r"\s*profile:\s*([a-z0-9-]+)\s*", marker.read_text(encoding="utf-8"))
                if not match:
                    raise SystemExit(f"{marker}: expected exactly 'profile: <slug>'")
                name = match.group(1)
                break
    if name is None:
        raise SystemExit(f"no --profile given and no .diagram-design marker above {figure}")
    if not SLUG.match(name):
        raise SystemExit(f"invalid profile name: {name}")
    return name


def shipped_roles() -> dict[str, str]:
    return light_roles(plugin_root() / "skills/diagram-design/references/style-guide.md")


def profile_roles(name: str) -> dict[str, str]:
    if name == "default":
        return shipped_roles()
    path = PROFILES / f"{name}.md"
    if not path.is_file():
        raise SystemExit(f"profile not found: {path}")
    return light_roles(path)


def color_maps(name: str) -> tuple[dict, dict, dict, frozenset]:
    """(hex map, exact rgb(a) map, RGB-triple map for other alphas, colors the profile reuses from the shipped palette)."""
    shipped, target = shipped_roles(), profile_roles(name)
    missing = sorted(set(shipped) - set(target))
    if missing:
        raise SystemExit(f"profile {name} is missing role(s): {', '.join(missing)}")
    hex_map: dict[str, str] = {}
    exact_map: dict[str, str] = {}
    triple_map: dict[tuple, tuple] = {}
    for role, old in shipped.items():
        new = target[role]
        if new == old:
            continue
        if old.startswith("#"):
            _put(hex_map, old, new, role)
            if new.startswith("#"):
                _put(triple_map, rgb(old), rgb(new), role)
        else:
            _put(exact_map, old, new, role)
    reused = {c for c in hex_map.values() if c in hex_map}
    reused |= {c for c in exact_map.values() if c in exact_map}
    reused |= {t for t in triple_map.values() if t in triple_map}
    return hex_map, exact_map, triple_map, frozenset(reused)


def profile_colors(name: str) -> tuple[set[str], set[tuple]]:
    roles = profile_roles(name)
    hexes = {value for value in roles.values() if value.startswith("#")}
    triples = {triple for triple in (rgb(value) for value in roles.values()) if triple}
    return hexes, triples


def recolor(text: str, maps: tuple, skip: frozenset = frozenset()) -> tuple[str, dict[str, int]]:
    """Replace shipped colors in one pass. Colors in `skip` are left alone."""
    hex_map, exact_map, triple_map, _ = maps
    counts: dict[str, int] = {}

    def bump(label: str) -> None:
        counts[label] = counts.get(label, 0) + 1

    def swap(match: re.Match) -> str:
        original = match.group(0)
        key = normalize(original)
        if match.group("hex"):
            if key in hex_map and key not in skip:
                bump(key)
                return hex_map[key]
            return original
        if key in exact_map:
            if key in skip:
                return original
            bump(key)
            return exact_map[key]
        triple = tuple(int(match.group(k)) for k in "rgb")
        new = triple_map.get(triple)
        if new is None or triple in skip:
            return original
        bump("rgb(%d,%d,%d)" % triple)
        head = "rgba(" if original.lower().startswith("rgba") else "rgb("
        alpha = (match.group("a") or "").replace(" ", "")
        return f"{head}{new[0]},{new[1]},{new[2]}{alpha})"

    return COLOR.sub(swap, text), counts


def applied_profile(text: str) -> str | None:
    match = MARKER.search(text)
    return match.group(1) if match else None


def with_marker(text: str, name: str) -> str:
    marker = f"<!-- apply-profile: {name} -->"
    if MARKER.search(text):
        return MARKER.sub(marker, text, count=1)
    doctype = re.match(r"\s*<!DOCTYPE[^>]*>[ \t]*\n?", text, re.I)
    cut = doctype.end() if doctype else 0
    return text[:cut] + marker + "\n" + text[cut:]


def _put(mapping: dict, key, value, role: str) -> None:
    if mapping.get(key, value) != value:
        raise SystemExit(f"the profile maps {key} to two different colors (role {role})")
    mapping[key] = value
