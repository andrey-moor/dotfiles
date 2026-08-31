# P3 — kb-engine Extraction Design

**Date:** 2026-08-31. **Answers:** step 2 ("kb-engine extraction") of
`2026-07-23-environment-refactor-design.md` §8, with one owner amendment: kb-engine is
**removed from dotfiles entirely, not re-wired** — no nix module survives.

## Why

kb-engine is a product (the owner's knowledge-base engine: Python package, 542 tests, its
own release cadence) living inside an infrastructure repo. Measured 2026-08-31: 126 of the
last 200 dotfiles commits touch `kb-engine/` — the dotfiles history is mostly not about
dotfiles. Tracked footprint 130 files / 1.8 MB (the in-tree `.venv` and caches account for
the ~995 MB working-directory figure and are untracked). The owner explicitly does not want
second-brain work entangled with the environment refactor.

## Decisions (owner, 2026-08-31)

1. **History-preserving extraction.** New repo built with
   `git-filter-repo --subdirectory-filter kb-engine` on a **fresh clone** of dotfiles.
   kb-engine's full commit history becomes the new repo's timeline. Dotfiles itself gets a
   tip-level `git rm` only — **no force-push, dotfiles history untouched**.
2. **Destination:** `andrey-moor/kb-engine`, **private** (test fixtures embed vectors
   derived from the owner's real vault; public later only after a fixture audit).
3. **Local clone:** `~/Documents/kb-engine` (sibling of `~/Documents/dotfiles`).
4. **No reinstall wiring.** Delete `modules/home/dev/kb-engine.nix` and the enable block in
   `hosts/behemoth/default.nix` (~line 202). No `repoPath` option, no PATH shim, no launchd
   timers. Re-wiring is a future decision, out of scope.

## Accepted consequences (owner confirmed knowingly)

- `kb-engine` disappears from PATH; the **scheduled KB pipeline stops** (embedding refresh,
  weekly digest nudge via launchd + osascript).
- kb skills that shell out to the CLI degrade until re-wired some other way: `kb:topics`,
  `kb:review`, `kb:surface`, and the hybrid-search portion of `kb:search`. MCP-based kb
  skills (Obsidian server) are unaffected.
- Manual escape hatch, documented in the new repo's README:
  `uv run --project ~/Documents/kb-engine --extra ml --extra topics kb-engine <cmd>`
  (secrets still read from `~/.config/kb-engine/secrets.env` where applicable).

## Untouched, deliberately

The Obsidian vault; `~/.config/kb-engine/secrets.env`; pipeline behavior/code (no
functional changes ride along); all chezmoi-managed kb skill/command files (they reference
the CLI by name and degrade gracefully — editing them is second-brain work, out of scope);
rocinante/stargazer (never enabled the module); KB design docs and plans under `docs/`
(they are dotfiles project history and stay).

## Execution outline

1. Fresh clone of dotfiles → `git-filter-repo --subdirectory-filter kb-engine` → verify the
   result contains only kb-engine history → create private GitHub repo → push.
2. Clone to `~/Documents/kb-engine`; `uv run … pytest` — the full suite must pass there
   before anything is removed from dotfiles.
3. Add the manual-run README section to the new repo.
4. Dotfiles: `git rm -r kb-engine/`; delete `modules/home/dev/kb-engine.nix`; remove the
   `hosts/behemoth/default.nix` enable block; `just build` green, then `just switch`.
5. Verify: `kb-engine` gone from PATH; launchd timers unloaded
   (`launchctl list | grep kb-engine` empty); dotfiles CI green.
6. Update memory: `project_obsidian_kb.md` gets the new home + "not installed via dotfiles"
   status; `project_env_refactor.md` marks P3 done.

## Success criteria

- New private repo exists with kb-engine's full history; tests pass in `~/Documents/kb-engine`.
- `git ls-files | grep kb-engine` empty in dotfiles; no nix module references remain
  (`git grep kb-engine -- modules/ hosts/` empty); `just switch` clean; CI green.
- Dotfiles history untouched (no force-push anywhere).

## Risks

Low. The extraction never mutates the original repo; the removal is one revertable commit.
Worst case: the owner misses the pipeline sooner than expected — remedy is either manual
runs (README) or a future re-wiring decision, both outside this phase.
