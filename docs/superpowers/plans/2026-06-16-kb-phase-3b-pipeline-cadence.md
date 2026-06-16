# KB Phase 3b — Scheduled Pipeline & Review Flow Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development with TDD.

**Goal:** Make the KB self-maintaining: a deterministic `kb-engine pipeline` command (sync → apply approved-topic tags → sticky-discover proposals → write digest, no LLM), a weekly **launchd** agent (nix) that runs it + nudges via notification, and a `kb` skill **review** operation for the user's ~5-min Claude pass (process new inbox items, name proposals, resolve borderline).

**Architecture:** The pipeline is an engine command composing the already-tested steps — testable with FakeEmbedder/FakeClusterer. Only `topics apply --status active` mutates notes, and only for *approved* topics (discovered proposals stay `proposed` until the review confirms them), so the unattended job never silently mis-tags. The launchd agent (home-manager `launchd.agents`) runs the Nix `kb-engine` wrapper weekly. The review flow is `kb` skill markdown (Claude reads `_system/kb-digest.md`, drives `/kb:process` + `/kb:topics`).

**Tech Stack:** unchanged + home-manager `launchd.agents` (macOS), `osascript` for the notification.

## Testing strategy
`pipeline` unit-tested with fakes (asserts it runs each step + returns a summary). launchd module validated via `just build`. Review flow is skill markdown (deployed via chezmoi). Real validation: run `kb-engine pipeline` once against the live vault (writes only the engine cache DB + `_system/kb-digest.md`; no note mutation since no topics are `active` yet).

---

### Task 1: `pipeline` engine command

**Files:** `src/kb_engine/pipeline.py`, `cli.py`, `tests/test_pipeline.py`

- [ ] **Step 1: Failing test** (fakes)
```python
def test_pipeline_runs_steps_and_summarizes(tmp_path, monkeypatch):
    # fake vault with 2 notes; KB_FAKE_EMBED + KB_FAKE_CLUSTER
    ...
    from kb_engine.pipeline import run_pipeline
    from kb_engine.store import Store
    res = run_pipeline(cfg, Store(cfg.db_path), embedder, clusterer)
    assert res.synced >= 0 and res.applied >= 0 and res.proposals >= 0
    assert (cfg.vault_path/"_system"/"kb-digest.md").exists()
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `run_pipeline(cfg, store, embedder, clusterer) -> PipelineResult`:
  1. `sync(cfg, store, embedder)` → synced counts.
  2. `apply_topic_tags(store, cfg.vault_path, only_status=("active",))` → applied count (no-op if no active topics — safe).
  3. `sticky_discover(store, clusterer)` → new proposals.
  4. `build_digest(...)` → write `<vault>/_system/kb-digest.md`.
  Return `PipelineResult(synced, applied, proposals, unfiled, digest_path)` (frozen, tuple fields). CLI `pipeline [--json]` builds real embedder/clusterer (or fakes via env) and runs it; `--json` prints the summary. `init_schema()` first.
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): deterministic pipeline command`

---

### Task 2: launchd weekly agent (nix) + notification

**Files:** `modules/home/dev/kb-engine.nix` (extend), `hosts/behemoth/default.nix` (if a toggle is needed), `tests` n/a (nix)

- [ ] **Step 1:** Extend `modules/home/dev/kb-engine.nix`: add an option `modules.dev.kb-engine.schedule.enable` (default false) and `schedule.calendar` (default weekly Mon 09:00). When enabled, define a home-manager `launchd.agents.kb-engine-pipeline`:
  - `config.ProgramArguments` = a wrapper script that runs `kb-engine --vault "<vault>" pipeline` then, on success, an `osascript -e 'display notification …'` nudge ("KB digest ready — N to review"). The vault path is the iCloud `Main` dir (make it an option `modules.dev.kb-engine.vaultPath` with that default).
  - `config.StartCalendarInterval` from `schedule.calendar`.
  - `config.StandardOutPath`/`StandardErrorPath` to `~/Library/Logs/kb-engine-pipeline.{log,err}`.
- [ ] **Step 2:** Enable on behemoth: `modules.dev.kb-engine.schedule.enable = true;` (with the vault path).
- [ ] **Step 3:** Validate: `just build` evaluates cleanly with the launchd agent. Do NOT `just switch`. Paste the build tail.
- [ ] **Step 4: Commit** `feat(kb-engine): weekly launchd pipeline agent + notification`

---

### Task 3: `kb` skill review flow

**Files:** `chezmoi/private_dot_claude/skills/kb/SKILL.md`, `chezmoi/private_dot_claude/commands/kb/review.md` (new), `commands/kb/process.md` (enhance)

- [ ] **Step 1:** Add a **Review** operation (op 11) to `SKILL.md`: the nudged ~5-min flow — read `_system/kb-digest.md` → for each unprocessed `inbox/` note: fetch content (tiered WebFetch→agent-browser), generate summary, suggest tags (auto-apply high-confidence, ask on borderline), file to `Knowledge/` → run `/kb:topics` to LLM-name new proposals + approve/merge → optionally `kb-engine topics apply --status active` for newly-approved topics. Note the digest is the entry point and the launchd job refreshes it weekly.
- [ ] **Step 2:** Create `/kb:review` command doc mirroring the flow (digest → process inbox batch → topic proposals → confirm). Enhance `process.md` to mention the auto-file-high-confidence / batch-borderline model + dedup-at-ingest (already handled by `import-things`).
- [ ] **Step 3:** Deploy scoped: `chezmoi apply ~/.claude/commands/kb ~/.claude/skills/kb`. Confirm `review.md` landed.
- [ ] **Step 4: Commit** `feat(kb): kb skill review flow (digest-driven)`

---

### Task 4: Coverage + README + real pipeline validation

- [ ] **Step 1:** `uv run pytest --cov`; ≥80% on `pipeline`. Edge tests: pipeline with no active topics (applied=0), empty vault.
- [ ] **Step 2:** README — "Scheduled pipeline" + "Weekly cadence" sections (what runs unattended vs the review pass; the digest; the launchd toggle).
- [ ] **Step 3:** Real validation — run the pipeline ONCE against the live vault (safe: writes only the engine cache DB + `_system/kb-digest.md`; applies no tags since no topics are `active`):
  ```bash
  cd kb-engine && uv run kb-engine --vault "<Main>" pipeline --json
  cat "<Main>/_system/kb-digest.md"
  ```
  Report the pipeline summary + the rendered digest. (This also creates the steady-state engine DB at `~/.local/state/kb-engine/`.)
- [ ] **Step 4: Commit** `test(kb-engine): 3b coverage + README + real pipeline run`

## Self-review
- **Spec coverage (§7.2–§7.4, §8):** deterministic unattended pipeline (sync/apply/discover/digest, no LLM) ✓ (T1), weekly schedule + nudge ✓ (T2), digest-driven review flow ✓ (T3), auto-file-approved-only (no silent mis-tag) ✓, backlog-can't-rot (digest nags) ✓. Bulk import RUN is teed up for user confirmation (not auto-run). Index/lint integrity already in Phase 0; synthesis re-activation + proactive surfacing = Phase 4.
- **Safety:** unattended job mutates notes only for `active` (approved) topics; everything else is engine-cache + a regenerable `_system/` digest.
- **No placeholders / type consistency:** `run_pipeline`/`PipelineResult` consistent; reuses tested `sync`/`apply_topic_tags`/`sticky_discover`/`build_digest`.
```
