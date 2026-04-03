# Wiki Article Schema

Wiki articles are synthesized concept-level knowledge compiled from multiple source notes. They live in `Knowledge/wiki/` and are maintained by the LLM via `/kb:synthesize`.

## Frontmatter

```yaml
---
type: wiki
title: "RAG Retrieval Strategies — Knowledge Synthesis"
topic: "AI/RAG"              # Tag OR freeform topic string
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

The `topic` field can be either a taxonomy tag (e.g., `AI/RAG`) or a freeform description (e.g., `Rust LLM Tools`). Freeform topics enable wiki articles that span multiple tags.

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

**Good wiki articles** synthesize notes that share a specific topic with meaningful overlap:
- Multiple notes address the same question or domain
- Synthesizing produces comparisons, patterns, or narrative the individual notes don't have
- You'd want to read the compiled version instead of individual notes

**Bad wiki articles** try to synthesize notes that only share a broad category:
- "GameDev" with notes about hex maps, isometric builders, agent templates, and RTS games — too diverse
- Cross-cutting tags (Tutorials, Reference, Inspiration, Tools) — too broad, incoherent when compiled

**Auto-suggestion threshold** (during `/kb:process`):
- 5+ source notes on a specific subtag (e.g., `AI/RAG`, not `AI`)
- Never suggest for cross-cutting tags (Tutorials, Reference, Inspiration, Tools)
- Never suggest for parent categories without subtags that have < 5 notes each

**Manual creation** — always available via `/kb:synthesize`, regardless of note count. Use freeform topics to synthesize across tag boundaries.

## Topic Types

| Type | Example | `topic` field | Source discovery |
|------|---------|---------------|-----------------|
| Tag-based | `/kb:synthesize AI/RAG` | `AI/RAG` | Tag match in frontmatter |
| Freeform | `/kb:synthesize "Rust LLM tools"` | `Rust LLM Tools` | Content + summary search |

## Naming Convention

`Knowledge/wiki/<topic-kebab>.md` — derived from topic.
- Tag `AI/RAG` → `wiki/ai-rag.md`
- Freeform `Rust LLM Tools` → `wiki/rust-llm-tools.md`

## Coherence Check

Before synthesizing, the system checks if source notes actually share meaningful overlap. If they cover distinct sub-topics with no connection, it warns and offers options: synthesize anyway (broad overview), pick a subset, or cancel.

## Linking

- Wiki articles link to their sources in the `## Sources` section
- Source notes link back to their wiki article in `## Related`
- Wiki articles can link to other wiki articles in `## Related` when topics are connected
