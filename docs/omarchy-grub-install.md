# Omarchy Installation with GRUB Preservation

Install Omarchy (Hyprland desktop) on an encrypted Arch Linux ARM system while preserving the GRUB bootloader. The armarchy installer (Omarchy for ARM64) installs Limine by default, which would break LUKS boot - this guide shows how to preserve GRUB.

## Prerequisites

- Working LUKS+GRUB system from [arch-arm-encrypted-install.md](arch-arm-encrypted-install.md)
- VM boots successfully with LUKS passphrase prompt
- Can login as root after decryption

## Step 1: Create Pre-Omarchy Snapshot

Before running armarchy, create a Parallels snapshot as a safety net.

**Why**: The armarchy installer installs the Limine bootloader by default (PR #1897). Limine doesn't support LUKS decryption prompts the same way GRUB does. If something goes wrong, you can restore from snapshot.

```bash
# In the VM - shutdown cleanly
shutdown -h now
```

On macOS host:
```bash
# Create snapshot before armarchy installation
prlctl snapshot "YourVMName" -n "Pre-Omarchy-GRUB" -d "Clean LUKS+GRUB base before armarchy install"

# Verify snapshot was created
prlctl snapshot-list "YourVMName"
```

Start the VM again after creating the snapshot.

## Step 2: Backup GRUB Configuration

Before running armarchy, backup all GRUB-related files.

```bash
# Login as root

# Create backup directory
mkdir -p /root/grub-backup

# Backup GRUB directory
cp -a /boot/grub /root/grub-backup/

# Backup kernel and initramfs
cp /boot/vmlinuz-linux /root/grub-backup/
cp /boot/Image /root/grub-backup/
cp /boot/initramfs-linux.img /root/grub-backup/
cp /boot/initramfs-linux-fallback.img /root/grub-backup/ 2>/dev/null || true

# Backup GRUB EFI entry
cp -a /boot/EFI/GRUB /root/grub-backup/EFI-GRUB 2>/dev/null || true

# Verify backups
ls -la /root/grub-backup/
ls -la /root/grub-backup/grub/

# Record the current boot entry
efibootmgr -v | grep -i grub
```

## Step 3: Run Armarchy Installer

Install Omarchy using the ARM64 version (armarchy).

```bash
# Install wget if not present
pacman -S wget --noconfirm

# Run armarchy installer (Omarchy for ARM64)
# Source: https://github.com/basecamp/omarchy/pull/1897
curl -fsSL hdwy.link/armarchy-3-x | bash
```

The installer will prompt for:

1. **Username**: Enter your desired username
2. **Password**: Must meet Intune requirements:
   - 12+ characters
   - At least 1 uppercase (A-Z)
   - At least 1 lowercase (a-z)
   - At least 1 digit (0-9)
   - At least 1 symbol (!@#$%^&*...)

**Note**: The installer will install Limine bootloader. We'll restore GRUB in the next step.

After installation completes, **DO NOT REBOOT YET**.

## Step 4: Restore GRUB Bootloader

Restore GRUB after armarchy has finished but before rebooting.

```bash
# Restore GRUB directory
cp -a /root/grub-backup/grub /boot/

# Restore kernel symlink if removed
ln -sf /boot/Image /boot/vmlinuz-linux

# Restore GRUB EFI entry
mkdir -p /boot/EFI
cp -a /root/grub-backup/EFI-GRUB /boot/EFI/GRUB 2>/dev/null || true

# Reinstall GRUB EFI entry
grub-install --target=arm64-efi --efi-directory=/boot --bootloader-id=GRUB

# Regenerate GRUB config (picks up any new kernels from armarchy)
grub-mkconfig -o /boot/grub/grub.cfg

# Verify grub-mkconfig found kernel and initramfs
# Should show:
#   Found linux image: /boot/vmlinuz-linux
#   Found initrd image: /boot/initramfs-linux.img

# Verify initrd is in config
grep "initrd" /boot/grub/grub.cfg

# CRITICAL: Override Limine's fallback boot with GRUB
# Armarchy installs Limine to /boot/EFI/BOOT/BOOTAA64.EFI (fallback path)
# EFI firmware uses this path regardless of efibootmgr order
cp /boot/EFI/GRUB/grubaa64.efi /boot/EFI/BOOT/BOOTAA64.EFI

# Verify the copy (should be ~160KB, not ~90KB like Limine)
ls -la /boot/EFI/BOOT/BOOTAA64.EFI

# Now reboot
reboot
```

## Verification

After reboot, verify everything works:

### During Boot
1. GRUB menu should appear (not Limine)
2. LUKS passphrase prompt should appear
3. Enter passphrase - system should boot to login manager

### After Login
```bash
# Login with the user account created by armarchy

# Verify you're in Hyprland/Wayland
echo $XDG_SESSION_TYPE
# Should show: wayland

# Verify LUKS encryption status
sudo cryptsetup status cryptroot
# Should show type: LUKS2

# Verify shared folders mount (for dotfiles access)
ls /mnt/psf/
# Should show shared folders from macOS

# Test that Rosetta is configured (if enabled)
cat /proc/sys/fs/binfmt_misc/rosetta 2>/dev/null || echo "Rosetta not configured yet"
```

## Troubleshooting

### Limine Boots Instead of GRUB

If you see Limine bootloader instead of GRUB:

```bash
# Boot from archboot ISO
cryptsetup open /dev/sda2 cryptroot
mount /dev/mapper/cryptroot /mnt
mount /dev/sda1 /mnt/boot
arch-chroot /mnt

# Reinstall GRUB
grub-install --target=arm64-efi --efi-directory=/boot --bootloader-id=GRUB

# Ensure vmlinuz-linux symlink exists
ln -sf /boot/Image /boot/vmlinuz-linux

# Regenerate config
grub-mkconfig -o /boot/grub/grub.cfg

# Set GRUB as primary boot option
efibootmgr -v
efibootmgr -o 0001  # Use GRUB's boot number

# Exit and reboot
exit
umount -R /mnt
reboot
```

### No LUKS Passphrase Prompt After Reboot

If GRUB loads but you don't see a passphrase prompt:

```bash
# Boot from ISO and chroot (as above)

# Check mkinitcpio HOOKS
grep "^HOOKS=" /etc/mkinitcpio.conf
# Must include 'encrypt' after 'block' and before 'filesystems'
# Must include 'keyboard' before 'encrypt'

# Fix if needed:
sed -i 's/^HOOKS=.*/HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt filesystems fsck)/' /etc/mkinitcpio.conf

# Regenerate initramfs
mkinitcpio -P

# Regenerate GRUB config
grub-mkconfig -o /boot/grub/grub.cfg
```

### Restore from Snapshot

If all else fails, restore from the pre-Omarchy snapshot:

On macOS host:
```bash
# List snapshots
prlctl snapshot-list "YourVMName"

# Restore to pre-Omarchy state
prlctl snapshot-switch "YourVMName" -i "{snapshot-uuid}"

# Start VM
prlctl start "YourVMName"
```

### Shared Folders Not Mounting

```bash
# Check if prtools kernel module is loaded
lsmod | grep prl

# If not present, install Parallels Tools
# (armarchy should include this, but if missing:)
# Mount the Parallels Tools ISO from Parallels menu and run installer

# Verify mount points
mount | grep psf
```

## Next Steps

Once Omarchy is running with GRUB+LUKS:
- [template-generalization.md](template-generalization.md) - Generalize VM for cloning as template

## References

- [Armarchy (Omarchy for ARM64)](https://github.com/basecamp/omarchy/pull/1897)
- [Omarchy v3.2.0](https://github.com/basecamp/omarchy/releases/tag/v3.2.0)
- [Arch Wiki - GRUB](https://wiki.archlinux.org/title/GRUB)
- [Parallels Tools for Linux](https://kb.parallels.com/en/115835)
