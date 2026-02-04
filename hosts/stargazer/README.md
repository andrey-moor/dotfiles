# Stargazer Setup

> **Last updated:** 2026-02-04
> **Intune Portal:** 1.2511.7 | **Broker:** 2.10.90 | **OpenSSL:** 3.3.2
> **Template:** arch-base-template.pvmp v1.0

Encrypted Arch Linux ARM VM in Parallels with LUKS for Microsoft Intune compliance.

**ARM64 Omarchy:** Based on [PR #1897](https://github.com/basecamp/omarchy/pull/1897)

## Prerequisites

- **macOS on Apple Silicon** (M1/M2/M3/M4)
- **Parallels Desktop** (Pro or Business edition)
- **Template file**: `arch-base-template.pvmp`
- **30+ minutes** for full setup
- **YubiKey** for enrollment (optional - can enroll later)

## Quick Start

```
1. Import    → Import template via Parallels GUI, configure VM
2. Boot      → Enter LUKS passphrase, log in as root
3. Security  → Change LUKS passphrase, reboot to verify, set hostname
4. Omarchy   → Mount Parallels Tools, install desktop (armarchy)
5. GRUB Fix  → Restore GRUB bootloader (critical!)
6. Clone     → Clone dotfiles repo to ~/dotfiles
7. Prereqs   → Run prerequisites.sh (Rosetta + Nix)
8. Nix       → Apply home-manager configuration
9. Intune    → Run intune-prerequisites + create keyring
10. Enroll   → Launch intune-portal and enroll device
```

---

## Pre-Flight Checklist

Before starting, verify these requirements:

- [ ] macOS on Apple Silicon (M1/M2/M3/M4)
- [ ] Parallels Desktop Pro or Business installed
- [ ] Template file available (`arch-base-template.pvmp`)
- [ ] 30+ minutes for full setup (mostly waiting for downloads)
- [ ] YubiKey available for enrollment step (optional - can enroll later)

**Tip:** Create VM snapshots before major changes. If something breaks, restore and retry.

---

## 1. Import Template

### Import via Parallels GUI

1. Double-click `arch-base-template.pvmp` to import
2. Or: **File → Open** and select the `.pvmp` file
3. Name the VM (e.g., `stargazer`)

### Configure VM Settings

After import, configure the VM in **Parallels → Configure**:

| Setting | Value | Location |
|---------|-------|----------|
| CPUs | 8 cores | Hardware → CPU & Memory |
| Memory | 32 GB | Hardware → CPU & Memory |
| Network | Bridged | Hardware → Network |
| Graphics | Scaled (for better resolution) | Hardware → Graphics |
| Rosetta Linux | ON | Hardware → CPU & Memory → Advanced |
| EFI Secure Boot | OFF | Hardware → Boot Order → Advanced |
| 3D Acceleration | Highest | Hardware → Graphics |
| Smart Card Sharing | ON | Hardware → USB & Bluetooth |

**Optional for development:** Add shared folder `dotfiles` → `~/Documents/dotfiles`

### Verification

- [ ] VM imported with correct name
- [ ] CPU/Memory configured (8 cores, 32GB)
- [ ] Rosetta Linux enabled
- [ ] Smart card sharing enabled (for YubiKey)

---

## 2. First Boot

Start the VM from Parallels.

**At GRUB:** Press Enter or wait.

**At LUKS prompt:** Enter passphrase `4815162342`

**At login:** Username `root`, password `481516`

### Verification

- [ ] GRUB menu appeared (not Limine)
- [ ] LUKS passphrase prompt accepted `4815162342`
- [ ] Logged in as root successfully

**If verification fails:** See [Troubleshooting: No LUKS Passphrase Prompt](../../docs/TROUBLESHOOTING.md#no-luks-passphrase-prompt)

---

## 3. Security Setup

**Do this immediately** - the template uses known credentials.

### Change LUKS Passphrase

```bash
cryptsetup luksChangeKey /dev/vda2
```

Enter current passphrase (`4815162342`), then your new passphrase twice.

### Reboot to Verify LUKS Change

**Important:** Verify your new passphrase works before proceeding!

```bash
reboot
```

At LUKS prompt, enter your **new** passphrase. If it works, log back in as root.

**If you forgot the passphrase:** Restore from snapshot and try again.

### Change Root Password

```bash
passwd
```

### Set Hostname

```bash
hostnamectl set-hostname stargazer
```

Replace `stargazer` with your desired hostname.

### Verification

- [ ] Rebooted and new LUKS passphrase worked
- [ ] Root password changed
- [ ] Hostname updated (`hostnamectl` shows new name)

---

## 4. Install Omarchy

### Mount Parallels Tools

Before running armarchy, mount Parallels Tools:

**In Parallels menu:** Actions → Install Parallels Tools

Or the CD should auto-mount. Verify:

```bash
ls /media/cdrom/
# Should show Parallels Tools files
```

### Run armarchy

```bash
curl -fsSL hdwy.link/armarchy-3-x | bash
```

Follow prompts to create your user account.

**Password requirements** (for Intune compliance):
- 12+ characters
- At least 1 uppercase, 1 lowercase, 1 digit, 1 symbol

**After armarchy completes:** Press `Ctrl+C` to return to root terminal.

⚠️ **DO NOT REBOOT when prompted!** You must fix GRUB first.

### Verification

```bash
id yourusername
# Expected: uid and gid shown
```

- [ ] User created with username you specified
- [ ] Password meets Intune requirements (12+ chars, mixed case, digit, symbol)
- [ ] **Did NOT reboot yet** (GRUB fix required first)

**If armarchy fails:** Re-run the curl command. Script is idempotent.

---

## 5. Restore GRUB Bootloader

### Confirm Omarchy Loaded

Before fixing GRUB, confirm you're in the Omarchy/Hyprland environment:
- You should see the Hyprland desktop (or login screen)
- If not, something went wrong with armarchy

**Resolution tip:** If the display resolution is poor, go to **Parallels → Hardware → Graphics → select "Scaled"**, then restart Hyprland. See [PR #1897 comments](https://github.com/basecamp/omarchy/pull/1897) for details.

### Fix GRUB

**Critical!** Armarchy installs Limine which breaks LUKS boot.

```bash
sudo cp /boot/EFI/GRUB/grubaa64.efi /boot/EFI/BOOT/BOOTAA64.EFI
```

Verify the file is ~160KB (not ~90KB):

```bash
ls -la /boot/EFI/BOOT/BOOTAA64.EFI
# Expected: ~158720 bytes (GRUB), not ~90KB (Limine)
```

### Reboot

```bash
sudo reboot
```

After reboot:
1. Enter your LUKS passphrase
2. Log in as your new user (not root)

### Verification

- [ ] File size is ~160KB (GRUB), not ~90KB (Limine)
- [ ] Reboot completed successfully
- [ ] LUKS prompt appeared with your passphrase
- [ ] Logged in as your user (not root)

**If verification fails:** See [Troubleshooting: Limine Boots Instead of GRUB](../../docs/TROUBLESHOOTING.md#limine-boots-instead-of-grub)

---

## 6. Clone Dotfiles

Clone the dotfiles repository to your home directory:

```bash
git clone https://github.com/andrey-moor/dotfiles.git ~/dotfiles
```

Or if using SSH:

```bash
git clone git@github.com:andrey-moor/dotfiles.git ~/dotfiles
```

### Verification

```bash
ls ~/dotfiles/scripts/prerequisites.sh
# Expected: file exists
```

- [ ] Dotfiles cloned to `~/dotfiles`

---

## 7. Run Prerequisites Script

This configures Rosetta and installs Nix.

```bash
~/dotfiles/scripts/prerequisites.sh
```

The script configures:
- Rosetta binfmt for x86_64 emulation
- Nix package manager
- extra-platforms for cross-architecture builds
- Dynamic linker for x86_64 binaries
- os-release spoof for Intune compatibility

### Verification

```bash
# Check Rosetta
cat /proc/sys/fs/binfmt_misc/rosetta
# Expected: "enabled" in output

# Check Nix
nix --version
# Expected: nix (Nix) 2.x.x

# Check os-release spoof
cat /etc/os-release | head -2
# Expected: NAME="Ubuntu", VERSION_ID="22.04"
```

- [ ] Rosetta binfmt registered and enabled
- [ ] Nix installed and in PATH
- [ ] os-release shows Ubuntu 22.04

**If verification fails:** See [Troubleshooting: Rosetta/Nix Issues](../../docs/TROUBLESHOOTING.md#rosetta-binfmt-not-registered)

---

## 8. Apply Home-Manager

```bash
cd ~/dotfiles
nix run home-manager -- switch --flake .#stargazer -b backup
```

First run takes several minutes. This installs all Intune packages and tools.

### Verification

```bash
# Check intune commands available
which intune-health
# Expected: path in ~/.nix-profile/bin/
```

- [ ] Home-manager switch completed without errors
- [ ] `intune-health`, `intune-portal-rosetta` commands exist

**If verification fails:** Re-run the `nix run home-manager` command.

---

## 9. Intune Setup

### 9.1 Run Intune Prerequisites

```bash
intune-prerequisites
```

This configures:
- Device broker (D-Bus policy + systemd service)
- pcscd for YubiKey/smart card support
- PKCS#11 modules
- PAM password policy

### 9.2 Create Login Keyring (Required)

```bash
seahorse &
```

In Seahorse:
1. **File → New → Password Keyring**
2. Name it exactly: `login`
3. Set a password (can match your user password)
4. Right-click the keyring → **Set as Default**

**Why?** Intune stores tokens in the keyring. Without a proper login keyring, enrollment fails.

### 9.3 Enable Intune Agent Timer

```bash
systemctl --user enable --now intune-agent.timer
```

### 9.4 Verify Setup

```bash
intune-health
```

All critical checks should show `[PASS]`. YubiKey warnings are OK if not inserted.

### Verification

- [ ] `intune-health` exits with code 0
- [ ] All critical checks PASS
- [ ] Login keyring created and set as default in Seahorse

**If verification fails:** See [Troubleshooting: Intune Prerequisites](../../docs/TROUBLESHOOTING.md#device-broker-fails)

---

## 10. Enroll Device

### Pre-enrollment Checklist

- [ ] `intune-health` passes (exit code 0)
- [ ] Login keyring created in Seahorse
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

- [ ] Device shows as enrolled in portal
- [ ] Compliance check completes

**If enrollment fails:** See [Troubleshooting: Enrollment Issues](../../docs/TROUBLESHOOTING.md#enrollment-fails)

---

## Troubleshooting

See [docs/TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md) for comprehensive troubleshooting.

### Quick Fixes

**No LUKS prompt after reboot:** GRUB fix wasn't applied. See Section 5.

**Device broker D-Bus error:**
```bash
sudo systemctl reload dbus
sudo systemctl restart microsoft-identity-device-broker
```

**Enrollment fails with keyring error:** Create login keyring via `seahorse` (Section 9.2).

**Rosetta not registered:**
```bash
sudo systemctl restart systemd-binfmt
```

---

## Appendix A: Template Creation

If you need to create the template from scratch:

1. Follow [docs/arch-arm-encrypted-install.md](../../docs/arch-arm-encrypted-install.md)
2. Create snapshot before Omarchy: `prlctl snapshot VM -n "EncryptedBase-GRUB"`
3. Export: `prlctl pack VM --output ~/arch-base-template.pvmp`

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

# Snapshots
prlctl snapshot-list stargazer
prlctl snapshot stargazer -n "name" -d "description"
prlctl snapshot-switch stargazer --id "{uuid}"
```
