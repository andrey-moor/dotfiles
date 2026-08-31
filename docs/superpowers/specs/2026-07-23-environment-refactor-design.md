# Environment Refactor — Design

*2026-07-23. Product of the two-pass environment review
(`docs/environment-design-independent.md`, `docs/environment-review-pass-b.md`) plus the
fork-by-fork brainstorm. All forks and ride-along aspects resolved with the owner; research
citations live in the two review docs. This is the spec the implementation plan derives from.*

## 0 · North star & principles

- **Everything nixed**: hosts and VMs run NixOS (or nix-darwin) unless a hard constraint
  forbids it; the only candidate exceptions are the Intune-facing VM (pending spikes) and
  Windows.
- **Updates must be boring**: every machine updates atomically with generation rollback;
  nothing imperative mutates a live system on someone else's schedule. The Omarchy
  "scared to update" problem is eliminated structurally, not managed.
- **Boring, legible Nix**: explicit imports over auto-discovery; options only where
  parameterized; a config readable after three months away.
- **One tool per job**: home-manager owns dotfiles (chezmoi retires); native HM modules
  over hand-rolled sync; each agent harness's native plugin manager over custom installers.
- **Tools are replaceable** when a better fit exists — no sunk-cost attachment.

## 1 · Target fleet

| Host | Hardware/locus | OS / manager | Role |
|---|---|---|---|
| **behemoth** | MacBook (Apple Silicon) | macOS · nix-darwin + integrated HM · Determinate Nix | Primary workstation |
| **rocinante** | Framework Desktop (Strix Halo, 128 GB) | **NixOS** (unstable), LUKS+btrfs via disko, on 2nd NVMe (`…801777`) | Devbox · VM host · fleet builder · LLM server |
| **work-vm** | VM on rocinante | Winner of spikes: NixOS+himmelblau / NixOS+intuneme / Ubuntu 24.04 | The *only* corporate-enrolled Linux; full dev env (compliant-device requirement) |
| **ubuntu-baseline** | VM on rocinante | Ubuntu 24.04 LTS, NixVirt-declared shape + autoinstall | Guaranteed corporate access regardless of spike outcomes; standalone HM for dotfiles |
| **stargazer** (successor) | Parallels VM on behemoth | NixOS aarch64, declared in flake | Fallback devbox when rocinante unreachable; himmelblau if proven; keep-alive automated |
| **Nostromo** | Parallels on behemoth (286G, 10 vCPU/64G RAM) | Windows 11 ARM (existing, **domain-joined**) | Mac-side corporate access **today** — chosen because Windows joins the company tenant easily; sanctioned, in daily use, **kept regardless**. Not the preferred UX: it is the safety net that lets the Linux path be experimented with freely. Not nixed; backed up. (`Orrery-Win11-ARM64`, 29G, is a second stopped Win11 VM.) |
| *(legacy)* rocinante/Omarchy disk | 1st NVMe | frozen — no further updates ever | Fallback of record until 30 days post-cutover, then reclaimed |
| *(legacy)* old stargazer | Parallels | frozen | Deleted after successor passes fire drill |

Corporate blast radius: Intune/Entra/Azure-VPN/YubiKey live **only** in work-vm,
ubuntu-baseline, stargazer-successor (if himmelblau proves out), and windows-vm.
The hosts stay clean. No Rosetta anywhere (Apple is sunsetting it).

*Collapse rule: if both spikes fail, work-vm and ubuntu-baseline merge into a single
Ubuntu 24.04 VM (B2 becomes the work-vm); the fleet then has one Linux corporate VM,
not two.*

## 2 · Resolved decisions (forks A–E)

