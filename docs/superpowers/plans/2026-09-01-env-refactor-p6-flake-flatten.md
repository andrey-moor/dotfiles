# Env Refactor P6 — Flake Flatten Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 482-line `lib/` DSL + filesystem auto-discovery with a plain hand-rolled `flake.nix` (explicit per-host `darwinSystem` / `homeManagerConfiguration`), drop the `enable` ceremony on the 32 pure wrapper modules (import = enabled), keep options only on the 12 genuinely parameterized modules, prune dead inputs/options/code, add a `formatter` + CI lint gate, and prove zero regression via identical closure output paths.

**Spec:** `docs/superpowers/specs/2026-07-23-environment-refactor-design.md` §3 (+ §7 "Updates" row for CI lint). Brainstorm decisions 2026-09-01: bundles (A); lint level 2 (nixfmt formatter + CI `fmt --check`/statix/deadnix, repo-wide reformat, no treefmt); delete `modules/nixos/` (zero uses; P7 rewrites); rocinante/stargazer stay standalone HM until P7.

**Architecture:**
- **`flake.nix`** (~100 lines): 15 inputs (drop `fenix`, `mcp-hub`; keep `disko` for P7). Inline `mkPkgs = system: import nixpkgs { inherit system; config.allowUnfree = true; overlays = [ (import ./overlays) pkgsMainOverlay nur.overlays.default ]; }` where `pkgsMainOverlay` provides `pkgs.main` from `nixpkgs-main` (allowUnfree) — the `pkgs.unstable` overlay is dead and goes. Three explicit host blocks. `specialArgs` / `extraSpecialArgs = { inherit inputs; dotfilesDir = "<per-host path>"; }` replaces the thrice-declared `modules.dotfilesDir` option. HM integration on darwin: `useGlobalPkgs`, `useUserPackages`, `backupFileExtension`, `sharedModules = [ catppuccin.homeModules.catppuccin sops-nix.homeManagerModules.sops ]` — preserve exactly what `lib/mkFlake.nix` does today (read it; darwin builder lines 81-127, home builder 130-164). `formatter.<system> = nixfmt-rfc-style`; `devShells.<system>.default = import ./shell.nix` exposed properly. Also `nixpkgs.pkgs = mkDefault pkgs` + `networking.hostName = mkDefault name` for darwin, `home.username`/`home.homeDirectory` base for standalone HM — exactly as mkFlake does.
- **Layout**: `hosts/<h>/default.nix` = plain module (imports + config; the current `{ system; config = {...}: {...}; }` host-record form disappears — `system` moves into flake.nix). `modules/home/` → `home/`: bundles `home/core.nix`, `home/dev.nix`, `home/darwin.nix`, `home/linux.nix` (plain `imports = [ ... ]` lists) over feature files in `home/{shell,dev,linux,profiles}/`. Bundle membership is derived from what the three hosts enable today (compute the intersection/differences from `hosts/*/default.nix`; universal shell+profile items → core; universal dev items → dev; platform-specific → darwin/linux; anything enabled on only one host stays a per-host import). `modules/darwin/` keeps `containers.nix`, `homebrew.nix`, and the macOS base (`default.nix`), imported explicitly by behemoth. DELETE: `lib/`, `modules/default.nix` (loader), `modules/nixos/`, `modules/home/linux/*.bak`, `modules/home/dev/default.nix` (empty stub), dead option `modules.shell.default`, the `user.*` option set in `modules/default.nix` (replace consumers with literals/specialArgs preserving identical values — `containers.nix` reads `config.user.dataDir`).
- **Options**: 32 wrappers lose `options.modules.*.enable` + `mkIf cfg.enable` — body becomes unconditional config. The 12 parameterized modules (`darwin/containers`, `darwin/homebrew`, `linux/containers`, `linux/intune` (debug), `linux/wayvnc`, `shell/git`, `shell/lan-mouse`, `shell/onepassword` (signer), `dev/claude` (obsidianVault), `dev/jj`, `dev/kubernetes` (helm), — `nixos/docker` is deleted) keep their non-enable options under the EXISTING `modules.<cat>.<name>` names (no renames); their `enable` option is dropped too (import = enabled) unless a host currently imports-but-disables it (rocinante has `lan-mouse.enable = false` with config retained → simply don't import lan-mouse on rocinante; keep the config block commented or drop — implementer's call, note it). `modules.profiles.user` dropped: `home/profiles/andreym.nix` is imported by `core`. Cross-coupling made explicit: `intune.nix` + `edge-rosetta.nix` get `imports = [ ./rosetta.nix ]` instead of setting `modules.linux.rosetta.enable`; `ssh.nix`'s `config.modules.shell.onepassword.enable` guard becomes unconditional (both in core everywhere); `andreym.nix` keeps writing `modules.shell.git.*` (git keeps those options).
- **nixGL**: `config.lib.nixGL.wrap` usage and per-host `targets.genericLinux.nixGL.packages` stay as-is.
- **Zero-regression proof**: baseline output paths captured 2026-09-01 BEFORE any change:
  - behemoth `darwinConfigurations.behemoth.system` → `/nix/store/dhd449ybbfzpvy9x5kk51m35rjqz16ac-darwin-system-26.11.4cff07d`
  - rocinante `homeConfigurations.rocinante.activationPackage` → `/nix/store/kiawmmid7gqfiyz5r83km1hblqqjh4w9-home-manager-generation`
  - stargazer `homeConfigurations.stargazer.activationPackage` → `/nix/store/vzm7f58w8i24kx4z656630ss39q6fy9i-home-manager-generation`
  After Task 1 and again after Tasks 2–3, `nix eval --raw .#<attr>` MUST print these exact paths. Any deviation: STOP, diff the two closures (`nix derivation show` / `nix-diff` via `nix run nixpkgs#nix-diff`), identify the cause, and either fix the flatten or report the justified difference to the controller. Do not proceed on a mismatch without controller sign-off.

