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

## Intune Portal

**Current version:** 1.2511.7-noble
**Package source:** Microsoft .deb repackaged via Nix
**Location:** `packages/intune-portal/default.nix`
**Update frequency:** When Microsoft releases new version
**Risk level:** MEDIUM - May break enrollment flow

### When to Upgrade

- Microsoft announces security fix
- Current version has bugs you're experiencing
- Microsoft deprecates current version

### Finding New Versions

Microsoft publishes Linux packages at: https://packages.microsoft.com/ubuntu/24.04/prod/pool/main/i/intune-portal/

Check for new versions:
```bash
curl -s https://packages.microsoft.com/ubuntu/24.04/prod/pool/main/i/intune-portal/ | grep -oP 'intune-portal_[0-9.]+[^_]*_amd64\.deb' | sort -V | tail -5
```

### Pre-Upgrade Checklist

- [ ] VM snapshot created
- [ ] Noted new version number and download URL
- [ ] Device currently enrolled and compliant

### Procedure

1. **Create snapshot:**
   ```bash
   prlctl snapshot stargazer -n "Pre-Portal-Upgrade" -d "Before intune-portal upgrade"
   ```

2. **Get new package hash:**
   ```bash
   nix-prefetch-url https://packages.microsoft.com/ubuntu/24.04/prod/pool/main/i/intune-portal/intune-portal_NEW_VERSION_amd64.deb
   ```

3. **Update package definition:**
   Edit `packages/intune-portal/default.nix`:
   - Update `version = "NEW_VERSION";`
   - Update `sha256 = "NEW_HASH";`

4. **Rebuild:**
   ```bash
   cd /mnt/psf/Home/Documents/dotfiles  # or your dotfiles path
   nix run home-manager -- switch --flake .#stargazer -b backup
   ```

5. **Test launch:**
   ```bash
   intune-portal-rosetta
   ```

### Post-Upgrade Verification

```bash
# Check version
intune-portal-rosetta --version 2>/dev/null || echo "Check UI for version"

# Verify can sign in
# Launch portal and verify sign-in still works
```

- [ ] Portal launches without errors
- [ ] Can see device status
- [ ] Sign-in flow works (if you sign out and back in)

### Rollback

```bash
# Restore old version in default.nix
git checkout packages/intune-portal/default.nix

# Rebuild
nix run home-manager -- switch --flake .#stargazer -b backup
```

Or restore VM snapshot if Nix rebuild fails.

### Version History

| Date | Version | Notes |
|------|---------|-------|
| 2026-02-04 | 1.2511.7-noble | Current working version |

---

## Microsoft Identity Broker

**Current version:** 2.0.4
**Package source:** Microsoft .deb repackaged via Nix
**Location:** `packages/microsoft-identity-broker/default.nix`
**Update frequency:** When Microsoft releases new version
**Risk level:** HIGH - Handles authentication tokens

### When to Upgrade

- Security advisory from Microsoft
- Authentication failures with current version
- Compatibility issues with new Intune portal version

### Pre-Upgrade Checklist

- [ ] VM snapshot created
- [ ] Current enrollment verified working
- [ ] Noted new version from Microsoft packages site

### Finding New Versions

```bash
curl -s https://packages.microsoft.com/ubuntu/24.04/prod/pool/main/m/microsoft-identity-broker/ | grep -oP 'microsoft-identity-broker_[0-9.]+_amd64\.deb' | sort -V | tail -5
```

### Procedure

Same as Intune Portal:
1. Create snapshot
2. Get new package hash with nix-prefetch-url
3. Update `packages/microsoft-identity-broker/default.nix`
4. Rebuild with home-manager
5. Test authentication

### Post-Upgrade Verification

```bash
# Check D-Bus activation
dbus-send --session --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames | grep microsoft

# Test sign-in flow
intune-portal-rosetta
```

- [ ] Broker activates on D-Bus
- [ ] Portal authentication works

### Rollback

```bash
git checkout packages/microsoft-identity-broker/default.nix
nix run home-manager -- switch --flake .#stargazer -b backup
```

### Version History

| Date | Version | Notes |
|------|---------|-------|
| 2026-02-04 | 2.0.4 | Current working version |

---

## Microsoft Identity Device Broker

**Current version:** 2.0.4 (bundled with microsoft-identity-broker)
**Package source:** Same package as user broker
**Location:** `packages/microsoft-identity-broker/default.nix`
**Update frequency:** When Microsoft releases new version
**Risk level:** HIGH - System service, handles device identity

### When to Upgrade

- Security advisory
- Compliance reporting issues
- Microsoft deprecates current version

### Pre-Upgrade Checklist

- [ ] VM snapshot created
- [ ] Device broker currently running: `systemctl status microsoft-identity-device-broker`
- [ ] Compliance currently working

### Procedure

Same pattern as Microsoft Identity Broker (same package contains both binaries).

After rebuild, restart the service:
```bash
sudo systemctl restart microsoft-identity-device-broker
```

### Post-Upgrade Verification

```bash
# Check service status
systemctl status microsoft-identity-device-broker

# Check D-Bus registration
dbus-send --system --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames | grep microsoft

# Run health check
intune-health
```

- [ ] Service running (active)
- [ ] D-Bus name registered
- [ ] intune-health passes

### Rollback

Same as Microsoft Identity Broker - git checkout and rebuild.

### Version History

| Date | Version | Notes |
|------|---------|-------|
| 2026-02-04 | 2.0.4 | Current working version |

---
