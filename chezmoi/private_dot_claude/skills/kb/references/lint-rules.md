# Lint Rules

All health check rules for `/kb:lint`, grouped by severity.

## Errors (data integrity)

| ID | Rule | Auto-fixable | Fix |
|----|------|-------------|-----|
| E01 | Missing required field (title, source, date_added, tags, status) | No | Manual |
| E02 | Invalid status (not inbox/reference/archived) | No | Manual |
| E03 | Invalid source (not in allowed list) | No | Manual |
| E04 | Bad date format (ISO timestamp instead of YYYY-MM-DD) | Yes | Truncate to YYYY-MM-DD |
| E05 | Duplicate URL across notes | No | Manual (delete or merge) |
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

## Info (suggestions)

| ID | Rule | Action |
|----|------|--------|
| I01 | Tag with 5+ notes but no wiki article | Suggest /kb:synthesize |
| I02 | Tag used by only 1 note | Consider taxonomy cleanup |
| I03 | Summary shorter than 10 words | Consider expanding |
| I04 | Note older than 90 days | May need review |

## Not Checked (by design)

- **Dead URLs**: Opt-in only via `/kb:lint urls` (slow, auth issues)
- **Cross-note claim consistency**: Too expensive and unreliable for automated checking
- **Content quality**: Subjective, not mechanically verifiable

See DECISIONS.md D11 for rationale.