## Global Constraints

- Identical output paths are the acceptance test for Tasks 1–3 (see above). `just build` green and `nix flake check --all-systems` green in addition.
- CI attribute paths must keep working unchanged: `darwinConfigurations.behemoth.system`, `homeConfigurations.{rocinante,stargazer}.activationPackage`.
- Implementer ceiling: `just build` / `nix eval` / `nix build`. No `just switch` (controller runs it with the brew-no-op guard).
- Do not change any module's *behavior* (packages, settings, file contents) — this phase is declaration-shape only. If you find a bug, note it, don't fix it.
- Do not touch `agents/`, `config/`, `spikes/`, `secrets/`, `.sops.yaml`, `overlays/`, `packages/` contents (paths may be re-referenced if files move).
- Conventional commits; commit trailer per the session's git attribution instructions (Co-Authored-By + Claude-Session lines).
- Public repo — nothing secret is involved.

---

### Task 1: The flatten (single coherent commit)

**Steps:**
- [ ] Read `lib/mkFlake.nix` fully and write down every value it injects (pkgs config, overlays + ORDER, specialArgs, HM flags, base modules, sharedModules) — this list is what flake.nix must reproduce.
- [ ] Compute the host×module enable matrix from `hosts/*/default.nix` → derive bundle membership (core / dev / darwin / linux / per-host-only). Record the matrix in the commit message body or a short comment at the top of each bundle.
- [ ] Write `flake.nix` per Architecture. Run `nix flake lock` so `flake.lock` drops `fenix`/`mcp-hub`.
- [ ] `git mv modules/home/* → home/*` (feature files keep their filenames); create the four bundles; rewrite `hosts/*/default.nix` as plain modules; strip enable ceremony from the 32 wrappers; convert coupling to imports; replace `config.modules.dotfilesDir` → `dotfilesDir` specialArg and `config.user.*` → literals/specialArgs; delete `lib/`, `modules/default.nix`, `modules/nixos/`, `.bak` files, `modules/home/dev/default.nix`, `modules.shell.default`, `modules.profiles.user`.
- [ ] Update `justfile`: recipes referencing flake attrs keep working; remove `disko-format` (points at a nonexistent `disk.nix`; P7 recreates) — or leave with a comment; implementer's call, note it.
- [ ] Verify: the three `nix eval --raw` paths match the baseline EXACTLY; `just build` green; `nix flake check --all-systems` green (matches CI); `nix flake show` lists formatter + devShells for all 4 systems; `rg "modules\.(shell\.default|profiles\.user|dotfilesDir)|mapModulesRec|mkFlake|lib\.my" --glob '!docs/**'` returns nothing live.
- [ ] Commit: `refactor(flake): hand-rolled flake, bundles, drop lib/ DSL and enable ceremony` with the enable-matrix summary in the body.

