#!/usr/bin/env python3
"""Flag the plain-prose rules that a script can check: dashes, semicolons, parentheses, sentences over
the word limit, a high average sentence length, and sentences that open with "It" or "They".

Usage: lint-prose.py FILE... [--max-words 25] [--max-average 20]

Checks the sentences the writer wrote. Skipped: YAML front matter, fenced code, inline code, HTML
comments, link targets and URLs, text in double quotes, and bold text such as UI labels. Headings,
list items, table cells and paragraphs are separate units, so a heading never runs into the bullet
below it. Table cells and headings get the punctuation checks, not the length checks.
Prints path:line: rule: detail for every finding. Exit 1 on any finding, 2 on a usage error.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

FENCE_OPEN = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
LIST_ITEM = re.compile(r"^(\s*)(?:[-*+]|\d{1,9}[.)])\s+(.*)$")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
CODE_SPAN = re.compile(r"(`+)(.+?)\1")
LINK_TARGET = re.compile(r"\]\((?:[^()\s]|\([^()]*\))*\)")
URL = re.compile(r"<?https?://[^\s>]+>?")
ENTITY = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z]+);")
QUOTED = re.compile(r"\"[^\"\n]*\"|“[^”\n]*”")
BOLD = re.compile(r"\*\*[^*\n]+\*\*|__[^_\n]+__")
DASH = re.compile(r"[—–]|(?<=\w) -{1,2} (?=\w)")
PAREN = re.compile(r"[()]")
ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "cf.", "approx.", "Dr.", "Mr.", "Ms.", "Mrs.", "No.", "Fig.", "U.S.")
SENTENCE_END = re.compile(r"(?<=[.!?])[\"”')\]*_]*\s+(?=[\"“(\[*_]*[A-Z0-9])")
PRONOUN_START = re.compile(r"^(?:It|They)\b")
WORD = re.compile(r"[A-Za-z0-9][\w'’./-]*")


@dataclass
class Unit:
    line: int
    text: str
    kind: str  # paragraph, item, heading, cell
    starts: list[tuple[int, int]] | None = None  # (offset in text, line number) where each source line begins

    def add(self, number: int, line: str) -> None:
        self.starts = self.starts or [(0, self.line)]
        self.text += " "
        self.starts.append((len(self.text), number))
        self.text += line

    def line_at(self, offset: int) -> int:
        line = self.line
        for start, number in self.starts or []:
            if start <= offset:
                line = number
        return line


def strip_comments(lines: list[str]) -> list[str]:
    """Blank out HTML comments while keeping line numbers."""
    out, in_comment = [], False
    for line in lines:
        kept, position = [], 0
        while position <= len(line):
            if in_comment:
                end = line.find("-->", position)
                if end == -1:
                    break
                position, in_comment = end + 3, False
            else:
                start = line.find("<!--", position)
                if start == -1:
                    kept.append(line[position:])
                    break
                kept.append(line[position:start])
                position, in_comment = start + 4, True
        out.append(" ".join(kept))
    return out


def prose_lines(text: str) -> list[str]:
    """The file's lines with front matter and fenced code blanked out; line numbers are kept."""
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for end in range(1, len(lines)):
            if lines[end].strip() == "---":
                lines[: end + 1] = [""] * (end + 1)
                break
    fence = None
    for index, line in enumerate(lines):
        match = FENCE_OPEN.match(line)
        if fence is None and match:
            fence = match.group(1)
            lines[index] = ""
        elif fence is not None:
            closing = line.strip()
            if closing.startswith(fence[0] * len(fence)) and set(closing) == {fence[0]}:
                fence = None
            lines[index] = ""
    return strip_comments(lines)


def table_cells(line: str) -> list[str]:
    """Cells of a table row. A pipe inside inline code or escaped as \\| does not split a cell."""
    cells, current, index, fence = [], [], 0, ""
    text = line.strip()
    while index < len(text):
        char = text[index]
        if char == "`":
            run = len(text[index:]) - len(text[index:].lstrip("`"))
            ticks = text[index:index + run]
            fence = "" if fence == ticks else (ticks if not fence else fence)
            current.append(ticks)
            index += run
            continue
        if char == "\\" and text[index + 1:index + 2] == "|":
            current.append("|")
            index += 2
            continue
        if char == "|" and not fence:
            cells.append("".join(current))
            current = []
        else:
            current.append(char)
        index += 1
    cells.append("".join(current))
    return cells[1:-1] if text.startswith("|") and text.endswith("|") else cells


