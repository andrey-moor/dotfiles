# Dotfiles

Nix-based dotfiles for macOS (nix-darwin) and Linux (NixOS/home-manager).

## Architecture

**Hybrid approach:**
- **Nix/home-manager**: Packages, services, and declarative configs (starship, tmux, bat, git, jj, gpg)
- **chezmoi**: Mutable configs that change frequently (neovim/AstroVim, nushell)
- **Homebrew** (macOS): GUI applications via casks

## Initial Setup (macOS)

**1. Install Nix (Determinate Systems installer):**
```bash
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install
```

**2. Install Homebrew:**
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**3. Clone this repository:**
```bash
git clone <your-repo-url> ~/Documents/dotfiles
cd ~/Documents/dotfiles
```

**4. Bootstrap nix-darwin:**

Since `just` isn't available yet, run the bootstrap command directly:
```bash
nix run nixpkgs#darwin-rebuild -- switch --flake .#behemoth
```

This builds the configuration and installs nix-darwin itself along with all packages (including `just`).

**5. After bootstrap, use `just` commands:**
```bash
just switch
```

## Prerequisites

After initial setup, you'll have:
- [Nix](https://nixos.org/) with flakes enabled (via Determinate Systems)
- [Just](https://github.com/casey/just) command runner (installed by nix-darwin)

## Quick Start

## Common Commands

```bash
just switch      # Apply configuration
just build       # Build without applying
just update      # Update flake inputs (nixpkgs, etc.)
just clean       # Garbage collect old generations
just fmt         # Format nix files
```

## Chezmoi (Mutable Configs)

Neovim and nushell configs are managed by chezmoi and live in `chezmoi/` directory.

**Editing configs (e.g., neovim):**
```bash
# 1. Edit files directly in the repo
nvim chezmoi/dot_config/nvim/lua/plugins/user.lua

# 2. Apply changes to ~/.config
just chezmoi-apply   # or: chezmoi apply

# Preview changes before applying:
just chezmoi-diff    # or: chezmoi diff
```

**Path configuration:**
- Default dotfiles path: `~/.dotfiles`
- Override per-host via `modules.dotfilesDir` (e.g., behemoth uses `~/Documents/dotfiles`)
- Chezmoi source dir is automatically set to `${dotfilesDir}/chezmoi`
- `$DOTFILES` env var is exported for shell scripts

## Upgrading Packages

```bash
just update   # Update all flake inputs
just switch   # Rebuild with new versions
```

Homebrew packages auto-update on each `switch` (configured via `onActivation.autoUpdate`).

## Directory Structure

```
.
├── flake.nix              # Flake entrypoint
├── hosts/
│   ├── behemoth/          # macOS host (nix-darwin)
│   └── rocinante/         # Linux host (NixOS)
├── modules/
│   ├── darwin/            # macOS-specific modules
│   │   └── homebrew.nix   # Homebrew casks & brews
│   └── home/              # home-manager modules
│       ├── shell/         # Shell tools (starship, tmux, bat, gpg, ssh, etc.)
│       ├── dev/           # Dev tools (neovim, go, rust, jj, kubernetes, claude)
│       └── profiles/      # User-specific configs
├── chezmoi/               # Mutable configs (nushell, nvim)
│   └── dot_config/
├── justfile               # Command runner
└── README.md
```

## Modules

### Shell (`modules/home/shell/`)
| Module | Description |
|--------|-------------|
| `starship.nix` | Prompt with Nerd Font symbols |
| `tmux.nix` | Terminal multiplexer (Catppuccin theme) |
| `bat.nix` | Better cat (Catppuccin theme) |
| `lazygit.nix` | Git TUI |
| `gpg.nix` | GPG agent with Yubikey/SSH support |
| `ssh.nix` | SSH client config (GitHub, FIDO2 keys) |
| `ghostty.nix` | Terminal emulator |
| `nushell.nix` | Nu shell (package only, config via chezmoi) |
| `git.nix` | Git configuration with GPG signing |
| `direnv.nix` | Directory-based environments |
| `chezmoi.nix` | Chezmoi dotfile manager |

### Dev (`modules/home/dev/`)
| Module | Description |
|--------|-------------|
| `neovim.nix` | Neovim + LSP deps (config via chezmoi/AstroVim) |
| `go.nix` | Go toolchain + gopls, delve |
| `rust.nix` | Rust toolchain via rustup + cargo tools |
| `jj.nix` | Jujutsu VCS |
| `kubernetes.nix` | kubectl, helm, k9s, kubectx, kind, stern, kubelogin |
| `claude.nix` | Claude Code CLI |

### Darwin (`modules/darwin/`)
| Module | Description |
|--------|-------------|
| `homebrew.nix` | Homebrew integration via nix-homebrew |

## Adding a New Tool

1. Create module in appropriate directory:
   ```nix
   # modules/home/shell/mytool.nix
   { lib, config, pkgs, ... }:
   with lib;
   let cfg = config.modules.shell.mytool;
   in {
     options.modules.shell.mytool = {
       enable = mkEnableOption "MyTool";
     };
     config = mkIf cfg.enable {
       home.packages = [ pkgs.mytool ];
     };
   };
   ```

2. Enable in host config (`hosts/behemoth/default.nix`):
   ```nix
   modules.shell.mytool.enable = true;
   ```

3. Rebuild: `just switch`

Note: Modules are auto-discovered from the filesystem - no manual imports needed.

## Disko (Disk Formatting)

**Note**: Disko is only relevant for NixOS installations (not macOS/nix-darwin). This dotfiles repo currently focuses on macOS (nix-darwin) and Linux (home-manager). If you plan to use NixOS in the future, disko provides declarative disk partitioning.

For fresh NixOS installs:

```bash
just disko-format <host>
```

**Warning**: This erases the target disk completely.
