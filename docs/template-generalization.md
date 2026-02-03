# VM Clone Workflow

Create new Arch Linux ARM VMs by cloning from the encrypted base snapshot and running Omarchy installation fresh. This approach is simpler than post-Omarchy generalization because each clone gets unique identifiers during the fresh install.

## Overview

**Clone Strategy (Option B):**
- Clone point: `EncryptedBase-GRUB` snapshot (LUKS+GRUB, before Omarchy)
- Each clone: Runs armarchy fresh with real user credentials
- Rationale: Simpler than username/key generalization; Omarchy install takes ~15 minutes

**Why not generalize after Omarchy?**
- Omarchy creates user-specific configs (username, SSH keys, dotfiles)
- Generalizing username requires complex sed/mv operations
- Fresh install guarantees clean, unique identifiers

## Prerequisites

- Working ArchBase-Template VM with `EncryptedBase-GRUB` snapshot
- Snapshot created per [arch-arm-encrypted-install.md](arch-arm-encrypted-install.md)
- LUKS passphrase: 4815162342 (change after clone if desired)

## Step 1: Clone from Encrypted Base

From macOS host:

```bash
# List available snapshots
prlctl snapshot-list ArchBase-Template

# Clone from the encrypted base snapshot (before Omarchy)
# Use --id with the EncryptedBase-GRUB snapshot UUID
prlctl clone ArchBase-Template --name "YourNewVM" --id "{snapshot-uuid}"

# Or clone from current state if VM is at EncryptedBase-GRUB
prlctl clone ArchBase-Template --name "YourNewVM"

# Verify clone exists
prlctl list -a | grep YourNewVM
```

**Clone Types:**
- Full clone (default): Independent copy, can delete template
- Linked clone (`--linked`): Shares base disk, smaller, template must be kept

## Step 2: Configure VM Settings (Optional)

```bash
# Set CPU and memory (adjust as needed)
prlctl set "YourNewVM" --cpus 4 --memsize 8192

# Ensure shared folders are enabled
prlctl set "YourNewVM" --shf-host on

# Configure specific shared folder
prlctl set "YourNewVM" --shf-host-add Home --path /Users/yourusername

# Ensure Rosetta is enabled
prlctl set "YourNewVM" --rosetta-linux on
```

## Step 3: Start and Install Omarchy

```bash
# Start the clone
prlctl start "YourNewVM"
```

**In VM console:**

1. Enter LUKS passphrase (4815162342)
2. Login as root
3. Follow [omarchy-grub-install.md](omarchy-grub-install.md) starting from Step 2 (backup GRUB)

**Quick reference:**

```bash
# Backup GRUB
mkdir -p /root/grub-backup
cp -a /boot/grub /root/grub-backup/
cp -a /boot/EFI/GRUB /root/grub-backup/EFI-GRUB 2>/dev/null || true

# Install wget and run armarchy
pacman -S wget --noconfirm
curl -fsSL hdwy.link/armarchy-3-x | bash

# Enter YOUR username and password when prompted
# Password must meet: 12+ chars, uppercase, lowercase, digit, symbol

# IMPORTANT: After armarchy, BEFORE rebooting:
# Restore GRUB
cp -a /root/grub-backup/grub /boot/
grub-install --target=arm64-efi --efi-directory=/boot --bootloader-id=GRUB
grub-mkconfig -o /boot/grub/grub.cfg

# CRITICAL: Override Limine's fallback boot with GRUB
cp /boot/EFI/GRUB/grubaa64.efi /boot/EFI/BOOT/BOOTAA64.EFI

# Verify (should be ~160KB, not ~90KB)
ls -la /boot/EFI/BOOT/BOOTAA64.EFI

# Now reboot
reboot
```

## Step 4: Verify and Finalize

After reboot:

1. **GRUB appears** (not Limine)
2. **LUKS passphrase prompt** - enter passphrase
3. **Login** with credentials you created in armarchy

