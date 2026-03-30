Search the knowledge base by topic, tags, or content.

## Usage

`/kb:search <query>`

Examples:
- `/kb:search sprite generation`
- `/kb:search tag:AI/RAG`
- `/kb:search rust FUSE filesystem`

## Instructions

1. Parse `$ARGUMENTS` as the search query.

2. **Search strategy** — run these in parallel:

   a. **Full-text search**: Use `mcp__obsidian__search_notes` with the query string, `searchContent: true`, `searchFrontmatter: true`, `limit: 20`. This searches both note content and frontmatter (tags, summary, context, title) in one call.

   b. **Tag listing**: Use `mcp__obsidian__list_all_tags` to find tags matching query terms, then identify which notes use those tags.

3. Filter all results to notes under `Main/Knowledge/` path only. Exclude `_system/` and `Archive/` results.

4. If query starts with `tag:`, search only by tag match (exact prefix match). Use `mcp__obsidian__search_notes` with `searchFrontmatter: true` and the tag value as query.

5. For each matching note, read its frontmatter via `mcp__obsidian__get_frontmatter` to build the result display.

6. **Present results** sorted by relevance:
   ```
   ## KB Search: "<query>"

   **N results found**

   1. **Note Title** — [source]
      Tags: AI/RAG, Tutorials
      Summary: "Brief summary..."
      Context: "why user saved it"
      → Main/Knowledge/note-name.md

   2. **Another Note** — [github]
      Tags: Dev/Rust, Tools
      Summary: "..."
      → Main/Knowledge/another-note.md
   ```

7. If no results found:
   ```
   No results for "<query>" in Knowledge Base.

   Try broader terms or check Archive/ for old notes.
   ```
