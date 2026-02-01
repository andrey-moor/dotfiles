# Stargazer Setup

Encrypted Arch Linux ARM VM in Parallels with LUKS for Microsoft Intune compliance.

## Base Template

The base VM template is stored as `ArchBase-Template.pvm.tar.zst`:

```bash
# Extract
cd ~/Parallels
zstd -d ArchBase-Template.pvm.tar.zst -c | tar -xvf -

# Register with Parallels
prlctl register ~/Parallels/ArchBase-Template.pvm

# Clone for new VM
prlctl clone ArchBase-Template --name "stargazer"
prlctl start stargazer
```

Default credentials:
- Encryption password: `4815162342`
- Root password: `481516`

Template contents:
- Clean Arch Linux ARM (aarch64)
- LUKS full-disk encryption
- btrfs filesystem
- wget & sudo installed
- Ready for omarchy install

## Intune Setup

After cloning the base template:

### 1. Install Nix (Determinate)

```bash
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install --no-confirm
```

Fix permissions (Determinate creates with 600):
```bash
sudo chmod 644 /etc/systemd/system/nix-daemon.service /etc/systemd/system/nix-daemon.socket /etc/systemd/system/determinate-nixd.socket
```

### 2. Enable x86_64 Platform

```bash
echo "extra-platforms = x86_64-linux" | sudo tee -a /etc/nix/nix.custom.conf
sudo chmod 644 /etc/nix/nix.conf
sudo systemctl restart nix-daemon
```

### 3. Rosetta binfmt

```bash
echo ':rosetta:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x3e\x00:\xff\xff\xff\xff\xff\xfe\xfe\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/mnt/psf/RosettaLinux/rosetta:PFC' | sudo tee /etc/binfmt.d/rosetta.conf
sudo systemctl restart systemd-binfmt
```

Create path unit to trigger binfmt when Rosetta mount appears (Parallels mounts are created by prltoolsd, not systemd, so mount dependencies don't work):
```bash
cat << 'EOF' | sudo tee /etc/systemd/system/rosetta-binfmt.path
[Unit]
Description=Watch for Rosetta binary to appear

[Path]
PathExists=/mnt/psf/RosettaLinux/rosetta
Unit=rosetta-binfmt.service

[Install]
WantedBy=multi-user.target
EOF

cat << 'EOF' | sudo tee /etc/systemd/system/rosetta-binfmt.service
[Unit]
Description=Register Rosetta binfmt after mount

[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl restart systemd-binfmt
RemainAfterExit=yes
EOF

sudo systemctl daemon-reload
sudo systemctl enable rosetta-binfmt.path
```

### 4. x86_64 Dynamic Linker

```bash
GLIBC_PATH=$(nix build --no-link --print-out-paths nixpkgs#pkgsCross.gnu64.glibc)
sudo mkdir -p /lib64
sudo chmod 755 /lib64
sudo ln -sf "$GLIBC_PATH/lib/ld-linux-x86-64.so.2" /lib64/
```

### 5. Apply Home-Manager

```bash
cd /mnt/psf/Home/Documents/dotfiles
nix run home-manager -- switch --flake .#stargazer -b backup
```

### 6. Fake Ubuntu os-release

```bash
sudo cp /usr/lib/os-release /usr/lib/os-release.arch.bak
sudo tee /usr/lib/os-release << 'EOF'
NAME="Ubuntu"
VERSION="22.04.3 LTS (Jammy Jellyfish)"
ID=ubuntu
ID_LIKE=debian
PRETTY_NAME="Ubuntu 22.04.3 LTS"
VERSION_ID="22.04"
VERSION_CODENAME=jammy
UBUNTU_CODENAME=jammy
EOF
```

### 7. Device Broker D-Bus + Systemd

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

### 8. pcscd for YubiKey

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

**Parallels**: Enable **Hardware > USB & Bluetooth > Share smart card readers with Linux**

### 9. Keyring Default

Set login keyring as default (auto-unlocked at login):
```bash
echo -n login > ~/.local/share/keyrings/default
```

### 10. Intune Compliance (PAM Password Policy)

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

**Ensure your password meets**: 12+ chars, 1 uppercase, 1 lowercase, 1 number, 1 symbol.

### 11. Enable Intune Agent Timer

The intune-agent periodically reports compliance status to Microsoft:
```bash
systemctl --user enable --now intune-agent.timer
```

To trigger an immediate compliance report:
```bash
intune-agent-rosetta
```

### 12. Apply Chezmoi Configuration

Home-manager installs packages and declarative configs. Chezmoi manages mutable user configs (neovim, nushell, etc.):

```bash
chezmoi apply
```

## Verify

```bash
intune-status                    # Check all components
systemctl --user list-timers     # Verify intune-agent.timer is active
pcsc_scan -r                     # Should show YubiKey reader
intune-portal-rosetta            # Launch portal
```

To check compliance reporting:
```bash
intune-agent-rosetta             # Trigger manual compliance report
journalctl --user -u intune-agent --since "5 minutes ago"
```

## Troubleshooting

**Rosetta binfmt not registered** (check with `cat /proc/sys/fs/binfmt_misc/rosetta`):
```bash
sudo systemctl restart systemd-binfmt
sudo systemctl restart microsoft-identity-device-broker
```

The `rosetta-binfmt.path` unit should handle this automatically by watching for the Rosetta binary to appear after boot.

**Device broker fails to start with D-Bus error**:
```bash
# Reload D-Bus config without restarting
sudo pkill -HUP dbus-daemon
sudo systemctl restart microsoft-identity-device-broker
```

**Device broker not running** (intune-portal crashes or shows auth errors):
```bash
sudo systemctl restart microsoft-identity-device-broker
systemctl status microsoft-identity-device-broker
```

**Permission errors after running commands via prlctl exec**:
Commands run via `prlctl exec` run as root, creating files owned by root in user directories. Fix with:
```bash
sudo chown -R $USER:$USER ~/.config ~/.local
```