```bash
# Verify Wayland session
echo $XDG_SESSION_TYPE  # Should show: wayland

# Verify encryption
sudo cryptsetup status cryptroot  # Should show: LUKS2

# Verify shared folders (for dotfiles access)
ls /mnt/psf/Home/Documents/dotfiles

# Verify Rosetta
cat /proc/sys/fs/binfmt_misc/rosetta 2>/dev/null || echo "Rosetta not configured yet"
```

## Step 5: Change LUKS Passphrase (Recommended)

For security, change the template passphrase to something unique.

```bash
sudo cryptsetup luksChangeKey /dev/sda2
# Enter current passphrase: 4815162342
# Enter new passphrase
# Confirm new passphrase
```

## Step 6: Create Omarchy-Ready Snapshot (Optional)

If you want a restore point after successful Omarchy setup:

```bash
# Shutdown VM
sudo shutdown -h now
```

From macOS:
```bash
prlctl snapshot "YourNewVM" -n "Omarchy-Ready" -d "Working GRUB+LUKS+Omarchy"
```

## Quick Clone Script

For rapid cloning, create `scripts/clone-arch-vm.sh`:

```bash
#!/bin/bash
# Clone Arch Linux VM from encrypted base
# Usage: ./clone-arch-vm.sh <new-vm-name>

set -euo pipefail

VM_NAME="${1:-}"
TEMPLATE="ArchBase-Template"
SNAPSHOT_NAME="EncryptedBase-GRUB"

if [[ -z "$VM_NAME" ]]; then
    echo "Usage: $0 <new-vm-name>"
    exit 1
fi

# Find snapshot ID
SNAPSHOT_ID=$(prlctl snapshot-list "$TEMPLATE" | grep "$SNAPSHOT_NAME" | grep -oE '\{[^}]+\}' | head -1)

if [[ -z "$SNAPSHOT_ID" ]]; then
    echo "Error: Snapshot '$SNAPSHOT_NAME' not found in $TEMPLATE"
    exit 1
fi

echo "Cloning $TEMPLATE (snapshot: $SNAPSHOT_NAME) -> $VM_NAME"
prlctl clone "$TEMPLATE" --name "$VM_NAME" --id "$SNAPSHOT_ID"

echo "Configuring VM..."
prlctl set "$VM_NAME" --cpus 4 --memsize 8192
prlctl set "$VM_NAME" --shf-host on
prlctl set "$VM_NAME" --rosetta-linux on

echo ""
echo "Clone created: $VM_NAME"
echo ""
echo "Next steps:"
echo "  1. prlctl start \"$VM_NAME\""
echo "  2. Enter LUKS passphrase: 4815162342"
echo "  3. Run armarchy installer (see omarchy-grub-install.md)"
echo "  4. Apply GRUB fix before reboot"
echo ""
```

## Troubleshooting

### Limine Boots Instead of GRUB

If you see "Omarchy Bootloader" after armarchy install:

```bash
# From emergency shell:
cryptsetup open /dev/sda2 cryptroot
mount /dev/mapper/cryptroot /new_root
mount /dev/sda1 /new_root/boot
cp /new_root/boot/EFI/GRUB/grubaa64.efi /new_root/boot/EFI/BOOT/BOOTAA64.EFI
reboot -f
```

### Clone Won't Start

```bash
# Check VM status
prlctl list -a | grep YourNewVM

# Try stopping and starting
prlctl stop "YourNewVM" --kill
prlctl start "YourNewVM"
```

### Shared Folders Not Visible

```bash
# In VM - check mount
mount | grep psf

# If not mounted, check if prtools is installed
lsmod | grep prl

# Remount manually
sudo mount -t prl_fs Host /mnt/psf
```

## References

- [arch-arm-encrypted-install.md](arch-arm-encrypted-install.md) - Base LUKS+GRUB setup
- [omarchy-grub-install.md](omarchy-grub-install.md) - Omarchy with GRUB preservation
- [Parallels CLI Reference](https://download.parallels.com/desktop/v18/docs/en_US/Parallels%20Desktop%20Pro%20Edition%20Command-Line%20Reference.pdf)
