from dataclasses import dataclass
from pathlib import Path

from kb_engine.vault import load_post, write_post_atomic

_VALID_STATUSES = frozenset({"reference", "archived"})
_PLACEHOLDER_MARKER = "Pending processing"


@dataclass(frozen=True)
class FileResult:
    n_filed: int  # notes filed as reference
    n_archived: int  # notes filed as archived
    skipped_missing: tuple[str, ...] = ()  # filename not found in inbox
    skipped_collision: tuple[str, ...] = ()  # dst already exists
    skipped_invalid: tuple[str, ...] = ()  # bad filename or status


def _is_valid_filename(filename: str) -> bool:
    """Return True only for a safe bare basename (no path separators, not empty, not dot/dotdot)."""
    if not filename:
        return False
    if "/" in filename or "\\" in filename:
        return False
    if filename in (".", ".."):
        return False
    # Reject absolute paths: on POSIX the leading-slash check above covers "/etc/passwd";
    # the backslash check is the real defense against "..\evil" traversal paths.
    p = Path(filename)
    if p.is_absolute():
        return False
    # After the above guards, a valid bare basename has exactly one part
    if len(p.parts) != 1:
        return False
    return True


def apply_dispositions(
    vault_path: Path,
    dispositions: list[dict],
    *,
    dry_run: bool = True,
) -> FileResult:
    """Move inbox notes to ``Knowledge/`` and update their frontmatter.

    For each disposition ``{"filename": str, "status": str, "tags": list[str], "summary": str}``:

    1. Validate ``filename`` is a bare basename (no path separators, not ``.``/``..``,
       not absolute, not empty) → else ``skipped_invalid``.
    2. Validate ``status`` in ``{"reference", "archived"}`` → else ``skipped_invalid``.
    3. Resolve ``src`` and ``dst``; verify both remain inside the vault
       (guards against symlink attacks) → else ``skipped_invalid``.
    4. ``src`` not a file → ``skipped_missing``.
    5. ``dst`` already exists → ``skipped_collision`` (never overwrite).
    6. Load ``src`` via ``load_post`` (tolerates a ``content`` frontmatter key);
       set ``tags``, ``summary``, ``status`` (all other keys preserved). Replace
       body when empty/whitespace or contains "Pending processing"; otherwise
       leave body unchanged.
    7. If ``dry_run``: count but write nothing. Else write ``dst`` atomically and
       unlink ``src``.
    """
    vault_resolved = vault_path.resolve()

    n_filed = 0
    n_archived = 0
    skipped_missing: list[str] = []
    skipped_collision: list[str] = []
    skipped_invalid: list[str] = []

    for disp in dispositions:
        # Fix 1: Guard malformed disposition items (non-dict)
        if not isinstance(disp, dict):
            skipped_invalid.append(repr(disp))
            continue

        filename = disp.get("filename", "")
        # Fix 1: Guard non-string filename
        if not isinstance(filename, str):
            skipped_invalid.append(str(filename))
            continue

        status: str = disp.get("status", "")

        # Fix 2: Type-guard tags
        raw_tags = disp.get("tags") or []
        if not isinstance(raw_tags, list):
            skipped_invalid.append(filename)
            continue
        tags: list[str] = [str(t) for t in raw_tags]

        # Fix 2: Type-guard summary
        summary = disp.get("summary", "")
        if not isinstance(summary, str):
            skipped_invalid.append(filename)
            continue

        # 1. Validate filename
        if not _is_valid_filename(filename):
            skipped_invalid.append(filename)
            continue

        # 2. Validate status
        if status not in _VALID_STATUSES:
            skipped_invalid.append(filename)
            continue

        # 3. Resolve paths and check vault boundary
        src = (vault_path / "Knowledge" / "inbox" / filename).resolve()
        dst = (vault_path / "Knowledge" / filename).resolve()

        if not src.is_relative_to(vault_resolved) or not dst.is_relative_to(vault_resolved):
            skipped_invalid.append(filename)
            continue

        # 4. Source must exist
        if not src.is_file():
            skipped_missing.append(filename)
            continue

        # Fix 4: Reject a symlink at the destination (before collision check)
        if dst.is_symlink():
            skipped_invalid.append(filename)
            continue

        # 5. Destination must not already exist
        if dst.exists():
            skipped_collision.append(filename)
            continue

        # 6. Load and mutate frontmatter (never mutate in-place — build new post state)
        post = load_post(src.read_text(encoding="utf-8"))
        post["tags"] = tags
        post["summary"] = summary
        post["status"] = status

        body = post.content
        if not body or not body.strip() or _PLACEHOLDER_MARKER in body:
            post.content = f"## Notes\n\n{summary}"

        # Fix 3: Classify and tally in BOTH modes; gate only the two side-effects
        if status == "reference":
            n_filed += 1
        else:
            n_archived += 1

        if dry_run:
            continue

        # Write dst atomically (house I/O) before unlinking src — order matters.
        write_post_atomic(dst, post)
        src.unlink()

    return FileResult(
        n_filed=n_filed,
        n_archived=n_archived,
        skipped_missing=tuple(skipped_missing),
        skipped_collision=tuple(skipped_collision),
        skipped_invalid=tuple(skipped_invalid),
    )
