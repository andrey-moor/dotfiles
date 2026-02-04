# Troubleshooting Guide

> **Last updated:** 2026-02-03
> **Applies to:** Stargazer and similar Intune-enrolled Arch Linux ARM VMs on Parallels

Quick diagnosis: Run `intune-health` to identify most common issues automatically.

## Table of Contents

1. [Boot Issues](#boot-issues)
   - [No LUKS Passphrase Prompt](#no-luks-passphrase-prompt)
   - [Limine Boots Instead of GRUB](#limine-boots-instead-of-grub)
   - [Kernel Panic: Unable to Mount Root FS](#kernel-panic-unable-to-mount-root-fs)
   - [Wrong UUID in GRUB Config](#wrong-uuid-in-grub-config)
2. [VM Issues](#vm-issues)
   - [Clone Won't Start](#clone-wont-start)
   - [Shared Folders Not Visible](#shared-folders-not-visible)
   - [No Network After Reboot](#no-network-after-reboot)
3. [Rosetta and Nix Issues](#rosetta-and-nix-issues)
   - [Rosetta binfmt Not Registered](#rosetta-binfmt-not-registered)
   - [x86_64 Binaries Fail to Execute](#x86_64-binaries-fail-to-execute)
   - [Nix Build Fails for x86_64 Packages](#nix-build-fails-for-x86_64-packages)
4. [Intune Issues](#intune-issues)
   - [Device Broker Fails with D-Bus Error](#device-broker-fails-with-d-bus-error)
   - [Enrollment Fails with Keyring Error](#enrollment-fails-with-keyring-error)
   - [Portal Shows Blank Screen](#portal-shows-blank-screen)
   - [Authentication Fails](#authentication-fails)
5. [YubiKey Issues](#yubikey-issues)
   - [YubiKey Not Detected](#yubikey-not-detected)
   - [Certificate Not Shown in Picker](#certificate-not-shown-in-picker)
   - [PIN Rejected](#pin-rejected)

---

## Quick Diagnosis

Before diving into specific issues, run:

```bash
intune-health
```

This checks all critical components and provides hints for failures. Exit code 0 = all critical checks pass.

For more detail:

```bash
intune-health --verbose
intune-logs --all | tail -50
```

---

## Boot Issues

### No LUKS Passphrase Prompt

**What you see:**
- Boot hangs at "Loading initial ramdisk..."
- Or: Boots directly to login without asking for passphrase
- Or: Boots to Limine menu instead of GRUB

**Root cause:**
GRUB EFI binary was replaced by Limine during armarchy installation, or never installed correctly.

**Solution:**

1. Boot from archboot ISO in Parallels
2. Open the encrypted partition:
   ```bash
   cryptsetup open /dev/vda2 cryptroot
   ```
3. Mount filesystems:
   ```bash
   mount /dev/mapper/cryptroot /mnt
   mount /dev/vda1 /mnt/boot
   ```
4. Restore GRUB:
   ```bash
   cp /mnt/boot/EFI/GRUB/grubaa64.efi /mnt/boot/EFI/BOOT/BOOTAA64.EFI
   ```
5. Unmount and reboot:
   ```bash
   umount -R /mnt
   reboot
   ```

**Prevention:**
After running armarchy, ALWAYS run `sudo cp /boot/EFI/GRUB/grubaa64.efi /boot/EFI/BOOT/BOOTAA64.EFI` BEFORE rebooting.

**Related:** [Setup Step 5: Restore GRUB Bootloader](../hosts/stargazer/README.md#5-restore-grub-bootloader)

---

### Limine Boots Instead of GRUB

**What you see:**
- Black screen with "Limine" text
- Menu shows "Arch Linux" without LUKS support
- System boots without asking for disk passphrase

**Root cause:**
armarchy installs Limine bootloader to the fallback EFI path, overwriting GRUB.

**Solution:**
Same as [No LUKS Passphrase Prompt](#no-luks-passphrase-prompt) above.

**Prevention:**
Create a snapshot before running armarchy. If you forget the GRUB fix, restore the snapshot.

---

### Kernel Panic: Unable to Mount Root FS

**What you see:**
- "Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)"
- System halts completely

**Root cause:**
Either GRUB config has wrong UUID, or 'encrypt' hook missing from initramfs.

**Solution:**

1. Boot from archboot ISO
2. Check if you can decrypt manually:
   ```bash
   cryptsetup open /dev/vda2 cryptroot
   ls /dev/mapper/cryptroot  # Should exist
   ```
3. If decryption works, the issue is GRUB config. Mount and check:
   ```bash
   mount /dev/mapper/cryptroot /mnt
   mount /dev/vda1 /mnt/boot
   cat /mnt/boot/grub/grub.cfg | grep cryptdevice
   ```
4. UUID should match `blkid /dev/vda2`

**Prevention:**
During initial setup, verify UUIDs match before first reboot.

**Related:** [docs/arch-arm-encrypted-install.md](arch-arm-encrypted-install.md)

---

### Wrong UUID in GRUB Config

**What you see:**
- GRUB menu appears
- Selecting entry fails with cryptdevice errors

**Root cause:**
GRUB config was generated with incorrect partition UUID.

**Solution:**

1. At GRUB menu, press `e` to edit
2. Find the line with `cryptdevice=UUID=...`
3. Note the incorrect UUID
4. Boot from ISO and fix:
   ```bash
   # Get correct UUID
   blkid /dev/vda2

   # Mount and edit
   cryptsetup open /dev/vda2 cryptroot
   mount /dev/mapper/cryptroot /mnt
   mount /dev/vda1 /mnt/boot

   # Edit grub.cfg with correct UUID
   nano /mnt/boot/grub/grub.cfg
   ```

**Prevention:**
After grub-mkconfig, verify UUID matches with `blkid`.

---

## VM Issues

### Clone Won't Start

**What you see:**
- Parallels shows error starting VM
- "Unable to open disk image" or similar

**Root cause:**
Usually permissions issue or corrupted clone operation.

**Solution:**

1. Check VM exists:
   ```bash
   prlctl list -a
   ```
2. If listed but won't start, check configuration:
   ```bash
   prlctl list -i vmname
   ```
3. Try stopping and starting:
   ```bash
   prlctl stop vmname --kill
   prlctl start vmname
   ```
4. If persistent, delete and re-clone from template

**Prevention:**
Ensure source VM is stopped before cloning.

---

### Shared Folders Not Visible

**What you see:**
- `/mnt/psf` exists but is empty
- `ls /mnt/psf/dotfiles` returns "No such file or directory"

**Root cause:**
Parallels Tools hasn't mounted shared folders yet (happens async after boot).

**Solution:**

1. Wait 15-30 seconds after login:
   ```bash
   sleep 15 && ls /mnt/psf/
   ```
2. Check prltoolsd is running:
   ```bash
   systemctl status prltoolsd
   ```
3. If not running, start it:
   ```bash
   sudo systemctl start prltoolsd
   ```
4. Verify shared folders enabled in Parallels VM config

**Prevention:**
Scripts that need shared folders should include retry loops (see prerequisites.sh pattern).

---

### No Network After Reboot

**What you see:**
- `ping google.com` fails
- `ip addr` shows no IP on main interface

**Root cause:**
Network manager not configured or interface name changed.

**Solution:**

1. Check interface name:
   ```bash
   ip link
   ```
2. Start network:
   ```bash
   sudo systemctl start NetworkManager
   sudo nmcli device connect enp0s5
   ```
3. Enable for future boots:
   ```bash
   sudo systemctl enable NetworkManager
   ```

**Prevention:**
Omarchy should configure this automatically. If issues persist, check armarchy completed successfully.

---
