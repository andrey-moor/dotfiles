#!/usr/bin/env bash
# Automated Arch Linux ARM installation for Parallels VM
# Uses pre_mounted_config approach: manual partition/LUKS, archinstall for base
#
# Run this inside archboot live environment:
#   curl -fsSL https://raw.githubusercontent.com/andrey-moor/dotfiles/main/scripts/install-arch.sh | bash

set -euo pipefail

CONFIG_BASE="${1:-https://raw.githubusercontent.com/andrey-moor/dotfiles/main/scripts}"
DISK="${DISK:-/dev/sda}"
LUKS_PASS="${LUKS_PASS:-temppass}"
USER_PASS="${USER_PASS:-temppass}"
ROOT_PASS="${ROOT_PASS:-temppass}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[x]${NC} $1"; exit 1; }

echo "=================================================="
echo " Arch Linux ARM Automated Installation"
echo " For Parallels VM with LUKS encryption"
echo "=================================================="
echo ""
echo " Disk: $DISK"
echo " LUKS passphrase: $LUKS_PASS"
echo " User: user / $USER_PASS"
echo " Root: $ROOT_PASS"
echo ""
warn "CHANGE ALL PASSWORDS AFTER INSTALLATION!"
echo ""
echo "Starting in 5 seconds... (Ctrl+C to abort)"
sleep 5

# ============================================================
# CLEANUP: Make script idempotent
# ============================================================
log "Cleaning up any previous state..."

# Unmount any existing mounts (in reverse order)
umount -R /mnt/archinstall 2>/dev/null || true
umount /mnt/archinstall/boot/efi 2>/dev/null || true
umount /mnt/archinstall/boot 2>/dev/null || true
umount /mnt/archinstall 2>/dev/null || true

# Close LUKS if open
if [[ -e /dev/mapper/cryptroot ]]; then
    log "Closing existing LUKS mapping..."
    cryptsetup close cryptroot 2>/dev/null || true
fi

# Kill any processes using the disk
fuser -km "$DISK" 2>/dev/null || true
sleep 1

# Check we're in live environment
if [[ ! -d /run/archiso ]] && [[ $(hostname) != *archboot* ]]; then
    warn "This script should be run from archboot live environment"
fi

# Ensure network is up
log "Checking network..."
if ! ping -c 1 -W 3 archlinux.org &>/dev/null; then
    warn "No network connectivity. Trying DHCP..."
    dhcpcd 2>/dev/null || dhclient 2>/dev/null || true
    sleep 3
    ping -c 1 archlinux.org &>/dev/null || error "No network - check manually"
fi

# ============================================================
# PHASE 1: Partition disk
# ============================================================
log "Partitioning $DISK..."

# Wipe disk
wipefs -af "$DISK" 2>/dev/null || true
dd if=/dev/zero of="$DISK" bs=1M count=10 2>/dev/null || true

# Create GPT partition table and partitions using fdisk
# 1: EFI System Partition (512MB)
# 2: Boot partition (1GB, unencrypted)
# 3: LUKS partition (remaining space)
fdisk "$DISK" <<'FDISK'
g
n
1

+512M
t
1
n
2

+1G
n
3


w
FDISK

# Ensure kernel sees new partitions
sleep 2
partprobe "$DISK" 2>/dev/null || true
sleep 2

log "Partitions created:"
lsblk "$DISK"

# ============================================================
# PHASE 2: Set up LUKS encryption
# ============================================================
log "Setting up LUKS2 encryption with argon2id..."

# LUKS2 with argon2id (safe because /boot is unencrypted, GRUB doesn't decrypt)
echo -n "$LUKS_PASS" | cryptsetup luksFormat --type luks2 \
    --cipher aes-xts-plain64 \
    --key-size 512 \
    --hash sha512 \
    --pbkdf argon2id \
    --batch-mode "${DISK}3"

log "Opening LUKS partition..."
echo -n "$LUKS_PASS" | cryptsetup open "${DISK}3" cryptroot

# ============================================================
# PHASE 3: Format filesystems
# ============================================================
log "Formatting filesystems..."

