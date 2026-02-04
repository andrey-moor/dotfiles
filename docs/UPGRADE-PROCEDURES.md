# Upgrade Procedures

> **Last updated:** 2026-02-04
> **Applies to:** Stargazer and similar Intune-enrolled VMs

This document covers upgrade procedures for components in the Intune-compliant Arch Linux ARM setup. Because several packages are pinned to specific versions for compatibility, upgrades require careful testing.

## Golden Rule

**Always create a VM snapshot before upgrading anything.** If an upgrade breaks enrollment or compliance, restore the snapshot and report the issue.

```bash
# Before any upgrade
prlctl snapshot stargazer -n "Pre-Upgrade-$(date +%Y%m%d)" -d "Before upgrading X"
```

## Table of Contents

1. [Omarchy (System)](#omarchy-system)
2. [Intune Portal](#intune-portal)
3. [Microsoft Identity Broker](#microsoft-identity-broker)
4. [Microsoft Identity Device Broker](#microsoft-identity-device-broker)
5. [OpenSSL (Pinned)](#openssl-pinned)
6. [OpenSC (Pinned)](#opensc-pinned)
7. [Full System Upgrade](#full-system-upgrade)

---

## Omarchy (System)

**Current version:** armarchy-3-x
**Update frequency:** When new Omarchy releases (major versions)
**Risk level:** MEDIUM - Desktop environment changes

### When to Upgrade

- New Omarchy major version released (armarchy-4-x, etc.)
- Security patches for base system
- New features you want

### Pre-Upgrade Checklist

- [ ] VM snapshot created
- [ ] Device currently enrolled and compliant
- [ ] Documented any custom configs outside home-manager
- [ ] Know your LUKS passphrase (you'll need it)

### Procedure

1. **Create snapshot:**
   ```bash
   # From macOS
   prlctl snapshot stargazer -n "Pre-Omarchy-Upgrade" -d "Before armarchy upgrade"
   ```

2. **Check current version:**
   ```bash
   cat /etc/os-release | grep -i omarchy
   ```

3. **Run upgrade:**
   ```bash
   curl -fsSL hdwy.link/armarchy-X-x | bash
   ```
   (Replace X with new version number)

4. **CRITICAL: Restore GRUB before reboot:**
   ```bash
   sudo cp /boot/EFI/GRUB/grubaa64.efi /boot/EFI/BOOT/BOOTAA64.EFI
   ```

5. **Reboot:**
   ```bash
   sudo reboot
   ```

### Post-Upgrade Verification

```bash
# Check system boots with LUKS
# Enter your passphrase

# Verify Omarchy version
cat /etc/os-release

# Verify Nix still works
nix --version

# Verify Intune still works
intune-health

# Check enrollment status
intune-status
```

- [ ] System boots with LUKS passphrase prompt
- [ ] Logged in successfully
- [ ] `nix --version` works
- [ ] `intune-health` passes (exit code 0)
- [ ] Device still shows enrolled in portal

### Rollback

If verification fails:

1. Shutdown VM:
   ```bash
   # From macOS
   prlctl stop stargazer --kill
   ```

2. Restore snapshot:
   ```bash
   prlctl snapshot-switch stargazer --name "Pre-Omarchy-Upgrade"
   ```

3. Start VM:
   ```bash
   prlctl start stargazer
   ```

### Version History

| Date | Version | Notes |
|------|---------|-------|
| 2026-02-04 | armarchy-3-x | Current working version |

---
