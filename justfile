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

# Update only the Claude Code input (leaves nixpkgs and everything else pinned)
update-claude:
    nix flake update claude-code-nix

# Bump copilot CLI pin to the latest @github/copilot release on npm
bump-copilot:
    #!/usr/bin/env bash
    set -euo pipefail
    pin_file=home/dev/copilot-pin.json
    latest=$(curl -fsSL "https://registry.npmjs.org/@github/copilot/latest" \
      | python3 -c "import json,sys;print(json.load(sys.stdin)['version'])")
    current=$(python3 -c "import json;print(json.load(open('$pin_file'))['version'])")
    echo "current pin: $current"
    echo "npm latest:  $latest"
    if [ "$latest" = "$current" ]; then
      echo "already at latest, no change."
      exit 0
    fi
    echo "prefetching tarball hash..."
    hash=$(nix-prefetch-url --type sha256 \
      "https://registry.npmjs.org/@github/copilot/-/copilot-$latest.tgz" 2>/dev/null | tail -1)
    python3 -c "
    import json
    p='$pin_file'
    d=json.load(open(p))
    d['version']='$latest'
    d['hash']='$hash'
    json.dump(d,open(p,'w'),indent=2)
    open(p,'a').write('\n')
    "
    echo "updated $pin_file -> $latest ($hash)"

# Garbage collect old generations
clean:
    nix-collect-garbage -d

# Remove result symlink
clean-result:
    rm -f result

# Format nix files
fmt:
    nix fmt -- $(git ls-files '*.nix')

# Check formatting + run statix/deadnix (same gate as CI)
lint:
    nix fmt -- --check $(git ls-files '*.nix')
    nix run nixpkgs#statix -- check .
    nix run nixpkgs#deadnix -- --fail --exclude spikes

# Check flake
check:
    nix flake check

# Show flake info
info:
    nix flake show

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
