#!/usr/bin/env bash
# Create Arch Linux ARM VM template for Parallels
# Configures: Rosetta, shared folders, bridged networking
# MUST run before first boot to enable Rosetta

set -euo pipefail

VM_NAME="${1:-ArchBase-Template}"
CPUS="${2:-4}"
MEMORY="${3:-8192}"
DISK="${4:-131072}"  # 128GB in MB
ISO_PATH="${5:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[x]${NC} $1"; exit 1; }

# Check prerequisites
command -v prlctl >/dev/null 2>&1 || error "prlctl not found. Is Parallels Desktop installed?"

# Check if VM already exists
if prlctl list -a | grep -q "$VM_NAME"; then
    error "VM '$VM_NAME' already exists. Delete it first or choose a different name."
fi

# Find archboot ISO if not provided
if [[ -z "$ISO_PATH" ]]; then
    # Common download locations
    for path in \
        ~/Downloads/archboot-*-aarch64.iso \
        ~/Downloads/archlinux-*-aarch64.iso \
        /tmp/archboot-*.iso; do
        if compgen -G "$path" > /dev/null; then
            ISO_PATH=$(ls -t $path 2>/dev/null | head -1)
            break
        fi
    done
fi

if [[ -z "$ISO_PATH" || ! -f "$ISO_PATH" ]]; then
    warn "No archboot ISO found. Download from:"
    echo "  https://archboot.com/iso/aarch64/latest/"
    echo ""
    echo "Then run: $0 $VM_NAME $CPUS $MEMORY $DISK /path/to/archboot.iso"
    exit 1
fi

log "Creating VM: $VM_NAME"
log "  CPUs: $CPUS, Memory: ${MEMORY}MB, Disk: ${DISK}MB"
log "  ISO: $ISO_PATH"

# Create VM
prlctl create "$VM_NAME" \
    --ostype linux \
    --distribution linux

log "Configuring VM resources..."
prlctl set "$VM_NAME" --cpus "$CPUS"
prlctl set "$VM_NAME" --memsize "$MEMORY"

# Configure disk (resize default disk)
prlctl set "$VM_NAME" --device-set hdd0 --size "$DISK"

# CRITICAL: Enable Rosetta BEFORE first boot
log "Enabling Rosetta (must be before first boot)..."
prlctl set "$VM_NAME" --rosetta-linux on

# Enable shared folders
log "Enabling shared folders..."
prlctl set "$VM_NAME" --shf-host on
# Add dotfiles as a shared folder (will be at /media/psf/dotfiles in VM)
DOTFILES_PATH="$(cd "$(dirname "$0")/.." && pwd)"
prlctl set "$VM_NAME" --shf-host-add dotfiles --path "$DOTFILES_PATH" || true

# Configure bridged networking
log "Configuring bridged networking..."
prlctl set "$VM_NAME" --device-set net0 --type bridged

# Attach ISO
log "Attaching archboot ISO..."
prlctl set "$VM_NAME" --device-set cdrom0 --image "$ISO_PATH"

# Set boot order to CD first
prlctl set "$VM_NAME" --device-bootorder "cdrom0 hdd0"

echo ""
log "VM '$VM_NAME' created successfully!"
echo ""
echo "Next steps:"
echo "  1. Start VM:  prlctl start '$VM_NAME'"
echo "  2. Open console in Parallels Desktop"
echo "  3. Wait for archboot to boot (1-2 minutes)"
echo "  4. Run these commands in the VM:"
echo ""
echo "     curl -fsSL https://raw.githubusercontent.com/andrey-moor/dotfiles/main/scripts/install-arch.sh | bash"
echo ""
echo "  Or if no network, manually run archinstall with the config."
echo ""
warn "After install, change the LUKS passphrase from 'temppass' to your own!"
