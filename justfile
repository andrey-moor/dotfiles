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

# ============================================
# OrbStack VM (Stargazer) - Build VM
# ============================================
# Setup (one-time):
#   1. just stargazer-create
#   2. just stargazer-nix-install
#   3. just stargazer-switch
#   4. ssh -F ~/.orbstack/ssh/config stargazer@orb "touch ~/.netrc"
#
# Note: Uses Ubuntu (not NixOS) for binary compatibility with Bazel downloads

# Create OrbStack Ubuntu VM for builds
stargazer-create:
    orbctl create ubuntu:noble stargazer

# Install Nix on Stargazer (first-time setup)
stargazer-nix-install:
    ssh -F ~/.orbstack/ssh/config stargazer@orb "curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install --no-confirm"

# Delete OrbStack VM
stargazer-delete:
    orbctl delete stargazer -f

# Apply home-manager config to Stargazer
stargazer-switch:
    ssh -F ~/.orbstack/ssh/config stargazer@orb ". /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh && nix run home-manager/master -- switch --flake /Users/andreym/Documents/dotfiles#stargazer"

# Build stargazer config locally (validation)
stargazer-build:
    nix build '.#homeConfigurations.stargazer.activationPackage' --dry-run

# SSH into Stargazer
stargazer-ssh:
    ssh stargazer@orb

# Run monorepo build on Stargazer
stargazer-monorepo-build target="//...":
    ssh stargazer@orb "cd /Users/andreym/Documents/Microsoft/monorepo && bazel build {{target}}"

# Configure Stargazer as remote builder for behemoth (Determinate Nix)
stargazer-builder-setup:
    @echo "Adding Stargazer as remote builder to /etc/nix/nix.conf..."
    @grep -q "stargazer@orb" /etc/nix/nix.conf 2>/dev/null || \
        sudo tee -a /etc/nix/nix.conf <<< "builders = ssh://andreym@stargazer@orb aarch64-linux /Users/andreym/.ssh/id_ed25519 4 2 nixos-test,big-parallel"
    @grep -q "builders-use-substitutes" /etc/nix/nix.conf 2>/dev/null || \
        sudo tee -a /etc/nix/nix.conf <<< "builders-use-substitutes = true"
    @echo "Restarting nix-daemon..."
    sudo launchctl kickstart -k system/org.nixos.nix-daemon
    @echo "Done! Test with: nix build --builders '' .#homeConfigurations.stargazer.activationPackage"