| Fork | Resolution |
|---|---|
| **A — NixOS staging** | `nixos-anywhere` from behemoth over tailnet onto the 2nd NVMe, targeted **by-id** (`nvme-WD_BLACK_SN7100_2TB_25317P801777` — NVMe enumeration swaps on this box; never `/dev/nvmeXn1`). Old install on that disk confirmed orphaned (no fstab/crypttab/ESP references from Omarchy). Dual-boot via firmware menu; Omarchy disk untouched. |
| **B — Intune path** | **RESOLVED 2026-08-31 — see `2026-08-31-p2-spike-verdict.md`. B4 (himmelblau) wins.** Entra join + Intune enrollment + compliance machinery all PASS on x86_64 and aarch64 NixOS (join-then-Intune ordering defused the 530003 catch-22; FIDO key at a local console is the passwordless-account first factor). Compliance verdict is NonCompliant on exactly three axes: distro allowlist (honest "NixOS" not allowed — the strategic P8 decision), LUKS, Secure Boot (both ordinary engineering). B3 (intuneme) not viable on NixOS: systemic bare-FHS-path exec failures, portal UI never launched, 10 manual pokes vs B4's 0. The old `intune.nix` + os-release spoof retire unported once P8 lands; the fuse is now understood to be the allowlist policy question. |
| **C — Mac-side VM** | Parallels stays (already licensed; hosts Nostromo). Successor = aarch64 NixOS in Parallels, same dev layer, corp layer = himmelblau-or-nothing (no Rosetta port). **Wanted in addition to Nostromo, not instead of it** — the owner prefers working in Linux; Windows was the path of least resistance for joining the tenant. Nostromo staying live is what makes the Linux path low-risk to attempt: a failed himmelblau spike costs nothing operationally. If himmelblau doesn't prove out, the successor remains a pure dev VM and corporate work stays on Nostromo. Weekly keep-alive: boot → `nh` switch → Intune check-in (if enrolled) → shutdown. Fire drill before old stargazer is deleted. |
| **D — Repo visibility** | Public. sops-nix for secrets (age; host keys via ssh-to-age; master key in 1Password). Rotate the exposed wayvnc passwords + untrack `archinstall-creds.json`; **no history rewrite**. Escape valve: a private flake input for corp-sensitive material *if it ever accumulates* — decide per artifact (see §10, doc placement). |
| **E — Chezmoi & agent stack** | Chezmoi **retired, not deleted** (tree stays in history; standalone HM covers Ubuntu VMs — every fleet machine can run Nix). Agent stack rebuilt on native HM modules (§5). GSD deleted. |

## 3 · Flake & module architecture

- **Plain hand-rolled flake.** Explicit `darwinSystem` / `nixosSystem` /
  `homeManagerConfiguration` per host in `flake.nix` (~10 lines each,
  `specialArgs = { inherit inputs; }`). `lib/mkFlake.nix` + `mapModulesRec'`
  auto-discovery deleted; no framework (flake-parts optional later, not now).
- **Module discipline**: hosts import feature files directly. `mkEnableOption` ceremony
  dropped for the ~35 wrapper modules; options survive only where genuinely parameterized
  (containers, lan-mouse, git identity). Promotion to `modules/` at second use only.
- **Integrated HM** on behemoth + rocinante + NixOS VMs; `homeConfigurations` only for
  foreign-distro machines (ubuntu-baseline, work-vm-if-Ubuntu, legacy transitional).
- **Inputs**: single `nixpkgs` (nixos-unstable) + `nixpkgs-main` (bleeding-edge apps);
  the redundant `nixpkgs-unstable` alias dropped. Dead inputs pruned (agenix out —
  sops-nix in; disko stays, now actually used). `follows` discipline maintained.
- **Layout**:

```
flake.nix flake.lock justfile
hosts/{behemoth,rocinante,stargazer,work-vm…}/   # per-host: default.nix (+hardware,disko)
home/            # shared HM layer: core, dev, desktop-linux, darwin
modules/         # nixos/, darwin/ — only multi-host shared code
agents/          # AGENTS.md, skills/, memory — the agent-stack source of truth
vms/             # NixVirt domains, autoinstall/cloud-init seeds
secrets/         # sops age-encrypted + .sops.yaml
overlays/ packages/ docs/{runbooks,archive,superpowers}
```

