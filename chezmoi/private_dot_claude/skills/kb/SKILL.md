---
name: kb
description: >-
  Obsidian knowledge base via MCP. Triggers: (1) Save links ("save this", "bookmark", URL with intent to save),
  (2) Process inbox ("tag my notes", "process inbox"), (3) Search ("find notes about X", "what do I have on Y"),
  (4) Taxonomy ("show tags", "add tag"), (5) Retag ("fix tags", "rename tag"),
  (6) Synthesize wiki ("synthesize topic", "compile wiki"), (7) Health check ("lint", "check KB"),
  (8) Capture answer ("capture this", "save this answer", "remember this"),
  (9) KB overview ("index", "what's in my KB"),
  (10) Topics ("discover topics", "restructure my taxonomy", "what topics emerged", "cluster my notes"),
  (11) Review ("review my KB", "kb review", "do my weekly review", "process the digest", responding to the weekly digest nudge),
  (12) Surface ("what do I have related to X", "surface notes for my current project", "what's relevant to what I'm working on now").
  Requires Obsidian MCP server (mcpvault). Topics (10), Review (11), and Surface (12) additionally use the local `kb-engine` CLI.
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

Search runs through the local `kb-engine` **hybrid search** (semantic + keyword) per the
updated `/kb:search` procedure — the engine replaced the old Obsidian full-text search here.

1. **Tag queries** (`tag:X`) use the Obsidian MCP tag search (`mcp__obsidian__search_notes`,
   `searchFrontmatter: true`); the engine does not index tag filters yet.
2. **Everything else** → `kb-engine --vault "<Main>" search "<query>" --json`; take the top
   N (default 10). Read each hit's frontmatter via `mcp__obsidian__get_frontmatter` and
   present title, source, tags, summary. Mark `[wiki]` / `[derived]` types.
3. **Fallback**: if the engine call fails, fall back to `mcp__obsidian__search_notes`
   full-text and say so explicitly ("engine unavailable — keyword-only results").
4. When the user opens a result, log it fire-and-forget:
   `kb-engine --vault "<Main>" log-event --kind open --path "<path>"`.
5. **Probe-on-miss**: if the user says a result was "not it" and then finds the right note,
   append a probe to `_system/probes.yaml` (query = their phrasing, expect = found path) and
   tell them the suite grew.
6. Post-search: user can archive ("archive X" → set status to archived), open, or retag from results.

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

**Triggers**: "synthesize", "compile wiki", "summarize topic", "create wiki article",
"what should I synthesize", `/kb:synthesize`

**Suggesting targets (no topic given):** run the engine to find topics that have
enough material but no wiki article yet, then offer to compile them:

```bash
kb-engine synthesis-candidates --min 5 --json
```

Returns `{candidates:[{slug, label, size}]}` — discovered/manual topics with **≥5
members** and **no** `Knowledge/wiki/<slug>.md`, biggest first. Present them and offer
`/kb:synthesize <slug>` for each. This is in **addition** to the existing tag-based
suggestion (any specific subtag with 5+ sources and no wiki, skipping cross-cutting tags
like Tutorials/Reference/Inspiration/Tools).

**Compiling a given topic:**

1. Resolve topic — can be a taxonomy tag (`AI/RAG`) or freeform description (`Rust LLM tools`).
2. Find source notes by tag match (tag-based) or content search (freeform).
3. **Coherence check** — if notes cover distinct sub-topics, warn before synthesizing.
4. Create or incrementally update wiki article in `Knowledge/wiki/` (see [references/wiki-schema.md](references/wiki-schema.md)).
5. Update source notes with backlinks to wiki article.
6. Update index.

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

### 10. Topics

**Triggers**: "discover topics", "restructure my taxonomy", "what topics emerged", "cluster my notes", `/kb:topics`

This operation is **engine-driven**: the local `kb-engine` CLI does the deterministic
compute (embedding, clustering, diffing, file writes); **Claude supplies the naming
and judgment** the engine deliberately omits. The engine is **LLM-free** — its topic
labels are raw keyword slugs (e.g. `rust-async-tokio`); your job is to turn those into
human-readable labels and area names, present the restructure as a reviewable diff, and
gate the write-backs.

