#!/usr/bin/env bash
# Prerequisites script for Rosetta + Nix on Omarchy VM
# Configures x86_64 emulation and Nix package manager
#
# Idempotent: safe to re-run - each section checks if already configured
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/andrey-moor/dotfiles/main/scripts/prerequisites.sh | bash
#   # Or from cloned repo:
#   /mnt/psf/Home/Documents/dotfiles/scripts/prerequisites.sh

set -euo pipefail

# Helper functions
log() { echo "[+] $1"; }
warn() { echo "[!] $1"; }
skip() { echo "[=] $1 (already configured)"; }

# Ensure running with proper permissions for sudo
if [[ $EUID -eq 0 ]]; then
    warn "Running as root. Some operations may not work correctly."
    warn "Consider running as regular user with sudo access."
fi

# ============================================================================
# 1. Rosetta binfmt configuration
# ============================================================================
log "Checking Rosetta binfmt configuration..."

if [[ -f /etc/binfmt.d/rosetta.conf ]]; then
    skip "Rosetta binfmt"
else
    log "Installing Rosetta binfmt configuration..."
    echo ':rosetta:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x3e\x00:\xff\xff\xff\xff\xff\xfe\xfe\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/mnt/psf/RosettaLinux/rosetta:PFC' | sudo tee /etc/binfmt.d/rosetta.conf > /dev/null
    log "Rosetta binfmt installed"
fi

# ============================================================================
# 2. Path watcher for boot race condition
# ============================================================================
# Parallels mounts /mnt/psf after boot, creating a race with systemd-binfmt.
# This path unit watches for the Rosetta binary and triggers binfmt re-registration.
log "Checking Rosetta path watcher..."

if [[ -f /etc/systemd/system/rosetta-binfmt.path ]]; then
    skip "Rosetta path watcher"
else
    log "Installing Rosetta binfmt path watcher..."

    # Path unit - watches for Rosetta binary
    cat << 'EOF' | sudo tee /etc/systemd/system/rosetta-binfmt.path > /dev/null
[Unit]
Description=Watch for Rosetta binary to appear

[Path]
PathExists=/mnt/psf/RosettaLinux/rosetta
Unit=rosetta-binfmt.service

[Install]
WantedBy=multi-user.target
EOF

    # Service unit - restarts binfmt when path appears
    cat << 'EOF' | sudo tee /etc/systemd/system/rosetta-binfmt.service > /dev/null
[Unit]
Description=Register Rosetta binfmt after mount

