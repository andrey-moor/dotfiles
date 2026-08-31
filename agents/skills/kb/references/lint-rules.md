# Lint Rules

All health check rules for `/kb:lint`, grouped by severity.

## Scope

All checks run over `Main/Knowledge/` (source notes + `wiki/` + `inbox/`) **only**. Notes under
`Main/Orrery/`, `Main/Archive/`, `Main/Clippings/`, and `_system/` are excluded — their inline
hashtags are not KB taxonomy and must never be counted (this is why a whole-vault `list_all_tags`
shows phantom tags like `active`, `clippings`, `bathroomfan`).

## Errors (data integrity)

| ID | Rule | Auto-fixable | Fix |
|----|------|-------------|-----|
| E01 | Missing required field (title, source, date_added, tags, status) | No | Manual |
| E02 | Invalid status (not inbox/reference/archived) | No | Manual |
| E03 | Invalid source (not in allowed list) | No | Manual |
| E04 | Bad date format (ISO timestamp instead of YYYY-MM-DD) | Yes | Truncate to YYYY-MM-DD |
| E05 | Duplicate URL **or byte-identical body** across notes (including `inbox/`) | No | Manual — keep one, delete the rest |
| E07 | Inbox note still in raw Web-Clipper schema (`source` holds a URL, or `status` missing) | Yes | Normalize: `url`←`source`, `source`←inferred type, `date_added`←`created`, `status`←`inbox`, strip `Knowledge/inbox` tag, drop `published`/`created`/`description` |
| E06 | Status-location mismatch (inbox note with status:reference or vice versa) | Yes | Update status to match location |

## Warnings (quality)

| ID | Rule | Auto-fixable | Fix |
|----|------|-------------|-----|
| W01 | Empty tags on reference note | No | Run /kb:retag review |
| W02 | Empty summary on reference note | No | Manual or reprocess |
| W03 | No `## Related` section (graph orphan) | No | Run /kb:retag review or add manually |
| W04 | Tag not in taxonomy (orphan tag) | No | Add to taxonomy or retag |
| W05 | Deprecated tag in use | Yes | Replace with mapped replacement |
| W06 | Stale wiki article (sources added since last_compiled) | No | Run /kb:synthesize |
| W07 | Stale index — `_system/index.md` `last_updated` > 14 days old, or its Stats counts diverge from live counts | Yes | Regenerate via `/kb:index` |
| W08 | Stub body on a reference note (contains "Pending processing" or "Content not yet fetched") | No | Reprocess via `/kb:process` |

## Info (suggestions)

| ID | Rule | Action |
|----|------|--------|
| I01 | Tag with 5+ notes but no wiki article | Suggest /kb:synthesize |
| I02 | Tag used by only 1 note | Consider taxonomy cleanup |
| I03 | Summary shorter than 10 words | Consider expanding |
| I04 | Note older than 90 days | May need review |
| I05 | Inbox backlog — > 10 notes in `inbox/`, or oldest inbox note > 30 days | Suggest `/kb:process` |

## Not Checked (by design)

- **Dead URLs**: Opt-in only via `/kb:lint urls` (slow, auth issues)
- **Cross-note claim consistency**: Too expensive and unreliable for automated checking
- **Content quality**: Subjective, not mechanically verifiable

See DECISIONS.md D11 for rationale.
