---
name: kb
description: >-
  Knowledge base management for Obsidian vault via MCP. Use when the user wants to:
  (1) Save a link or article ("save this", "bookmark this", "add to KB", any URL shared with intent to save),
  (2) Process or tag saved content ("process inbox", "tag my notes", "what's in my inbox"),
  (3) Search their knowledge base ("find my notes about X", "what do I have on Y", "search KB for Z"),
  (4) Manage taxonomy ("show tags", "add a tag", "rename tag", "what tags do I have"),
  (5) Retag notes after taxonomy changes ("retag", "update tags", "fix tags").
  Requires the Obsidian MCP server (mcpvault). Vault structure: Knowledge/ for notes, Knowledge/inbox/ for unprocessed, _system/_taxonomy.md for tag definitions.
---

# Knowledge Base Manager

Obsidian-based knowledge base with AI-assisted tagging and retrieval.

## Vault Layout

```
Main/
├── Knowledge/          # Processed notes (status: reference)
│   └── inbox/          # Unprocessed notes (status: inbox)
├── _system/
│   ├── _taxonomy.md    # Tag definitions and proposals
│   ├── DECISIONS.md    # Design rationale
│   └── templates/      # Note templates
```

## Key References

- **Note schema**: See [references/schema.md](references/schema.md) for frontmatter fields and allowed values.
- **Taxonomy guide**: See [references/taxonomy-guide.md](references/taxonomy-guide.md) for tag structure, evolution rules, and confidence-based tagging.
- **Content fetching**: See [references/content-fetching.md](references/content-fetching.md) for the tiered fetch strategy (WebFetch → agent-browser), Twitter auth, and error handling rules.
- **Graph links**: See [references/graph-links.md](references/graph-links.md) for cross-note linking strategy that builds the Obsidian graph.

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
      - **Tier 1**: `WebFetch` (fast, works for static pages)
      - **Tier 2**: `agent-browser` (for JS-heavy pages: Twitter, YouTube, SPAs)
      - Twitter/X URLs use saved auth state at `~/.agent-browser/twitter-auth.json`
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

### 3. Search

**Triggers**: "find notes about", "what do I have on", "search KB", `/kb:search`

1. Use `mcp__obsidian__search_notes` with `searchContent: true`, `searchFrontmatter: true`, `limit: 20`.
2. Filter to `Main/Knowledge/` path only.
3. For `tag:` prefix, search frontmatter only.
4. Read frontmatter of matches via `mcp__obsidian__get_frontmatter`.
5. Present with title, source, tags, summary, context.

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