- **Repo hygiene**: `kb-engine/` extracted to its own repository (dotfiles module
  references it by path); root `.pkg.tar.xz` artifacts + `hypr-pkgs/` deleted (the NixOS
  migration ends hand-built Arch packages); `.bak` modules deleted; stale justfile
  sections pruned.

## 4 · Mutable-config boundary

Fast-iterating configs live in the repo, deployed via `mkOutOfStoreSymlink` (path built as
a string from `config.home.homeDirectory`; repo at `~/dotfiles` canonically — on behemoth
the repo stays at `~/Documents/dotfiles` and HM creates the `~/dotfiles` symlink to it): **neovim (AstroNvim stays
plain Lua; `lazy-lock.json` commits straight from the working copy — revert gotcha dead),
nushell, hyprland overrides, personal skills, AGENTS.md.** Everything else is normal
declarative HM. Chezmoi's `modify_settings.json` merge idea survives inside
`programs.claude-code`'s generated-merge handling.

## 5 · Agent-stack architecture (multi-harness)

- **Instructions**: one `agents/AGENTS.md` (source of truth; Linux-Foundation standard,
  read natively by Codex/Copilot/Cursor); `CLAUDE.md` becomes a thin `@`-importer.
  Content = distilled invariants only (~30–50 lines: immutability, explicit-over-implicit,
  nix-not-brew, commit format, chosen karpathy lines). The nine always-on ECC rule files
  and seven language packs are deleted.
- **Rule taxonomy** (the "skillify?" answer): invariants → AGENTS.md (always-on is
  correct); workflows → skills (superpowers already covers TDD/debugging/planning/review —
  dedupe, don't duplicate); mechanically-checkable rules → hooks/linters (gitleaks
  pre-commit, treefmt, statix/deadnix — prose deleted where a check exists); reference
  material → deleted.
- **Skills**: authored once in `agents/skills/`, fanned out by HM to `~/.claude/skills`
  and `~/.agents/skills` (the vendor-neutral dir Codex + Copilot read). SKILL.md is an
  open cross-tool standard now — write once, run everywhere.
- **HM native modules**: `programs.claude-code` (settings, plugins, marketplaces, skills,
  hooks, memory), `programs.codex`, `programs.opencode`; Copilot CLI (no module yet) gets
  the skills symlink + managed config file. Runtime-mutable state (`~/.claude.json`,
  plugin registry internals) stays unmanaged.
- **MCP servers**: declared once as a Nix attrset (`programs.mcp.servers` /
  mcp-servers-nix pattern), rendered per-tool; secrets via `op run` references, never
  in the store.
- **Plugins**: native marketplaces per harness. Keep: superpowers (must-have; same
  SHA-pinned repo as upstream), Anthropic official (plugins + document-skills),
  agent-browser (conditional on headless-automation use). Drop: GSD, sentrux,
  karpathy-plugin (lines inlined into AGENTS.md), ECC mega-plugin (cherry-pick individual
  MIT-licensed skills into `agents/skills/` if ever wanted). ECC's installer/CLI machinery:
  never adopted.
- All five chezmoi `run_onchange` installers deleted; no `npx`/`curl` at apply time
  anywhere.

## 6 · Desktop: Omarchy as tracked upstream

