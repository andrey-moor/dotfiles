# Env Refactor P4 — Agent Stack Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the five chezmoi `run_onchange` agent-stack installers with native home-manager wiring: one `agents/` source of truth (AGENTS.md + skills + commands) fanned out to Claude Code, Codex, Copilot CLI, and opencode; a declarative MCP attrset; GSD/sentrux/karpathy/ECC deleted from live state.

**Architecture (settled in brainstorm, 2026-08-31):**
- **Declare what we author; the app owns what it mutates.** Three file classes: (1) authored content (AGENTS.md, skills, commands) — full nix via out-of-store symlinks per spec §4; (2) shared read/write files (`~/.claude/settings.json`, `~/.codex/config.toml`) — a declared subset merged at activation time, everything else preserved; (3) app-owned state (`~/.claude.json`, plugin caches, `~/.copilot/config.json`) — never touched.
- **settings.json**: `home.activation` jq merge porting `modify_settings.json` semantics, with `enabledPlugins` + `extraKnownMarketplaces` now **authoritative overwrites** (declared list is the single source of truth; ad-hoc installs revert on switch). `autoMode`, `model`, `permissions`, `tui`, etc. are never declared and never touched. **Do NOT set `programs.claude-code.settings` or `.marketplaces`** — either one flips settings.json to a read-only store symlink (verified in module source: write condition is `settings != {} || marketplaces != {} || disabledMcpServerNames != []`).
- **MCP**: `programs.mcp.servers` + `programs.claude-code.enableMcpIntegration`. Verified in the pinned HM source: this synthesizes a personal plugin named `hm` carrying `.mcp.json`; Claude Code loads it natively (tools become `mcp__plugin_hm_<server>__*`). MCP stays Claude-only in P4 (codex/copilot MCP would require managing their mutable config files — deferred).
- **Plugins**: nix declares *which* (enabledPlugins/marketplaces via the merge); each harness's native manager handles *content* fetch/update (spec §0). Add = one attrset line + switch; remove = delete line + switch.
- **Other harnesses**: AGENTS.md context + skills fan-out only. Provider/model config (`~/.codex/config.toml` Azure work endpoint + runtime-appended trust list, `~/.copilot/config.json`) stays hand-managed and out of the public repo.
- **Vendor-neutral skills dir**: `~/.agents/skills` (read by codex + copilot) gets the same out-of-store symlinks as `~/.claude/skills`.

**Tech stack:** home-manager `programs.{claude-code,codex,opencode,github-copilot-cli,mcp}` (pin 82c265fa, 2026-08-31 — all modules verified present), `mkOutOfStoreSymlink`, jq activation script, nix-darwin/`just`.

**Spec:** `docs/superpowers/specs/2026-07-23-environment-refactor-design.md` §5 (+ §4 mutable boundary, §8 step 3). Owner decisions from brainstorm: GSD delete now; keep plugins superpowers, frontend-design, code-review, document-skills, example-skills, skill-creator, agent-browser, context7; drop supabase, swift-lsp, clangd-lsp, karpathy (lines inlined into AGENTS.md), sentrux, GSD; ralph-loop@local stays unmanaged; opencode standardized like the others (not dropped).

## Global Constraints

