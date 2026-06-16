Discover, name, and govern emergent topics over the knowledge base via the local `kb-engine` CLI.

## Usage

`/kb:topics` — full flow: sync → discover (sticky) → diff → propose names → review → render
`/kb:topics discover` — cluster note vectors into topics (sticky re-discover)
`/kb:topics diff` — diff discovered topics against the existing `_taxonomy.md`
`/kb:topics areas` — group topics into broader areas
`/kb:topics add <slug> "<label>" "<description>"` — add a manual (anchored) topic
`/kb:topics render` — render MOCs + taxonomy proposals (idempotent)
`/kb:topics apply` — write `topic/<slug>` tags into member notes (gated)

## Background

The engine is **LLM-free**: it does the deterministic compute (embedding, clustering,
Jaccard diffing) and the file writes. It labels topics with raw **keyword slugs** like
`rust-async-tokio`. **Claude's job is the naming and judgment** the engine omits: turn
slugs into human-readable labels, propose area names, present the restructure as a
reviewable diff, and gate the write-backs.

Assume `kb-engine` is on `PATH` (the Nix wrapper runs the in-repo project) and the vault
is the iCloud `Main` dir. Pass `--json` to every command and parse the output. Topic
membership is recorded on notes via the `topic/<slug>` frontmatter tag; MOCs live in
`_system/topics/` (regenerable, excluded from embedding).

## Instructions

### Default (no subcommand): full flow

1. **Sync** so topics reflect the current vault:
   ```bash
   kb-engine sync
   ```
2. **Discover (sticky)** — existing approved topics keep their members; only the residual
   is clustered into new proposals:
   ```bash
   kb-engine topics discover --sticky --json
   ```
   `--json` → `{n_assigned_existing, n_new_topics, n_unfiled}`.
3. **Diff** the discovered structure against the taxonomy:
   ```bash
   kb-engine topics diff-taxonomy --json
   ```
4. **Propose names (Claude):** read the slug topics + their member notes (`kb-engine topics
   list --json`) and draft human labels + area names.
5. **Present** the restructure diff + proposals to the user (see format below). **Do not
   write yet.**
6. On approval: `kb-engine topics render --json`.
7. Only if the user then confirms tagging notes: `kb-engine topics apply --status active --json`.

### `discover` subcommand

```bash
kb-engine topics discover --sticky --json
```
Plain `discover` (no `--sticky`) replaces all discovered topics. `--sticky` assigns notes
scoring `>= --high` (default `0.55`) to existing active topics first, then clusters only the
residual — use it once the user has approved topics worth preserving. Report new topics,
assigned-to-existing counts, and the unfiled residual.

### `diff` subcommand

```bash
kb-engine topics diff-taxonomy --json
```
Returns `{mapping, new_topics, orphan_tags, covered_topics}`:
- `mapping` — each existing tag → ranked aligned topics (Jaccard overlap)
- `new_topics` — discovered topics no tag covers (**structure the data found that the taxonomy lacks**)
- `orphan_tags` — tags no topic aligns with (candidates to deprecate or merge)
- `covered_topics` — topics aligned with an existing tag

A missing `_taxonomy.md` is treated as greenfield (every topic is `new`). Optional
`--taxonomy <path>` overrides the default `<vault>/_system/_taxonomy.md`.

### `areas` subcommand

```bash
kb-engine topics areas --threshold 0.3 --json
```
Groups topic centroids agglomeratively into broader areas. A higher `--threshold` yields
fewer, broader areas. `--json` → `{n_areas, areas:[{slug, label, topics:[...]}]}`. Propose
nicer area names to the user before they land in the rendered `index.md`.

### `add` subcommand

```bash
kb-engine topics add <slug> --label "<Human Label>" --description "<what it's about>"
```
Creates a **manual** topic (`kind=manual`, `status=active`) anchored by an embedding of
`label + ". " + description`. Manual topics survive a later `discover` and are the
mechanism for promoting a Claude-named cluster into an approved, sticky topic. Adding an
existing slug fails.

### `render` subcommand

```bash
kb-engine topics render --json
```
Idempotent, **render-not-append**:
- `<vault>/_system/topics/index.md` — areas→topics outline with `[[_system/topics/<slug>]]`
  wikilinks, member counts, kind/status.
- `<vault>/_system/topics/<slug>.md` — one MOC per topic: label, keywords, and a `## Notes`
  list of member `[[Knowledge/...]]` wikilinks sorted by score.
- Splices a proposals table into `<vault>/_system/_taxonomy.md` between
  `<!-- KB-PROPOSALS:START -->` … `<!-- KB-PROPOSALS:END -->` markers (creating the block if
  absent), preserving the rest of the file.

Safe to re-run; `_system/topics/` is outside `Knowledge/` so `sync` never embeds it.

### `apply` subcommand

```bash
kb-engine topics apply --status active --json
```
**The only note-mutating command — running it IS the gate.** Never run it without the
user's explicit go-ahead. Adds the `topic/<slug>` tag to each active topic's member notes'
frontmatter (preserving body + other frontmatter, deduped, idempotent). Defaults to
`--status active`, so discovered proposals stay `proposed` until promoted (e.g. via
`topics add` or a future approval). `--json` → `{n_changed, n_tags_added, skipped_missing}`.
Surface `skipped_missing` (member files not found on disk) to the user — never drop silently.

## Presenting the restructure diff

```
Discovered N topics over M notes (P assigned to existing, U unfiled).

New topics (no aligned tag — structure your taxonomy lacks):
  • rust-async-tokio   → proposed label "Async Rust & Tokio"   (7 notes)
  • local-llm-serving  → proposed label "Local LLM Serving"    (5 notes)

Aligned with existing tags:
  • Dev/Rust  ↔ rust-async-tokio (0.62 overlap)

Orphan tags (no topic aligns — consider deprecating):
  • Misc/Old

Proposed areas:
  • "AI Infrastructure" = {local-llm-serving, vector-db, …}

Approve to render MOCs into _system/topics/ + proposal table into _taxonomy.md?
(rendering does NOT tag your notes — that's a separate, explicit `apply` step)
```

## Report

```
Topics: discovered X (Y new, Z aligned), U unfiled
Rendered: _system/topics/index.md + N topic MOCs, proposals → _taxonomy.md
Applied: (only if confirmed) tagged C notes with topic/<slug>, skipped S missing
```
