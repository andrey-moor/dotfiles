# Rocinante Setup

x86_64 Omarchy (Arch Linux) workstation with standalone home-manager.

## Initial Setup

### 1. Install Nix

```bash
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install --no-confirm
. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
```

### 2. Clone and Apply

```bash
git clone <repo-url> ~/dotfiles
cd ~/dotfiles
nix run home-manager -- switch --flake .#rocinante -b backup
```

### 3. Chezmoi (mutable configs)

```bash
chezmoi apply
```

## Intune Enrollment

### 4. Device Broker

The device broker is a system-level D-Bus service. Copy the config and service
files from the Nix profile, then override ExecStart to use our wrapper:

```bash
sudo cp ~/.nix-profile/share/dbus-1/system.d/com.microsoft.identity.devicebroker1.conf /usr/share/dbus-1/system.d/
sudo chmod 644 /usr/share/dbus-1/system.d/com.microsoft.identity.devicebroker1.conf

sudo cp ~/.nix-profile/lib/systemd/system/microsoft-identity-device-broker.service /etc/systemd/system/
WRAPPER=$(readlink -f ~/.nix-profile/bin/microsoft-identity-device-broker-wrapped)
sudo mkdir -p /etc/systemd/system/microsoft-identity-device-broker.service.d
printf "[Service]\nExecStart=\nExecStart=$WRAPPER\n\n[Install]\nWantedBy=multi-user.target\n" | \
  sudo tee /etc/systemd/system/microsoft-identity-device-broker.service.d/nix.conf

sudo systemctl daemon-reload
sudo systemctl enable --now microsoft-identity-device-broker
```

### 5. Keyring

GNOME keyring must have a password-protected "login" keyring set as default
(passwordless keyrings silently fail due to a known gnome-keyring bug):

```bash
mkdir -p ~/.local/share/keyrings
echo -n login > ~/.local/share/keyrings/default
# Set keyring password (use seahorse GUI, or login via PAM to auto-create)
seahorse
```

### 6. Remove lsb_release (if present)

```bash
sudo mv /usr/bin/lsb_release /usr/bin/lsb_release.bak 2>/dev/null || true
```

### 7. Enroll

```bash
intune-portal-wrapped
```

os-release spoofing is handled automatically via bubblewrap (no system-wide modification needed).

## Compliance

### PAM Password Policy

This creates a compliance-reporting file that intune-agent checks.
Note: Arch uses `/etc/pam.d/system-auth`, not `common-password` —
this file is for Intune compliance only (we spoof Ubuntu via bwrap).

```bash
sudo tee /etc/pam.d/common-password << 'EOF'
password    requisite     pam_pwquality.so retry=3 dcredit=-1 ocredit=-1 ucredit=-1 lcredit=-1 minlen=12
password    required      pam_unix.so sha512 shadow try_first_pass use_authtok
EOF
sudo chmod 644 /etc/pam.d/common-password
```

### Agent Timer

```bash
systemctl --user enable --now intune-agent.timer
```

## Verify

```bash
intune-status
```

## Troubleshooting

Reference: https://github.com/recolic/microsoft-intune-archlinux

```bash
intune-logs              # tail broker + device logs
intune-logs --device     # device broker only
sudo journalctl -u microsoft-identity-device-broker -f
```
