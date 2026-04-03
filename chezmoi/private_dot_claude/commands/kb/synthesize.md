Create or update a wiki article that synthesizes knowledge from multiple source notes on a topic.

## Usage

`/kb:synthesize <topic>` — create or incrementally update wiki article
`/kb:synthesize <topic> --full` — full rewrite from all sources

Topics can be taxonomy tags OR freeform descriptions:
- `/kb:synthesize AI/RAG` — matches a specific tag
- `/kb:synthesize "Rust LLM tools"` — freeform topic spanning Dev/Rust + AI/LLMs
- `/kb:synthesize "indie app business"` — freeform topic spanning Business/SaaS + Business/Startups

## Instructions

### 1. Resolve topic

Parse `$ARGUMENTS` for topic. Strip `--full` flag if present.

**Two modes:**

**Tag-based topic** (input looks like a taxonomy tag):
- If input exactly matches a tag (e.g., "AI/RAG") → use it, search by tag
- If input is a substring matching exactly one subtag (e.g., "RAG" → AI/RAG) → use that tag
- If input matches multiple tags (e.g., "AI") → list matches with note counts, ask user to pick
- If no tags match → fall through to freeform mode

**Freeform topic** (input is a description, not a tag):
- Use the topic string as-is for the wiki article title
- Find source notes by content/summary search (step 2) rather than tag match
- The wiki article's `topic` field stores the freeform string (not a tag)
- Tags on the wiki article are inferred from the source notes' tags (union of most common)

### 2. Find source notes

a. **For tag-based topics**: Use `mcp__obsidian__search_notes` with `searchFrontmatter: true` for the tag
b. **For freeform topics**: Use `mcp__obsidian__search_notes` with `searchContent: true` and `searchFrontmatter: true` for the topic keywords. Read frontmatter of results to confirm relevance.
c. Deduplicate results. Filter to `Main/Knowledge/` only (exclude wiki/, inbox/, _system/)
d. Read frontmatter of all matches via `mcp__obsidian__get_frontmatter`
e. Exclude notes with `type: wiki` (don't synthesize from wiki articles)

If fewer than 2 source notes found: "Only N source(s) for '<topic>'. Need at least 2 to synthesize."

**Coherence check**: Before proceeding, scan the source notes' titles and summaries. If they cover very different sub-topics with no meaningful overlap (e.g., 4 GameDev notes about hex maps, isometric builders, game studios, and RTS games), warn:

```
Found N notes but they cover distinct sub-topics:
  - Procedural generation (hex-map-wave-function-collapse)
  - World building (middle-earth-isometric-builder)
  - AI agent templates (claude-code-game-studios)
  - RTS games (widelands-open-source-rts)

A synthesis of all 4 may be incoherent.
Options:
  1. Synthesize anyway (broad overview)
  2. Pick a subset (e.g., just procedural generation notes)
  3. Cancel
```

### 3. Check for existing wiki article

- For tag-based: check `Main/Knowledge/wiki/<tag-kebab>.md`
- For freeform: check `Main/Knowledge/wiki/<topic-kebab>.md`
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
   topic: "<tag or freeform string>"
   tags: [<primary tags from sources>, Reference]
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