- **PUBLIC REPO.** Never commit: `autoMode` content (Microsoft/OCTO work facts), the Azure OpenAI work endpoint, tenant material, or anything from `~/.claude.json`. `op://` references are fine (they are pointers, not secrets).
- **NEVER run `just switch` non-interactively** (2026-08-31 Homebrew incident: brew bundle prompts get EOF and proceed destructively). `just build` is the implementer ceiling; `just switch` is owner-run with Touch ID.
- Do not touch: `spikes/`, `chezmoi/dot_config/` (nvim/nushell — that's P5), the Obsidian vault, `~/.gsd` data (only harness integration is removed), unmanaged keepers in `~/.claude/skills` (`orrery-*`, `wrap`, `code-search`, `xcodebuildmcp-cli`) and `~/.claude/plugins/ralph-loop-v2`.
- The chezmoi **module** stays enabled (nvim/nushell still need it until P5). Only the agent-stack parts of the chezmoi source tree are removed.
- Conventional commits, one commit per task, CI green after every push.
- HM module options are preferred, but **verify each module does not take ownership of a hand-managed file** (codex `config.toml`, copilot `config.json`) before enabling; fall back to raw `home.file`/`mkOutOfStoreSymlink` where a module would clobber. The effect (a symlink in the right place) is identical.
- All cleanup scripts must be idempotent and print what they would delete before deleting.

---

### Task 1: `agents/` source tree + AGENTS.md distillation

**Files:**
- Create `agents/AGENTS.md`, `agents/CLAUDE.md.tpl` note not needed — importer is generated in Task 2.
- `git mv chezmoi/private_dot_claude/skills/kb agents/skills/kb` (SKILL.md + references/×6).
- `git mv` commands: `chezmoi/private_dot_claude/commands/commit.md` → `agents/commands/commit.md`; `commands/kb/*.md` (12 files) → `agents/commands/kb/`. The three `commands/dotfiles/*.md` are **not** moved (retired in Task 5).

**Steps:**
- [ ] Extract the karpathy lines: read the installed karpathy plugin content (`~/.claude/plugins/` cache / marketplace checkout for `andrej-karpathy-skills`) and shortlist the guidance lines worth keeping, BEFORE the plugin is uninstalled in Task 6.
- [ ] Draft `agents/AGENTS.md`, ~30–50 lines, distilled invariants only. Sources: current global `chezmoi/private_dot_claude/CLAUDE.md` (14 lines — carry all of it), the ECC `rules/common/*` files (keep only true invariants: immutability preference, explicit-over-implicit, KISS/YAGNI, conventional-commit format; drop everything that is workflow prose, reference material, or covered by superpowers/linters per spec §5 taxonomy), chosen karpathy lines. Structure: Coding style / Environment & machines / Tools / Git.
- [ ] Move skills + commands as listed above; delete the stale packaged `chezmoi/private_dot_claude/skills/kb.skill` zip from the chezmoi source if present there (live copy handled in Task 6).
- [ ] **USER REVIEW GATE:** present the AGENTS.md draft diff to the owner and iterate until approved. Do not proceed to Task 2 without approval.
- [ ] Commit (`feat(agents): AGENTS.md + skills/commands source tree`).

### Task 2: Claude Code home-manager module + settings merge

**Files:**
- Rewrite `modules/home/dev/claude.nix` → agent-stack wiring (or new `modules/home/dev/agent-stack.nix` absorbing claude.nix; implementer's call, one module preferred).
- Edit `hosts/{behemoth,rocinante,stargazer}/default.nix` (enable; obsidian-MCP flag on behemoth only — used in Task 3).

**Steps:**
- [ ] `programs.claude-code.enable = true`, `package = inputs.claude-code-nix...` (same source as today's claude.nix). **Leave `settings`, `marketplaces`, `mcpServers` unset** (read-only trap, see Architecture).
- [ ] Global context: `~/.claude/CLAUDE.md` = thin importer whose content is a single `@~/.agents/AGENTS.md` line (module `context` option is fine here — static one-liner). `~/.agents/AGENTS.md` = `mkOutOfStoreSymlink "${dotfilesDir}/agents/AGENTS.md"` via `home.file` (out-of-store per spec §4: edit in repo, live immediately).
- [ ] Skills fan-out: for each dir under `agents/skills/` create out-of-store symlinks at BOTH `~/.claude/skills/<name>` and `~/.agents/skills/<name>`. Prefer `programs.claude-code.skills` with out-of-store paths if it accepts them; else `home.file`. Watch the module's unique-name assertions vs. unmanaged live skills (orrery-* etc. are not module-declared, so no collision expected).
- [ ] Commands fan-out: `agents/commands/` → `~/.claude/commands/` entries (same mechanism; keep `commit.md` and `kb/` namespace exactly as today so `/commit` and `/kb:*` keep working).
- [ ] Settings merge: `home.activation.claudeSettingsMerge` (after `writeBoundary`), jq, creating the file if absent. Declared attrset rendered with `builtins.toJSON`:
  - authoritative overwrite: `alwaysThinkingEnabled = true`, `effortLevel = "high"`, `env.CLAUDE_CODE_SHELL = "/usr/bin/bash"` (comment: bare `bash` breaks OpenSSH 10.2 `Match exec`), `enabledPlugins`, `extraKnownMarketplaces`.
  - `enabledPlugins`: the 8 keepers — derive the exact `name@marketplace` keys from the live `~/.claude/settings.json` (survey lists 13; keep superpowers, frontend-design, code-review, document-skills, example-skills, skill-creator, agent-browser, context7). `ralph-loop@local` is not in enabledPlugins and must not appear in the declared set.
  - `extraKnownMarketplaces`: `claude-plugins-official`, `anthropic-agent-skills`, `agent-browser` (exact JSON shapes copied from live settings.json). sentrux-marketplace and karpathy-skills are dropped (removal itself happens in Task 6; the authoritative overwrite keeps them from coming back).
  - everything else in settings.json: preserved verbatim (`model`, `permissions`, `tui`, `autoMode`, `statusLine`, `hooks`, misc flags).
  - merge must be idempotent (running twice = no change) and must fail loudly (non-zero) on jq errors, never truncate the file (write to temp + `mv`).
- [ ] `just build` passes on behemoth config; `nix flake check` green. (No switch yet.)
- [ ] Commit (`feat(agents): native claude-code HM module + settings merge`).

### Task 3: MCP attrset

**Files:** same module; `hosts/behemoth/default.nix` (obsidian flag); delete repo-root `.mcp.json` gsd-workflow entry (drop the file if nothing else remains).

**Steps:**
- [ ] `programs.mcp.enable = true`; `programs.claude-code.enableMcpIntegration = true`; servers:
  - `kagi`: `op run -- uvx --python 3.13 kagimcp` with `env.KAGI_API_KEY = "op://Private/Kagi/api_key"` (reference, not a secret — same as today).
  - `fetch`: `uvx mcp-server-fetch`.
  - `obsidian` (behemoth-gated option): `npx -y @bitbonsai/mcpvault@latest "<iCloud Obsidian path>"` — copy the exact path from the live `~/.claude.json` entry.
- [ ] Ensure all declared servers have `enabled = true`/default — a disabled server flips the settings.json read-only condition (`disabledMcpServerNames`).
- [ ] Remove `gsd-workflow` from repo `.mcp.json`.
- [ ] Note in the module comment: user-scope duplicates in `~/.claude.json` are removed in Task 6; tool namespace changes to `mcp__plugin_hm_<server>__*`.
- [ ] `just build` green. Commit (`feat(agents): declarative MCP servers`).

### Task 4: Codex / Copilot / opencode standardization

**Files:** rewrite `modules/home/dev/codex.nix` (delete the LiteLLM `OPENAI_BASE_URL=127.0.0.1:4000` wrapper — dead code, live config is Azure); edit `modules/home/dev/copilot.nix`, `modules/home/dev/opencode.nix`; hosts files.

**Steps:**
- [ ] **codex**: package as today (`pkgs.codex`, no wrapper). Context: `~/.codex/AGENTS.md` ← out-of-store symlink to `agents/AGENTS.md`. Skills: `~/.agents/skills` already covers codex. **Before using `programs.codex`, read its module source (store path in Architecture) and confirm enabling with empty `settings` does NOT write/own `~/.codex/config.toml`** — the live file is hand-managed (Azure endpoint, runtime-appended trust list). If the module would touch it, use raw `home.file` for AGENTS.md and skip `programs.codex` entirely.
- [ ] **copilot**: keep the `copilot-cli-flake` + version-pin machinery as the package source. Context + skills via `programs.github-copilot-cli` **only if** it leaves `~/.copilot/config.json` and `settings.json` alone (same verification rule); else raw symlinks. Port the openssl-cert-warning filter wrapper from the retired installer only if the warning still reproduces (test `copilot --help` after switch). Superpowers stays via its existing direct install; document the reinstall one-liner (`copilot plugin install obra/superpowers`) in the module comment.
- [ ] **opencode**: `programs.opencode.enable`, package `pkgs.main.opencode`, `context` ← same AGENTS.md source, `skills` ← same skills set. No provider settings declared (repo-level `opencode.json` continues to carry the Azure project config; nothing exists in `~/.config/opencode` today, so the module can own its config dir safely).
- [ ] Enable codex + opencode on behemoth (currently missing there; rocinante/stargazer already enable them).
- [ ] `just build` green for all three hosts (`nix build` the rocinante/stargazer HM configs too — catches Linux-only eval errors). Commit (`feat(agents): AGENTS.md + skills fan-out for codex/copilot/opencode`).

### Task 5: Chezmoi purge + docs

**Files:**
- Delete from `chezmoi/`: all five `run_onchange_install-{ecc,gsd,plugins,mcp,copilot-plugins}.sh.tmpl`, `.ecc-version`, `.gsd-version`, and the whole `private_dot_claude/` tree (skills/commands already moved in Task 1; CLAUDE.md + modify_settings.json are superseded).
- Edit repo `CLAUDE.md` (project): chezmoi section now covers only `dot_config/` (nvim/nushell/alacritty); remove the modify-template + `/dotfiles:claude-setup`//`claude-sync` paragraph; add a short "Agent stack" section pointing at `agents/` + the HM modules and the add/remove-a-plugin one-liner workflow.
- Check `justfile` for dead references (ecc/gsd targets, if any).

**Steps:**
- [ ] Delete + edit as above. `chezmoi-diff` should show no pending agent-stack changes (chezmoi never deletes deployed targets — live cleanup is Task 6).
- [ ] Verify `rg -i "ecc|gsd|modify_settings|claude-setup|claude-sync" chezmoi/ CLAUDE.md justfile` returns nothing stale.
- [ ] Commit (`refactor(agents): retire chezmoi agent-stack layer`).

### Task 6: Live-state cleanup (OWNER-GATED — destructive)

**Files:** create `scripts/agent-stack-cleanup.sh` (committed — it will be re-run on rocinante/stargazer later).

**Steps:**
- [ ] Script (idempotent; `--dry-run` default, `--apply` to execute; prints every path before removal):
  - `claude plugin uninstall` + marketplace removal for: sentrux, andrej-karpathy-skills, supabase, swift-lsp, clangd-lsp; `claude plugin marketplace remove sentrux-marketplace karpathy-skills`.
  - ECC: remove `~/.claude/rules/` (44 ECC files — the whole dir is ECC-installed), the 10 ECC agents in `~/.claude/agents/` (exact names in survey: security-reviewer, code-reviewer, database-reviewer, go-reviewer, go-build-resolver, python-reviewer, kotlin-reviewer, build-error-resolver, tdd-guide, refactor-cleaner), the 7 ECC skills (api-design, security-review, tdd-workflow, docker-patterns, deployment-patterns, golang-patterns, golang-testing).
  - GSD: remove `gsd-*` skills (~65), `gsd-*` agents (33), `~/.claude/hooks/` GSD files + `lib/`, `~/.claude/get-shit-done/`, `~/.claude/gsd-local-patches/`, `~/.claude/gsd-migration-journal/`; jq-delete the `hooks` and `statusLine` keys from `~/.claude/settings.json` (all entries are GSD; nothing else uses them). **Leave `~/.gsd` untouched** (data, incl. the KB project the `.planning` symlink targets).
  - MCP dedup: `claude mcp remove -s user kagi fetch obsidian` (now served by the `hm` plugin).
  - Misc: remove live `~/.claude/skills/kb.skill` (stale zip) and `~/.claude/skills/kb` + `~/.claude/commands/{kb,dotfiles,commit.md}` copies IF they are plain files/dirs (chezmoi-deployed) — HM will replace them with symlinks on switch; leave anything already a symlink.
  - MUST NOT touch: `orrery-*`, `wrap`, `code-search`, `xcodebuildmcp-cli` skills; `ralph-loop-v2` plugin dir; `~/.claude/projects/`, `backups/`, `history`/session state; `~/.claude.json` beyond the `claude mcp remove` CLI calls.
- [ ] Run `--dry-run`, show the owner the full deletion list, **wait for explicit approval**, then `--apply` on behemoth.
- [ ] Commit the script (`feat(agents): live-state cleanup script`).

### Task 7: Switch, verify, close out

**Steps:**
- [ ] `just build` final; then **owner runs `just switch` interactively** (Touch ID; watch brew bundle prompts).
- [ ] Verify on behemoth, fresh `claude` session:
  - `~/.claude/CLAUDE.md` importer resolves (context shows AGENTS.md content); `~/.agents/AGENTS.md` + skills symlinks point into the repo working copy (edit a skill file, confirm live without switch).
  - `/kb:*` commands + kb skill present; `/commit` present; orrery skills untouched.
  - Plugins converge to exactly the 8 declared (+ ralph-loop local); dropped plugins gone; `mcp__plugin_hm_*` tools available (kagi/fetch/obsidian); no duplicate user-scope MCP.
  - `/config` still works (settings.json is a writable real file); re-run `home-manager` activation → settings merge idempotent (file unchanged).
  - No `gsd`/ECC remnants: statusline gone, no hook errors on tool use, `rg gsd ~/.claude/settings.json` empty.
  - codex: `~/.codex/AGENTS.md` present, `~/.codex/config.toml` byte-identical to pre-switch backup (take one before switching), superpowers plugin still loads.
  - copilot + opencode launch; opencode sees context/skills.
- [ ] Push; CI green.
- [ ] Note for later (not this session): run `scripts/agent-stack-cleanup.sh` + HM switch on rocinante and stargazer at next visit.
- [ ] Update memory `project_env_refactor.md`: P4 complete, next P5; record the read-only-settings trap + `hm` MCP plugin mechanics as recipe facts.

## Completion checklist (controller)

- [ ] All five installers gone from chezmoi; `agents/` is the only authoring location.
- [ ] AGENTS.md owner-approved; CLAUDE.md is a one-line importer everywhere.
- [ ] settings.json writable, merge idempotent, declared keys authoritative, `autoMode` untouched and uncommitted.
- [ ] 8 plugins + 3 marketplaces declared; add/remove = attrset edit + switch.
- [ ] MCP via `hm` plugin; `~/.claude.json` user-scope entries removed.
- [ ] GSD/ECC/sentrux/karpathy fully out of `~/.claude`; `~/.gsd` data intact.
- [ ] codex/copilot provider configs hand-managed and unpolluted; LiteLLM wrapper deleted.
- [ ] rocinante/stargazer follow-up noted; CI green; memory updated.
