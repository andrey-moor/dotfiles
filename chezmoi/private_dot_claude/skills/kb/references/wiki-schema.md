# Wiki Article Schema

Wiki articles are synthesized concept-level knowledge compiled from multiple source notes. They live in `Knowledge/wiki/` and are maintained by the LLM via `/kb:synthesize`.

## Frontmatter

```yaml
---
type: wiki
title: "RAG Retrieval Strategies — Knowledge Synthesis"
topic: "AI/RAG"              # Primary taxonomy tag this article covers
tags: [AI/RAG, Reference]    # Standard taxonomy tags
sources:                     # Source note filenames (without .md)
  - graphrag-vs-vector-db-retrieval
  - advanced-rag-techniques-collection
  - colbert-embeddings-vector-search
last_compiled: "2026-04-03"  # Date of last synthesis
summary: "Overview of RAG retrieval approaches..."
status: reference
---
```

## Article Structure

```markdown
## Overview
What this topic is about and why it matters. Synthesized narrative, not a list.

## Key Concepts
Core ideas distilled across sources.

## Techniques & Approaches
Specific methods, tools, patterns. Compare different approaches.

## Trade-offs & Comparisons
Where sources agree, disagree, or offer different perspectives.

## Open Questions
Gaps in coverage. Areas worth exploring.

## Sources
- [[source-note]] — what this source contributes
```

## Update Rules

- **Incremental** (default): Read new sources since `last_compiled`, weave into existing sections. Don't rewrite unchanged content.
- **Full** (`--full` flag): Rewrite entirely from all sources.
- **Staleness**: A wiki article is stale when source notes exist for its topic that aren't in the `sources` array.

## When to Create

Suggest creating a wiki article when a specific tag (subcategory level like `AI/RAG`, not parent like `AI`) has 3+ source notes.

## Naming Convention

`Knowledge/wiki/<topic-kebab>.md` — derived from the topic tag.
- `AI/RAG` → `wiki/ai-rag.md`
- `Dev/Rust` → `wiki/dev-rust.md`
- `Business/Marketing` → `wiki/business-marketing.md`

## Linking

- Wiki articles link to their sources in the `## Sources` section
- Source notes link back to their wiki article in `## Related`
- Wiki articles can link to other wiki articles in `## Related` when topics are connected
