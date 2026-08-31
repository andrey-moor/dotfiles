Retag knowledge base notes after taxonomy changes. Updates all downstream systems: source notes, wiki articles, Bases views, and index.

## Usage

`/kb:retag` — interactive retag session
`/kb:retag rename <old-tag> <new-tag>` — rename a tag across all notes
`/kb:retag merge <tag1> <tag2> <target-tag>` — merge two tags into one
`/kb:retag review` — find notes that may need retagging based on content

All subcommands support `--dry-run` — show what would change without applying.

## Instructions

### Dry-run mode

If `$ARGUMENTS` contains `--dry-run`:
- Run the full analysis and compute all changes
- Present a diff-style preview:
  ```
  ## Retag Preview (dry-run)

  Would rename AI/Prompting → AI/PromptEng:
    - 17 source notes: tags updated
    - 1 wiki article: wiki/ai-prompting.md → wiki/ai-prompt-eng.md
    - tags.base: view "AI" unaffected (parent category unchanged)
    - Index: would regenerate

  No changes applied. Run without --dry-run to apply.
  ```
- Do NOT apply any changes

### Default: Interactive retag

1. Read `Main/_system/_taxonomy.md` — check for recent changes (Deprecated table, new tags).
2. List all notes in `Main/Knowledge/` AND `Main/Knowledge/wiki/` via `mcp__obsidian__list_directory`, then read their frontmatter via `mcp__obsidian__get_frontmatter`.
3. Identify issues:
   - Notes using deprecated tags (compare against Deprecated table in `_taxonomy.md`)
   - Notes using tags not in the taxonomy (orphan tags)
   - Notes with empty tags array
   - Notes that might benefit from newly added tags
   - Wiki articles with stale `topic` field matching deprecated/renamed tags
   - Wiki articles with deprecated tags in their `tags` array (catches freeform-topic wikis where `topic` isn't a tag but `tags` contains the deprecated tag)

4. Present findings:
   ```
   ## Retag Analysis

   **Deprecated tags in use:** N notes
     - OldTag → NewTag: note1.md, note2.md

   **Orphan tags (not in taxonomy):** N notes
     - UnknownTag: note3.md

   **Untagged notes:** N notes
     - note4.md, note5.md

   **Stale wiki articles:** N
     - wiki/ai-prompting.md — topic "AI/Prompting" was renamed

   **Candidates for new tags:** N notes
     - note6.md could use NewlyAdded/Tag based on content
   ```

5. Ask user how to proceed:
   - "Fix all automatically" — apply all suggested changes
   - "Review one by one" — step through each change
   - "Fix deprecated only" — only handle deprecated tag replacements

6. Apply tag changes via `mcp__obsidian__update_frontmatter` with merge: true:
   ```json
   {"tags": ["NewTag1", "NewTag2"]}
   ```

### `rename <old-tag> <new-tag>`

**Source + derived notes:**
1. Find all notes with `old-tag` in their tags via frontmatter scan (include `Main/Knowledge/` AND `Main/Knowledge/wiki/`).
2. For each note, compute new tags array (replace old with new) and update via `mcp__obsidian__update_frontmatter`.

**Taxonomy:**
3. Update `_taxonomy.md` body via `mcp__obsidian__patch_note` — remove old tag line, ensure new tag line exists.
4. Add to Deprecated table via `mcp__obsidian__patch_note` (append row to table in note body).

**Wiki articles:**
5. Check `Main/Knowledge/wiki/` for articles with `topic: <old-tag>`:
   - Update `topic` field via `mcp__obsidian__update_frontmatter`
   - Update `tags` array (replace old with new)
   - Rename the wiki file if it was named after the old tag:
     e.g., `wiki/ai-prompting.md` → `wiki/ai-prompt-eng.md` via `mcp__obsidian__move_note`
   - Update all wiki-links in source notes that referenced the old wiki filename via `mcp__obsidian__patch_note`
     (search for `[[wiki/old-name]]` and replace with `[[wiki/new-name]]`)

**Bases views:**
6. Check if `Main/Knowledge/tags.base` has `file.hasTag("<old-tag>")` or a view named after the old tag.
   If so, warn the user:
   ```
   ⚠ tags.base has a view using the old tag. Update manually in Obsidian,
     or I can regenerate the .base file on the filesystem.
   ```
   If user approves, update the .base file via Bash.

**Index:**
7. Regenerate `_system/index.md`.

8. Report: `Renamed <old-tag> → <new-tag> in N notes, M wiki articles. Index updated.`

### `merge <tag1> <tag2> <target-tag>`

Same as rename but for two source tags:

1. Find all notes with either `tag1` or `tag2` in their tags.
2. For each note, compute new tags array (replace both with target, deduplicate) and update via `mcp__obsidian__update_frontmatter`.
3. Update `_taxonomy.md` body via `mcp__obsidian__patch_note`.
4. Add both to Deprecated table via `mcp__obsidian__patch_note`.
5. **Wiki articles:** If wiki articles exist for either tag's topic, merge them:
   - If only one wiki exists: update its `topic` to target tag, rename file
   - If both exist:
     - **Primary** = the article with more sources (or older `last_compiled` if tied)
     - Read both articles' content
     - Merge: for each section (Overview, Key Concepts, etc.), combine content from both, deduplicate overlapping points
     - Union all `sources` arrays, deduplicate
     - Write merged content to primary article, update `topic` and `tags`
     - Rename primary to target tag filename if needed via `mcp__obsidian__move_note`
     - Delete secondary article via Bash `rm` on the filesystem
     - Update all backlinks: search for `[[wiki/secondary-name]]` across all notes, replace with `[[wiki/primary-name]]` via `mcp__obsidian__patch_note`
6. **Bases views:** Warn if views reference either old tag.
7. **Index:** Regenerate `_system/index.md`.
8. Report: `Merged <tag1> + <tag2> → <target-tag> in N notes`

### `review`

1. For each note in `Main/Knowledge/` AND `Main/Knowledge/wiki/`, read content and current tags.
2. Use the same confidence-based tagging approach as `/kb:process` (see taxonomy-guide.md):
   - **High confidence**: Content clearly matches a tag not currently applied
   - **Medium confidence**: Reasonable inference
   - Only suggest tags at medium+ confidence
3. Present suggestions with confidence levels:
   ```
   ? note-name.md
     Current tags: AI/LLMs, Reference
     Suggested additions:
       + AI/Prompting (high) — note is primarily about prompting techniques
       + Tutorials (medium) — contains step-by-step examples
   ```
4. Ask user to approve/reject each suggestion.
5. Apply approved changes via `mcp__obsidian__update_frontmatter`.
6. Regenerate index after changes.