- `inputs.omarchy = { url = "github:basecamp/omarchy"; flake = false; }` — pinned on
  `master`. *(Verified 2026-07-23: upstream branches are `master`/`dev`/`rc`/**`quattro`**;
  latest stable v3.8.4, 2026-07-21.)* Quattro is adopted by pointing the URL at
  `github:basecamp/omarchy/quattro` in a branch of our own, whenever we choose.
  Updates arrive as lockfile-bump PRs with full upstream diff; CI
  builds before merge; generations roll back after. Tracking is continuous, adoption is
  deliberate — the inversion of `omarchy-update` mutating a live system.
- **Base layer (theirs)**: hypr defaults via Hyprland `source =` include; waybar / walker /
  mako configs; theme sets; the portable subset of `omarchy-*` scripts packaged as a
  derivation (shebangs patched, pacman-coupled scripts filtered) so keybindings and
  muscle memory port unchanged.
- **Override layer (ours)**: personal deltas as separate files loaded after; vendored
  content never edited. **Exit path**: snapshot used files out of the input, delete the
  input — override layer keeps working (proven reversible by construction).
- **System layer (never Omarchy's)**: `programs.hyprland.enable` (portals/session wired),
  PipeWire, `hardware.bluetooth` + blueman, NetworkManager, greetd autologin after LUKS,
  nixos-hardware `framework-desktop-amd-ai-max-300-series` profile.
- **Known risks**: Hyprland 0.55+ hyprlang→Lua migration (port planned within a few
  releases); aquamarine issue #272 (Strix Halo crash — run latest kernel/Mesa via
  unstable; `amdgpu.gpu_recovery=1` mitigation ready).

## 7 · Fleet services

- **Secrets**: sops-nix everywhere; wayvnc-class passwords via `passwordFile` from sops;
  1Password SSH agent for auth; age master key in 1Password + offline copy.
- **Network**: `services.tailscale` declarative on every host (pacman-tailscale retired);
  NixOS firewall default-deny, services tailnet-bound (wayvnc `0.0.0.0` bind eliminated);
  WoL on rocinante + `just wake-rocinante`; SSH host keys pinned in repo `known_hosts`.
- **Remote builds**: rocinante = fleet x86_64-linux builder; behemoth enables nix-darwin
  `nix.linux-builder` for aarch64-linux closures (builds the Mac VM system locally).
- **Local LLM serving** (rocinante): llama.cpp (Vulkan/RADV) + **llama-swap** (nixpkgs;
  speaks OpenAI *and* Anthropic APIs), tailnet-bound; kernel
  `ttm.pages_limit=33554432 ttm.page_pool_size=33554432`; models: gpt-oss-120b (default),
  Qwen3-Coder-30B-A3B (fast), GLM-4.5-Air (strongest agentic) — MoE only, no dense 70B.
  behemoth keeps LM Studio (interactive); LiteLLM fronts local+cloud mixing only.
  hellas-ai/nix-strix-halo adoptable later for ROCm prefill gains.
- **Backups**: restic → Backblaze B2 (per-host repos, creds via sops) for the precious-state
  inventory: `~/dev` uncommitted work, `~/.claude` + `~/.agents` state, Obsidian vault
  (iCloud is sync, not backup), Windows VM cold image. snapper btrfs snapshots on
  rocinante (local oops-recovery). NixOS VMs + work-VM: explicitly cattle, not backed up.
  behemoth currently has **no backup at all** (Time Machine unconfigured) and is at
  **99% disk** — early remediation item. Restore drill documented and rehearsed once.
- **Updates**: weekly `update-flake-lock` PR → CI builds every host closure
  (`macos-15` aarch64-darwin, `ubuntu-latest`, `ubuntu-24.04-arm` — all free on the
  public repo) + `nix flake check` + treefmt/statix/deadnix → auto-merge on green →
  hosts pull via `nh` at leisure; `nh clean all --keep 5 --keep-since 14d`;
  `configurationLimit = 15`.
- **Observability**: GitHub notifications for CI failures; dead-man's-switch pings
  (healthchecks.io free tier) on the two silent-death timers — work-VM Intune check-in,
  stargazer keep-alive; kb-engine's osascript notifications unchanged.

## 8 · Migration sequence

Each step independently valuable, reversible, machines usable throughout.

| # | Step | Retires / delivers |
|---|---|---|
| 0 | **Day-1 triage**: rotate + sops-ify VNC passwords, untrack creds file; declare Omarchy update-freeze; behemoth disk-pressure cleanup (GC, old images) | The scary-update problem (by fiat); public-repo credential exposure |
| 1 | **CI + update automation** on current shape; prune dead inputs + stale justfile | Unguarded updates; input rot; the safety net for everything after |
| 2 | **kb-engine extraction** to own repo | 995 MB + 37/40 commit-noise colocation |
| 3 | **Agent stack rebuild** (§5): HM native modules, AGENTS.md distillation, GSD/sentrux/karpathy/ECC-rules deletion, skills fan-out, MCP attrset | All five run_onchange installers; always-on rules bloat |
| 4 | **Chezmoi retirement**: nvim/nushell/alacritty → mkOutOfStoreSymlink | Second tool; lazy-lock revert gotcha |
| 5 | **Flake flatten**: explicit hosts + imports; delete `lib/` DSL; drop wrapper options | 480-line private lib; option ceremony. Strictly before step 7 |
| 6 | **Spikes B3/B4** (parallel track — begins alongside step 0; Aug fuse): Claude preps 2 VMs on Omarchy-rocinante to enrollment doorstep; joint session for credentials; verdict per success bar | The B-fork uncertainty; informs step 8 |
| 7 | **NixOS install** on 2nd NVMe via nixos-anywhere + disko (by-id!); port `home/` layer; Omarchy-input desktop (§6); backups, tailscale, firewall, builders, llama-swap; **data migration checklist** (~/dev rsync, browser profiles, atuin/shell history, GPG state, rice files off Omarchy disk) | Omarchy as daily driver (disk kept 30 days); nixGL; hand-built packages |
| 8 | **Work-VM** per spike verdict + **ubuntu-baseline** (NixVirt + autoinstall + standalone HM); enroll; verify compliance + CA + VPN + YubiKey | `intune.nix`, os-release spoof, `packages/{intune-portal,microsoft-identity-broker}`, rosetta hacks |
| 9 | **stargazer successor** in Parallels (aarch64 NixOS; himmelblau if proven); keep-alive; fire drill; delete old VM | Hand-installed stargazer; the unexercised-fallback fiction |
| 10 | **Closeout**: reclaim Omarchy disk (becomes scratch/VM storage); docs restructure (`runbooks/` vs `archive/`); README/bootstrap runbooks per host; rollback + restore drills rehearsed; wipe ~/.config/sops/age/keys.txt from the reclaimed Omarchy disk; migrate sops to per-host ssh-to-age keys | Docs drift; the migration itself |

## 9 · Risks & watch-items

- **Aug 2026 Intune 22.04 EOL** — the fuse under step 6's priority.
- **himmelblau vs tenant**: corp precedent unverified; CA enrollment catch-22 possible —
  that's what the spike is for. intuneme unproven on NixOS. Ubuntu baseline caps the
  downside.
- **Compliance-posture honesty**: B3/B4 both end the os-release spoof; policy comfort is
  the owner's judgment as the employee. The sanctioned floor (ubuntu-baseline +
  windows-vm) always exists.
- **Hyprland Lua migration + aquamarine #272** on Strix Halo (§6).
- **Determinate Nix** is now a distinct distribution (upstream option dropped Jan 2026) —
  staying on it is a conscious choice; Lix is the exit if divergence ever bites.
- **Parallels dependency** for both Mac VMs — acceptable (licensed, Windows VM anchors it);
  UTM remains the free exit for the NixOS guest only.

## 10 · Doc placement note (pre-commit decision)

This spec and the review docs discuss the compliance workarounds and spike plans. The
repo is public by decision D. Before these files are committed/pushed, the owner decides:
commit as-is (transparency posture — history already contains the spoof), or hold
env-review docs in a gitignored/private location. Default recommendation: commit the
*design* (it documents the honest end-state), keep the *Pass-B review* (which details the
current spoof mechanics) local-only until step 8 retires the spoof.
