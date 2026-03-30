# Knowledge Base Note Schema

## Frontmatter Fields

```yaml
---
title: "Page title or descriptive name"
url: "https://..."
source: "article"          # See Source Types below
date_added: "2026-03-29"   # YYYY-MM-DD, date note was created
tags:                       # Array of taxonomy tags
  - "AI/RAG"
  - "Tutorials"
summary: "1-3 sentence description of what the content is about"
status: "inbox"            # See Status Values below
context: "why I saved this" # User's reason for saving (optional)
author: "Author Name"      # Content author (optional)
---
```

## Source Types

Infer from URL pattern:

| Pattern | Source |
|---|---|
| `github.com` | `github` |
| `x.com`, `twitter.com` | `tweet` |
| `youtube.com`, `youtu.be` | `youtube` |
| `arxiv.org` | `paper` |
| `substack.com`, contains "newsletter" | `newsletter` |
| `*.podcast*`, podcast platforms | `podcast` |
| Everything else | `article` |
| No URL / manual note | `other` |

## Status Values

| Status | Meaning | Location |
|---|---|---|
| `inbox` | Unprocessed, needs tagging | `Knowledge/inbox/` |
| `reference` | Processed, tagged, available | `Knowledge/` |
| `archived` | Deprioritized, kept for history | `Knowledge/` |

## Filename Convention

- Kebab-case, max 60 characters
- Derived from URL path or page title
- Examples: `github-foo-bar.md`, `building-rag-with-langchain.md`

## Content Structure

```markdown
## Notes

User's manual notes, highlights, or AI-generated content summary.
```
