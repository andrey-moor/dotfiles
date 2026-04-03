Create or update a wiki article that synthesizes knowledge from multiple source notes on a topic.

## Usage

`/kb:synthesize <topic>` — create or incrementally update wiki article
`/kb:synthesize <topic> --full` — full rewrite from all sources

## Instructions

### 1. Resolve topic

- Parse `$ARGUMENTS` for topic (tag like "AI/RAG" or free text like "RAG retrieval")
- Read taxonomy from `Main/_system/_taxonomy.md` to validate/resolve to a tag
- If ambiguous, ask user to clarify

### 2. Find source notes

a. **Tag search**: Use `mcp__obsidian__search_notes` with `searchFrontmatter: true` for the topic tag
b. **Content search**: Search for topic keywords with `searchContent: true`
c. Deduplicate results. Filter to `Main/Knowledge/` only (exclude wiki/, inbox/, _system/)
d. Read frontmatter of all matches via `mcp__obsidian__get_frontmatter`
e. Exclude notes with `type: wiki` (don't synthesize from wiki articles)

If fewer than 2 source notes found: "Only N source(s) for <topic>. Need at least 2 to synthesize."

### 3. Check for existing wiki article

- Check if `Main/Knowledge/wiki/<topic-kebab>.md` exists via `mcp__obsidian__get_frontmatter`
- If not exists or `--full` flag: go to step 4 (full create)
- If exists: go to step 5 (incremental update)

### 4. Full create

a. Read content of all source notes (use `mcp__obsidian__read_note` or `mcp__obsidian__read_multiple_notes`)
b. Synthesize into wiki article with this structure:

```markdown
## Overview
Brief synthesis — what this topic area is about and why it matters.
Draw from the collective understanding across all sources.

## Key Concepts
Core ideas distilled from source notes. Not a list of sources —
a coherent narrative of the important concepts.

## Techniques & Approaches
Specific methods, tools, patterns found across sources.
Compare where sources offer different approaches.

## Trade-offs & Comparisons
Where sources agree, disagree, or offer different perspectives.
Highlight tensions and nuances.

## Open Questions
Gaps in the KB's coverage. Areas worth exploring further.
Topics mentioned across sources but not deeply covered.

## Sources
- [[source-note-1]] — what this source contributes
- [[source-note-2]] — what this source contributes
```

c. Write via `mcp__obsidian__write_note` to `Main/Knowledge/wiki/<topic-kebab>.md`:
   ```yaml
   ---
   type: wiki
   title: "<Topic> — Knowledge Synthesis"
   topic: "<tag>"
   tags: [<tag>, Reference]
   sources:
     - source-note-1
     - source-note-2
   last_compiled: "<today YYYY-MM-DD>"
   summary: "<1-2 sentence overview>"
   status: reference
   ---
   ```

### 5. Incremental update

a. Read existing wiki article
b. Compare `sources` array against found source notes
c. Identify new sources not yet in the array
d. If no new sources: "Wiki article is up to date (N sources). Use `--full` to force rewrite."
e. If new sources:
   - Read their content
   - Read existing wiki article content
   - Weave new insights into existing sections (don't rewrite unchanged sections)
   - Add new sources to the Sources section
   - Update `sources` array and `last_compiled` in frontmatter via `mcp__obsidian__update_frontmatter`
   - Update content via `mcp__obsidian__write_note` (preserve frontmatter, rewrite body)

### 6. Update source notes

For each source note referenced by the wiki article:
- Check if it already has a Related link to the wiki article
- If not, append via `mcp__obsidian__patch_note`:
  ```
  - [[wiki/<topic-kebab>]] — synthesized wiki article
  ```

### 7. Update index

Regenerate `Main/_system/index.md` with current KB stats — read all notes, compute counts by status/source/tag, list recent additions, list wiki articles with source counts and last_compiled dates, compute graph health, write via `mcp__obsidian__write_note`.

### 8. Report

```
Synthesized: wiki/<topic-kebab>.md
Sources: N notes compiled (M new since last compile)
Sections: Overview, Key Concepts, Techniques, Trade-offs, Open Questions

View in Obsidian: Knowledge/wiki/<topic-kebab>.md
```
