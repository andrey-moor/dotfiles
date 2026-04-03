Capture Claude's answer from the current conversation as a derived knowledge base note.

## Usage

`/kb:capture` — capture the most recent substantive answer
`/kb:capture <title>` — capture with a specific title

## Instructions

### 1. Identify the answer

- Look at the current conversation for the most recent substantive answer (analysis, explanation, comparison, recommendation)
- Skip trivial responses (confirmations, status updates, error messages)
- If no clear answer found, ask: "What would you like me to capture?"

### 2. Identify source notes

- Scan the conversation for any KB notes that were read, referenced, or searched during this answer
- These become the `informed_by` list (array of filenames without .md)
- If none were explicitly referenced but the answer is about a KB topic, search for related notes via `mcp__obsidian__search_notes`

### 3. Prepare the note

a. **Title**: From `$ARGUMENTS` if provided, otherwise generate from the question/answer topic (concise, descriptive)

b. **Filename**: Kebab-case from title, max 60 chars

c. **Context**: Extract the user's original question that prompted the answer

d. **Content** (under `## Notes`):
   - Remove conversational filler ("Sure, here's...", "Let me explain...")
   - Structure with headings and bullet points
   - Keep factual content, analysis, comparisons
   - Preserve code examples, tables, key data

e. **Tags**: Read taxonomy from `Main/_system/_taxonomy.md`. Suggest tags using same confidence-based approach as `/kb:process`.

f. **Summary**: 1-3 sentence description of the captured knowledge

### 4. Preview

```
## Capture Preview

**Title:** "When to Use GraphRAG vs Vector Retrieval"
**Tags:** AI/RAG, Reference
**Informed by:** graphrag-vs-vector-db-retrieval, colbert-embeddings-vector-search
**Summary:** "Analysis comparing graph-based vs vector retrieval..."

[first 10 lines of content]

Save to Knowledge Base? (yes / edit / cancel)
```

Wait for user approval. If "edit": ask what to change, update, re-preview.

### 5. Finalize

1. Write note via `mcp__obsidian__write_note` to `Main/Knowledge/<filename>.md`:
   ```yaml
   ---
   title: "<title>"
   url: ""
   source: derived
   date_added: "<today YYYY-MM-DD>"
   tags: [<approved tags>]
   summary: "<summary>"
   status: reference
   context: "<user's original question>"
   author: ""
   informed_by:
     - <source-note-1>
     - <source-note-2>
   ---
   ```

2. Add `## Related` section with wiki-links to `informed_by` notes + any other related KB notes

3. Update informed_by notes with backlinks via `mcp__obsidian__patch_note` (append to their `## Related` section)

4. Update index: run the index generation logic (same as `/kb:index`)

5. Confirm: `Captured: <filename> | Tags: <tags> | N source links`
