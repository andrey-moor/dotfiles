# Stargazer Setup

Encrypted Arch Linux ARM VM in Parallels with LUKS for Microsoft Intune compliance.

**What is stargazer?** An Intune-compliant Arch Linux workstation running on Apple Silicon via Parallels Desktop. Uses LUKS full-disk encryption (required for Intune) and Omarchy (Hyprland desktop).

## Prerequisites

Before starting, ensure you have:

- **macOS on Apple Silicon** (M1/M2/M3)
- **Parallels Desktop** (Pro or Business edition for prlctl CLI)
- **Dotfiles repository** cloned to `~/Documents/dotfiles`
- **Template file**: `ArchBase-LUKS-GRUB.pvmp` (see [Appendix A](#appendix-a-template-source) if you need to create it)

## Overview

The setup workflow:

1. **Import** - Import the `.pvmp` template into Parallels
2. **Boot** - Start VM and enter LUKS passphrase
3. **Security** - Change the default LUKS passphrase
4. **Omarchy** - Install the Omarchy desktop (armarchy for ARM)
5. **GRUB Fix** - Restore GRUB bootloader (critical!)
6. **Prerequisites** - Run Rosetta/Nix setup script
7. **Home-Manager** - Apply Nix configuration
8. **Intune** - Run `intune-prerequisites` to configure components
9. **Verify** - Run `intune-health` to confirm everything works

---

## 1. Import Template

Import the encrypted base template into Parallels.

### Option A: GUI Import

1. Open Parallels Desktop
2. **File > Open** (or drag `.pvmp` file to Parallels)
3. Select the `ArchBase-LUKS-GRUB.pvmp` file
4. Name the VM `stargazer`
5. Choose location (default `~/Parallels/` is fine)

### Option B: CLI Import

```bash
# Import the .pvmp template
prlctl import ~/Downloads/ArchBase-LUKS-GRUB.pvmp --name stargazer
```

### Configure VM Settings

After import, configure resources:

```bash
# Set CPU and memory
prlctl set stargazer --cpus 4 --memsize 8192

# Enable Rosetta (x86_64 emulation)
prlctl set stargazer --rosetta-linux on

# Enable shared folders (for dotfiles access)
prlctl set stargazer --shf-host on
```

Or configure via Parallels GUI: **Configuration > Hardware** (CPU/Memory) and **Options > Sharing** (shared folders).

---

## 2. First Boot

Start the VM and unlock encryption.

```bash
prlctl start stargazer
```

Or click **Start** in Parallels Control Center.

**At the GRUB menu:** Press Enter or wait for timeout.

**At the LUKS prompt:**
- Enter passphrase: `4815162342`

**At the login prompt:**
- Username: `root`
- Password: `481516`

---

## 3. Change LUKS Passphrase (Security)

**IMPORTANT:** The template uses a known passphrase. Change it immediately for security.

```bash
cryptsetup luksChangeKey /dev/vda2
```

When prompted:
1. Enter current passphrase: `4815162342`
2. Enter your new passphrase (strong, you'll type it at every boot)
3. Confirm new passphrase

**Passphrase tips:**
- Use a memorable but strong phrase (you'll type it often)
- Consider a passphrase like `correct-horse-battery-staple`
- This is separate from your user password

---

## 4. Install Omarchy (armarchy)

Install the Omarchy desktop environment using the ARM64 installer.

### What armarchy does:

- Installs Hyprland (Wayland compositor)
- Configures desktop environment (waybar, rofi, etc.)
- Creates your user account
- Installs Parallels Tools for shared folders

### Run the installer:

**From inside the VM:**

```bash
curl -fsSL hdwy.link/armarchy-3-x | bash
```

**Or type from macOS using prl-type.sh:**

```bash
./scripts/prl-type.sh stargazer "curl -fsSL hdwy.link/armarchy-3-x | bash"
# Then press Enter in the VM console
```

### Installer prompts:

The installer will ask for:
- **Your name** (display name)
- **Your email** (for git config)
- **Username** (login name, e.g., `andreym`)
- **Password** (must meet Intune requirements)

**Password requirements for Intune compliance:**
- 12+ characters minimum
- At least 1 uppercase letter (A-Z)
- At least 1 lowercase letter (a-z)
- At least 1 digit (0-9)
- At least 1 symbol (!@#$%^&*...)

Example: `MyP@ssw0rd123!` or `Secure-Pass-2024!`

**DO NOT REBOOT when prompted by armarchy!** You must fix GRUB first (next step).

---

## 5. Restore GRUB Bootloader (Critical!)

**WARNING:** armarchy installs the Limine bootloader, which breaks LUKS boot. You MUST restore GRUB before rebooting.

If you skip this step, your VM will not boot properly - you'll see "Omarchy Bootloader" instead of GRUB, and LUKS decryption will fail.

### Restore GRUB:

```bash
sudo cp /boot/EFI/GRUB/grubaa64.efi /boot/EFI/BOOT/BOOTAA64.EFI
```

### Verify the fix:

```bash
ls -la /boot/EFI/BOOT/BOOTAA64.EFI
```

The file should be **~160KB**. If it's ~90KB, that's Limine (wrong) - run the copy command again.

### Now reboot:

```bash
sudo reboot
```

After reboot:
1. GRUB menu appears (not "Omarchy Bootloader")
2. LUKS passphrase prompt appears
3. Login manager appears (log in with your new user, not root)

---

## 6. Run Prerequisites Script

After logging in as your new user (not root), run the prerequisites script to configure Rosetta and Nix.

**Note on shared folder paths:** The path depends on how Parallels shared folders are configured:
- If shared as "dotfiles" folder: `/mnt/psf/dotfiles`
- If sharing full Home folder: `/mnt/psf/Home/Documents/dotfiles`

Check which exists: `ls /mnt/psf/`

**From inside the VM:**

```bash
# If dotfiles is shared directly:
/mnt/psf/dotfiles/scripts/prerequisites.sh

# Or if Home folder is shared:
/mnt/psf/Home/Documents/dotfiles/scripts/prerequisites.sh
```

**Or type from macOS:**

```bash
./scripts/prl-type.sh stargazer "/mnt/psf/dotfiles/scripts/prerequisites.sh"
```

### What prerequisites.sh configures:

- **Rosetta binfmt** - Enables x86_64 binary execution via Apple's Rosetta
- **Rosetta boot service** - Ensures Rosetta binfmt survives reboot
- **Nix installation** - Installs Determinate Nix package manager
- **extra-platforms** - Enables Nix to build x86_64 packages
- **Dynamic linker** - Creates /lib64/ld-linux-x86-64.so.2 symlink
- **os-release spoof** - Spoofs Ubuntu 22.04 for Microsoft tools

The script is idempotent - safe to run multiple times.

---

## 7. Apply Home-Manager Configuration

Apply the Nix-based home configuration.

```bash
# Use the path that exists for your setup:
cd /mnt/psf/dotfiles  # or /mnt/psf/Home/Documents/dotfiles
nix run home-manager -- switch --flake .#stargazer -b backup
```

This installs:
- Shell configuration (nushell, starship)
- Development tools
- Microsoft Intune packages (intune-portal, device broker, intune-agent)
- Various CLI utilities

The first run may take several minutes to download and build packages.

---

## 8. Intune Setup

Configure the Microsoft Intune components for device compliance.

### Automated Setup (Recommended)

Run the automated prerequisites script to configure all Intune components:

```bash
intune-prerequisites
```

This configures:
- Device broker D-Bus policy and systemd service
- User broker D-Bus activation
- pcscd for YubiKey/smart card support
- PKCS#11 modules for certificate access
- Keyring default
- PAM password policy for Intune compliance
- Intune agent timer

The script is idempotent - safe to run multiple times. Each section shows either `[+]` (applied) or `[=]` (already configured).

**Parallels Setting:** After running, enable **Hardware > USB & Bluetooth > Share smart card readers with Linux** in Parallels VM settings for YubiKey support.

### Apply Chezmoi Configuration

Home-manager installs packages and declarative configs. Chezmoi manages mutable user configs (neovim, nushell, etc.):

```bash
chezmoi apply
```

<details>
<summary>Manual setup (for reference/debugging)</summary>

### 8.1 Device Broker D-Bus + Systemd

The device broker handles Microsoft authentication:

```bash
# D-Bus policy (use /usr/share, NOT /etc - don't restart dbus!)
BROKER_PKG=$(find /nix/store -maxdepth 1 -name '*microsoft-identity-broker-2.0.4' -type d | head -1)
sudo cp "$BROKER_PKG/share/dbus-1/system.d/com.microsoft.identity.devicebroker1.conf" /usr/share/dbus-1/system.d/
sudo chmod 644 /usr/share/dbus-1/system.d/com.microsoft.identity.devicebroker1.conf

# Reload D-Bus to pick up new policy
sudo pkill -HUP dbus-daemon

# Systemd service + Rosetta override (with HOME for MSAL initialization)
sudo cp "$BROKER_PKG/lib/systemd/system/microsoft-identity-device-broker.service" /etc/systemd/system/
WRAPPER=$(readlink -f ~/.nix-profile/bin/microsoft-identity-device-broker-rosetta)
sudo mkdir -p /etc/systemd/system/microsoft-identity-device-broker.service.d
echo "[Service]
ExecStart=
ExecStart=$WRAPPER
Environment=HOME=/root
Environment=XDG_CONFIG_HOME=/root/.config
Environment=XDG_CACHE_HOME=/root/.cache
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target" | sudo tee /etc/systemd/system/microsoft-identity-device-broker.service.d/rosetta.conf

sudo systemctl daemon-reload
sudo systemctl enable --now microsoft-identity-device-broker

# User-level broker D-Bus service (for intune-portal authentication)
USER_WRAPPER=$(readlink -f ~/.nix-profile/bin/microsoft-identity-broker-rosetta)
mkdir -p ~/.local/share/dbus-1/services
echo "[D-BUS Service]
Name=com.microsoft.identity.broker1
Exec=$USER_WRAPPER" > ~/.local/share/dbus-1/services/com.microsoft.identity.broker1.service
```

### 8.2 pcscd for YubiKey

Configure smart card daemon for YubiKey authentication:

```bash
# Install packages
sudo pacman -S --noconfirm pcsc-tools opensc ccid

# Socket symlink (x86_64 expects /run/pcscd/pcscd)
echo 'L /run/pcscd/pcscd - - - - /run/pcscd/pcscd.comm' | sudo tee /etc/tmpfiles.d/pcscd-symlink.conf
sudo systemd-tmpfiles --create /etc/tmpfiles.d/pcscd-symlink.conf

# Disable polkit (blocks Rosetta processes)
sudo mkdir -p /etc/systemd/system/pcscd.service.d
echo '[Service]
ExecStart=
ExecStart=/usr/bin/pcscd --foreground --auto-exit --disable-polkit' | sudo tee /etc/systemd/system/pcscd.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl enable --now pcscd.socket

# p11-kit modules
sudo mkdir -p /etc/pkcs11/modules
sudo chmod 755 /etc/pkcs11 /etc/pkcs11/modules
OPENSC_NIX=$(find /nix/store -maxdepth 1 -name '*opensc-arch-0.25.1' -type d | head -1)
echo "module: $OPENSC_NIX/lib/pkcs11/opensc-pkcs11.so
critical: no" | sudo tee /etc/pkcs11/modules/opensc-x86.module
echo "module: /usr/lib/pkcs11/opensc-pkcs11.so
critical: no" | sudo tee /etc/pkcs11/modules/opensc.module
sudo chmod 644 /etc/pkcs11/modules/*.module

# Add Parallels Proxy CCID to ccid driver (required for smart card sharing)
sudo sed -i.bak '
  /<key>ifdVendorID<\/key>/,/<\/array>/ {
    /<\/array>/ i\                <string>0x203A</string>
  }
  /<key>ifdProductID<\/key>/,/<\/array>/ {
    /<\/array>/ i\                <string>0xFFFD</string>
  }
  /<key>ifdFriendlyName<\/key>/,/<\/array>/ {
    /<\/array>/ i\                <string>Parallels Proxy CCID</string>
  }
' /usr/lib/pcsc/drivers/ifd-ccid.bundle/Contents/Info.plist
```

**Parallels Setting:** Enable **Hardware > USB & Bluetooth > Share smart card readers with Linux**

### 8.3 Login Keyring Setup

**CRITICAL:** The login keyring must exist AND have a password for Intune enrollment to succeed.

1. **Create login keyring** (via GUI - required):
   ```bash
   seahorse &
   ```
   - In Seahorse: File → New → Password Keyring
   - Name it exactly: `login`
   - Set a password (can match your user password for auto-unlock)
   - Right-click the new keyring → Set as Default

2. **Set default pointer** (automated by intune-prerequisites):
   ```bash
   mkdir -p ~/.local/share/keyrings
   echo -n login > ~/.local/share/keyrings/default
   ```

3. **Verify keyring works**:
   ```bash
   # Check keyring service is running
   busctl --user tree org.freedesktop.secrets
   # Should show: /org/freedesktop/secrets/collection/login
   ```

**Note:** If you see "Object does not exist at path /org/freedesktop/secrets/collection/login" during enrollment, the login keyring wasn't created properly. Use `seahorse` to create it.

### 8.4 Intune Compliance (PAM Password Policy)

Intune checks `/etc/pam.d/common-password` for password complexity:

```bash
sudo tee /etc/pam.d/common-password << 'EOF'
# /etc/pam.d/common-password - password-related modules for PAM
# Created for Microsoft Intune compliance

# Password strength requirements (Intune compliance)
password    requisite     pam_pwquality.so retry=3 dcredit=-1 ocredit=-1 ucredit=-1 lcredit=-1 minlen=12

# Standard password handling
password    required      pam_unix.so sha512 shadow try_first_pass use_authtok
EOF

# IMPORTANT: Make readable by intune-agent (runs as user)
sudo chmod 644 /etc/pam.d/common-password
```

### 8.5 Enable Intune Agent Timer

The intune-agent periodically reports compliance status to Microsoft:

```bash
systemctl --user enable --now intune-agent.timer
```

To trigger an immediate compliance report:

```bash
intune-agent-rosetta
```

</details>

---

## 9. Verify

Run the health check to verify all components are working:

```bash
intune-health
```

Expected output:
- All critical checks show `[PASS]`
- YubiKey check may show `[WARN]` if not inserted (that's OK)
- Exit code 0 means all critical components are healthy

### Additional Verification

```bash
# Check intune-agent timer is active
systemctl --user list-timers | grep intune

# Launch Intune portal (should show Microsoft login)
intune-portal-rosetta

# Insert YubiKey and check reader detection
pcsc_scan -r
```

### Check Compliance Reporting

```bash
# Trigger manual compliance report
intune-agent-rosetta

# Check logs
journalctl --user -u intune-agent --since "5 minutes ago"
```

---

## 10. Troubleshooting

### No LUKS passphrase prompt after reboot

**Cause:** GRUB fix was not applied before reboot.

**Solution:** Boot from snapshot and redo setup, or recover manually:

1. In Parallels, reset VM to pre-armarchy state if you have a snapshot
2. Or boot from archboot ISO and fix manually:

```bash
# Boot from archboot ISO
cryptsetup open /dev/vda2 cryptroot
mount /dev/mapper/cryptroot /mnt
mount /dev/vda1 /mnt/boot
cp /mnt/boot/EFI/GRUB/grubaa64.efi /mnt/boot/EFI/BOOT/BOOTAA64.EFI
umount -R /mnt
reboot
```

### "Omarchy Bootloader" appears instead of GRUB

This means Limine is booting instead of GRUB. See recovery steps above.

### Rosetta binfmt not registered

Check registration status:

```bash
cat /proc/sys/fs/binfmt_misc/rosetta
```

If not registered:

```bash
sudo systemctl restart systemd-binfmt
sudo systemctl restart microsoft-identity-device-broker
```

The `rosetta-binfmt.path` unit should handle this automatically by watching for the Rosetta binary to appear after boot.

### Device broker fails to start with D-Bus error

```bash
# Reload D-Bus config (required after installing new policy)
sudo systemctl reload dbus
sudo systemctl restart microsoft-identity-device-broker
```

If "Name Error (Request to own name refused by policy)" persists after reload, reboot the VM.

### Device broker not running (intune-portal crashes)

```bash
sudo systemctl restart microsoft-identity-device-broker
systemctl status microsoft-identity-device-broker
```

### Permission errors after running commands via prlctl exec

Commands run via `prlctl exec` run as root, creating files owned by root in user directories. Fix with:

```bash
sudo chown -R $USER:$USER ~/.config ~/.local
```

### Shared folders not visible (/mnt/psf empty)

```bash
# Check if mount exists
mount | grep psf

# Wait for prltoolsd (may take 10-15 seconds after boot)
sleep 15 && ls /mnt/psf/Home

# If still not working, check Parallels Tools
lsmod | grep prl
```

### intune-portal authentication fails

1. Check device broker is running: `systemctl status microsoft-identity-device-broker`
2. Check user broker service exists: `ls ~/.local/share/dbus-1/services/`
3. Try restarting: `sudo systemctl restart microsoft-identity-device-broker`

---

## Quick Reference: prl-type.sh

The `prl-type.sh` script types text into the VM console from macOS. Useful when you can't copy-paste.

### Basic usage:

```bash
# Type a command (VM must be at a prompt)
./scripts/prl-type.sh stargazer "echo hello"

# With custom delay (slower, more reliable)
DELAY=50 ./scripts/prl-type.sh stargazer "complex command"

# For a different VM
VM=endurance ./scripts/prl-type.sh "echo hello"
```

### Common examples:

```bash
# Type the armarchy installer command
./scripts/prl-type.sh stargazer "curl -fsSL hdwy.link/armarchy-3-x | bash"

# Type the prerequisites script path (adjust based on your mount)
./scripts/prl-type.sh stargazer "/mnt/psf/dotfiles/scripts/prerequisites.sh"

# Type LUKS passphrase change command
./scripts/prl-type.sh stargazer "cryptsetup luksChangeKey /dev/vda2"

# Type the GRUB fix
./scripts/prl-type.sh stargazer "sudo cp /boot/EFI/GRUB/grubaa64.efi /boot/EFI/BOOT/BOOTAA64.EFI"
```

**Note:** After typing, you still need to press Enter in the VM console. The script types but doesn't submit.

---

## Appendix A: Template Source

### Creating the .pvmp Template

If you need to create the template from scratch, follow these guides in order:

1. **Base encrypted system:** [docs/arch-arm-encrypted-install.md](../../docs/arch-arm-encrypted-install.md)
   - Creates LUKS-encrypted Arch Linux with GRUB bootloader

2. **Create the template snapshot:**
   ```bash
   # After base system is working, create snapshot
   prlctl snapshot ArchBase-Template -n "EncryptedBase-GRUB" -d "LUKS+GRUB base, before Omarchy"
   ```

3. **Export as .pvmp:**
   ```bash
   # Ensure VM is stopped
   prlctl stop ArchBase-Template

   # Revert to the clean snapshot
   prlctl snapshot-switch ArchBase-Template --id "EncryptedBase-GRUB"

   # Pack as template
   prlctl pack ArchBase-Template --output ~/ArchBase-LUKS-GRUB.pvmp
   ```

### Template Contents

The template provides:
- Clean Arch Linux ARM (aarch64)
- LUKS2 full-disk encryption
- GRUB bootloader configured for LUKS
- btrfs filesystem
- Minimal packages (wget, sudo)
- Ready for Omarchy installation

### Template Credentials

| Item | Value |
|------|-------|
| LUKS passphrase | `4815162342` |
| Root password | `481516` |

**Always change the LUKS passphrase after importing!**

---

## Appendix B: prlctl Quick Reference

Common Parallels CLI commands:

### VM Lifecycle

```bash
# Start VM
prlctl start stargazer

# Stop VM (graceful)
prlctl stop stargazer

# Stop VM (force)
prlctl stop stargazer --kill

# Suspend VM
prlctl suspend stargazer

# Resume VM
prlctl resume stargazer
```

### VM Information

```bash
# List all VMs
prlctl list -a

# Show VM details
prlctl list -i stargazer

# Check VM status
prlctl list | grep stargazer
```

### Configuration

```bash
# Set CPU cores
prlctl set stargazer --cpus 4

# Set memory (MB)
prlctl set stargazer --memsize 8192

# Enable Rosetta
prlctl set stargazer --rosetta-linux on

# Enable shared folders
prlctl set stargazer --shf-host on
```

### Snapshots

```bash
# List snapshots
prlctl snapshot-list stargazer

# Create snapshot
prlctl snapshot stargazer -n "snapshot-name" -d "description"

# Revert to snapshot
prlctl snapshot-switch stargazer --id "{snapshot-uuid}"

# Delete snapshot
prlctl snapshot-delete stargazer --id "{snapshot-uuid}"
```

### Remote Execution

```bash
# Run command in VM (as root)
prlctl exec stargazer "hostname"

# Run command as specific user
prlctl exec stargazer --user andreym "whoami"

# Take screenshot
prlctl capture stargazer --file /tmp/screenshot.png
```

### Cloning

```bash
# Clone VM
prlctl clone stargazer --name new-vm-name

# Clone from specific snapshot
prlctl snapshot-switch stargazer --id "{snapshot-uuid}"
prlctl clone stargazer --name new-vm-name
```

---

## References

- [Parallels CLI Reference](https://download.parallels.com/desktop/v19/docs/en_US/Parallels%20Desktop%20Pro%20Edition%20Command-Line%20Reference.pdf)
- [Omarchy (armarchy for ARM64)](https://github.com/basecamp/omarchy)
- [Microsoft Intune for Linux](https://learn.microsoft.com/en-us/mem/intune/user-help/microsoft-intune-app-linux)
- [Arch Linux ARM](https://archlinuxarm.org/)
