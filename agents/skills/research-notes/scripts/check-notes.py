#!/usr/bin/env python3
"""Check research notes: every claim bullet is tagged and cited; every note lists open questions.

Usage: check-notes.py <notes-dir-or-file>... [--sources DIR]... [--deliverable FILE]... [--skip-section NAME]...

With --sources, each file:line or file:start-end citation that resolves to a file under DIR is
opened, and every multi-digit number in the claim, outside code spans, must appear in the cited
lines or within two lines of them. A missing number fails a [verified], [doc] or [web] claim. For an
[inferred] claim it is reported as a note, because an inference may compute a new number; check that
the arithmetic is general, not a worked example's. The check proves a number is absent from the
cited passage. It cannot prove that a number which is present belongs to the noun the claim
attaches it to.

A claim that cites a file under an evidence/ folder describes state observed at one time, so it must
carry the date it was observed (YYYY-MM-DD).

With --deliverable, the document written from the notes is checked too: every multi-digit number
and every code span in it must appear somewhere in the notes. Front matter, fenced code, HTML
comments, link targets and list markers are skipped, and so is each --skip-section heading's section,
such as a lesson's "Worked example", whose values are illustrative.

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
STRICT_NUMBER_TAGS = {"verified", "doc", "web"}
BULLET = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.*)$")
TAG = re.compile(r"^\[([a-z]+)\]\s+(.*)$")
# The citation is the last parenthetical on the line; trailing punctuation is allowed.
LAST_PAREN = re.compile(r"\(((?:[^()]|\([^()]*\))*)\)[.;,\s]*$")
FILE_LINE = re.compile(r"[\w./-]+\.[A-Za-z0-9]{1,6}:\d+")
CITED_FILE_LINE = re.compile(r"([\w./-]+\.[A-Za-z0-9]{1,6}):(\d+)(?:-(\d+))?")
URL = re.compile(r"https?://\S+")
# A claim's number may carry a unit (80GB, 900ms, 2.3x, 128K) but not a letter prefix (p99, h100).
# Commas are thousands separators only before exactly three digits, so (16,32,64) is three numbers.
NUMBER_BODY = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
NUMBER = re.compile(rf"(?<![\w.])({NUMBER_BODY})(?=[A-Za-z%]{{0,4}}(?!\w))")
# Sources glue numbers to units and prefixes (x2.0, p99, h100, 50ms), so source text is scanned loosely.
SOURCE_NUMBER = re.compile(NUMBER_BODY)
FENCE = re.compile(r"^\s*(```|~~~)")
CODE_SPAN = re.compile(r"(`+)(.+?)\1")
EVIDENCE_PATH = re.compile(r"(^|/)evidence/")
DATE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
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


def file_citations(text: str) -> list[tuple[str, int, int | None]]:
    """file:line and file:start-end citations, ignoring host:port inside URLs."""
    return [(name, int(start), int(end) if end else None) for name, start, end in CITED_FILE_LINE.findall(URL.sub(" ", text))]


def without_code_spans(text: str) -> str:
    """Model names and identifiers in backticks (gpt-5.6-luna, v2) carry digits that are not claims."""
    return CODE_SPAN.sub(" ", text)


def check_numbers(where: str, tag: str, body: str, citation: str, index: SourceIndex, stats: dict) -> tuple[list[str], list[str]]:
    wanted = numbers_in(without_code_spans(body))
    hard: list[str] = []
    window_numbers: set[str] = set()
    resolved = False
    for cited, first, last in file_citations(citation):
        last = first if last is None else last
        label = f"{cited}:{first}" if first == last else f"{cited}:{first}-{last}"
        if last < first:
            hard.append(f"{where}: cites {label}, a line range that ends before it starts")
            continue
        lines = index.lines(cited)
        if lines is None:
            stats["unresolved"] += 1
            continue
        if not (1 <= first and last <= len(lines)):
            hard.append(f"{where}: cites {label}, but that file has {len(lines)} lines")
            continue
        resolved = True
        start = max(0, first - 1 - CONTEXT_LINES)
        window_numbers |= numbers_in(" ".join(lines[start:last + CONTEXT_LINES]), SOURCE_NUMBER)
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
        if any(EVIDENCE_PATH.search(cited) for cited, _, _ in file_citations(paren.group(1))) and not DATE.search(text):
            findings.append(f"{where}: a claim that cites evidence/ needs the date the state was observed (YYYY-MM-DD): {text[:70]}")
        if index is not None and name in STRICT_NUMBER_TAGS | {"inferred", "thin"}:
            body = tag.group(2)[: paren.start()]
            hard, soft = check_numbers(where, name, body, paren.group(1), index, stats)
            findings.extend(hard)
            notes.extend(soft)
    if not has_open_questions:
        findings.append(f"{path}: no 'Open questions' section")
    return findings, notes


FRONT_MATTER = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.S)
LIST_MARKER = re.compile(r"^\s*(?:\d+[.)]|[-*+])\s+")
LINK_TARGET = re.compile(r"\]\([^)]*\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def notes_corpus(files: list[Path]) -> tuple[str, set[str]]:
    """All note text with each bullet's closing citation removed, and the numbers in it."""
    kept = []
    for path in files:
        for line in path.read_text(encoding="utf-8").split("\n"):
            paren = LAST_PAREN.search(line) if BULLET.match(line) else None
            kept.append(line[: paren.start()] if paren else line)
    text = "\n".join(kept)
    # Digits inside code spans (llama-13b) are names, not numbers, so they cannot vouch for a number.
    return text, numbers_in(without_code_spans(text), SOURCE_NUMBER)


