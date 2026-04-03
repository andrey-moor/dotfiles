Search the knowledge base by topic, tags, or content.

## Usage

`/kb:search <query>`
`/kb:search <query> --limit N` — show up to N results (default: 20)

Examples:
- `/kb:search sprite generation`
- `/kb:search tag:AI/RAG`
- `/kb:search rust FUSE filesystem`
- `/kb:search AI agents --limit 50`

## Instructions

1. Parse `$ARGUMENTS`:
   - Extract `--limit N` if present (default: 20)
   - Remaining text is the search query

2. **Search strategy** — run these in parallel:

   a. **Full-text search**: Use `mcp__obsidian__search_notes` with the query string, `searchContent: true`, `searchFrontmatter: true`, `limit: <parsed limit>`. This searches both note content and frontmatter (tags, summary, context, title) in one call.

   b. **Tag listing**: Use `mcp__obsidian__list_all_tags` to find tags matching query terms, then identify which notes use those tags.

3. Filter all results to notes under `Main/Knowledge/` path only (includes `wiki/`). Exclude `_system/` and `Archive/` results.

4. If query starts with `tag:`, search only by tag match (exact prefix match). Use `mcp__obsidian__search_notes` with `searchFrontmatter: true` and the tag value as query.

5. For each matching note, read its frontmatter via `mcp__obsidian__get_frontmatter` to build the result display.

6. **Present results** sorted by relevance:
   ```
   ## KB Search: "<query>"

   **N results found**

   1. **Note Title** — [source] [wiki]
      Tags: AI/RAG, Tutorials
      Summary: "Brief summary..."
      Context: "why user saved it"
      → Main/Knowledge/note-name.md

   2. **Another Note** — [github]
      Tags: Dev/Rust, Tools
      Summary: "..."
      → Main/Knowledge/another-note.md
   ```

   Mark wiki articles with `[wiki]` and derived notes with `[derived]` after the source type.

7. If results hit the limit:
   ```
   Showing <limit> results. Use `/kb:search <query> --limit 50` for more.
   ```

8. If no results found:
   ```
   No results for "<query>" in Knowledge Base.

   Try broader terms or check Archive/ for old notes.
   ```

## Post-search actions

After presenting results, the user may ask to:
- **Archive a note**: "archive note X" → update status to `archived` via `mcp__obsidian__update_frontmatter`, regenerate index
- **Open a note**: "show me note X" → read and display full content via `mcp__obsidian__read_note`
- **Retag a note**: "retag note X" → read content, suggest new tags with confidence levels, apply if approved
