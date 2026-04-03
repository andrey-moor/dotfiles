---
name: kb
description: >-
  Obsidian knowledge base via MCP. Triggers: (1) Save links ("save this", "bookmark", URL with intent to save),
  (2) Process inbox ("tag my notes", "process inbox"), (3) Search ("find notes about X", "what do I have on Y"),
  (4) Taxonomy ("show tags", "add tag"), (5) Retag ("fix tags", "rename tag"),
  (6) Synthesize wiki ("synthesize topic", "compile wiki"), (7) Health check ("lint", "check KB"),
  (8) Capture answer ("capture this", "save this answer", "remember this"),
  (9) KB overview ("index", "what's in my KB").
  Requires Obsidian MCP server (mcpvault).
---

# Knowledge Base Manager

Obsidian-based knowledge base with AI-assisted tagging, synthesis, and retrieval.

## Vault Layout

```
Main/
├── Knowledge/          # Source + derived notes (status: reference)
│   ├── inbox/          # Unprocessed notes (status: inbox)
│   └── wiki/           # Synthesized concept articles (type: wiki)
├── _system/
│   ├── _taxonomy.md    # Tag definitions and proposals
│   ├── DECISIONS.md    # Design rationale
│   ├── INSTRUCTIONS.md # Usage guide
│   ├── index.md        # Auto-maintained KB overview
│   └── templates/      # Note templates
```

## Key References

- **Note schema**: See [references/schema.md](references/schema.md) for frontmatter fields and allowed values.
- **Wiki schema**: See [references/wiki-schema.md](references/wiki-schema.md) for wiki article structure and update rules.
- **Taxonomy guide**: See [references/taxonomy-guide.md](references/taxonomy-guide.md) for tag structure, evolution rules, and confidence-based tagging.
- **Content fetching**: See [references/content-fetching.md](references/content-fetching.md) for the tiered fetch strategy (WebFetch → agent-browser), Twitter auth, and error handling rules.
- **Graph links**: See [references/graph-links.md](references/graph-links.md) for cross-note linking strategy that builds the Obsidian graph.
- **Lint rules**: See [references/lint-rules.md](references/lint-rules.md) for all health check rules and auto-fix capabilities.

Always read the live taxonomy at `Main/_system/_taxonomy.md` before tagging.

## Operations

### 1. Add

**Triggers**: "save this", "bookmark", URL shared with intent to save, `/kb:add`

