Generate or refresh the Knowledge Base index — a living overview of everything in the KB.

## Usage

`/kb:index` — regenerate the index

## Instructions

1. **Gather data:**
   - List all `.md` files in `Main/Knowledge/` via `mcp__obsidian__list_directory` (source + derived notes)
   - List all files in `Main/Knowledge/wiki/` via `mcp__obsidian__list_directory` (wiki articles, if folder exists)
   - List all files in `Main/Knowledge/inbox/` via `mcp__obsidian__list_directory`
   - Read frontmatter of all notes via `mcp__obsidian__get_frontmatter` (batch in parallel where possible)
   - Get tag counts via `mcp__obsidian__list_all_tags`

2. **Compute stats:**
   - Total notes by status (reference, inbox, archived)
   - Count by source type (article, tweet, github, youtube, derived, etc.)
   - Count wiki articles (from wiki/ folder)
   - Count derived notes (source == "derived")
   - **Inbox health:** count notes in `Knowledge/inbox/`; of those, count any still in raw
     Web-Clipper schema (`source` is a URL or `status` missing); compute the oldest inbox note's
     age (today − min `date_added`).

3. **Recent additions:**
   - Sort all notes by `date_added` descending
   - List notes from last 14 days with title, summary, date

4. **Topics by size:**
   - For each taxonomy category, count notes per subcategory
   - Sort categories by total count descending
   - For each category, list any wiki articles that exist

5. **Wiki articles:**
   - For each wiki article, show source count and `last_compiled` date
   - Flag stale articles (sources added since last_compiled)

6. **Graph health:**
   - For each note, check if content contains `## Related`
   - Compute: notes with links / total notes (percentage)
   - Count orphan notes (no Related section)

7. **Write index** via `mcp__obsidian__write_note` to `Main/_system/index.md`:

```markdown
---
type: system
purpose: index
last_updated: <today YYYY-MM-DD>
---

# Knowledge Base Index

> Auto-generated. Last updated: <today>

## Stats
- **Total notes:** N
- **Reference:** X | **Inbox:** Y | **Archived:** Z
- **Wiki articles:** W
- **Derived notes:** D
- **Sources:** A articles, B tweets, C github, D youtube, E newsletters

## Inbox Health
- **Inbox notes:** N (X still raw Web-Clipper schema)
- **Oldest inbox note:** D days
- Backlog: ✓ clear / ⚠ N awaiting `/kb:process`

## Recent Additions (last 14 days)
- [[note-name]] — summary (date_added)
- ...

## Topics by Size

### AI (N notes)
AI/LLMs (X) | AI/Agents (Y) | AI/RAG (Z) | AI/Prompting (W) | AI/MLOps (V)
Wiki: [[wiki/article-name]]

### Dev (N notes)
Dev/Tools (X) | Dev/Rust (Y) | Dev/TypeScript (Z) | ...

...

## Wiki Articles
| Article | Sources | Last Compiled | Status |
|---------|---------|---------------|--------|
| [[wiki/name]] | N | date | current/stale |

## Synthesis Candidates
Subtags with 5+ source notes and no wiki article (excluding cross-cutting tags):
- **AI/Agents** (26 notes) → `/kb:synthesize AI/Agents`
- **Dev/Rust** (12 notes) → `/kb:synthesize Dev/Rust`

## Graph Health
- Notes with Related links: X/Y (Z%)
- Orphan notes: N
```

The **Synthesis Candidates** section is computed by:
1. Count source notes per specific subtag (not parent categories, not cross-cutting tags like Tutorials/Reference/Inspiration/Tools)
2. Check if a wiki article exists for that subtag in `Main/Knowledge/wiki/`
3. List subtags with 5+ notes and no wiki, sorted by count descending
4. Include the `/kb:synthesize` command for easy copy-paste

If no candidates exist, show: `All eligible topics have wiki articles. ✓`

8. Confirm: `Index updated: N notes, M wiki articles, K recent additions, L synthesis candidates`
