# Plan 01-03 Summary: Test Omarchy Documentation

## Execution Info
- **Started**: 2026-02-02
- **Completed**: 2026-02-02
- **Duration**: ~60 minutes (interactive, with debugging)

## Deliverables

### VM Updated
- **Name**: ArchBase-Template
- **User**: andreym (real user, not generic template)
- **Desktop**: Omarchy/Hyprland working

### Snapshot Created
- **Name**: Omarchy-Ready (user-created)
- **Description**: Working Omarchy desktop with GRUB+LUKS preserved

## Verification
- [x] VM boots with GRUB (not Limine)
- [x] LUKS passphrase prompt appears at boot
- [x] Omarchy/Hyprland desktop loads after decryption
- [x] User can login with credentials
- [x] Shared folders accessible at /mnt/psf/
- [x] XDG_SESSION_TYPE = wayland

## Critical Issue Found and Fixed

### Problem: Limine Boots Instead of GRUB
**Symptom**: After armarchy install, reboot shows "Omarchy Bootloader" (Limine), not GRUB. Limine can't decrypt LUKS, drops to emergency shell.

**Root Cause**: Armarchy installs Limine to `/boot/EFI/BOOT/BOOTAA64.EFI` - the EFI fallback boot path. EFI firmware uses this path regardless of efibootmgr boot order settings.

**Fix**: Copy GRUB's efi over Limine's fallback:
```bash
cp /boot/EFI/GRUB/grubaa64.efi /boot/EFI/BOOT/BOOTAA64.EFI
```

**Verification**: BOOTAA64.EFI should be ~160KB (GRUB), not ~90KB (Limine).

### Recovery Steps Used
When we booted into Limine emergency shell:
1. `cryptsetup open /dev/sda2 cryptroot` (enter passphrase)
2. `mount /dev/mapper/cryptroot /new_root`
3. `mount /dev/sda1 /new_root/boot`
4. `cp /new_root/boot/EFI/GRUB/grubaa64.efi /new_root/boot/EFI/BOOT/BOOTAA64.EFI`
5. `reboot -f`

## Documentation Updates
- **docs/omarchy-grub-install.md**: Added critical step to copy GRUB efi to fallback boot path
- Removed efibootmgr steps (not sufficient - firmware ignores boot order for fallback path)

## Approach Change
Decided during execution to use Option B for templating:
- **Clone point**: EncryptedBase-GRUB snapshot (before Omarchy)
- **Each clone**: Runs armarchy fresh with real user credentials
- **Rationale**: Simpler than username/key generalization scripts; Omarchy install is quick (~15 min)

Plan 01-04 will document the clone workflow instead of generalization scripts.

## Files Modified
- docs/omarchy-grub-install.md (critical fix added)

## Commits
- Pending: doc update with critical GRUB fix