Assume `kb-engine` is on `PATH` (Nix wrapper) and the vault is the iCloud `Main` dir.
Use `--json` on every command so you can parse the output.

**Flow:**

1. **Sync** the cache so topics reflect the current vault:
   ```bash
   kb-engine sync
   ```

2. **Discover** topics. Use `--sticky` so existing approved (manual/active) topics keep
   their members and only the residual is clustered into new proposals:
   ```bash
   kb-engine topics discover --sticky --json
   ```
   Optionally run `kb-engine topics areas --json` to group topics into broader areas.

3. **Diff against the existing taxonomy** to see how discovered structure maps onto the
   tags already in `_system/_taxonomy.md`:
   ```bash
   kb-engine topics diff-taxonomy --json
   ```
   Returns `{mapping, new_topics, orphan_tags, covered_topics}`:
   - `mapping` — each existing tag → ranked aligned topics (Jaccard overlap)
   - `new_topics` — discovered topics no tag covers (**structure the data found that the taxonomy lacks**)
   - `orphan_tags` — tags no topic aligns with (candidates to deprecate/merge)
   - `covered_topics` — topics that align with an existing tag

4. **LLM-name (Claude's job):** read the keyword-slug topics + their member notes and
   propose nice human labels and area names. The engine cannot do this — naming and
   judgment are yours. Use `kb-engine topics list --json` to see slugs/members; you can
   also `kb-engine topics add <slug> --label "<Nice Label>" --description "<…>"` to anchor
   a manual topic.

5. **Present the restructure diff + proposals to the user.** Show: new topics (with your
   proposed labels), how they map to existing tags, orphan tags, and proposed area names.
   **Do not write anything yet** — wait for approval.

6. **On approval, render** the MOCs + taxonomy proposals (idempotent, render-not-append):
   ```bash
   kb-engine topics render --json
   ```
   Writes `<vault>/_system/topics/index.md` (areas→topics outline) + one MOC per topic at
   `<vault>/_system/topics/<slug>.md`, and splices a proposals table into
   `<vault>/_system/_taxonomy.md` between `<!-- KB-PROPOSALS:START -->` … `<!-- KB-PROPOSALS:END -->`
   markers (preserving the rest of the file). `_system/topics/` is outside `Knowledge/`,
   so `sync` never embeds these MOCs.

7. **Gated apply** — only after explicit user confirmation, write `topic/<slug>` tags into
   member notes' frontmatter. The command itself IS the gate; there is no implicit apply.
   It defaults to `--status active`, so discovered proposals stay `proposed` until promoted:
   ```bash
   kb-engine topics apply --status active --json
   ```
   Idempotent; reports `{n_changed, n_tags_added, skipped_missing}`. Member files missing
   on disk are skipped and reported — surface those to the user, never silently drop them.

**Conventions:**
- MOCs live in `_system/topics/` (regenerable; excluded from embedding).
- Topic membership is recorded on notes via the `topic/<slug>` frontmatter tag (namespaced
  under `topic/`, distinct from human taxonomy tags like `Dev/Rust`).
- The engine is the source of compute + file writes; Claude is the source of naming + the
  approval gate. Never run `topics apply` without the user's explicit go-ahead.

See `/kb:topics` for the per-subcommand command reference.

### 11. Review

**Triggers**: "review my KB", "kb review", "do my weekly review", "process the digest",
responding to the weekly digest notification, `/kb:review`

The **nudged ~5-minute pass** that keeps the KB self-maintaining. A weekly **launchd**
agent (Nix `modules.dev.kb-engine.schedule`) runs the deterministic, LLM-free
`kb-engine pipeline` (sync → apply active-topic tags → sticky-discover proposals →
write digest) and fires a notification. The pipeline never silently mis-tags: it
applies `topic/<slug>` tags only for **active** (approved) topics, so freshly
discovered clusters stay `proposed` until you confirm them here. This Review op is
the human half — the judgment the engine deliberately omits.

The digest at `Main/_system/kb-digest.md` is the **entry point**: it lists the inbox
backlog, proposals awaiting naming/approval, and unfiled notes. Read it first.

**Flow:**

1. **Refresh, then read the digest.** The digest is only as fresh as the last pipeline run
   (weekly via launchd, or whenever last run by hand), so off-cycle reviews can show stale
   counts. Refresh the live counts first — fast and LLM-free:
   `kb-engine --vault "<Main>" digest --json`. Then `mcp__obsidian__read_note` on
   `Main/_system/kb-digest.md`. Its "Needs review" checklist drives the rest of this pass.
   If everything is `- [x] Nothing to review.`, say so and stop.

2. **Process new inbox items** (digest "inbox backlog" > 0). Run the **Process**
   operation (op 2 / `/kb:process`) over `Knowledge/inbox/`: for each unprocessed note,
   fetch content (tiered `WebFetch` → `agent-browser`, see
   [references/content-fetching.md](references/content-fetching.md)), generate a summary,
   and suggest tags. **Auto-apply high-confidence tags**; **batch the borderline ones**
   and ask the user once. File approved notes from `inbox/` into `Knowledge/`. Dedup is
   already handled at ingest by `kb-engine import-things`, so expect no duplicate URLs.

3. **Name & govern topic proposals** (digest "proposals awaiting review" > 0). Run the
   **Topics** operation (op 10 / `/kb:topics`): read the keyword-slug proposals + their
   member notes, propose human labels and area names, present the restructure as a
   reviewable diff, and on approval `kb-engine topics render`. Promote a proposal you
   want to keep into an approved, sticky topic with
   `kb-engine topics add <slug> --label "<Label>" --description "<…>"`.

4. **Apply newly-approved topics (optional, gated).** Only after the user confirms, write
   `topic/<slug>` tags for the topics just promoted to active:
   ```bash
   kb-engine topics apply --status active --json
   ```
   This is the only note-mutating step and running it IS the gate. Surface any
   `skipped_missing` member paths; never drop them silently.

5. **Wrap up.** Optionally `kb-engine digest` (or just re-run `pipeline`) to refresh
   `kb-digest.md`, and report what was processed, named, and applied.

Note: the launchd job refreshes the digest weekly, so the backlog can't silently rot —
the nudge keeps reminding you until the checklist is clear.

See `/kb:review` for the command reference.

### 12. Surface

**Triggers**: "what do I have related to X", "surface notes for my current project",
"what's relevant to <note>", "what's relevant to what I'm working on now", `/kb:surface`

Proactive surfacing — given **what you're working on now** (a description, a project, or
a specific note), return the most semantically relevant KB notes. This is **engine-driven
and read-only**: the local `kb-engine` does the retrieval; you present and offer follow-ups.
Assume `kb-engine` is on `PATH` (Nix wrapper) over the iCloud `Main` vault, and use
`--json` so you can parse it.

**Flow:**

1. Decide the mode from what the user gave you:
   - **A description / project / topic** → query mode:
     ```bash
     kb-engine related --query "<the context, e.g. long-term memory for agents>" --limit 10 --json
     ```
   - **A specific note** (a path or an obvious note reference) → note mode (surfaces its
     nearest neighbors by mean-vector cosine, excluding the note itself):
     ```bash
     kb-engine related --to "Knowledge/<note>.md" --limit 10 --json
     ```
   Pass **exactly one** of `--query` / `--to` (the command errors otherwise).

2. Both emit `{hits:[{note_path, title, score}]}`, ranked best-first. If `hits` is empty,
   say nothing matched and stop.

3. **Present** the ranked notes (title + path + score). Then offer follow-ups:
   - open one in Obsidian / read it (`mcp__obsidian__read_note`),
   - `/kb:synthesize` a wiki if several relevant notes cluster on one topic,
   - refine the query.

The engine never mutates the vault here — surfacing is purely read-only retrieval.

See `/kb:surface` for the command reference.

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
