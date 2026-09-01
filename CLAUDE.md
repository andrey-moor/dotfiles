# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
just switch          # Build and apply nix configuration
just build           # Build without applying
just update          # Update flake inputs (nixpkgs, etc.)
just fmt             # Format nix files (nixfmt over `git ls-files '*.nix'`)
just lint            # Same gate as CI: nixfmt --check + statix + deadnix
just check           # Check flake validity
```

For a different host: `just --set host <hostname> switch`

## Architecture

**Hybrid dotfiles approach:**
- **Nix (nix-darwin + home-manager)**: Packages, services, declarative configs
- **agents/**: AI agent config (AGENTS.md, skills, commands) — fanned out by home-manager as out-of-store symlinks
- **config/**: Authored configs (nvim, nushell, alacritty, litellm) — deployed by home-manager as out-of-store symlinks, edits live immediately
- **Homebrew** (macOS only): GUI applications via casks

### Flake Structure

`flake.nix` is hand-rolled — no builder lib, no filesystem magic. It declares one explicit block per host:

- `darwinConfigurations.behemoth` → `darwin.lib.darwinSystem` (nix-darwin + home-manager as a darwin module)
- `homeConfigurations.rocinante` / `homeConfigurations.stargazer` → `home-manager.lib.homeManagerConfiguration` (standalone HM on foreign Linux; P7 will move rocinante to NixOS)

Shared pieces, all inline in `flake.nix`:
- **`mkPkgs system`** — `import nixpkgs` with `config.allowUnfree = true` and overlays, in order: `./overlays`, a `pkgs.main` overlay (nixpkgs master, also allowUnfree, for packages that land there first), `nur.overlays.default`.
- **`specialArgs` / `extraSpecialArgs` = `{ inherit inputs dotfilesDir; }`** — `dotfilesDir` is a per-host string literal (`/Users/andreym/Documents/dotfiles` on behemoth, `/home/andreym/dotfiles` on Linux), not an option. Modules take it as a function argument.
- **`homeBase`** — `./home` (HM base: stateVersion, `$DOTFILES`, xdg, core packages) + `catppuccin.homeModules.catppuccin` + `sops-nix.homeManagerModules.sops`, applied on every host.
- `formatter.<system> = pkgs.nixfmt` and `devShells.<system>.default = import ./shell.nix` for `x86_64-linux`, `aarch64-linux`, `aarch64-darwin` (`x86_64-darwin` is dropped — nixpkgs 26.11 no longer evaluates it).

Each `hosts/<host>/default.nix` is a self-contained plain module: its own `imports` list plus its config. The flake block only supplies `system`, `pkgs`, `dotfilesDir` and the HM wiring.

### Module System

**Importing a module is what enables it.** There is no auto-discovery and no `enable` flag on ordinary modules.

Layout:
- `home/{core,dev,darwin,linux}.nix` — bundles: plain `{ imports = [ ... ]; }` lists.
  - `core` — profile + shell tools every host gets
  - `dev` — dev tooling every host gets
  - `darwin` / `linux` — platform-only members
- `home/{shell,dev,linux,profiles}/*.nix` — the feature files themselves.
- `modules/darwin/{default,containers,homebrew}.nix` — macOS system-level (nix-darwin) modules, imported explicitly by `hosts/behemoth`.

A host imports the bundles it wants plus any one-off feature files (e.g. rocinante adds `home/dev/lmstudio.nix`; behemoth deliberately gets `home/shell/lan-mouse.nix` via `home/darwin.nix` while rocinante deliberately does not import it).

**Adding a tool:**
1. Write `home/<category>/<tool>.nix` — a plain module, no options, no `mkIf`:
   ```nix
   { pkgs, ... }:
   {
     home.packages = [ pkgs.mytool ];
   }
   ```
2. Add it to a bundle (`home/core.nix`, `home/dev.nix`, ...) if every host should have it, or to a single host's `imports` if not.
3. `just switch`.

Add an option only when two hosts need the *same* module with *different* values.

### Parameterized Modules

These 11 modules keep options (under their existing `modules.*` names); hosts set values, imports still do the enabling:

| Option path | What it configures |
|-------------|--------------------|
| `modules.darwin.containers` | `runtime`, `logDir`, `containers.*` — launchd container services |
| `modules.darwin.homebrew` | `casks`, `brews`, `masApps` |
| `modules.linux.containers` | `containers.*` — podman systemd user units |
| `modules.linux.intune` | `debug` |
| `modules.linux.wayvnc` | `passwordFile`, `port`, `address`, `monitor`, resolutions, `gpu`, `renderCursor` |
| `modules.shell.git` | `userName`, `userEmail`, `signingKey`, `signingFormat`, `signer` |
| `modules.shell.lan-mouse` | `port`, `gpu`, `releaseBind`, `authorizedFingerprints`, `clients` |
| `modules.shell.onepassword` | `signer` (op-ssh-sign path; read by the andreym profile) |
| `modules.dev.claude` | `obsidianVault` (adds the obsidian MCP server when set) |
| `modules.dev.jj` | `userName`, `userEmail` |
| `modules.dev.kubernetes` | `helm` (opt-in; nixpkgs helm breaks recurrently) |

### Formatting & Lint

`nix fmt` uses `pkgs.nixfmt`. `just fmt` formats, `just lint` runs the exact CI gate: `nixfmt --check` over `git ls-files '*.nix'`, `statix check .`, `deadnix --fail --exclude spikes`. CI runs the same three in a `lint` job alongside `flake-check` and the three per-host builds.

`statix.toml` disables `repeated_keys` (flat dotted paths like `home.packages` / `programs.git.enable` are the nixpkgs idiom here) and ignores `spikes/`.

### Mutable Configs

Frequently-edited configs live in `config/{nvim,nushell,alacritty}` and are deployed by home-manager as out-of-store symlinks into `~/.config` — edits in the repo are live immediately, no apply step. Notes:
- nvim's `lazy-lock.json` writes through the symlink; commit it straight from the working copy
- nushell: only `config.nu`, `env.nu`, `catppuccin_mocha.nu` are symlinked — `history.txt` and `vendor/` stay machine-local

### Agent Stack

`agents/` is the source of truth for AI agent config: `AGENTS.md` (global context) + `skills/` + `commands/`. Home-manager modules (`home/dev/{claude,codex,copilot,opencode}.nix`) fan it out as out-of-store symlinks — edits in the repo are live immediately, no rebuild.

- **settings.json**: declared-subset merge at activation; everything else (model, permissions, autoMode, ...) is app-owned and never touched. Never set `programs.claude-code.settings`/`.marketplaces` (makes settings.json a read-only store symlink).
- **Plugins/marketplaces**: declared in `home/dev/claude.nix` (`enabledPlugins`/`extraKnownMarketplaces`, authoritative). Add/remove = edit attrset + `just switch`; content updates via `claude plugin update`.
- **MCP servers**: same module, via `programs.mcp` (surfaced as the `hm` plugin, tools `mcp__plugin_hm_<server>__*`).

## Hosts

- **behemoth**: macOS workstation (aarch64-darwin)
- **rocinante**: x86_64 Arch Linux (Omarchy) workstation, accessed via Tailscale
- **stargazer**: aarch64-linux Parallels VM on behemoth with LUKS encryption (Intune compliance)

### Behemoth (macOS)

Primary macOS workstation. Dotfiles at `/Users/andreym/Documents/dotfiles`.

**Build/switch:** `just switch` (runs `darwin-rebuild switch`)

### Rocinante (Tailscale)

x86_64 Arch Linux (Omarchy) workstation, accessed via Tailscale SSH.

**Access:** `ssh rocinante` (via Tailscale SSH)
**Dotfiles:** `/home/andreym/dotfiles` (git clone)

**Build/switch:**
```bash
cd ~/dotfiles
nix run home-manager -- switch --flake .#rocinante -b backup
```

**Notes:**
- Native x86_64 — no Rosetta needed
- See `hosts/rocinante/README.md` for full setup instructions

### Stargazer (Parallels VM - Encrypted)

aarch64-linux Parallels VM on behemoth with LUKS full-disk encryption for Microsoft Intune compliance. Runs Omarchy (Hyprland).

**Dotfiles:** `/home/andreym/dotfiles` (git clone, same path as rocinante)

**Build/switch (from within stargazer):**
```bash
cd ~/dotfiles
nix run home-manager -- switch --flake .#stargazer -b backup
```

**Notes:**
- aarch64-linux with Rosetta for x86_64 emulation
- Same `/home/andreym/dotfiles` path as rocinante — distinguish by `hostname` or `uname -m` (aarch64 vs x86_64)
- Uses nixGL with mesa (virtio_gpu in Parallels)
- See `hosts/stargazer/README.md` for full setup instructions

## Notes

- Uses Determinate Nix installer (`nix.enable = false` in darwin config)
- A new `.nix` file under `home/` does nothing until something imports it — add it to a bundle or a host
- Cross-module coupling is explicit: `home/linux/{intune,edge-rosetta}.nix` import `home/linux/rosetta.nix` directly
