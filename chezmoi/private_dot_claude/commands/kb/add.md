Quick-add a URL to the knowledge base inbox with optional context.

## Usage

`/kb:add <url> [context]`

Examples:
- `/kb:add https://example.com/article`
- `/kb:add https://example.com/sprites useful for game project sprite generation`

## Instructions

1. Parse `$ARGUMENTS`:
   - First token that looks like a URL (starts with `http://` or `https://`) → `url`
   - Everything after the URL → `context` (user's reason for saving)
   - If no URL found, ask the user for one

2. **Check for duplicate URL**: Use `mcp__obsidian__search_notes` with `searchFrontmatter: true` for the URL.
   If found in an existing note:
   ```
   ⚠ URL already exists in KB: <existing-note-name>.md
     Added on <date_added> with tags: <tags>

   Save anyway? (yes / open existing / cancel)
   ```

3. Generate a short filename from the URL:
   - Use the page title if obvious from the URL path
   - Remove special characters, use kebab-case
   - Max 60 characters
   - Example: `https://github.com/foo/bar` → `github-foo-bar.md`

4. Use the `mcp__obsidian__write_note` tool to create the note:
   - **path**: `Main/Knowledge/inbox/<filename>.md`
   - **frontmatter**:
     ```json
     {
       "title": "<from URL path or domain>",
       "url": "<url>",
       "source": "<infer: article|tweet|newsletter|github|youtube|paper|podcast|other>",
       "date_added": "<today YYYY-MM-DD>",
       "tags": [],
       "summary": "",
       "status": "inbox",
       "context": "<context if provided, empty string if not>",
       "author": ""
     }
     ```
   - **content**: `## Notes\n\nPending processing. Run \`/kb:process\` to fetch content, generate summary, and apply tags.`

5. Infer `source` from URL pattern:
   - `github.com` → `github`
   - `twitter.com` or `x.com` → `tweet`
   - `youtube.com` or `youtu.be` → `youtube`
   - `arxiv.org` → `paper`
   - `substack.com` or contains `newsletter` → `newsletter`
   - Otherwise → `article`

6. Confirm to the user:
   ```
   Added to inbox: <filename>
   Source: <source> | Context: <context or "none">

   Run `/kb:process` to fetch content and apply tags.
   ```
