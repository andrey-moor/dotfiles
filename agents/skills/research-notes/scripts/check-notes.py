#!/usr/bin/env python3
"""Check research notes: every claim bullet is tagged and cited; every note lists open questions.

Usage: check-notes.py <notes-dir-or-file>... [--sources DIR]...

With --sources, each file:line citation that resolves to a file under DIR is opened, and every
multi-digit number in the claim must appear within two lines of the cited line. A missing number
fails a [verified] or [doc] claim. For an [inferred] claim it is reported as a note, because an
inference may compute a new number; check that the arithmetic is general, not a worked example's.
The check proves a number is absent from the cited passage. It cannot prove that a number which is
present belongs to the noun the claim attaches it to.

Terms entries (- **Term**: definition. (citation)) need a citation like any claim. An Open questions
entry that starts with "Conflict:" must cite both sides, so it needs at least two citations.

Exit 1 on any finding.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TAGS = {"verified", "doc", "web", "inferred", "thin"}
CLAIM_SECTIONS = {"in general", "in this system", "claims"}
STRICT_NUMBER_TAGS = {"verified", "doc"}
BULLET = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.*)$")
TAG = re.compile(r"^\[([a-z]+)\]\s+(.*)$")
# The citation is the last parenthetical on the line; trailing punctuation is allowed.
LAST_PAREN = re.compile(r"\(((?:[^()]|\([^()]*\))*)\)[.;,\s]*$")
FILE_LINE = re.compile(r"[\w./-]+\.[A-Za-z0-9]{1,6}:\d+")
CITED_FILE_LINE = re.compile(r"([\w./-]+\.[A-Za-z0-9]{1,6}):(\d+)")
URL = re.compile(r"https?://\S+")
# A claim's number may carry a unit (80GB, 900ms, 2.3x, 128K) but not a letter prefix (p99, h100).
# Commas are thousands separators only before exactly three digits, so (16,32,64) is three numbers.
NUMBER_BODY = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
NUMBER = re.compile(rf"(?<![\w.])({NUMBER_BODY})(?=[A-Za-z%]{{0,4}}(?!\w))")
# Sources glue numbers to units and prefixes (x2.0, p99, h100, 50ms), so source text is scanned loosely.
SOURCE_NUMBER = re.compile(NUMBER_BODY)
FENCE = re.compile(r"^\s*(```|~~~)")
BINARY_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".gz", ".docx", ".xlsx", ".pptx"}
CONTEXT_LINES = 2
TERM = re.compile(r"^\*\*[^*]+\*\*\s*:\s*\S")
CONFLICT = re.compile(r"^(?:\*\*|__)?conflict\s*:", re.I)


def citation_is_valid(tag: str, citation: str) -> bool:
    """A file:line or URL for sourced claims; inferred claims name their inputs; thin claims give a reason."""
    if tag == "thin":
        return len(citation.strip()) >= 8
    if tag == "inferred":
        return citation.strip().lower().startswith("from ") and bool(FILE_LINE.search(citation) or URL.search(citation))
    if tag == "web":
        return bool(URL.search(citation))
    return bool(FILE_LINE.search(citation) or URL.search(citation))


def numbers_in(text: str, pattern: re.Pattern = NUMBER) -> set[str]:
    """Multi-digit or decimal numbers, commas removed. Single digits are too common to verify."""
    found = set()
    for raw in pattern.findall(text):
        value = raw.replace(",", "").rstrip(".")
        if len(value.replace(".", "")) >= 2:
            found.add(value)
    return found


class SourceIndex:
    """Resolves a cited file name to a readable file under the --sources directories."""

    def __init__(self, roots: list[Path]):
        self.roots = roots
        self.by_name: dict[str, list[Path]] = {}
        for root in roots:
            for path in root.rglob("*"):
                if path.is_file():
                    self.by_name.setdefault(path.name, []).append(path)
        self.cache: dict[Path, list[str]] = {}

    def lines(self, cited: str) -> list[str] | None:
        for root in self.roots:
            candidate = root / cited
            if candidate.is_file():
                return self._read(candidate)
        matches = self.by_name.get(Path(cited).name, [])
        if len(matches) == 1:
            return self._read(matches[0])
        return None

    def _read(self, path: Path) -> list[str] | None:
        """Lines split on newline only, as grep -n counts them. Binary files are not line-addressable."""
        if path.suffix.lower() in BINARY_SUFFIXES:
            return None
        if path not in self.cache:
            data = path.read_bytes()
            self.cache[path] = None if b"\0" in data[:4096] else data.decode("utf-8", errors="replace").split("\n")
        return self.cache[path]


def file_citations(text: str) -> list[tuple[str, str]]:
    """file:line citations, ignoring host:port inside URLs."""
    return CITED_FILE_LINE.findall(URL.sub(" ", text))


def check_numbers(where: str, tag: str, body: str, citation: str, index: SourceIndex, stats: dict) -> tuple[list[str], list[str]]:
    wanted = numbers_in(body)
    hard: list[str] = []
    window_numbers: set[str] = set()
    resolved = False
    for cited, line in file_citations(citation):
        lines = index.lines(cited)
        if lines is None:
            stats["unresolved"] += 1
            continue
        if not 1 <= int(line) <= len(lines):
            hard.append(f"{where}: cites {cited}:{line}, but that file has {len(lines)} lines")
            continue
        resolved = True
        start = max(0, int(line) - 1 - CONTEXT_LINES)
        window_numbers |= numbers_in(" ".join(lines[start:int(line) + CONTEXT_LINES]), SOURCE_NUMBER)
    if not resolved or not wanted:
        return hard, []
    stats["checked"] += 1
    missing = sorted(wanted - window_numbers)
    if not missing:
        return hard, []
    message = f"{where}: [{tag}] numbers not found within {CONTEXT_LINES} lines of the citation: {', '.join(missing)}"
    return (hard + [message], []) if tag in STRICT_NUMBER_TAGS else (hard, [message])


def check_term(where: str, text: str) -> list[str]:
    if not TERM.match(text):
        return [f"{where}: a Terms entry must read '**Term**: definition. (citation)': {text[:70]}"]
    paren = LAST_PAREN.search(text)
    if not paren or not (FILE_LINE.search(paren.group(1)) or URL.search(paren.group(1))):
        return [f"{where}: Terms entry has no file:line or URL citation at the end: {text[:70]}"]
    return []


def check_file(path: Path, index: SourceIndex | None, stats: dict) -> tuple[list[str], list[str]]:
    findings: list[str] = []
    notes: list[str] = []
    section = ""
    section_level = 0
    has_open_questions = False
    in_fence = False
    for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            if level > section_level and (section in CLAIM_SECTIONS or section == "terms" or section.startswith("open questions")):
                continue  # a sub-heading keeps its parent section, so its bullets are still checked
            section = heading.group(2).strip().lower()
            section_level = level
            if section.startswith("open questions"):
                has_open_questions = True
            continue
        bullet = BULLET.match(line)
        if not bullet:
            continue
        text = bullet.group(1).strip()
        where = f"{path}:{number}"
        if section == "terms":
            findings.extend(check_term(where, text))
            continue
        if section.startswith("open questions"):
            if CONFLICT.match(text) and len(file_citations(text)) + len(URL.findall(text)) < 2:
                findings.append(f"{where}: a Conflict entry must cite both sides (two file:line or URL citations): {text[:70]}")
            continue
        if section not in CLAIM_SECTIONS:
            continue
        tag = TAG.match(text)
        if not tag:
            findings.append(f"{where}: claim has no confidence tag: {text[:70]}")
            continue
        name = tag.group(1)
        if name not in TAGS:
            findings.append(f"{where}: unknown tag [{name}]; use {sorted(TAGS)}")
            continue
        paren = LAST_PAREN.search(tag.group(2))
        if not paren:
            findings.append(f"{where}: claim has no citation in parentheses at the end: {text[:70]}")
            continue
        if not citation_is_valid(name, paren.group(1)):
            findings.append(f"{where}: [{name}] citation must be a file:line or URL"
                            f"{' after from' if name == 'inferred' else ''}: ({paren.group(1)[:60]})")
            continue
        if index is not None and name in STRICT_NUMBER_TAGS | {"inferred", "thin"}:
            body = tag.group(2)[: paren.start()]
            hard, soft = check_numbers(where, name, body, paren.group(1), index, stats)
            findings.extend(hard)
            notes.extend(soft)
    if not has_open_questions:
        findings.append(f"{path}: no 'Open questions' section")
    return findings, notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", help="note files or folders of notes")
    parser.add_argument("--sources", action="append", default=[], metavar="DIR",
                        help="folder holding the cited files; repeatable")
    args = parser.parse_args()

    files: list[Path] = []
    for arg in args.paths:
        p = Path(arg)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.md")))
        elif p.is_file():
            files.append(p)
        else:
            print(f"check-notes: not found: {p}", file=sys.stderr)
            return 2
    if not files:
        print("check-notes: no .md files found", file=sys.stderr)
        return 2
    roots = [Path(s) for s in args.sources]
    for root in roots:
        if not root.is_dir():
            print(f"check-notes: --sources is not a folder: {root}", file=sys.stderr)
            return 2
    index = SourceIndex(roots) if roots else None

    stats = {"checked": 0, "unresolved": 0}
    findings: list[str] = []
    notes: list[str] = []
    for path in files:
        hard, soft = check_file(path, index, stats)
        findings.extend(hard)
        notes.extend(soft)
    for finding in findings:
        print(finding)
    for note in notes:
        print(f"note: {note}")
    summary = f"check-notes: {len(files)} note(s), {len(findings)} finding(s)"
    if index is not None:
        summary += f", {stats['checked']} claim(s) number-checked, {stats['unresolved']} citation(s) not under --sources"
        if notes:
            summary += f", {len(notes)} inferred claim(s) to review"
    print(summary)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
