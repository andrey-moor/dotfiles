# Requirements: Obsidian Knowledge Base

**Defined:** 2026-03-29
**Core Value:** Save anything interesting with minimal friction and find it months later when it matters

## v1 Requirements

### Vault Structure

- [ ] **VAULT-01**: Existing vault content archived to Archive/ directory
- [ ] **VAULT-02**: Knowledge/inbox/ folder exists for unprocessed links
- [ ] **VAULT-03**: _system/ folder with taxonomy, decisions, templates, bases

### Schema

- [ ] **SCHEMA-01**: Note template with standard frontmatter (title, url, source, date_added, tags, summary, status, context, author)
- [ ] **SCHEMA-02**: Source field supports: article, tweet, newsletter, github, youtube, paper, podcast, other
- [ ] **SCHEMA-03**: Status field supports: inbox, reference, archived

### Taxonomy

- [ ] **TAX-01**: _taxonomy.md with seed categories and tag definitions
- [ ] **TAX-02**: Proposal staging section for new tag candidates
- [ ] **TAX-03**: Version tracking for taxonomy changes

### Skills

- [ ] **SKILL-01**: /kb:add — accepts URL + optional context, creates inbox note
- [ ] **SKILL-02**: /kb:process — processes inbox notes (fetch, summarize, tag, move)
- [ ] **SKILL-03**: /kb:process auto-applies tags at high confidence, asks user when uncertain
- [ ] **SKILL-04**: /kb:retag — finds notes affected by taxonomy changes and retags
- [ ] **SKILL-05**: /kb:search — searches KB by tags and content via MCP
- [ ] **SKILL-06**: /kb:taxonomy — displays taxonomy, reviews proposals, approve/reject

### Views

- [ ] **VIEW-01**: Obsidian Base view for inbox (unprocessed notes)
- [ ] **VIEW-02**: Obsidian Base view for all KB notes with tag/source/date columns
- [ ] **VIEW-03**: Obsidian Base view grouped by tags

### Migration

- [ ] **MIG-01**: Existing relevant notes identified and ported to new schema
- [ ] **MIG-02**: Notes not fitting KB archived with everything else

### Documentation

- [ ] **DOC-01**: DECISIONS.md in vault _system/ capturing all design rationale
- [ ] **DOC-02**: DECISIONS.md updated as decisions are validated

## Future Requirements

### Readwise Integration

- **RW-01**: Readwise MCP server connected
- **RW-02**: Import workflow for Readwise highlights/articles
- **RW-03**: Sync strategy (one-time import vs ongoing)

### Budget Tracking (Milestone 2)

- **BUD-01**: Budget note schema and taxonomy
- **BUD-02**: Expense tracking workflow

### People KB (Milestone 3)

- **PPL-01**: People note schema and taxonomy
- **PPL-02**: Relationship tracking workflow

## Out of Scope

| Feature | Reason |
|---------|--------|
| Unified taxonomy across KB/budget/people | Premature — each domain has different needs, refactor later |
| Automated RSS/email capture | Manual + share extension sufficient for 10-20/week volume |
| Plugin-specific syntax (Dataview, etc.) | Portability — plain markdown + YAML + Bases only |
| Full-text indexing beyond MCP | MCPVault BM25 search + tag filtering sufficient |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| VAULT-01 | Phase 1 | Pending |
| VAULT-02 | Phase 1 | Pending |
| VAULT-03 | Phase 1 | Pending |
| SCHEMA-01 | Phase 1 | Pending |
| SCHEMA-02 | Phase 1 | Pending |
| SCHEMA-03 | Phase 1 | Pending |
| TAX-01 | Phase 1 | Pending |
| TAX-02 | Phase 1 | Pending |
| TAX-03 | Phase 1 | Pending |
| DOC-01 | Phase 1 | Pending |
| DOC-02 | Phase 1 | Pending |
| SKILL-01 | Phase 2 | Pending |
| SKILL-02 | Phase 2 | Pending |
| SKILL-03 | Phase 2 | Pending |
| SKILL-04 | Phase 2 | Pending |
| SKILL-05 | Phase 2 | Pending |
| SKILL-06 | Phase 2 | Pending |
| VIEW-01 | Phase 3 | Pending |
| VIEW-02 | Phase 3 | Pending |
| VIEW-03 | Phase 3 | Pending |
| MIG-01 | Phase 4 | Pending |
| MIG-02 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0

---
*Requirements defined: 2026-03-29*
