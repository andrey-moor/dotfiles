# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
just switch          # Build and apply nix configuration
just build           # Build without applying
just update          # Update flake inputs (nixpkgs, etc.)
just fmt             # Format nix files
just check           # Check flake validity
just chezmoi-apply   # Apply chezmoi changes to ~/.config
just chezmoi-diff    # Preview chezmoi changes
```

For a different host: `just --set host <hostname> switch`

## Architecture

**Hybrid dotfiles approach:**
- **Nix (nix-darwin + home-manager)**: Packages, services, declarative configs
- **Chezmoi**: Mutable configs that change frequently (neovim, nushell)
- **Homebrew** (macOS only): GUI applications via casks

### Flake Structure

The flake uses a custom `lib.mkFlake` builder (`lib/mkFlake.nix`) that:
- Auto-detects host type from system string (darwin vs linux)
- Darwin hosts → `darwinConfigurations` (nix-darwin + home-manager)
- Linux hosts → `homeConfigurations` (standalone home-manager)
- Auto-discovers modules via `mapModulesRec'` from filesystem

### Module System

Modules are **auto-discovered** from the filesystem - no manual imports needed.

**Module pattern** (`modules/home/{shell,dev}/*.nix`):
```nix
{ lib, config, pkgs, ... }:
with lib;
let cfg = config.modules.<category>.<name>;
in {
  options.modules.<category>.<name> = {
    enable = mkEnableOption "<description>";
  };
  config = mkIf cfg.enable {
    home.packages = [ ... ];
  };
}
```

Enable in host config: `modules.<category>.<name>.enable = true;`

### Key Options

- `modules.dotfilesDir`: Path to dotfiles repo (default: `~/.dotfiles`)
- `modules.profiles.user`: User profile to load (sets git identity, signing key)
- `modules.shell.*`: Shell tools (git, ssh, gpg, tmux, starship, etc.)
- `modules.dev.*`: Dev tools (neovim, go, rust, kubernetes, etc.)

### Chezmoi Integration

Chezmoi source lives in `chezmoi/` directory. The `modules.shell.chezmoi` module:
- Installs chezmoi
- Configures sourceDir to `${dotfilesDir}/chezmoi`
- Exports `$DOTFILES` env var for shell scripts

To edit neovim config: edit `chezmoi/dot_config/nvim/...`, then `chezmoi apply`.

## Hosts

- **behemoth**: macOS workstation (aarch64-darwin)
- **rocinante**: Linux host (x86_64-linux)

## Notes

- Uses Determinate Nix installer (`nix.enable = false` in darwin config)
- New `.nix` files in `modules/home/` are automatically loaded
- Files prefixed with `_` are ignored by module discovery
