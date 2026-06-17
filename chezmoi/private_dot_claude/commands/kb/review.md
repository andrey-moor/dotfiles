Run the nudged ~5-minute knowledge base review pass, driven by the weekly digest.

## Usage

`/kb:review` — full review pass: read the digest → process new inbox items → name/govern topic proposals → (optional, gated) apply newly-approved topics

## Background

A weekly **launchd** agent (Nix `modules.dev.kb-engine.schedule`, enabled on behemoth)
runs the deterministic, **LLM-free** `kb-engine pipeline` — sync → apply active-topic tags
→ sticky-discover proposals → write `Main/_system/kb-digest.md` — then fires a macOS
notification ("KB digest ready — N to review"). The pipeline mutates notes **only for
active (approved) topics**, so freshly discovered clusters stay `proposed` and nothing is
silently mis-tagged. This command is the **human half**: the naming and judgment the engine
deliberately omits.

The digest at `Main/_system/kb-digest.md` is the **entry point**. Read it first; its
"Needs review" checklist drives the pass. `kb-engine` is on `PATH` (the Nix wrapper) and
the vault is the iCloud `Main` dir; pass `--json` to engine commands and parse the output.

## Instructions

### 1. Refresh, then read the digest

The digest is only as fresh as the last pipeline run (weekly via launchd, or whenever it
was last run by hand). Starting a review off-cycle — e.g. right after a bulk import — can
show stale counts, so refresh the live counts first. It is fast and LLM-free:

```bash
kb-engine --vault "<Main>" digest --json   # heavier full refresh: pipeline --json
```

Then `mcp__obsidian__read_note` on `Main/_system/kb-digest.md` (now current). It reports:
- **Inbox backlog** — unprocessed `Knowledge/inbox/` stubs
- **Topic proposals awaiting review** — discovered clusters needing a name/approval
- **Unfiled notes** — notes in no topic

If the checklist is `- [x] Nothing to review.`, tell the user there's nothing to do and stop.

### 2. Process new inbox items (if backlog > 0)

Run the `/kb:process` flow over `Main/Knowledge/inbox/`:
- For each unprocessed note: fetch content with the tiered strategy (Tier 0 `gh` →
  Tier 1 `WebFetch` → Tier 2 `agent-browser`; never silently skip failures), generate a
  1–3 sentence summary, and suggest tags with confidence.
- **Auto-apply high-confidence tags.** **Batch all borderline (medium/low) suggestions**
  and ask the user once, rather than interrupting per note.
- File approved notes from `inbox/` into `Main/Knowledge/`, add `## Related` cross-links,
  and propose any new taxonomy tags.

Dedup is handled **at ingest** by `kb-engine import-things` (it normalizes + dedups URLs
against the vault and within the batch), so you should not encounter duplicate-URL stubs here.

### 3. Name & govern topic proposals (if proposals > 0)

Run the `/kb:topics` flow:
```bash
kb-engine sync
kb-engine topics discover --sticky --json
kb-engine topics diff-taxonomy --json
kb-engine topics list --json
```
Read the keyword-slug proposals + their member notes, draft **human labels** and **area
names**, and present the restructure as a reviewable diff. **Do not write anything yet.**
On approval:
```bash
kb-engine topics render --json
```
Promote a proposal worth keeping into an approved, sticky topic:
```bash
kb-engine topics add <slug> --label "<Human Label>" --description "<what it's about>"
```

### 4. Apply newly-approved topics (optional, gated)

Only after the user explicitly confirms tagging notes, write `topic/<slug>` tags for the
topics just promoted to active:
```bash
kb-engine topics apply --status active --json
```
This is the **only note-mutating step — running it IS the gate.** Reports
`{n_changed, n_tags_added, skipped_missing}`. Surface `skipped_missing` (member files not
on disk) to the user; never drop them silently.

### 5. Wrap up

Refresh the digest so the next nudge reflects the cleared backlog (either is fine):
```bash
kb-engine digest --json   # or: kb-engine pipeline --json
```
Then report what was processed, named, and applied.

## Report

```
Review complete.
  Inbox:     processed P (auto-tagged A, confirmed C, skipped S) — N remaining
  Proposals: named X, promoted Y to active topics
  Applied:   (only if confirmed) tagged Z notes with topic/<slug>, skipped M missing
  Digest:    refreshed _system/kb-digest.md
```
