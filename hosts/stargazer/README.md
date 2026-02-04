# Stargazer Setup

> **Last updated:** 2026-02-03
> **Intune Portal:** 1.2511.7 | **Broker:** 2.10.90 | **OpenSSL:** 3.3.2
> **Template:** ArchBase-LUKS-GRUB.pvmp v1.0

Encrypted Arch Linux ARM VM in Parallels with LUKS for Microsoft Intune compliance.

## Prerequisites

- **macOS on Apple Silicon** (M1/M2/M3)
- **Parallels Desktop** (Pro or Business edition)
- **Dotfiles repository** cloned to `~/Documents/dotfiles`
- **Template file**: `ArchBase-LUKS-GRUB.pvmp` (or clone from ArchBase-Template VM)

## Quick Start

```
1. Import    → Import template, configure VM
2. Boot      → Enter LUKS passphrase, log in as root
3. Security  → Change LUKS passphrase, root password, hostname
4. Omarchy   → Install desktop (armarchy)
5. GRUB Fix  → Restore GRUB bootloader (critical!)
6. Prereqs   → Run prerequisites.sh (Rosetta + Nix)
7. Nix       → Apply home-manager configuration
8. Intune    → Run intune-prerequisites + create keyring
9. Enroll    → Launch intune-portal and enroll device
```

---

## Pre-Flight Checklist

Before starting, verify these requirements:

- [ ] macOS on Apple Silicon (M1/M2/M3)
- [ ] Parallels Desktop Pro or Business installed
- [ ] Dotfiles cloned to `~/Documents/dotfiles`
- [ ] Template file available (`ArchBase-LUKS-GRUB.pvmp` or existing ArchBase-Template VM)
- [ ] 30+ minutes for full setup (mostly waiting for downloads)
- [ ] YubiKey available for enrollment step (optional - can enroll later)

**Tip:** Create VM snapshots before major changes. If something breaks, restore and retry.

---

## 1. Import Template

### Option A: Clone from existing VM

```bash
prlctl clone ArchBase-Template --name stargazer
```

### Option B: Import from .pvmp file

```bash
prlctl import ~/Downloads/ArchBase-LUKS-GRUB.pvmp --name stargazer
```

### Configure VM

```bash
prlctl set stargazer --cpus 4 --memsize 8192
prlctl set stargazer --rosetta-linux on
prlctl set stargazer --shf-host on
```

---

## 2. First Boot

```bash
prlctl start stargazer
```

**At GRUB:** Press Enter or wait.

**At LUKS prompt:** Enter passphrase `4815162342`

**At login:** Username `root`, password `481516`

---

## 3. Security Setup

**Do this immediately** - the template uses known credentials.

### Change LUKS Passphrase

```bash
cryptsetup luksChangeKey /dev/vda2
```

Enter current passphrase (`4815162342`), then your new passphrase twice.

### Change Root Password

```bash
passwd
```