def outside_comments(line: str, in_comment: bool) -> tuple[str, bool]:
    """The part of a line outside HTML comments, and whether a comment is still open at its end."""
    kept, position = [], 0
    while position <= len(line):
        if in_comment:
            end = line.find("-->", position)
            if end == -1:
                return " ".join(kept), True
            position, in_comment = end + 3, False
        else:
            start = line.find("<!--", position)
            if start == -1:
                kept.append(line[position:])
                break
            kept.append(line[position:start])
            position, in_comment = start + 4, True
    return " ".join(kept), in_comment


def deliverable_lines(text: str, skip_sections: set[str]):
    """(line number, text) for the prose a reader sees, minus skipped parts."""
    offset = 0
    front = FRONT_MATTER.match(text)
    if front:
        offset = front.group(0).count("\n")
        text = text[front.end():]
    in_fence = in_comment = False
    skip_level = 0
    for number, line in enumerate(text.split("\n"), start=1 + offset):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line, in_comment = outside_comments(line, in_comment)
        heading = HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            if skip_level and level <= skip_level:
                skip_level = 0
            if heading.group(2).strip().lower() in skip_sections:
                skip_level = level
        if skip_level:
            continue
        yield number, LINK_TARGET.sub("]", URL.sub(" ", LIST_MARKER.sub("", line)))


def check_deliverable(path: Path, corpus: str, corpus_numbers: set[str], skip_sections: set[str]) -> list[str]:
    findings = []
    for number, line in deliverable_lines(path.read_text(encoding="utf-8"), skip_sections):
        for _, name in CODE_SPAN.findall(line):
            if name.strip() and not re.search(rf"(?<![\w-]){re.escape(name.strip())}(?![\w-])", corpus):
                findings.append(f"{path}:{number}: code span `{name.strip()}` appears in no note")
        for value in sorted(numbers_in(without_code_spans(line)) - corpus_numbers):
            findings.append(f"{path}:{number}: number {value} appears in no note")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", help="note files or folders of notes")
    parser.add_argument("--sources", action="append", default=[], metavar="DIR",
                        help="folder holding the cited files; repeatable")
    parser.add_argument("--deliverable", action="append", default=[], metavar="FILE",
                        help="document written from the notes; its numbers and code spans must appear in them")
    parser.add_argument("--skip-section", action="append", default=[], metavar="NAME",
                        help="heading whose section --deliverable leaves out, such as 'Worked example'")
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
    deliverables = [Path(d) for d in args.deliverable]
    for deliverable in deliverables:
        if not deliverable.is_file():
            print(f"check-notes: --deliverable not found: {deliverable}", file=sys.stderr)
            return 2
    if deliverables:
        corpus, corpus_numbers = notes_corpus(files)
        skip = {name.strip().lower() for name in args.skip_section}
        for deliverable in deliverables:
            findings.extend(check_deliverable(deliverable, corpus, corpus_numbers, skip))
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
