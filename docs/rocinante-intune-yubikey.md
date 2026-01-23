# Rocinante: Intune + YubiKey Setup

Microsoft Intune Portal with YubiKey PIV certificate authentication on Arch Linux ARM (aarch64) via Parallels Rosetta x86_64 emulation.

## Current Status (December 2025)

| Component | Version | Source | Notes |
|-----------|---------|--------|-------|
| intune-portal | 1.2511.7 | Custom Nix package | From Microsoft .deb |
| microsoft-identity-broker | 2.0.4 | Custom Nix package | From Microsoft .deb |
| OpenSSL (broker) | 3.3.2 | Arch archives | LD_LIBRARY_PATH (fixes Code:1200) |
| OpenSC | 0.25.1 | Arch archives | Compatible with OpenSSL 3.3.2 |
| pcsclite | x86_64 | nixpkgs | LD_LIBRARY_PATH for socket communication |

**Working:**
- Device enrollment via Intune Portal
- Microsoft SSO via identity broker
- YubiKey PIV certificate authentication
- Microsoft Edge with YubiKey (FIDO2 + PIV)

**All components managed by Nix** - no AUR packages required.

## Architecture Overview

```
+------------------+     D-Bus      +----------------------+
|  intune-portal   | ------------> |  user broker (SSO)   |
|  (Nix + wrapper) |               |  (Nix + wrapper)     |
+------------------+               +----------------------+
        |                                    |
        | D-Bus                              | D-Bus
        v                                    v
+------------------+               +----------------------+
|  device broker   |               |    gnome-keyring     |
|  (Nix, system)   |               |    (credentials)     |
+------------------+               +----------------------+
```

**Key Components:**
- `intune-portal-rosetta` - Main enrollment GUI wrapper
- `intune-agent-rosetta` - Compliance reporting agent (runs via systemd timer)
- `microsoft-identity-broker-rosetta` - User SSO authentication wrapper
- `microsoft-identity-device-broker-rosetta` - Device attestation wrapper (system service)
- `intune-status` - Status checker for all components
- `intune-logs` - Combined log viewer
- `intune-pkcs11-diag` - PKCS#11/YubiKey diagnostic
- `intune-nss-setup` - NSS module setup for Edge/Chrome

## Manual Prerequisites

### 1. Fake Ubuntu os-release (Required)

intune-portal requires Ubuntu os-release. On Arch, authentication fails with Code:1200.

```bash
sudo tee /etc/os-release << 'EOF'
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

### 2. Rosetta binfmt (Required)

```bash
# Create binfmt config
sudo tee /etc/binfmt.d/rosetta.conf > /dev/null << 'EOF'
:rosetta:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x3e\x00:\xff\xff\xff\xff\xff\xfe\xfe\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/media/psf/RosettaLinux/rosetta:PFC
EOF

sudo systemctl restart systemd-binfmt
sudo systemctl enable systemd-binfmt

# Add to Nix config
echo "extra-platforms = x86_64-linux" | sudo tee -a /etc/nix/nix.custom.conf
sudo systemctl restart nix-daemon
```

**After reboot:** If `systemd-binfmt` fails (Rosetta not mounted yet), run:
```bash
sudo systemctl restart systemd-binfmt
```

### 3. pcscd Socket Symlink (Required for YubiKey)

x86_64 pcsclite looks for `/run/pcscd/pcscd`, but ARM64 pcscd creates `/run/pcscd/pcscd.comm`:

```bash
# Create persistent symlink
sudo tee /etc/tmpfiles.d/pcscd-symlink.conf << 'EOF'
L /run/pcscd/pcscd - - - - /run/pcscd/pcscd.comm
EOF

sudo systemd-tmpfiles --create /etc/tmpfiles.d/pcscd-symlink.conf
```

### 4. pcscd Polkit Override (Required for YubiKey)

Polkit blocks Rosetta-emulated processes. Disable it for pcscd:

```bash
sudo mkdir -p /etc/systemd/system/pcscd.service.d
sudo tee /etc/systemd/system/pcscd.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/pcscd --foreground --auto-exit --disable-polkit
EOF

sudo systemctl daemon-reload
sudo systemctl restart pcscd.socket
```

### 5. Device Broker Systemd Override (Required)

The device broker runs as a system service and needs the Nix wrapper:

```bash
sudo mkdir -p /etc/systemd/system/microsoft-identity-device-broker.service.d
sudo tee /etc/systemd/system/microsoft-identity-device-broker.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=/home/andreym/.nix-profile/bin/microsoft-identity-device-broker-rosetta
EOF

sudo systemctl daemon-reload
sudo systemctl restart microsoft-identity-device-broker.service
```

### 6. Parallels YubiKey Sharing

In VM settings: **Hardware** > **USB & Bluetooth**:
- Enable: **"Share smart card readers with Linux"**

This shares the Mac's smart card reader instead of USB passthrough (CCID via USB has issues).

## Quick Start

After prerequisites are configured:

```bash
# Check all components
intune-status

# Launch Intune Portal
intune-portal-rosetta

# View logs if needed
intune-logs
```

## YubiKey Certificate Setup

### Verify YubiKey Detection

```bash
# List YubiKeys
ykman list