### Task 2: Formatter + repo-wide reformat

**Steps:**
- [ ] Confirm `formatter.<system> = pkgs.nixfmt-rfc-style` (added in Task 1) works: `just fmt` runs clean.
- [ ] Run `nix fmt` over the repo; review the diff is formatting-only (`git diff --stat`; spot-check a few files).
- [ ] Verify the three output paths STILL match baseline; `just build` green.
- [ ] Commit: `style: nixfmt repo-wide` .

### Task 3: CI lint gate

**Steps:**
- [ ] Add a `lint` job to `.github/workflows/ci.yaml` (ubuntu): `nix fmt -- --check .` (or `nix run nixpkgs#nixfmt-rfc-style -- --check` over `**/*.nix`), `nix run nixpkgs#statix -- check .`, `nix run nixpkgs#deadnix -- --fail .`. Match the existing workflow's install/cache steps.
- [ ] Run all three locally; fix findings (deadnix will likely flag unused module args after the flatten; statix suggestions — apply the mechanical ones). Behavior must not change: re-verify the three output paths match baseline after fixes.
- [ ] Commit: `ci: nixfmt/statix/deadnix lint job` .

### Task 4: Docs

**Steps:**
- [ ] `CLAUDE.md`: rewrite "Flake Structure" + "Module System" (no mkFlake, no auto-discovery, no `_` prefix rule): explain flake.nix host blocks, `home/` bundles + feature files, "adding a tool = write a feature file, add it to a bundle or a host", where options still exist (the 12), `dotfilesDir` specialArg, `just fmt` + CI lint. Update the Commands block if justfile changed. Remove the "New .nix files are automatically loaded" notes.
- [ ] `README.md`: same for its architecture / add-a-module / Disko sections (Disko section: reword to "reserved for P7" or drop).
- [ ] `hosts/*/README.md` + `docs/rocinante-encrypted-install.md`: fix any `modules.*.enable` instructions that no longer apply.
- [ ] Sweep: `rg -i "mkFlake|auto-discover|mapModulesRec|mkEnableOption|modules\.shell\.default" --glob '!docs/superpowers/**' --glob '!docs/archive/**' --glob '!docs/environment-*'` → fix live hits; leave historical docs.
- [ ] Commit: `docs: flattened flake layout` .

### Task 5: Switch, verify, close out (controller)

- [ ] Brew-no-op guard (no `modules/darwin/homebrew.nix` behavior change — the file may have moved/reformatted; confirm the generated Brewfile content is unchanged via the identical system closure), then `just switch`. Expect a near no-op activation.
- [ ] Post-switch: `darwin-rebuild --list-generations | tail -2`; `readlink /run/current-system` equals the baseline behemoth path; `just fmt` clean; `nix develop -c true` works.
- [ ] Push; watch CI (4 existing jobs + new lint job) green.
- [ ] Memory: P6 complete, next P7 (NixOS on rocinante's 2nd NVMe — needs disko `disk.nix`, nixosSystem block, `home/` bundles reused); update MEMORY.md index; note that docs claiming CI lint are now TRUE.

## Completion checklist (controller)

- [ ] `lib/` gone; `flake.nix` hand-rolled; 15 inputs; formatter + devShells exposed.
- [ ] Three closures byte-identical to baseline after every task.
- [ ] 32 wrappers enable-free; 12 parameterized modules keep options; bundles `core/dev/darwin/linux` in place.
- [ ] `just fmt` works; CI lint job green; repo formatted.
- [ ] Docs describe the new shape; no auto-discovery claims remain.
- [ ] behemoth switched (no-op), memory updated.
