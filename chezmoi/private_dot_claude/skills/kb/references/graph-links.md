# Graph Links — Cross-Note Linking

Build Obsidian's graph view by adding wiki-links between related KB notes.

## When to Link

Add a `## Related` section during `/kb:process` after tagging is finalized. Also update existing related notes to link back.

## Finding Related Notes

After a note is tagged, find related notes by:

1. **Tag overlap**: Use `mcp__obsidian__search_notes` with `searchFrontmatter: true` to find notes sharing the same tags. Prioritize notes sharing 2+ tags.
2. **Content similarity**: Search for key terms from the note's summary/title across KB notes.
3. **Context match**: If the note has a `context` field referencing a project or topic, find other notes with the same context.

**Relevance threshold**: Only link notes that are genuinely related — not just "both tagged AI/LLMs." Look for:
- Same specific topic (both about RAG chunking strategies)
- Complementary content (one is a tutorial, another is a library for the same thing)
- Same project context ("for my game project")
- Direct references (one article cites or builds on another)

**Max links**: 3-5 per note. Too many dilutes the graph signal.

## Format

Append to the note body (after `## Notes` content):

```markdown
## Related

- [[graphrag-vs-vector-db-retrieval]] — also covers RAG retrieval approaches
- [[advanced-rag-techniques-collection]] — practical techniques for the patterns discussed here
```

Use the note filename (without `.md`) as the wiki-link target. Add a brief reason after the `—` dash.

## Bidirectional Links

When adding a `## Related` link from note A → note B, also update note B to link back to note A. Use `mcp__obsidian__patch_note` to append to note B's `## Related` section.

If note B doesn't have a `## Related` section yet, append one:

```markdown

## Related

- [[note-a-filename]] — reason for connection
```

## Wiki Articles

Wiki articles in `Knowledge/wiki/` link to their sources in the `## Sources` section (part of the article structure). Source notes link back to their wiki article in `## Related`:

```markdown
- [[wiki/ai-rag]] — synthesized wiki article
```

Wiki articles can also link to other wiki articles when topics are connected.

## Derived Notes

Derived notes (`source: derived`) link to their `informed_by` notes in `## Related`. The informed_by notes link back:

```markdown
- [[derived-note-name]] — derived analysis based on this source
```

## When NOT to Link

- Don't link notes that only share a broad category tag (e.g., both have `Dev/Rust` but are about completely different Rust topics)
- Don't link archived notes (`status: archived`)
- Don't create circular link chains just for the sake of connectivity
- Don't link to notes in `Knowledge/inbox/` (they're not finalized yet)
