Process knowledge base inbox: fetch content, generate summaries, and apply tags.

## Usage

`/kb:process` — process all inbox notes
`/kb:process <filename>` — process a specific note

## Instructions

### 1. Find inbox notes

Use `mcp__obsidian__list_directory` on `Main/Knowledge/inbox/` to list all notes in the inbox folder.
All notes in this folder are unprocessed by convention (status: inbox).

If `$ARGUMENTS` specifies a filename, process only that note.

If inbox is empty, tell the user and exit.

### 2. Read taxonomy

Use `mcp__obsidian__read_note` to read `Main/_system/_taxonomy.md`. Parse the categories and tags into a list of valid tags.

### 3. Process each note

For each inbox note:

**a. Read the note**
Use `mcp__obsidian__get_frontmatter` and `mcp__obsidian__read_note` to get current state.

**b. Fetch URL content**
If the note has a `url` field, fetch content using a tiered strategy:

**Tier 1 — WebFetch (try first):**
Use `WebFetch` to retrieve page content. This works for static pages (blogs, GitHub, docs, newsletters).

**Tier 2 — agent-browser (if WebFetch fails or returns no useful content):**
If WebFetch returns JS scaffolding, "JavaScript is not available", login walls, or empty content, use `agent-browser`:

- **Twitter/X** (`x.com`, `twitter.com`): Use saved auth state:
  ```bash
  agent-browser --state ~/.agent-browser/twitter-auth.json open "<url>"
  agent-browser wait 3000
  agent-browser eval --stdin <<'EVALEOF'
  Array.from(document.querySelectorAll('[data-testid="tweetText"]')).map(el => el.innerText).join("\n\n---\n\n")
  EVALEOF
  agent-browser close
  ```
- **YouTube, Notion, SPAs**: Load with `agent-browser open "<url>"`, wait for networkidle, extract text.
- Always `agent-browser close` when done.

**Error handling — never silently skip:**
- **Auth wall detected** (page shows "Log in"/"Sign up" as primary actions): Tell user auth is needed with re-export steps. Leave note in inbox.
- **Partial content** (e.g., got 1/6 tweets): Disclose what was extracted vs what's missing.
- **Total failure**: Report the error. Do NOT fabricate content from URL/title alone. Leave note in inbox.

Extract from whichever tier succeeds:
- Page title
- Author (if available)
- Main content/description

**c. Generate summary**
Write a 1-3 sentence summary of what the content is about. Be specific and factual.

**d. Suggest tags**
Based on the content AND the user's `context` field (if present), suggest tags from the taxonomy.

Assign a confidence level to each tag:
- **High**: Content clearly matches (e.g., a Rust crate README → Dev/Rust)
- **Medium**: Reasonable inference (e.g., article mentions K8s in passing)
- **Low**: Weak signal, needs user input

Also check if content suggests a tag that doesn't exist in the taxonomy. If so, note it as a potential proposal.

**e. Apply or ask**

**If ALL suggested tags are high confidence:**
- Auto-apply tags
- Show the user what was applied:
  ```
  ✓ processed-note-name
    Tags: Dev/Rust, Tools (auto-applied)
    Summary: "A Rust crate for building FUSE filesystems..."
  ```

**If ANY tag is medium/low confidence OR no context was provided and content is ambiguous:**
- Show the note and ask:
  ```
  ? ambiguous-note-name
    URL: https://example.com/...
    Summary: "Article about distributed consensus algorithms..."

    Suggested tags:
    - Arch/Distributed (high) ← auto-apply
    - Dev/Go (medium) — mentions Go implementation

    Context: <empty>

    Why did you save this? (or approve suggested tags)
  ```
- Wait for user input. They can:
  - Approve as-is
  - Add/remove tags
  - Provide context
  - Skip (leave in inbox)

**f. Finalize**

For approved notes:
1. Update frontmatter via `mcp__obsidian__update_frontmatter` (merge: true):
   ```json
   {
     "title": "<from fetched page title>",
     "author": "<if found>",
     "summary": "<generated summary>",
     "tags": ["<approved", "tag", "list>"],
     "status": "reference",
     "context": "<if user provided>"
   }
   ```

2. Find related notes and add cross-links:
   - Search `Main/Knowledge/` for notes sharing 2+ tags or similar content/context.
   - Append a `## Related` section with wiki-links (max 3-5, only genuinely related notes):
     ```markdown
     ## Related

     - [[related-note-filename]] — brief reason for connection
     ```
   - Update the related notes to link back (bidirectional). Use `mcp__obsidian__patch_note` to append to their `## Related` section.
   - Don't link notes that only share a broad tag. Look for specific topic overlap, complementary content, or shared project context.

3. Move note from `Main/Knowledge/inbox/` to `Main/Knowledge/` via `mcp__obsidian__move_note`.
   Keep the same filename unless the title suggests a better one (kebab-case, max 60 chars).

**g. Handle tag proposals**

If during processing you identified content that doesn't fit existing taxonomy well:
```
Taxonomy proposal: Content about [topic] doesn't fit current tags well.
Proposed: Category/NewTag — [brief justification]

Add to proposals? (yes/no)
```

If yes, use `mcp__obsidian__patch_note` to append a row to the Proposals table in `Main/_system/_taxonomy.md`.
This is a content edit (table row), not a frontmatter update, so `patch_note` is correct here.

### 4. Summary

After processing all notes:
```
Processed: X notes
  ✓ Auto-tagged: Y
  ? User-confirmed: Z
  ⏭ Skipped: W

Inbox remaining: N notes
```
