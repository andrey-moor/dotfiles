# Dotfiles

Nix-based dotfiles for macOS (nix-darwin) and Linux (NixOS/home-manager).

## Architecture

**Hybrid approach:**
- **Nix/home-manager**: Packages, services, and declarative configs (starship, tmux, bat, git, jj, gpg)
- **config/**: Mutable configs that change frequently (neovim/AstroVim, nushell, alacritty) — symlinked into `~/.config` by home-manager
- **Homebrew** (macOS): GUI applications via casks

`flake.nix` is hand-rolled: one explicit block per host — `darwinConfigurations.behemoth`
(nix-darwin + home-manager) and `homeConfigurations.{rocinante,stargazer}` (standalone
home-manager on foreign Linux). It shares a `mkPkgs` helper (allowUnfree; overlays
`./overlays`, a `pkgs.main` overlay from nixpkgs master, and NUR) and passes
`{ inherit inputs dotfilesDir; }` as `specialArgs` / `extraSpecialArgs`.

Modules are **not** auto-discovered. `home/{core,dev,darwin,linux}.nix` are bundles —
plain `imports` lists over the feature files in `home/{shell,dev,linux,profiles}/` — and
each `hosts/<host>/default.nix` imports the bundles it wants plus any one-off feature
files. Importing a module is what enables it.

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
just fmt         # Format nix files (nixfmt)
just lint        # Same gate as CI: nixfmt --check + statix + deadnix
```

## Mutable Configs

Neovim, nushell, and alacritty configs live in `config/` and are deployed by home-manager as out-of-store symlinks into `~/.config`.

**Editing configs (e.g., neovim):**
```bash
# Edit files directly in the repo — changes are live immediately, no apply step
nvim config/nvim/lua/plugins/user.lua
```

Neovim's `lazy-lock.json` writes through the symlink, so plugin updates are committed straight from the working copy. Nushell's `history.txt` and `vendor/` stay machine-local (only the `.nu` config files are symlinked).

**Path configuration:**
- The repo path is a per-host `dotfilesDir` string set in `flake.nix`
  (`~/Documents/dotfiles` on behemoth, `~/dotfiles` on the Linux hosts) and passed to
  modules as a `specialArgs` function argument
- `$DOTFILES` env var is exported for shell scripts

## Upgrading Packages

```bash
just update   # Update all flake inputs
just switch   # Rebuild with new versions
```

Homebrew packages auto-update on each `switch` (configured via `onActivation.autoUpdate`).

## Initial Setup (Linux - standalone home-manager)

For non-NixOS Linux (e.g., Omarchy, Arch, Ubuntu):

**1. Install Nix (Determinate Systems installer):**
```bash
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install
```

**2. Clone this repository:**
```bash
git clone <your-repo-url> ~/dotfiles
cd ~/dotfiles
```

**3. Apply home-manager configuration:**
```bash
nix run home-manager -- switch --flake .#rocinante
```

**4. Set nushell as default shell (one-time):**
```bash
echo ~/.nix-profile/bin/nu | sudo tee -a /etc/shells
chsh -s ~/.nix-profile/bin/nu
```

Neovim/nushell/alacritty configs are symlinked from `config/` by the home-manager switch itself — no extra step.

## Directory Structure

```
.
├── flake.nix              # Flake entrypoint (explicit per-host blocks)
├── hosts/
│   ├── behemoth/          # macOS host (nix-darwin)
│   ├── rocinante/         # x86_64 Linux host (standalone home-manager)
│   └── stargazer/         # aarch64 Linux VM (standalone home-manager)
├── home/                  # home-manager modules
│   ├── default.nix        # HM base, loaded on every host
│   ├── core.nix           # Bundle: profile + shell tools every host gets
│   ├── dev.nix            # Bundle: dev tooling every host gets
│   ├── darwin.nix         # Bundle: macOS-only members
│   ├── linux.nix          # Bundle: Linux-only members
│   ├── shell/             # Shell tools (starship, tmux, bat, gpg, ssh, etc.)
│   ├── dev/               # Dev tools (neovim, go, rust, jj, kubernetes, claude)
│   ├── linux/             # Linux-only features (intune, wayvnc, edge, firefox)
│   └── profiles/          # User-specific configs
├── modules/darwin/        # macOS system modules (base, containers, homebrew)
├── overlays/              # nixpkgs overlays
├── packages/              # Local package definitions
├── config/                # Mutable configs (nvim, nushell, alacritty, litellm)
├── justfile               # Command runner
└── README.md
```

## Modules

Importing a module enables it — there is no `enable` flag on ordinary modules. The
"Imported by" column says which bundle carries it (`home/core.nix`, `home/dev.nix`,
`home/darwin.nix`, `home/linux.nix`) or which host imports it directly.

### Shell (`home/shell/`)
| Module | Description | Imported by |
|--------|-------------|-------------|
| `alacritty.nix` | Alacritty terminal (config from `config/alacritty`) | core |
| `atuin.nix` | Shell history sync/search | core |
| `bat.nix` | Better cat (Catppuccin theme) | core |
| `direnv.nix` | Directory-based environments | core |
| `ghostty.nix` | Ghostty terminal emulator | core |
| `git.nix` | Git configuration + signing (**options**) | core |
| `gpg.nix` | GPG agent with Yubikey support | core |
| `lazygit.nix` | Git TUI | core |
| `nushell.nix` | Nu shell (config from `config/nushell`) | core |
| `onepassword.nix` | 1Password SSH agent + commit signing (**options**) | core |
| `openvpn.nix` | OpenVPN client | core |
| `ssh.nix` | SSH client config (GitHub, FIDO2 keys) | core |
| `starship.nix` | Prompt with Nerd Font symbols | core |
| `tmux.nix` | Terminal multiplexer (Catppuccin theme) | core |
| `lan-mouse.nix` | Keyboard/mouse sharing over LAN (**options**) | darwin |

### Dev (`home/dev/`)
| Module | Description | Imported by |
|--------|-------------|-------------|
| `bazel.nix` | Bazel build system tools | dev |
| `claude.nix` | Claude Code CLI + agent-stack wiring (**options**) | dev |
| `codex.nix` | OpenAI Codex CLI | dev |
| `go.nix` | Go toolchain + gopls, delve | dev |
| `jj.nix` | Jujutsu VCS (**options**) | dev |
| `kubernetes.nix` | kubectl, k9s, kubectx, kind, stern, kubelogin (**options**) | dev |
| `neovim.nix` | Neovim + LSP deps (config from `config/nvim`) | dev |
| `nix.nix` | Nix development tools | dev |
| `opencode.nix` | OpenCode AI coding agent | dev |
| `rust.nix` | Rust toolchain via rustup + cargo tools | dev |
| `terraform.nix` | Terraform infrastructure tools | dev |
| `vscode.nix` | VS Code with extensions | dev |
| `copilot.nix` | GitHub Copilot CLI | behemoth, rocinante |
| `hunk.nix` | Review-first terminal diff viewer | behemoth, rocinante |
| `lmstudio.nix` | LM Studio desktop app for local LLMs | rocinante |
| `python.nix` | Python development tools | rocinante, stargazer |

### Linux (`home/linux/`)
| Module | Description | Imported by |
|--------|-------------|-------------|
| `firefox.nix` | Firefox with privacy extensions (NUR) | linux |
| `intune.nix` | Microsoft Intune Portal + identity brokers (**options**) | linux |
| `wayvnc.nix` | WayVNC server for Wayland remote access (**options**) | linux |
| `containers.nix` | Podman container services via systemd user units (**options**) | stargazer |
| `edge.nix` | Microsoft Edge (x86_64) | rocinante |
| `edge-rosetta.nix` | Microsoft Edge (aarch64 via Rosetta) | stargazer |
| `rosetta.nix` | Rosetta x86_64 emulation for aarch64-linux | `intune.nix`, `edge-rosetta.nix` |

### Profiles (`home/profiles/`)
| Module | Description | Imported by |
|--------|-------------|-------------|
| `andreym.nix` | Git/jj identity, signing via 1Password | core |

### Darwin (`modules/darwin/`)
| Module | Description | Imported by |
|--------|-------------|-------------|
| `default.nix` | macOS base (defaults, state version, HM backup ext) | behemoth |
| `containers.nix` | Container services via launchd (**options**) | behemoth |
| `homebrew.nix` | Homebrew integration via nix-homebrew (**options**) | behemoth |

Modules marked **options** are the 11 parameterized ones; they declare settings under
`modules.<category>.<name>` that hosts fill in. Everything else is a plain module.

## Adding a New Tool

1. Create a plain module — no options, no `enable`, no `mkIf`:
   ```nix
   # home/shell/mytool.nix
   { pkgs, ... }:
   {
     home.packages = [ pkgs.mytool ];
   }
   ```

2. Import it. Every host → add to a bundle (`home/core.nix`, `home/dev.nix`,
   `home/darwin.nix`, `home/linux.nix`):
   ```nix
   imports = [
     # ...
     ./shell/mytool.nix
   ];
   ```
   One host only → add it to that host's `imports` in `hosts/<host>/default.nix`.

3. Rebuild: `just switch`.

A new `.nix` file does nothing until something imports it. Add an option only when two
hosts need the same module with different values.

## Formatting & Lint

```bash
just fmt     # nixfmt over `git ls-files '*.nix'`
just lint    # nixfmt --check + statix check + deadnix --fail (the CI gate)
```

CI runs the same three checks in a `lint` job, plus `nix flake check --all-systems` and a
build (or eval, for stargazer) of each host. `statix.toml` disables `repeated_keys` and
ignores `spikes/`.

## Disko (Disk Formatting)

Not wired up yet. The `disko` flake input is kept for P7 (NixOS on rocinante's second
NVMe), which will add the `disk.nix` layout and a `nixosConfigurations` block. There is no
`disk.nix` and no `just disko-format` recipe today.
