# Rocinante

x86_64 Omarchy (Arch Linux) workstation managed with standalone home-manager.

- **Access:** Tailscale SSH (`ssh rocinante` from any tailnet machine)
- **Disk:** LUKS2-encrypted NVMe + btrfs

## Initial Setup

### 1. Tailscale

```bash
sudo systemctl enable --now tailscaled
sudo tailscale up --ssh
```

Requires an SSH ACL rule in the [Tailnet admin panel](https://login.tailscale.com/admin/acls).

### 2. Clone Dotfiles

```bash
git clone https://github.com/andrey-moor/dotfiles.git ~/dotfiles
```

### 3. Install Nix

```bash
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install --no-confirm
. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
```

### 4. Apply Home-Manager

```bash
cd ~/dotfiles
nix run home-manager -- switch --flake .#rocinante -b backup
```

### 5. Chezmoi (mutable configs)

```bash
chezmoi apply
```

## Intune Enrollment

Reference: https://github.com/recolic/microsoft-intune-archlinux

### 6. AUR Packages

```bash
yay -S intune-portal-bin microsoft-identity-broker-bin pcsclite ccid yubico-piv-tool
```

### 7. System Setup (one-time)

The `intune-setup` script (installed by home-manager) configures all system-level
requirements: os-release spoofing, device broker override, pcscd, and p11-kit.

```bash
intune-setup
```

This runs the following with sudo:
- Spoofs `/etc/os-release` and `/usr/lib/os-release` as Ubuntu 22.04
- Installs device broker systemd override (adds `LD_LIBRARY_PATH` for OpenSSL 3.3.2)
- Installs pcscd override (removes sandboxing for USB/YubiKey access)
- Registers YubiKey PKCS#11 module with p11-kit

### 8. Remove lsb_release

```bash
sudo mv /usr/bin/lsb_release /usr/bin/lsb_release.bak 2>/dev/null || true
```

### 9. Keyring

GNOME keyring must have a password-protected "login" collection (passwordless
keyrings silently fail due to a known gnome-keyring bug):

```bash
mkdir -p ~/.local/share/keyrings
echo -n login > ~/.local/share/keyrings/default
seahorse  # Create "login" keyring with a password via GUI
```

### 10. Verify Smart Card

```bash
yubico-piv-tool -a status
p11tool --list-tokens  # Should show "YubiKey PIV #..."
```

### 11. Enroll

```bash
intune-portal
```

## Compliance

### PAM Password Policy

Intune checks `/etc/pam.d/common-password`. This file is for compliance
reporting only (Arch uses `system-auth` natively):

```bash
sudo tee /etc/pam.d/common-password << 'EOF'
password    requisite     pam_pwquality.so retry=3 dcredit=-1 ocredit=-1 ucredit=-1 lcredit=-1 minlen=12
password    required      pam_unix.so sha512 shadow try_first_pass use_authtok
EOF
sudo chmod 644 /etc/pam.d/common-password
```

## Day-to-Day

```bash
# Update config
cd ~/dotfiles && git pull
nix run home-manager -- switch --flake .#rocinante -b backup

# Intune portal (enrollment/re-auth)
intune-portal

# Status and logs
intune-status
intune-logs --broker
intune-logs --device
intune-logs --agent
```

## Architecture

Nix (home-manager) manages:
- OpenSSL 3.3.2 override (`LD_LIBRARY_PATH` wrappers for all Intune binaries)
- User broker D-Bus service (auto-activated)
- Intune-agent systemd timer (hourly compliance reporting)
- Helper scripts (`intune-setup`, `intune-status`, `intune-logs`)

AUR packages provide:
- Binaries (`intune-portal`, `intune-agent`, `microsoft-identity-broker`, `microsoft-identity-device-broker`)
- System D-Bus policies and systemd services

System-level configs (installed by `intune-setup`):
- `/etc/os-release` — Ubuntu 22.04 spoof
- Device broker systemd override — `LD_LIBRARY_PATH` + `HOME`
- pcscd override — removes sandboxing for YubiKey USB access
- p11-kit module — YubiKey PKCS#11

## Troubleshooting

```bash
# Intune services
intune-logs --device
intune-logs --broker

# Smart card / YubiKey
systemctl status pcscd
yubico-piv-tool -a status
p11tool --list-tokens

# Re-run system setup after home-manager switch
intune-setup
```

Note: Run `intune-setup` again after `home-manager switch` if the OpenSSL nix
store path changes (the device broker override embeds the path).