def units(lines: list[str]) -> list[Unit]:
    """Split prose into headings, list items, table cells and paragraphs."""
    found: list[Unit] = []
    current: Unit | None = None

    def close() -> None:
        nonlocal current
        if current and current.text.strip():
            found.append(current)
        current = None

    for number, line in enumerate(lines, start=1):
        if not line.strip():
            close()
            continue
        heading = HEADING.match(line)
        if heading:
            close()
            found.append(Unit(number, heading.group(1), "heading"))
            continue
        if TABLE_ROW.match(line):
            close()
            if not TABLE_SEPARATOR.match(line):
                found.extend(Unit(number, cell, "cell") for cell in table_cells(line) if cell.strip())
            continue
        item = LIST_ITEM.match(line)
        if item:
            close()
            current = Unit(number, item.group(2), "item")
            continue
        if current is None:
            current = Unit(number, line.strip(), "paragraph")
        else:
            current.add(number, line.strip())
    close()
    return found


def blank(pattern: re.Pattern, text: str, keep: str = "") -> str:
    """Replace each match with spaces of the same length, so offsets still map to source lines."""
    return pattern.sub(lambda m: (keep + " " * len(m.group(0)))[: len(m.group(0))], text)


def visible(text: str) -> str:
    """Text as the reader sees the writer's words: no code, link targets, URLs or entities."""
    text = blank(CODE_SPAN, text, keep="C")  # a capital keeps sentence starts and counts the span as a word
    text = blank(LINK_TARGET, text, keep="]")
    text = blank(URL, text)
    return blank(ENTITY, text)


def sentences(text: str) -> list[tuple[int, str]]:
    """(offset, sentence) pairs. Abbreviations such as e.g. do not end a sentence."""
    protected = text
    for abbreviation in ABBREVIATIONS:
        protected = protected.replace(abbreviation, abbreviation.replace(".", "\0"))
    found, start = [], 0
    for match in SENTENCE_END.finditer(protected):
        found.append((start, protected[start:match.start()]))
        start = match.end()
    found.append((start, protected[start:]))
    return [(offset, part.replace("\0", ".")) for offset, part in found if part.strip()]


def hide_inner_stops(match: re.Match) -> str:
    """Stops inside a quote do not end the outer sentence, except one that closes the quote."""
    quote = match.group(0)
    inner, tail = quote[:-2], quote[-2:]
    inner = inner.replace(".", " ").replace("!", " ").replace("?", " ")
    return inner + tail if tail[0] in ".!?" else inner + tail.replace(".", " ")


def lint_unit(unit: Unit, max_words: int) -> tuple[list[tuple[int, str]], list[int]]:
    findings: list[tuple[int, str]] = []
    text = visible(unit.text)
    unquoted = blank(BOLD, blank(QUOTED, text))
    for rule, pattern, detail in (("dash", DASH, "use a period or a comma"),
                                  ("semicolon", re.compile(";"), "split into two sentences or use a comma"),
                                  ("parenthesis", PAREN, "make the aside its own sentence or cut it")):
        reported = set()
        for match in pattern.finditer(unquoted):
            line = unit.line_at(match.start())
            if line not in reported:
                reported.add(line)
                findings.append((line, f"{rule}: {detail}: {unit.text.strip()[:70]}"))
    lengths: list[int] = []
    if unit.kind in ("paragraph", "item"):
        quoted_periods_hidden = QUOTED.sub(hide_inner_stops, text)
        for offset, sentence in sentences(quoted_periods_hidden):
            count = len(WORD.findall(sentence))
            lengths.append(count)
            line = unit.line_at(offset + len(sentence) - len(sentence.lstrip()))
            if count > max_words:
                findings.append((line, f"long-sentence: {count} words, limit {max_words}: {sentence.strip()[:70]}"))
            if PRONOUN_START.match(sentence.strip()):
                findings.append((line, f"pronoun: name the subject instead of a pronoun that points back: {sentence.strip()[:70]}"))
    return findings, lengths


def lint_file(path: Path, max_words: int, max_average: float) -> list[str]:
    all_findings: list[tuple[int, str]] = []
    lengths: list[int] = []
    for unit in units(prose_lines(path.read_text(encoding="utf-8"))):
        findings, unit_lengths = lint_unit(unit, max_words)
        all_findings.extend(findings)
        lengths.extend(unit_lengths)
    if len(lengths) >= 3 and sum(lengths) / len(lengths) > max_average:
        all_findings.append((1, f"average-length: {sum(lengths) / len(lengths):.1f} words per sentence over {len(lengths)} sentences, limit {max_average:g}"))
    return [f"{path}:{line}: {message}" for line, message in sorted(all_findings, key=lambda f: f[0])]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--max-words", type=int, default=25, help="longest sentence allowed (default 25)")
    parser.add_argument("--max-average", type=float, default=20.0, help="highest average sentence length (default 20)")
    args = parser.parse_args()
    for path in args.files:
        if not path.is_file():
            print(f"lint-prose: not found: {path}", file=sys.stderr)
            return 2
    findings = [finding for path in args.files for finding in lint_file(path, args.max_words, args.max_average)]
    for finding in findings:
        print(finding)
    print(f"lint-prose: {len(args.files)} file(s), {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
