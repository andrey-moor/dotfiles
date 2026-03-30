# Obsidian Vault Organization

## What This Is

A structured Obsidian vault with AI-assisted knowledge management. Claude Code skills handle capture, tagging, and retrieval of links/articles/references. Taxonomy evolves over time with staged proposals and bulk retagging.

## Core Value

Save anything interesting with minimal friction and find it months later when it matters — whether through AI search or browsing tagged views.

## Current Milestone: v1 Knowledge Base

**Goal:** Build the knowledge base system — vault structure, taxonomy, processing skills, and capture workflow.

**Target features:**
- Vault reorganization (archive old content, new folder structure)
- Seed taxonomy with evolution workflow
- Claude Code skills for add/process/retag/search/taxonomy
- Obsidian Bases views for browsing
- iPhone capture via share extension
- Migration of existing relevant notes

## Requirements

### Active

- [ ] Vault reorganized with Knowledge/inbox/, _system/, Archive/
- [ ] Note schema with frontmatter (title, url, source, tags, summary, status, context)
- [ ] Seed taxonomy in _taxonomy.md with proposal staging
- [ ] /kb:add skill — quick-add links with optional context
- [ ] /kb:process skill — fetch, summarize, auto-tag (high confidence) or ask (uncertain)
- [ ] /kb:retag skill — bulk retag after taxonomy changes
- [ ] /kb:search skill — search KB via tags + content
- [ ] /kb:taxonomy skill — view, propose, approve/reject tags
- [ ] Obsidian Bases views (inbox, all, by-tag, needs-review)
- [ ] Obsidian note template for manual capture
- [ ] Existing relevant notes migrated to new schema
- [ ] DECISIONS.md capturing design rationale

### Out of Scope (this milestone)

- Budget/expenses tracking — future milestone
- People/relationship KB — future milestone
- Readwise integration — layer after core KB works
- Automated capture from RSS/email — manual + share extension first
- NLP-based auto-categorization — taxonomy-based tagging sufficient

## Context

- Vault syncs via iCloud, used on macOS + iPhone
- Obsidian Mobile v1.12+ share extension handles iOS capture
- MCPVault (@bitbonsai/mcpvault) provides Claude access to vault
- Readwise available but not connected yet — future integration
- ~170 existing notes to archive/migrate
- Skills live in dotfiles repo: chezmoi/private_dot_claude/commands/kb/

## Constraints

- **Sync**: iCloud — no server-side processing, everything local
- **Portability**: Plain markdown + YAML frontmatter only, no plugin-specific syntax
- **Taxonomy**: KB-only for now, budget/people get their own later
- **Tags**: Two levels max (Category/Subcategory)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Tags over folders | One note can span multiple interests, folders force single hierarchy | — Pending |
| Two-level max taxonomy | Deep hierarchies become unmanageable | — Pending |
| KB-only taxonomy | Budget and people will have different schemas, unify later if needed | — Pending |
| Context field in schema | Captures WHY user saved it, separate from content summary | — Pending |
| Staged tag proposals | Prevents taxonomy sprawl, new tags need approval | — Pending |
| Auto-tag with confidence threshold | High confidence = auto-apply, uncertain = ask user | — Pending |
| Flat Knowledge/ folder | Source is a frontmatter field, not a folder | — Pending |

---
*Last updated: 2026-03-29 after project initialization*
