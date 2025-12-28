# Default host (override with: just --set host myhost switch)
host := "behemoth"

# Show available commands
default:
    @just --list

# Bootstrap nix-darwin (first-time setup only)
bootstrap:
    nix build .#darwinConfigurations.{{host}}.system
    sudo ./result/sw/bin/darwin-rebuild switch --flake .#{{host}}

# Build and apply configuration
switch:
    sudo darwin-rebuild switch --flake .#{{host}}

# Build without applying (creates ./result symlink)
build:
    nix build .#darwinConfigurations.{{host}}.system

# Update all flake inputs
update:
    nix flake update

# Update a specific input
update-input input:
    nix flake lock --update-input {{input}}

# Garbage collect old generations
clean:
    nix-collect-garbage -d

# Remove result symlink
clean-result:
    rm -f result

# Format nix files
fmt:
    nix fmt

# Check flake
check:
    nix flake check

# Show flake info
info:
    nix flake show

# Apply chezmoi changes
chezmoi-apply:
    chezmoi apply

# Show chezmoi diff
chezmoi-diff:
    chezmoi diff

# Full rebuild: update inputs, switch, and clean
rebuild:
    just update
    just switch
    just clean

# ============================================
# Linux (home-manager) hosts
# ============================================

# Build home-manager config for a Linux host (from this machine)
hm-build linux-host:
    nix build '.#homeConfigurations.{{linux-host}}.activationPackage'

# Apply home-manager on rocinante via prlctl
rocinante-switch:
    prlctl exec Rocinante -- bash -c 'cd ~/dotfiles && home-manager switch --flake .#rocinante'

# Build rocinante config locally (cross-compile check)
rocinante-build:
    nix build '.#homeConfigurations.rocinante.activationPackage' --dry-run

# Format disk using disko for a specific host
disko-format disko-host:
    sudo nix run \
        --extra-experimental-features nix-command \
        --extra-experimental-features flakes \
        github:nix-community/disko \
        -- --mode zap_create_mount ./hosts/{{disko-host}}/disk.nix
