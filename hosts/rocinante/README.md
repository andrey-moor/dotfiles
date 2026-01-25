# Rocinante

x86_64 Omarchy (Arch Linux) workstation with LUKS2-encrypted NVMe + btrfs.

**Access:** `ssh rocinante` (Tailscale SSH)

## Intune Enrollment

Reference: https://github.com/recolic/microsoft-intune-archlinux

### 1. Install AUR Packages (Level 1 & 2)

```bash
yay -S microsoft-identity-broker-bin microsoft-edge-stable-bin intune-portal-bin
```

### 2. Fake Ubuntu os-release

```bash
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

### 3. PAM Password Policy

```bash
sudo tee /etc/pam.d/common-password << 'EOF'
password    requisite     pam_pwquality.so retry=3 dcredit=-1 ocredit=-1 ucredit=-1 lcredit=-1 minlen=12
password    required      pam_unix.so sha512 shadow try_first_pass use_authtok
EOF
sudo chmod 644 /etc/pam.d/common-password
```

Ensure password meets: 12+ chars, 1 uppercase, 1 lowercase, 1 number, 1 symbol.

### 4. Keyring Setup

```bash
# Install seahorse, create "login" keyring with password via GUI
sudo pacman -S seahorse
seahorse

# Set as default
echo -n login > ~/.local/share/keyrings/default
```

### 5. Fix OpenSSL (BadCertificate bug)

```bash
# Run recolic's fix script
curl -sL https://raw.githubusercontent.com/recolic/microsoft-intune-archlinux/master/fix-libssl.sh | bash
```

This installs OpenSSL 3.3.2 libs to `/usr/lib/libcrypto-332.so` and `/usr/lib/libssl-332.so`.

### 6. YubiKey / Smart Card Setup

```bash
# Install packages
sudo pacman -S pcsc-tools ccid libfido2

# Add user to pcscd group
sudo usermod -aG pcscd $USER

# Enable pcscd
sudo systemctl enable --now pcscd.socket

# Reload udev
sudo udevadm control --reload-rules
sudo udevadm trigger

# Log out and back in for group change
```

### 7. p11-kit Module for OpenSC

```bash
sudo mkdir -p /etc/pkcs11/modules
sudo chmod 755 /etc/pkcs11 /etc/pkcs11/modules
sudo tee /etc/pkcs11/modules/opensc.module << 'EOF'
module: /usr/lib/pkcs11/opensc-pkcs11.so
critical: no
EOF
sudo chmod 644 /etc/pkcs11/modules/opensc.module
```

Verify: `p11-kit list-modules | grep -A5 opensc`

### 8. WebKitGTK Fix

```bash
# Required for D-Bus spawned WebKitGTK processes
echo 'WEBKIT_DISABLE_DMABUF_RENDERER=1' | sudo tee -a /etc/environment
```

Log out and back in after this change.

### 9. Enable Intune Agent Timer

```bash
systemctl --user enable --now intune-agent.timer
```

### 10. Enroll

```bash
env LD_PRELOAD=/usr/lib/libcrypto-332.so:/usr/lib/libssl-332.so intune-portal
```

## Verify

```bash
# Smart card
pcsc_scan -r
p11-kit list-modules | grep opensc

# Intune agent
systemctl --user status intune-agent.timer
```

## Troubleshooting

### Clear intune-portal data

```bash
rm -rf ~/.Microsoft ~/.cache/intune-portal ~/.config/intune ~/.local/share/intune-portal
```

### WebKitGTK crashes

Known issue with WebKitGTK 2.50+ on Wayland/AMD. Do NOT set `GDK_BACKEND=x11` or `LIBGL_ALWAYS_SOFTWARE=1` globally - breaks Hyprland.

### Logs

```bash
journalctl --user -xe | grep -i intune
sudo journalctl -u microsoft-identity-device-broker
```
