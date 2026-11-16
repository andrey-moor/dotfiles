# Default host (override with: just --set host myhost switch)
host := "behemoth"

# Show available commands
default:
    @just --list

# On a Mac without `just` yet: nix develop --command just bootstrap

# Bootstrap nix-darwin (first-time setup only)
bootstrap:
    nix build .#darwinConfigurations.{{host}}.system
    sudo ./result/sw/bin/darwin-rebuild switch --flake .#{{host}}

# Build, show which packages change, then apply
switch:
    #!/usr/bin/env bash
    set -euo pipefail
    # nh is installed by this config. The plain command covers a system that
    # does not have it yet.
    if command -v nh >/dev/null; then
      nh darwin switch --hostname {{host}} .
    else
      sudo darwin-rebuild switch --flake .#{{host}}
    fi

# Apply without the change summary
switch-plain:
    sudo darwin-rebuild switch --flake .#{{host}}

# Build without applying (creates ./result symlink)
build:
    nix build .#darwinConfigurations.{{host}}.system

# Update all flake inputs
update:
    nix flake update

# Update a specific input
update-input input:
    nix flake update {{input}}

# Update only the Claude Code input (leaves nixpkgs and everything else pinned)
update-claude:
    nix flake update claude-code-nix

# Bump copilot CLI pin to the latest @github/copilot release on npm
bump-copilot:
    scripts/bump-copilot

# Delete every old generation and collect garbage (removes the rollback)
clean:
    nix-collect-garbage -d

# Remove result symlink
clean-result:
    rm -f result

# Format nix files
fmt:
    nix fmt -- $(git ls-files '*.nix')

# Check formatting + run statix/deadnix/shellcheck/actionlint (same gate as CI)
lint:
    nix fmt -- --check $(git ls-files '*.nix')
    nix run nixpkgs#statix -- check .
    nix run nixpkgs#deadnix -- --fail --exclude spikes
    nix run nixpkgs#shellcheck -- -S warning $(git ls-files scripts)
    nix run nixpkgs#actionlint -- -ignore SC2046

# Pure theme-library checks (no build)
test-theme:
    nix eval --raw --impure --expr 'import ./tests/theme.nix { pkgs = (builtins.getFlake (toString ./.)).nixosConfigurations.stargazer.pkgs; }'

# Check flake
check:
    nix flake check

# Show flake info
info:
    nix flake show

# Update inputs and switch. Old generations are kept, so a bad update can be
# rolled back. `just clean` removes them, and is a separate step on purpose.

# Update inputs and switch (keeps the rollback generations)
rebuild:
    just update
    just switch

# Lend this Mac's YubiKey to a Linux host over VirtualHere (hosts/behemoth/README.md)
yubikey host="rocinante":
    scripts/yubikey to {{host}}

# Take the YubiKey back and stop sharing it
yubikey-back host="rocinante":
    scripts/yubikey back {{host}}

# Show where the YubiKey is
yubikey-status host="rocinante":
    scripts/yubikey status {{host}}

# Render the gateway's secrets from 1Password (run again after changing a key)
gateway-secrets:
    mkdir -p ~/.config/behemoth-containers
    umask 077 && op inject --force -i config/containers/gateway.env.tpl -o ~/.config/behemoth-containers/gateway.env
    @echo "rendered. Apply with: just gateway-up"

# Apply config/containers/compose.yaml as it was at the last `just switch`
gateway-up:
    launchctl kickstart -k gui/$(id -u)/org.nixos.behemoth-containers
    @echo "started. Follow with: just gateway-logs"

# Show the containers and what the gateway can reach
gateway-status:
    /usr/local/bin/docker compose -p behemoth ps
    @curl -s -m 5 -o /dev/null -w "gateway /health: %{http_code}\n" http://127.0.0.1:8080/health
    @curl -s -m 5 -o /dev/null -w "LM Studio server: %{http_code}\n" http://127.0.0.1:1234/v1/models

# Follow the log of the agent that applies the Compose file
gateway-logs:
    tail -n 40 -f ~/Library/Logs/behemoth-containers.log

# ============================================
# Linux (home-manager) hosts
# ============================================

# Build home-manager config for a Linux host (from this machine)
hm-build linux-host:
    nix build '.#homeConfigurations.{{linux-host}}.activationPackage'

# Build rocinante config locally (cross-compile check)
rocinante-build:
    nix build '.#homeConfigurations.rocinante.activationPackage' --dry-run