1. Extract URL and optional context (user's reason for saving).
2. Generate kebab-case filename from URL path (max 60 chars).
3. Infer `source` from URL pattern (see [references/schema.md](references/schema.md)).
4. Create note via `mcp__obsidian__write_note`:
   - **path**: `Main/Knowledge/inbox/<filename>.md`
   - **frontmatter**: `{title, url, source, date_added, tags: [], summary: "", status: "inbox", context, author: ""}`
   - **content**: `## Notes\n\nPending processing.`
5. Confirm: `Added to inbox: <filename> | Source: <source>`

### 2. Process

**Triggers**: "process inbox", "tag my notes", "what's in my inbox", `/kb:process`

1. List `Main/Knowledge/inbox/` via `mcp__obsidian__list_directory`.
2. Read taxonomy from `Main/_system/_taxonomy.md`.
3. For each note:
   a. Read frontmatter via `mcp__obsidian__get_frontmatter`.
   b. Fetch URL content using tiered strategy (see [references/content-fetching.md](references/content-fetching.md)):
      - **Tier 0**: `gh` CLI (for GitHub repos)
      - **Tier 1**: `WebFetch` (fast, works for static pages)
      - **Tier 2**: `agent-browser` (for JS-heavy pages: Twitter, YouTube, SPAs)
      - **Never silently skip failures** — report auth walls, errors, partial content to user
   c. Generate 1-3 sentence summary from fetched content.
   d. Suggest tags with confidence (see [references/taxonomy-guide.md](references/taxonomy-guide.md)).

4. **All high confidence** → auto-apply, report:
   ```
   ✓ note-name — Tags: Dev/Rust, Tools (auto) — "summary..."
   ```

5. **Any uncertainty** → show and ask:
   ```
   ? note-name
     Summary: "..." | Suggested: Arch/Distributed (high), Dev/Go (medium)
     Context: <empty> — Why did you save this?
   ```

6. Finalize approved notes:
   - Update frontmatter via `mcp__obsidian__update_frontmatter` (merge: true)
   - Find related notes (see [references/graph-links.md](references/graph-links.md)) and append `## Related` section with wiki-links
   - Move to `Main/Knowledge/` via `mcp__obsidian__move_note`
7. Propose new tags → append to Proposals table in `_taxonomy.md` via `mcp__obsidian__patch_note`.
8. **Wiki suggestion**: Check if any specific subtags have 5+ sources without a wiki article. Skip cross-cutting tags (Tutorials, Reference, Inspiration, Tools). Suggest `/kb:synthesize <tag>` for candidates.
9. **Update index**: Regenerate `_system/index.md` (same logic as `/kb:index`).

### 3. Search

**Triggers**: "find notes about", "what do I have on", "search KB", `/kb:search`

1. Use `mcp__obsidian__search_notes` with `searchContent: true`, `searchFrontmatter: true`, `limit: N` (default 20, configurable via `--limit`).
2. Filter to `Main/Knowledge/` path (includes wiki/ and source notes).
3. For `tag:` prefix, search frontmatter only.
4. Read frontmatter of matches via `mcp__obsidian__get_frontmatter`.
5. Present with title, source, tags, summary, context. Mark `[wiki]` and `[derived]` note types.
6. Post-search: user can archive notes ("archive X" → set status to archived), view full content, or retag from results.

### 4. Taxonomy

**Triggers**: "show tags", "manage taxonomy", "what tags", `/kb:taxonomy`

| Subcommand | Action |
|---|---|
| *(default)* | Read `_taxonomy.md` + `mcp__obsidian__list_all_tags` → display with counts |
| `proposals` | Show pending proposals from Proposals table |
| `approve <tag>` | Add to taxonomy via `patch_note`, bump version via `update_frontmatter` |
| `reject <tag>` | Mark rejected in Proposals table via `patch_note` |
| `add <Cat/Tag> <desc>` | Insert in taxonomy via `patch_note`, bump version |
| `deprecate <tag> [new]` | Move to Deprecated table, suggest retag |

### 5. Retag

**Triggers**: "retag", "fix tags", "rename tag", `/kb:retag`

| Subcommand | Action |
|---|---|
| *(default)* | Scan Knowledge/ for deprecated, orphan, or missing tags. Present analysis, ask how to proceed. |
| `rename <old> <new>` | Update all notes via `update_frontmatter`, update `_taxonomy.md` |
| `merge <t1> <t2> <target>` | Replace both with target, deduplicate, update taxonomy |
| `review` | Re-evaluate each note's tags against content, suggest improvements |

### 6. Synthesize

**Triggers**: "synthesize", "compile wiki", "summarize topic", "create wiki article", `/kb:synthesize`

1. Resolve topic — can be a taxonomy tag (`AI/RAG`) or freeform description (`Rust LLM tools`).
2. Find source notes by tag match (tag-based) or content search (freeform).
3. **Coherence check** — if notes cover distinct sub-topics, warn before synthesizing.
4. Create or incrementally update wiki article in `Knowledge/wiki/` (see [references/wiki-schema.md](references/wiki-schema.md)).
5. Update source notes with backlinks to wiki article.
5. Update index.

### 7. Lint

**Triggers**: "lint", "health check", "check KB", "validate notes", `/kb:lint`

| Subcommand | Action |
|---|---|
| *(default)* | Full health check report (errors, warnings, info). See [references/lint-rules.md](references/lint-rules.md). |
| `fix` | Auto-fix mechanical issues (date formats, status mismatches, deprecated tags). Asks before applying. |
| `urls` | Check for dead URLs (slow, opt-in). |

### 8. Capture

**Triggers**: "capture this answer", "save this to KB", "remember this", `/kb:capture`

1. Extract the most recent substantive answer from conversation.
2. Identify KB notes referenced → `informed_by` field.
3. Format as structured note with `source: derived`.
4. Preview for user approval.
5. Write to `Knowledge/` with bidirectional links.
6. Update index.

### 9. Index

**Triggers**: "index", "KB overview", "what's in my KB", `/kb:index`

Regenerate `_system/index.md` with: stats, recent additions, topics by size, wiki articles, graph health.

## MCP Tool Reference

| Operation | Tool |
|---|---|
| Read note content + frontmatter | `mcp__obsidian__read_note` |
| Read frontmatter only | `mcp__obsidian__get_frontmatter` |
| Create new note | `mcp__obsidian__write_note` |
| Update frontmatter fields | `mcp__obsidian__update_frontmatter` (merge: true) |
| Edit note body text | `mcp__obsidian__patch_note` (string replacement) |
| Move/rename note | `mcp__obsidian__move_note` |
| List folder contents | `mcp__obsidian__list_directory` |
| Full-text search | `mcp__obsidian__search_notes` |
| Get all tags + counts | `mcp__obsidian__list_all_tags` |
| Batch read multiple notes | `mcp__obsidian__read_multiple_notes` |
