# Env Refactor P5 — Chezmoi Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire chezmoi entirely: `chezmoi/dot_config/` (nvim ×20, nushell ×3, alacritty ×1 — all literal files, zero templates/scripts) moves to `config/{nvim,nushell,alacritty}` and deploys via home-manager `mkOutOfStoreSymlink`; the chezmoi module, package, justfile targets, and live state are removed. The lazy-lock revert gotcha dies structurally (nvim writes through the symlink into the repo).

**Architecture (settled in brainstorm, 2026-09-01):**
- **Layout**: `config/` is the single home for authored configs (joins litellm there). Files get their REAL names (`private_init.lua` → `init.lua`, `private_dot_stylua.toml` → `.stylua.toml`, `dot_neoconf.json` → `.neoconf.json`).
- **Granularity**: `~/.config/nvim` and `~/.config/alacritty` = whole-dir out-of-store symlinks (live dirs verified 1:1 with source, no machine-local content). `~/.config/nushell` = **individual file symlinks only** (`config.nu`, `env.nu`, `catppuccin_mocha.nu`) — `history.txt` and `vendor/autoload/{atuin,starship}.nu` are machine-generated and MUST survive.
- **Accepted behavior change**: nvim files go 0600 → 0644 (repo perms; no secrets in them).
- **`$DOTFILES` survives** (consumers: nushell `nix-switch`/`nix-update`, `modules/home/linux/intune.nix`) — re-homed next to the `modules.dotfilesDir` option definition, not dropped with chezmoi.nix.
- Spec §4 ride-along: behemoth gets a `~/dotfiles` → `~/Documents/dotfiles` symlink so the canonical path exists fleet-wide.
- Owner decisions: chezmoi removal confirmed (spec fork E); `config/` layout chosen.

**Spec:** `docs/superpowers/specs/2026-07-23-environment-refactor-design.md` §4 + §8 step 4. Survey facts: chezmoi source has NO .chezmoiignore/.tmpl/run_/modify_/etc.; `chezmoi status` and `chezmoi diff` currently EMPTY; live lazy-lock byte-identical to source.

## Global Constraints

- **NEVER run `just switch` non-interactively without the controller's brew-no-op guard** (P4 precedent: verify no `modules/darwin/` / Brewfile changes in the phase, then controller runs it). Implementer ceiling is `just build`.
- Do not touch `~/.config/nushell/history.txt` or `~/.config/nushell/vendor/` — machine-local, protected.
- Do not modify `spikes/`, the vault, `agents/` content (except the one AGENTS.md line listed in Task 3).
- Conventional commits, one commit per task, CI green after push.
- Public repo — nothing secret is involved in this phase (verified: no templates, no secrets in the 24 files).
- rocinante/stargazer: repo changes land now; their live cutover (cleanup + HM switch) is deferred to the next visit — record in Task 4's closeout.

---

### Task 1: Move + rename into `config/`

**Steps:**
- [ ] `git mv` with prefix stripping:
  - `chezmoi/dot_config/nvim/*` → `config/nvim/` — strip `private_` everywhere; `dot_neoconf.json` → `.neoconf.json`; `private_dot_stylua.toml` → `.stylua.toml`; `lua/private_*.lua` → `lua/*.lua`; `lua/plugins/private_*.lua` → `lua/plugins/*.lua`. Result: exactly 20 files whose names match the live `~/.config/nvim` listing (verify by diffing name sets against `ls -A ~/.config/nvim` recursively).
  - `chezmoi/dot_config/nushell/{config.nu,env.nu,catppuccin_mocha.nu}` → `config/nushell/`.
  - `chezmoi/dot_config/alacritty/alacritty.toml` → `config/alacritty/`.
- [ ] `chezmoi/` directory is now empty of tracked files — confirm `git ls-files chezmoi` is empty; remove any leftover empty dirs.
- [ ] Content must be byte-identical to the live deployed copies (`diff -r` the moved trees against `~/.config/...` for the managed files) — this guarantees the later cutover is a no-op content-wise.
- [ ] Commit (`refactor(config): move chezmoi sources to config/ with real names`).

### Task 2: Home-manager wiring + chezmoi module removal

**Files:** `modules/home/dev/neovim.nix`, `modules/home/shell/nushell.nix`, alacritty's module home (locate it — if none exists, put the symlink in the module/host that installs alacritty; check `rg -il alacritty modules hosts`), the file defining `modules.dotfilesDir`, `modules/home/shell/chezmoi.nix` (delete), `hosts/*/default.nix` (drop `chezmoi.enable`), `justfile` (drop `chezmoi-apply`/`chezmoi-diff`), `hosts/behemoth/default.nix` (~/dotfiles symlink).

