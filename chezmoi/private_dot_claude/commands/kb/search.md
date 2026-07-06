Search the knowledge base by topic, tags, or content.

## Usage

`/kb:search <query>`
`/kb:search <query> --limit N` — show up to N results (default: 10)

Examples:
- `/kb:search sprite generation`
- `/kb:search tag:AI/RAG`
- `/kb:search rust FUSE filesystem`
- `/kb:search AI agents --limit 50`

## Procedure

1. Parse the query and optional `--limit N` (default 10).
2. **Tag queries** (`tag:X`): use the Obsidian MCP tag search as before — the engine
   does not index tag filters yet.
3. **Everything else — engine first (hybrid semantic + keyword):**

   ```bash
   kb-engine --vault "/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main" search "<query>" --json
   ```

   Take the top `N` hits. For each, read the note's frontmatter (title, source, tags,
   summary, why) via the Obsidian MCP and present: title — one-line summary — tags —
   path. Mark `[wiki]` / `[derived]` notes.
4. **Fallback:** if the engine call fails (missing binary, stale DB), fall back to the
   Obsidian MCP full-text search and say so explicitly in the reply ("engine
   unavailable — keyword-only results").
5. When the user opens or acts on a result, log it (fire-and-forget; ignore errors):
   `kb-engine --vault "<vault>" log-event --kind open --path "<note path>"`
6. **Probe-on-miss:** if the user indicates the thing they wanted was NOT in the
   results ("not it", "couldn't find"), once they locate the right note, append a probe
   to `_system/probes.yaml` (query = their original phrasing, expect = the found path)
   and tell them the suite grew.
7. Offer post-search actions: open, archive, retag (unchanged).