Enter a new root password (you'll rarely need this after creating your user).

### Set Hostname

```bash
hostnamectl set-hostname stargazer
```

Replace `stargazer` with your desired hostname.

---

## 4. Install Omarchy

```bash
curl -fsSL hdwy.link/armarchy-3-x | bash
```

Follow prompts to create your user account.

**Password requirements** (for Intune compliance):
- 12+ characters
- At least 1 uppercase, 1 lowercase, 1 digit, 1 symbol

**DO NOT REBOOT when prompted!** You must fix GRUB first.

---

## 5. Restore GRUB Bootloader

**Critical!** Armarchy installs Limine which breaks LUKS boot.

```bash
sudo cp /boot/EFI/GRUB/grubaa64.efi /boot/EFI/BOOT/BOOTAA64.EFI
```

Verify the file is ~160KB (not ~90KB):

```bash
ls -la /boot/EFI/BOOT/BOOTAA64.EFI
```

Now reboot:

```bash
sudo reboot
```

After reboot, log in as your new user (not root).

---

## 6. Run Prerequisites Script

This configures Rosetta and installs Nix.

```bash
# Check which path exists
ls /mnt/psf/

# Run the script (use whichever path exists)
/mnt/psf/dotfiles/scripts/prerequisites.sh
# or: /mnt/psf/Home/Documents/dotfiles/scripts/prerequisites.sh
```

The script configures: Rosetta binfmt, Nix installation, extra-platforms, dynamic linker, os-release spoof.

---

## 7. Apply Home-Manager

```bash
cd /mnt/psf/dotfiles  # or /mnt/psf/Home/Documents/dotfiles
nix run home-manager -- switch --flake .#stargazer -b backup
```

First run takes several minutes. This installs all Intune packages and tools.

---

## 8. Intune Setup

### 8.1 Run Prerequisites Script

```bash
intune-prerequisites
```

This configures:
- Device broker (D-Bus policy + systemd service)
- pcscd for YubiKey/smart card support
- PKCS#11 modules
- PAM password policy
- Keyring default pointer

### 8.2 Create Login Keyring (Required)

The script sets up the keyring pointer, but you must create the actual keyring via GUI:

```bash
seahorse &
```

In Seahorse:
1. **File → New → Password Keyring**
2. Name it exactly: `login`
3. Set a password (can match your user password)
4. Right-click the keyring → **Set as Default**

**Why?** Intune stores tokens in the keyring. Without a proper login keyring, enrollment fails with "Object does not exist at path /org/freedesktop/secrets/collection/login".

### 8.3 Configure Parallels Smart Card Sharing

In Parallels: **VM Configuration → Hardware → USB & Bluetooth → Share smart card readers with Linux**

This allows the VM to see your YubiKey.

### 8.4 Enable Intune Agent Timer

```bash
systemctl --user enable --now intune-agent.timer
```

### 8.5 Verify Setup

```bash
intune-health
```

All critical checks should show `[PASS]`. YubiKey warnings are OK if not inserted.

---

## 9. Enroll Device

### Pre-enrollment Checklist

- [ ] `intune-health` passes (exit code 0)
- [ ] Login keyring created in seahorse
- [ ] YubiKey inserted into Mac
- [ ] Parallels smart card sharing enabled

### Enrollment Steps

1. Launch the portal:
   ```bash
   intune-portal-rosetta
   ```

2. Click **Sign In**

3. Enter your Microsoft work email

4. When certificate picker appears, select your YubiKey PIV certificate

5. Enter YubiKey PIN

6. Complete the enrollment wizard

### Verify Enrollment

```bash
# Trigger compliance check
intune-agent-rosetta

# Check logs
journalctl --user -u intune-agent --since "5 minutes ago"
```

---

## 10. Ongoing Usage

### Check Status

```bash
intune-health              # Component health check
intune-status              # Quick status
intune-portal-rosetta      # Open portal UI
```

### Manual Compliance Check

```bash
intune-agent-rosetta
journalctl --user -u intune-agent --since "10 minutes ago"
```

### Timer Status

```bash
systemctl --user list-timers | grep intune
```

---

## Troubleshooting

### No LUKS passphrase prompt after reboot

GRUB fix wasn't applied. Boot from snapshot or recover manually:

```bash
# Boot from archboot ISO, then:
cryptsetup open /dev/vda2 cryptroot
mount /dev/mapper/cryptroot /mnt
mount /dev/vda1 /mnt/boot
cp /mnt/boot/EFI/GRUB/grubaa64.efi /mnt/boot/EFI/BOOT/BOOTAA64.EFI
umount -R /mnt
reboot
```

### Device broker fails with D-Bus error

```bash
sudo systemctl reload dbus
sudo systemctl restart microsoft-identity-device-broker
```

### Enrollment fails with keyring error

Create the login keyring via `seahorse` (see section 8.2).

### Rosetta binfmt not registered

```bash
cat /proc/sys/fs/binfmt_misc/rosetta  # Check status
sudo systemctl restart systemd-binfmt  # Re-register
```

### Shared folders not visible

```bash
mount | grep psf           # Check if mounted
sleep 15 && ls /mnt/psf/   # Wait for prltoolsd
```

### intune-portal authentication fails

```bash
systemctl status microsoft-identity-device-broker  # Check broker
ls ~/.local/share/dbus-1/services/                 # Check user service
sudo systemctl restart microsoft-identity-device-broker
```

---

## Appendix A: Template Creation

If you need to create the template from scratch:

1. Follow [docs/arch-arm-encrypted-install.md](../../docs/arch-arm-encrypted-install.md)
2. Create snapshot: `prlctl snapshot ArchBase-Template -n "EncryptedBase-GRUB"`
3. Export: `prlctl pack ArchBase-Template --output ~/ArchBase-LUKS-GRUB.pvmp`

### Template Credentials

| Item | Value |
|------|-------|
| LUKS passphrase | `4815162342` |
| Root password | `481516` |

---

## Appendix B: prlctl Quick Reference

```bash
# Lifecycle
prlctl start stargazer
prlctl stop stargazer
prlctl stop stargazer --kill

# Info
prlctl list -a
prlctl list -i stargazer

# Config
prlctl set stargazer --cpus 4 --memsize 8192

# Snapshots
prlctl snapshot-list stargazer
prlctl snapshot stargazer -n "name" -d "description"
prlctl snapshot-switch stargazer --id "{uuid}"

# Remote execution
prlctl exec stargazer "hostname"
```

---

## Appendix C: prl-type.sh

Type commands into VM console from macOS (useful when copy-paste unavailable):

```bash
./scripts/prl-type.sh stargazer "command here"
DELAY=50 ./scripts/prl-type.sh stargazer "slow typing"
```

Note: You still need to press Enter in the VM console after typing.