**Steps:**
- [ ] Out-of-store symlinks (same `mkOutOfStoreSymlink`-from-`dotfilesDir` pattern as `modules/home/dev/claude.nix` — reuse its approach):
  - neovim.nix: `xdg.configFile."nvim".source` → `<dotfilesDir>/config/nvim` (whole dir). Update the stale comment about chezmoi's init.lua winning — the rationale (no `programs.neovim` config generation, plain Lua config wins) survives, reworded.
  - nushell.nix: three entries `xdg.configFile."nushell/<f>.nu".source` → `<dotfilesDir>/config/nushell/<f>.nu`. NOT the whole dir. Fix its chezmoi comments.
  - alacritty: `xdg.configFile."alacritty".source` → `<dotfilesDir>/config/alacritty`.
- [ ] Move `home.sessionVariables.DOTFILES = dotfilesDir` from chezmoi.nix to wherever `modules.dotfilesDir` is defined (so it exists on every host regardless of modules enabled).
- [ ] behemoth only: `home.file."dotfiles".source = mkOutOfStoreSymlink "/Users/andreym/Documents/dotfiles"` (spec §4 canonical path; skip on Linux hosts where the repo already lives at `~/dotfiles`).
- [ ] Delete `modules/home/shell/chezmoi.nix`; remove `chezmoi.enable` lines from all three host configs; delete the two justfile targets.
- [ ] Fix the stale chezmoi mention in `modules/home/shell/atuin.nix:15` comment.
- [ ] `just build` green; rocinante + stargazer `activationPackage.drvPath` eval green; confirm built home files contain the new symlinks and NO chezmoi.toml.
- [ ] Commit (`feat(config): home-manager out-of-store symlinks replace chezmoi`).

### Task 3: Docs sweep

**Steps:**
- [ ] `CLAUDE.md`: drop `just chezmoi-apply`/`chezmoi-diff` from Commands; rewrite the Chezmoi bullet + "Chezmoi Integration" section into a short "Mutable configs" note (config/ + out-of-store symlinks, edits live immediately); keep the Agent Stack section accurate.
- [ ] `README.md`: same treatment for its chezmoi section, install step, repo tree, module table row.
- [ ] `hosts/rocinante/README.md` + `docs/rocinante-encrypted-install.md`: replace the `chezmoi apply` step (now covered by the HM switch itself).
- [ ] `agents/AGENTS.md` line "Dotfiles managed with Nix (nix-darwin + home-manager) and Chezmoi." → drop the chezmoi clause.
- [ ] Sweep: `rg -i chezmoi --glob '!docs/superpowers/**' --glob '!docs/archive/**' --glob '!docs/environment-*' --glob '!.planning/**'` — fix remaining live references (TODO.md, scripts/agent-stack-cleanup.sh comments may stay if historical; judgment call, note choices). Historical docs stay untouched.
- [ ] Commit (`docs: retire chezmoi references`).

### Task 4: Live cutover on behemoth (controller/owner)

**Steps (controller, not a subagent — small and sequential):**
- [ ] Safety: confirm no running `nvim` processes; confirm `chezmoi diff` still empty (source vs live unchanged since survey).
- [ ] Pre-switch cleanup on behemoth: `rm -rf ~/.config/nvim ~/.config/alacritty`; `rm ~/.config/nushell/{config.nu,env.nu,catppuccin_mocha.nu}` (KEEP history.txt + vendor/); `rm -rf ~/.config/chezmoi ~/.local/share/chezmoi` (stale boltdb + forgotten Nov-2025 source clone).
- [ ] Brew-no-op guard: verify no `modules/darwin/`/Brewfile changes in P5 commits, then run `just switch` (P4 precedent, owner standing approval assumed only if guard passes; otherwise hand to owner).
- [ ] Verify: `readlink -f ~/.config/nvim` → repo `config/nvim`; nushell files symlinked, history.txt + vendor intact; alacritty symlinked; `~/dotfiles` symlink exists; `echo $DOTFILES` correct in a fresh shell; `nvim --headless "+q"` exits 0 (config loads); write-through test: `touch` a file via `~/.config/nvim/` and see it appear in `git status`, then remove it; `chezmoi` gone from PATH; open a fresh nushell (`nu -c "version"`) exits 0.
- [ ] Push; CI green (watch the run).
- [ ] Update memory `project_env_refactor.md`: P5 complete, next P6 (flake flatten — includes the broken `just fmt` formatter fix); note rocinante/stargazer cutover pending (their next HM switch deploys symlinks; pre-clean their live `~/.config` copies + stale chezmoi state the same way); update MEMORY.md index line. Also update `project_nvim_update_workflow.md`: the re-add gotcha is dead — `:AstroUpdate` then plain `git commit` of `config/nvim/lazy-lock.json`.

## Completion checklist (controller)

- [ ] `chezmoi/` gone from the repo tree; `config/{nvim,nushell,alacritty}` in place with real filenames.
- [ ] All 24 files deployed as out-of-store symlinks; nushell machine-local files untouched.
- [ ] chezmoi module/package/justfile/live-state fully removed on behemoth.
- [ ] `$DOTFILES` still exported everywhere; `~/dotfiles` exists on behemoth.
- [ ] lazy-lock write-through verified (edit in `~/.config/nvim` shows in `git status`).
- [ ] Docs accurate; CI green; memories updated; Linux-host cutover noted.