mkfs.fat -F32 "${DISK}1"
mkfs.ext4 -F "${DISK}2"
mkfs.ext4 -F /dev/mapper/cryptroot

# ============================================================
# PHASE 4: Mount for archinstall
# ============================================================
log "Mounting filesystems to /mnt/archinstall..."

MOUNT_ROOT="/mnt/archinstall"
mkdir -p "$MOUNT_ROOT"

mount /dev/mapper/cryptroot "$MOUNT_ROOT"
mkdir -p "$MOUNT_ROOT/boot"
mount "${DISK}2" "$MOUNT_ROOT/boot"
mkdir -p "$MOUNT_ROOT/boot/efi"
mount "${DISK}1" "$MOUNT_ROOT/boot/efi"

log "Mount layout:"
findmnt -R "$MOUNT_ROOT"

# ============================================================
# PHASE 5: Download and run archinstall with pre_mounted_config
# ============================================================
log "Downloading archinstall configuration..."

cd /tmp
curl -fsSL "$CONFIG_BASE/archinstall-config.json" -o config.json
curl -fsSL "$CONFIG_BASE/archinstall-creds.json" -o creds.json

# Install archinstall if not available (archboot is minimal)
if ! command -v archinstall &>/dev/null; then
    log "Installing archinstall and dependencies..."
    pacman -Sy --noconfirm archinstall libxcrypt
fi

log "Running archinstall with pre_mounted_config..."
archinstall --config config.json --creds creds.json

# ============================================================
# PHASE 6: Post-install GRUB configuration
# ============================================================
log "Configuring GRUB for LUKS..."

# Get LUKS UUID
LUKS_UUID=$(blkid -s UUID -o value "${DISK}3")
log "LUKS UUID: $LUKS_UUID"

# ARM64 kernel symlink fix (GRUB expects vmlinuz-linux, ARM uses Image)
if [[ -f "$MOUNT_ROOT/boot/Image" ]] && [[ ! -f "$MOUNT_ROOT/boot/vmlinuz-linux" ]]; then
    log "Creating ARM64 kernel symlink..."
    cp "$MOUNT_ROOT/boot/Image" "$MOUNT_ROOT/boot/vmlinuz-linux"
fi

# Configure mkinitcpio with encrypt hook
log "Configuring mkinitcpio HOOKS..."
sed -i 's/^HOOKS=.*/HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt filesystems fsck)/' \
    "$MOUNT_ROOT/etc/mkinitcpio.conf"

# Configure GRUB
log "Configuring GRUB..."
sed -i "s|^GRUB_CMDLINE_LINUX=.*|GRUB_CMDLINE_LINUX=\"cryptdevice=UUID=$LUKS_UUID:cryptroot root=/dev/mapper/cryptroot\"|" \
    "$MOUNT_ROOT/etc/default/grub"

# Chroot and finalize
log "Finalizing installation in chroot..."
arch-chroot "$MOUNT_ROOT" /bin/bash -c "
    # Regenerate initramfs with encrypt hook
    mkinitcpio -P

    # Install GRUB for ARM64 UEFI
    grub-install --target=arm64-efi --efi-directory=/boot/efi --bootloader-id=GRUB

    # Generate GRUB config
    grub-mkconfig -o /boot/grub/grub.cfg

    # Enable services
    systemctl enable sshd || true
    systemctl enable NetworkManager || true
"

# ============================================================
# DONE
# ============================================================
echo ""
echo "=================================================="
echo " Installation Complete!"
echo "=================================================="
echo ""
echo " The VM will boot with LUKS encryption."
echo ""
echo " Default credentials (CHANGE IMMEDIATELY):"
echo "   LUKS passphrase: $LUKS_PASS"
echo "   User: user / $USER_PASS"
echo "   Root: root / $ROOT_PASS"
echo ""
echo " After reboot:"
echo "   1. Enter LUKS passphrase at boot"
echo "   2. Login as user"
echo "   3. Change LUKS passphrase:"
echo "      sudo cryptsetup luksChangeKey ${DISK}3"
echo "   4. Change user password:"
echo "      passwd"
echo ""
echo " Ready to reboot? Run: reboot"
echo ""