[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl restart systemd-binfmt
RemainAfterExit=yes
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable rosetta-binfmt.path
    log "Rosetta path watcher installed and enabled"
fi

# ============================================================================
# 3. Trigger binfmt immediately (if mount available)
# ============================================================================
if [[ -f /mnt/psf/RosettaLinux/rosetta ]]; then
    log "Rosetta binary available, restarting binfmt..."
    sudo systemctl restart systemd-binfmt
    log "binfmt restarted"
else
    warn "Rosetta binary not available at /mnt/psf/RosettaLinux/rosetta"
    warn "binfmt will be registered when Parallels mounts the share"
fi

# ============================================================================
# 4. Nix installation (Determinate)
# ============================================================================
log "Checking Nix installation..."

if command -v nix &>/dev/null; then
    skip "Nix"
else
    log "Installing Nix (Determinate)..."
    curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install --no-confirm

    # Source nix-daemon.sh for current shell
    if [[ -f /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh ]]; then
        # shellcheck source=/dev/null
        . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
        log "Nix installed and sourced"
    else
        warn "Nix installed but nix-daemon.sh not found - you may need to restart your shell"
    fi
fi

# ============================================================================
# 5. Fix Nix permissions
# ============================================================================
# Determinate Nix installer creates some files with 600 permissions,
# which can cause issues with multi-user access
log "Checking Nix permissions..."

if [[ -f /etc/nix/nix.conf ]]; then
    current_perms=$(stat -c "%a" /etc/nix/nix.conf 2>/dev/null || stat -f "%OLp" /etc/nix/nix.conf 2>/dev/null)
    if [[ "$current_perms" != "644" ]]; then
        log "Fixing /etc/nix/nix.conf permissions..."
        sudo chmod 644 /etc/nix/nix.conf
    else
        skip "Nix config permissions"
    fi
fi

# Fix systemd service permissions if they exist
for service_file in /etc/systemd/system/nix-daemon.service /etc/systemd/system/nix-daemon.socket /etc/systemd/system/determinate-nixd.socket; do
    if [[ -f "$service_file" ]]; then
        current_perms=$(stat -c "%a" "$service_file" 2>/dev/null || stat -f "%OLp" "$service_file" 2>/dev/null)
        if [[ "$current_perms" != "644" ]]; then
            log "Fixing permissions for $service_file..."
            sudo chmod 644 "$service_file"
        fi
    fi
done

# ============================================================================
# 6. extra-platforms configuration
# ============================================================================
log "Checking extra-platforms configuration..."

if grep -q "extra-platforms.*x86_64-linux" /etc/nix/nix.custom.conf 2>/dev/null; then
    skip "extra-platforms"
else
    log "Adding extra-platforms for x86_64..."
    echo "extra-platforms = x86_64-linux" | sudo tee -a /etc/nix/nix.custom.conf > /dev/null
    sudo systemctl restart nix-daemon
    log "extra-platforms configured and nix-daemon restarted"
fi

# ============================================================================
# 7. x86_64 dynamic linker
# ============================================================================
# Many x86_64 binaries expect /lib64/ld-linux-x86-64.so.2 to exist.
# We create this by building glibc via Nix and symlinking.
log "Checking x86_64 dynamic linker..."

if [[ -L /lib64/ld-linux-x86-64.so.2 ]]; then
    skip "x86_64 dynamic linker"
else
    log "Installing x86_64 dynamic linker..."

    # Build glibc for x86_64 (this may take a while on first run)
    log "Building glibc for x86_64 (this may take a moment)..."
    GLIBC_PATH=$(nix build --no-link --print-out-paths nixpkgs#pkgsCross.gnu64.glibc)

    # Create /lib64 directory and symlink
    sudo mkdir -p /lib64
    sudo chmod 755 /lib64
    sudo ln -sf "$GLIBC_PATH/lib/ld-linux-x86-64.so.2" /lib64/
    log "x86_64 dynamic linker installed: /lib64/ld-linux-x86-64.so.2 -> $GLIBC_PATH/lib/ld-linux-x86-64.so.2"
fi

# ============================================================================
# 8. os-release spoofing
# ============================================================================
# Some Microsoft tools check for Ubuntu. We spoof os-release to claim Ubuntu 22.04.
# Note: Use /usr/lib/os-release, NOT /etc/os-release (which is a symlink)
log "Checking os-release spoofing..."

if grep -q 'ID=ubuntu' /usr/lib/os-release 2>/dev/null; then
    skip "os-release spoof"
else
    log "Spoofing os-release as Ubuntu 22.04..."

    # Backup original
    if [[ -f /usr/lib/os-release ]] && [[ ! -f /usr/lib/os-release.arch.bak ]]; then
        sudo cp /usr/lib/os-release /usr/lib/os-release.arch.bak
        log "Original os-release backed up to /usr/lib/os-release.arch.bak"
    fi

    # Write Ubuntu os-release
    sudo tee /usr/lib/os-release > /dev/null << 'EOF'
NAME="Ubuntu"
VERSION="22.04.3 LTS (Jammy Jellyfish)"
ID=ubuntu
ID_LIKE=debian
PRETTY_NAME="Ubuntu 22.04.3 LTS"
VERSION_ID="22.04"
VERSION_CODENAME=jammy
UBUNTU_CODENAME=jammy
EOF
    log "os-release spoofed as Ubuntu 22.04"
fi

# ============================================================================
# Complete
# ============================================================================
echo ""
log "Prerequisites complete!"
echo ""
echo "Verification commands:"
echo "  cat /etc/binfmt.d/rosetta.conf              # Rosetta binfmt config"
echo "  cat /proc/sys/fs/binfmt_misc/rosetta        # Rosetta registration status"
echo "  nix --version                               # Nix version"
echo "  grep extra-platforms /etc/nix/nix.custom.conf  # x86_64 platform"
echo "  ls -la /lib64/ld-linux-x86-64.so.2          # Dynamic linker"
echo "  cat /usr/lib/os-release                     # OS identity"
echo ""
echo "Next steps:"
echo "  1. Apply home-manager: cd /mnt/psf/Home/Documents/dotfiles && nix run home-manager -- switch --flake .#endurance -b backup"
echo "  2. Complete remaining setup in hosts/endurance/README.md (Device Broker, pcscd, etc.)"
