Health check across the Knowledge Base. Finds data integrity issues, quality gaps, and improvement opportunities.

## Usage

`/kb:lint` — full lint report
`/kb:lint fix` — auto-fix mechanical issues (date formats, status mismatches, deprecated tags)
`/kb:lint urls` — check for dead URLs (slow, opt-in)

## Instructions

### 0. Scope

Run all checks over `Main/Knowledge/` only (source + `wiki/` + `inbox/`). Exclude `Main/Orrery/`,
`Main/Archive/`, `Main/Clippings/`, and `_system/`. Never count inline hashtags from those folders
as KB tags.

### 1. Gather data

- Read taxonomy from `Main/_system/_taxonomy.md` (including Deprecated table)
- List all notes in `Main/Knowledge/`, `Main/Knowledge/wiki/`, `Main/Knowledge/inbox/` via `mcp__obsidian__list_directory`
- Read frontmatter of all notes via `mcp__obsidian__get_frontmatter`
- For warnings that need content (Related section check), read note content

### 2. Run checks

**ERRORS (data integrity):**
- **E01 missing-field**: Required fields missing or null (title, source, date_added, tags, status)
- **E02 invalid-status**: Status not one of: inbox, reference, archived
- **E03 invalid-source**: Source not one of the allowed values from schema.md: article, tweet, newsletter, github, youtube, paper, podcast, derived, other. Note: Web Clipper notes store a URL in `source` — these should be flagged but with a note suggesting `/kb:process` to normalize.
- **E04 bad-date**: `date_added` not in YYYY-MM-DD format (flag ISO timestamps like `2024-08-30T00:00:00.000Z`)
- **E05 duplicate-url**: Same URL — or byte-identical body — across notes, including `inbox/`
- **E07 inbox-raw-schema**: Inbox note with `source` = a URL or no `status` field — repairable by the normalization in E07 (url←source, source←inferred type, date_added←created, status←inbox, strip Knowledge/inbox tag, drop published/created/description)
- **E06 status-mismatch**: Note in `inbox/` with status != inbox, or note in `Knowledge/` (not inbox/) with status == inbox

**WARNINGS (quality):**
- **W01 empty-tags**: Reference note with empty tags array
- **W02 empty-summary**: Reference note with empty or missing summary
- **W03 no-related**: Note without `## Related` section (orphan in graph)
- **W04 orphan-tag**: Note using a tag not defined in `_taxonomy.md`
- **W05 deprecated-tag**: Note using a tag in the Deprecated table
- **W06 stale-wiki**: Wiki article whose `last_compiled` is older than the newest source note for its topic. For tag-based topics: search by tag. For freeform topics (topic field is not a valid tag): search by topic keywords in content/summary, same as synthesize step 2
- **W07 stale-index**: `_system/index.md` `last_updated` > 14 days old, or its Stats counts diverge from the live note counts
- **W08 stub-body**: Reference note whose body contains "Pending processing" or "Content not yet fetched"

**INFO (suggestions):**
- **I01 synthesis-candidate**: Tag with 5+ source notes but no wiki article
- **I02 lonely-tag**: Tag used by only 1 note (potential taxonomy cleanup)
- **I03 short-summary**: Summary shorter than 10 words
- **I04 old-note**: Note older than 90 days with status reference (may need review)
- **I05 inbox-backlog**: > 10 notes in `inbox/`, or the oldest inbox note is > 30 days old

### 3. Present report

```
## KB Health Check

**Errors: N** | **Warnings: N** | **Info: N**

### Errors
- [E04] bad-date: firecracker-aws-microvms-rust.md — date "2024-08-12T00:00:00.000Z" should be "2024-08-12"
- [E05] duplicate-url: note1.md, note2.md — same URL "https://..."

### Warnings
- [W03] no-related: ia-presenter-markdown-presentations.md — no Related section
- [W04] orphan-tag: old-note.md — tag "bathroomfan" not in taxonomy

### Info
- [I01] synthesis-candidate: AI/Prompting has 8 sources, no wiki article
- [I02] lonely-tag: Arch/Distributed has only 1 note

N issues can be auto-fixed. Run `/kb:lint fix` to apply.
```

### 4. `/kb:lint fix` subcommand

Auto-fixable issues:
- **E04**: Convert ISO timestamps to YYYY-MM-DD via `mcp__obsidian__update_frontmatter`
- **E06**: Update status to match location via `mcp__obsidian__update_frontmatter`
- **W05**: Replace deprecated tags with mapped replacements via `mcp__obsidian__update_frontmatter`
- **E07**: normalize raw Web-Clipper schema (url←source, source←inferred type, date_added←created, status←inbox, strip Knowledge/inbox tag, drop published/created/description)
- **W07**: regenerate the index via `/kb:index`

Workflow:
1. List all auto-fixable issues with proposed changes
2. Ask user to approve: "Fix all N issues?" (yes / review one-by-one / cancel)
3. Apply fixes sequentially via `mcp__obsidian__update_frontmatter` (merge: true)
4. Report: "Fixed N issues. Run `/kb:lint` again to verify."

### 5. `/kb:lint urls` subcommand

For each note with a `url` field:
1. Attempt `WebFetch` on the URL
2. Classify: OK, redirect (URL changed), dead (HTTP error/timeout), auth-wall (login page)
3. Report results:
   ```
   URL Check: N notes checked
   ✓ OK: X
   ⚠ Redirect: Y (suggest updating URLs)
   ✗ Dead: Z (suggest archiving or removing)
   ? Auth-wall: W (cannot verify)
   ```