# Check smart card reader
pcsc_scan -r

# Check PIV certificates
ykman piv info

# Run PKCS#11 diagnostic
intune-pkcs11-diag
```

### NSS Setup for Edge (One-Time)

For Microsoft Edge to use YubiKey certificates:

```bash
intune-nss-setup
```

Or manually:
```bash
mkdir -p ~/.pki/nssdb
certutil -d sql:~/.pki/nssdb -N --empty-password
modutil -dbdir sql:~/.pki/nssdb -add 'OpenSC-x86' \
  -libfile ~/.nix-profile/lib/pkcs11/opensc-pkcs11.so -force
```

### p11-kit Module (Configured by Nix)

The Nix module creates `~/.config/pkcs11/modules/opensc-x86.module` pointing to Arch OpenSC 0.25.1.

## Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Code:1200 "credential is invalid" | OpenSSL 3.4.0+ bug or wrong os-release | Verify os-release is Ubuntu; broker wrapper includes OpenSSL 3.3.2 |
| Code:1001 "error in client communication" | Network/TLS issue | Check GIO TLS backend in wrapper |
| No YubiKey certificates in picker | OpenSC not loading | Run `intune-pkcs11-diag`; verify symlink and polkit override |
| Blank broker login window | WebKitGTK EGL issue | Wrapper includes Mesa software rendering; rebuild with home-manager |
| Terms of use / Internal Server Error | Wrong os-release | Set /etc/os-release to Ubuntu |
| "Enforce a secure password" compliance failure | PAM file not readable | `sudo chmod 644 /etc/pam.d/common-password` then run `intune-agent-rosetta` |
| Compliance "still checking" forever | intune-agent timer not running | `systemctl --user enable --now intune-agent.timer` |

### State Reset Procedure

If getting persistent authentication errors:

```bash
# Stop brokers
pkill -f microsoft-identity-broker
sudo systemctl stop microsoft-identity-device-broker.service

# Clear user state
rm -rf ~/.Microsoft
rm -rf ~/.cache/intune-portal
rm -rf ~/.config/intune
rm -rf ~/.local/share/intune-portal
rm -rf ~/.local/state/intune
rm -rf ~/.config/microsoft-identity-broker
rm -rf ~/.local/state/microsoft-identity-broker

# Clear device state
sudo rm -rf /var/lib/microsoft-identity-device-broker
sudo rm -rf /var/lib/microsoft-identity-broker

# Restart
sudo systemctl daemon-reload
sudo systemctl restart microsoft-identity-device-broker.service

# Verify and launch
intune-status
intune-portal-rosetta
```

### Diagnostic Commands

```bash
# Status check
intune-status

# Combined logs
intune-logs

# Device broker logs
sudo journalctl -u microsoft-identity-device-broker.service -n 50

# User broker logs
journalctl --user | grep -i broker

# PKCS#11 diagnostic
intune-pkcs11-diag

# Library loading debug
LD_DEBUG=libs intune-portal-rosetta 2>&1 | head -100
```

## Technical Details

### OpenSSL Architecture

**The Problem:** OpenSSL 3.4.0+ has an X509_REQ_set_version bug causing Code:1200 errors.

**The Solution:**
- Broker wrapper includes Arch OpenSSL 3.3.2 in `LD_LIBRARY_PATH`
- intune-portal uses its bundled OpenSSL 3.0.x (safe version)
- `curlNoHttp3` avoids ngtcp2's OPENSSL_3.5.0 symbol requirements

### OpenSC Architecture

**The Problem:** Nix OpenSC 0.26.1 requires OPENSSL_3.4.0 symbols, incompatible with Arch OpenSSL 3.3.2.

**The Solution:**
- Arch OpenSC 0.25.1 from archives (built before OpenSSL 3.4.0)
- Compatible with Arch OpenSSL 3.3.2
- Both in `LD_LIBRARY_PATH` for x86_64 processes

### Wrapper Environment

The Nix wrappers provide:
- Mesa llvmpipe software rendering (no GPU under Rosetta)
- OpenSSL 3.3.2 + OpenSC 0.25.1 via LD_LIBRARY_PATH
- x86_64 pcsclite for socket communication
- GIO TLS backend for HTTPS
- WebKitGTK with `WEBKIT_DISABLE_DMABUF_RENDERER=1`

## Known Limitations

1. **Software rendering** - intune-portal uses CPU-based llvmpipe (no GPU under Rosetta)
2. **WebKitGTK lacks WebAuthn** - Broker can't use FIDO2/passkeys; use password auth for broker, FIDO2 works in Edge
3. **USB CCID unreliable** - Use "Share smart card readers" in Parallels instead of USB passthrough
4. **Device broker needs manual override** - System service can't be configured by home-manager

## References

- [recolic/microsoft-intune-archlinux](https://github.com/recolic/microsoft-intune-archlinux) - Arch Linux workarounds
- [OpenSSL Issue #254](https://github.com/microsoft/linux-package-repositories/issues/254) - OpenSSL 3.4.0+ bug
- [Microsoft Broker 2.0 Docs](docs/intune-broker2.0.md) - Internal broker documentation
- [Encrypted Install Guide](docs/rocinante-encrypted-install.md) - LUKS setup for Intune compliance
