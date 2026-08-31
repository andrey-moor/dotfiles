# Taxonomy Guide

## Tag Format

Two-level maximum: `Category/Subcategory`

- `AI/RAG` — yes
- `AI/RAG/Chunking` — no (too deep, keep it as `AI/RAG`)

Notes can have multiple tags. Cross-cutting tags (Tutorials, Reference, Inspiration, Tools) combine with any category.

## Seed Categories

```
AI:         LLMs, Agents, RAG, Prompting, MLOps
Dev:        Rust, Go, TypeScript, Tools, Nix
Infra:      Kubernetes, GitOps, Networking
Arch:       Distributed, APIs, Databases
GameDev:    (subcategories emerge from content)
Business:   SaaS, Marketing, Startups
Career:     Interviews, Growth
Home:       Improvement, Organization, Gear
Personal:   Fitness, Travel, Cooking
```

Cross-cutting: `Tutorials`, `Reference`, `Inspiration`, `Tools`

The live taxonomy is always at `Main/_system/_taxonomy.md` — read it before tagging.

## Confidence-Based Tagging

When processing notes, assign confidence to each suggested tag:

**High confidence** — auto-apply:
- Content explicitly about the topic (Rust crate README → `Dev/Rust`)
- User context directly names the domain ("for my game project" → `GameDev`)
- URL pattern is definitive (github.com/rust-lang/* → `Dev/Rust`)

**Medium confidence** — ask user:
- Topic mentioned but not primary focus
- Reasonable inference from context but ambiguous
- Multiple plausible categories

**Low confidence** — ask user:
- Tangential mention only
- No user context and content is broad
- Could fit many categories equally

## Taxonomy Evolution

### Proposing New Tags

When content doesn't fit existing tags:
1. Note the gap during processing
2. Propose: `Category/NewTag — justification`
3. Append to Proposals table in `_taxonomy.md`
4. User approves/rejects via `/kb:taxonomy`

### When to Propose (not just tag)

- Multiple notes (3+) would benefit from the same new tag
- User's context repeatedly mentions a topic not in taxonomy
- A subcategory has grown too broad and needs splitting

### Deprecating Tags

1. Move from category section to Deprecated table
2. Record: old tag, action (renamed/merged/removed), new tag, date, reason
3. Run `/kb:retag` to update affected notes
