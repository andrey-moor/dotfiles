# Rocinante: Intune + YubiKey Setup (Experimental)

Running Microsoft Intune Portal with YubiKey smart card authentication on Arch Linux ARM (aarch64) in Parallels with Rosetta x86_64 emulation.

## Current Status (December 2025)

| Component | Version | Source | Notes |
|-----------|---------|--------|-------|
| intune-portal | 1.2503.10-noble | nixpkgs | Pre-November regression version |
| microsoft-identity-broker | **2.0.4** | Nix package | Pure Nix - downloads from Microsoft .deb |
| openssl (broker) | 3.3.2 | Arch archives | Included in LD_LIBRARY_PATH by wrapper |
| openssl (intune-portal) | 3.0.18 | bundled | Safe - predates X509 bug |

**Architecture:** All components are now managed by Nix. No AUR packages required.

### OpenSSL Architecture (Critical Understanding)

**The Nix intune-portal does NOT need LD_PRELOAD for OpenSSL:**
- nixpkgs intune-portal bundles OpenSSL 3.0.18 in its RUNPATH
- OpenSSL 3.0.18 predates the X509_REQ_set_version bug (introduced in 3.4.0+)
- Verified via: `readelf -d /nix/store/.../intune-portal | grep openssl-3.0.18`

**The Nix broker wrapper provides OpenSSL 3.3.2 via LD_LIBRARY_PATH:**
- The Microsoft broker binary links system OpenSSL dynamically
- System OpenSSL 3.6.0 has the X509 bug
- The Nix wrapper (`microsoft-identity-broker-rosetta`) includes OpenSSL 3.3.2 in LD_LIBRARY_PATH
- This fixes the Code:1200 "credential is invalid" error

**Why LD_PRELOAD in intune-portal causes crashes:**
- Adding LD_PRELOAD to intune-portal overwrites its bundled 3.0.18
- Some dependencies (like ngtcp2 for HTTP/3) require OPENSSL_3.5.0 symbols
- OpenSSL 3.3.2 lacks these symbols → SIGSEGV crash on ngtcp2 init
- Solution: Don't use LD_PRELOAD in intune-portal, only in broker wrapper

### Identity Broker Setup (Nix-Managed)

The identity broker is now fully managed by Nix via `modules/home/linux/intune.nix`:

**User Broker:**
- Binary: `${brokerPkg}/bin/microsoft-identity-broker` (from Nix package)
- Wrapper: `microsoft-identity-broker-rosetta` (in PATH after home-manager switch)
- D-Bus activation: `~/.local/share/dbus-1/services/com.microsoft.identity.broker1.service`
- Automatically configured with Mesa software rendering and OpenSSL 3.3.2

**Device Broker (requires manual systemd override):**
- Binary: `${brokerPkg}/bin/microsoft-identity-device-broker` (from Nix package)
- Wrapper: `microsoft-identity-device-broker-rosetta` (in PATH)
- **Create systemd override to use Nix wrapper:**
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

**What the Nix wrappers provide:**
- Mesa software rendering (llvmpipe) for WebKitGTK embedded browser
- OpenSSL 3.3.2 via LD_LIBRARY_PATH (fixes Code:1200)
- All required x86_64 libraries for Rosetta emulation
- GIO TLS backend for HTTPS

### Clean Test: Full State Reset Procedure

If getting Code:1200 "credential is invalid" errors, follow this complete reset procedure:

```bash
# 1. Stop all broker processes
pkill -f microsoft-identity-broker
sudo systemctl stop microsoft-identity-device-broker.service

# 2. Clear ALL user-level state
rm -rf ~/.Microsoft
rm -rf ~/.cache/intune-portal
rm -rf ~/.config/intune
rm -rf ~/.local/share/intune-portal
rm -rf ~/.local/state/intune
rm -rf ~/.config/microsoft-identity-broker
rm -rf ~/.local/state/microsoft-identity-broker
rm -rf ~/.local/state/log/microsoft-identity-broker

# 3. Clear device-level state (requires sudo)
sudo rm -rf /var/lib/microsoft-identity-device-broker
sudo rm -rf /var/lib/microsoft-identity-broker

# 4. Restart device broker with clean state
sudo systemctl daemon-reload
sudo systemctl restart microsoft-identity-device-broker.service

# 5. Verify status
intune-status

# 6. Launch intune-portal
intune-portal-rosetta
```

**Key diagnostic checks:**
```bash
# Check OpenSSL version intune-portal uses (should show 3.0.18)
readelf -d $(which intune-portal) | grep openssl

# Check broker status and D-Bus service
intune-status

# Check broker logs
sudo journalctl -u microsoft-identity-device-broker.service -n 50
```

**Key References:**
- [recolic/microsoft-intune-archlinux](https://github.com/recolic/microsoft-intune-archlinux) - Arch Linux fixes and workarounds
- [Issue #285](https://github.com/microsoft/linux-package-repositories/issues/285) - November 2025 regression (closed)
- [Issue #254](https://github.com/microsoft/linux-package-repositories/issues/254) - OpenSSL 3.4.0+ bug report

## Current Test Setup (Dec 29, 2025)

**Verified working:**
- Rosetta binfmt: ✓ enabled (restart `systemd-binfmt` after reboot if needed)
- os-release: ✓ Ubuntu 22.04 (required)
- User broker: ✓ 2.0.4 via Nix package + D-Bus activation
- Device broker: ✓ 2.0.4 via Nix package + systemd override
- YubiKey: ✓ detected via Parallels smart card sharing
- pcscd: ✓ socket at `/run/pcscd/pcscd.comm` + symlink
- gnome-keyring: ✓ running (password-protected keyring required)
- openssl: ✓ nixpkgs intune-portal links 3.0.18 (safe version)
- Microsoft Edge: ✓ YubiKey FIDO2/Passkey works (PIN prompt appears)

**Note:** Direct Edge access to `portal.manage.microsoft.com` may return "Access Denied" if org policy requires device enrollment through Intune Portal first.

**Nix packages (intune.nix):**
- intune-portal, intune-portal-rosetta wrapper
- microsoft-identity-broker (2.0.4 from Microsoft .deb)
- microsoft-identity-broker-rosetta, microsoft-identity-device-broker-rosetta wrappers
- gnome-keyring, seahorse, libsecret
- yubikey-manager (ykman), pcsc-tools
- x86_64: mesa, glib-networking, opensc, pcsclite, openssl 3.3.2 (Arch)

**Helper commands:**
- `intune-status` - Show status of all components
- `intune-logs` - Tail all Intune-related logs

**To test:**
```bash
# Check status
intune-status

# Run intune
intune-portal-rosetta
```

**If issues, check:**
- `intune-logs --all` for combined log output
- `journalctl --user -u microsoft-identity-broker.service`
- `sudo journalctl -u microsoft-identity-device-broker.service`

## Overview

| Component | Challenge | Solution |
|-----------|-----------|----------|
| intune-portal | x86_64-only package | Rosetta emulation via binfmt_misc |
| WebKitGTK GUI | EGL errors (no GPU) | x86_64 Mesa with llvmpipe software rendering |
| Network/TLS | GIO TLS backend missing | x86_64 glib-networking |
| OpenSSL 3.4.0+ | X509 bug causes auth failures | nixpkgs intune-portal links 3.0.18; broker uses 3.3.2 |
| YubiKey CCID | USB passthrough issues | Parallels "Share smart card readers" |
| PIV certificates | Browser can't find certs | OpenSC + NSS PKCS#11 module |
| Identity Broker | Needs x86_64 libs + OpenSSL fix | Nix package with Rosetta wrapper |
| Device Broker | System service needs Nix wrapper | Manual systemd override to Nix wrapper |
| Broker WebKit UI | EGL_BAD_PARAMETER under Rosetta | Wrapper includes Mesa software rendering |

## 1. Rosetta x86_64 Emulation

### Nix Configuration (Declarative)

`modules/home/linux/rosetta.nix` - Sets `extra-platforms = x86_64-linux` in nix.conf.

### Manual Setup (One-time, requires root)

```bash
# Register Rosetta with binfmt_misc
sudo tee /etc/binfmt.d/rosetta.conf > /dev/null << 'EOF'
:rosetta:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x3e\x00:\xff\xff\xff\xff\xff\xfe\xfe\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/media/psf/RosettaLinux/rosetta:PFC
EOF

sudo systemctl restart systemd-binfmt
sudo systemctl enable systemd-binfmt
```

**After reboot:** If `systemd-binfmt` fails, it's because `/media/psf/RosettaLinux` wasn't mounted yet at boot. Fix with:
```bash
sudo systemctl restart systemd-binfmt
```

```bash
# Add to system nix config (Determinate Nix)
echo "extra-platforms = x86_64-linux" | sudo tee -a /etc/nix/nix.custom.conf
sudo systemctl restart nix-daemon
```

## 2. Intune Portal

### Nix Configuration (Declarative)

`modules/home/linux/intune.nix` provides:
- `intune-portal` - Direct binary (won't work on aarch64 due to EGL errors)
- `intune-portal-rosetta` - Wrapper with x86_64 Mesa software rendering

### Wrapper Environment Variables

```bash
# x86_64 library paths (set FIRST in LD_LIBRARY_PATH)
LD_LIBRARY_PATH="${X86_GLVND}:${X86_WAYLAND}:${X86_MESA}/lib:..."

# Mesa EGL vendor
__EGL_VENDOR_LIBRARY_DIRS="${X86_MESA}/share/glvnd/egl_vendor.d"

# Force software rendering
LIBGL_ALWAYS_SOFTWARE=1
GALLIUM_DRIVER=llvmpipe
LIBGL_DRIVERS_PATH="${X86_MESA}/lib/dri"
MESA_LOADER_DRIVER_OVERRIDE=llvmpipe

# Graphics backend
GDK_BACKEND=x11
WEBKIT_DISABLE_COMPOSITING_MODE=1
WEBKIT_DISABLE_DMABUF_RENDERER=1

# TLS support
GIO_MODULE_DIR="${X86_GIO}"
SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt"
```

## 3. YubiKey Smart Card Support

### Parallels Configuration

In VM settings: **Hardware** > **USB & Bluetooth**:
- Enable: **"Share smart card readers with Linux"**

This shares the Mac's smart card reader with Linux instead of USB passthrough (which has CCID issues).

### System Packages (pacman)

```bash
sudo pacman -S pcsclite ccid opensc libfido2 pcsc-tools
```

### Services

```bash
sudo systemctl enable pcscd.socket
sudo systemctl start pcscd.socket
```

### udev Rules

```bash
sudo tee /etc/udev/rules.d/69-yubikey.rules > /dev/null << 'EOF'
# YubiKey udev rules
SUBSYSTEM=="usb", ATTR{idVendor}=="1050", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1050", MODE="0666"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Polkit Rules (PC/SC access)

```bash
sudo tee /etc/polkit-1/rules.d/99-pcscd.rules > /dev/null << 'EOF'
polkit.addRule(function(action, subject) {
    if (action.id == "org.debian.pcsc-lite.access_pcsc" ||
        action.id == "org.debian.pcsc-lite.access_card") {
        return polkit.Result.YES;
    }
});
EOF
```

### NSS PKCS#11 Module (for Chromium/Edge)

```bash
# Add OpenSC module to NSS database
modutil -dbdir sql:$HOME/.pki/nssdb -add 'OpenSC' \
  -libfile /usr/lib/pkcs11/opensc-pkcs11.so -force
```

## 4. Verification Commands

```bash
# Check Rosetta binfmt
cat /proc/sys/fs/binfmt_misc/rosetta

# List YubiKeys
ykman list

# Check smart card reader
pcsc_scan -r

# Check PIV certificates
ykman piv info
pkcs11-tool --list-slots
pkcs11-tool --list-objects

# Check NSS modules (for Edge)
modutil -dbdir sql:$HOME/.pki/nssdb -list
```

## 5. Usage

```bash
# Launch Intune Portal with working graphics
intune-portal-rosetta

# Alternative: Use Edge directly
microsoft-edge https://portal.manage.microsoft.com
```

## 6. x86_64 Smart Card Support (Critical)

The x86_64 intune-portal binary can only load x86_64 PKCS#11 modules. ARM64 opensc-pkcs11.so won't work.

### The Problem

x86_64 pcsclite library has a different socket path compiled in than the ARM64 pcscd daemon uses:
- ARM64 pcscd socket: `/run/pcscd/pcscd.comm`
- x86_64 pcsclite looks for: `/run/pcscd/pcscd` (without `.comm`)

### The Solution

Two steps are needed:

1. **Create a socket symlink** (x86_64 pcsclite ignores `PCSCLITE_CSOCK_NAME` env var in Nix build):

```bash
# Create tmpfiles.d rule for persistent symlink
sudo tee /etc/tmpfiles.d/pcscd-symlink.conf << 'EOF'
L /run/pcscd/pcscd - - - - /run/pcscd/pcscd.comm
EOF

# Apply immediately
sudo systemd-tmpfiles --create /etc/tmpfiles.d/pcscd-symlink.conf
```

2. **Disable polkit for pcscd** (polkit blocks Rosetta-emulated processes):

```bash
# Create systemd override
sudo mkdir -p /etc/systemd/system/pcscd.service.d
sudo tee /etc/systemd/system/pcscd.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/pcscd --foreground --auto-exit --disable-polkit
EOF

sudo systemctl daemon-reload
sudo systemctl restart pcscd.socket
```

### Complete Environment for Certificate Support

```bash
# x86_64 Nix store paths
X86_OPENSC="/nix/store/8ab57wrrv7ph4045c8cmg170w0p0l5hz-opensc-0.26.1"
X86_PCSCLITE="/nix/store/hsgy97sia1wzbm8xvf2w2bib37ya0v87-pcsclite-2.3.0-lib"
X86_LIBP11="/nix/store/kzfzg8hnqabl16r1pbnarr3z5y1kwm5p-libp11-0.4.13"

# Critical: Tell x86_64 pcsclite where the ARM64 pcscd socket is
export PCSCLITE_CSOCK_NAME="/run/pcscd/pcscd.comm"

# p11-kit module path for WebKitGTK
export P11_KIT_MODULE_PATH="${X86_OPENSC}/lib/pkcs11"

# x86_64 libraries
export LD_LIBRARY_PATH="${X86_OPENSC}/lib:${X86_PCSCLITE}/lib:${X86_LIBP11}/lib:${LD_LIBRARY_PATH}"
```

### Verification

```bash
# With PCSCLITE_CSOCK_NAME set, x86_64 opensc should find the YubiKey
PCSCLITE_CSOCK_NAME=/run/pcscd/pcscd.comm \
  /nix/store/8ab57wrrv7ph4045c8cmg170w0p0l5hz-opensc-0.26.1/bin/pkcs11-tool --list-slots

# List PIV certificates
PCSCLITE_CSOCK_NAME=/run/pcscd/pcscd.comm \
  /nix/store/8ab57wrrv7ph4045c8cmg170w0p0l5hz-opensc-0.26.1/bin/pkcs11-tool \
  --slot-index 0 --list-objects --type cert
```

## 7. Microsoft Identity Broker (Nix-Managed)

The identity broker is now managed by Nix. The package downloads the official Microsoft .deb
from `packages.microsoft.com` and extracts the native x86_64 binaries.

### Package Location

```
packages/microsoft-identity-broker/default.nix
```

### What's Included

- `microsoft-identity-broker` binary (x86_64 ELF)
- `microsoft-identity-device-broker` binary (x86_64 ELF)
- D-Bus service files (templates - wrappers override paths)
- Systemd service file

### Updating the Broker Version

1. Check for new versions at: `https://packages.microsoft.com/ubuntu/24.04/prod/pool/main/m/microsoft-identity-broker/`
2. Update `version` in `packages/microsoft-identity-broker/default.nix`
3. Get new hash: `nix-prefetch-url <new-url>`
4. Update `sha256` in the package
5. Rebuild: `home-manager switch --flake .#rocinante`

### Device Broker Override (One-Time Setup)

The device broker runs as a system service and needs a manual override to use the Nix wrapper:

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

## 8. OS Release Fix (Critical)

intune-portal requires Ubuntu os-release to function properly. On Arch Linux, the credential storage fails with "(Code:1200) The credential is invalid" errors.

### One-Time Fix

```bash
# Replace os-release with Ubuntu 22.04
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

Reference: https://github.com/recolic/microsoft-intune-archlinux

## 9. OpenSSL 3.4.0+ Bug Fix (Critical)

OpenSSL 3.4.0 introduced a breaking change ([PR #23965](https://github.com/openssl/openssl/pull/23965)) that causes:
- `X509_REQ_set_version:passed invalid argument` errors
- `BadCertificate` TLS errors
- Code:1200 "credential is invalid" authentication loops

### Safe OpenSSL Versions

| Version | Status |
|---------|--------|
| 3.0.x (LTS) | ✓ Safe - `openssl_3` in nixpkgs (3.0.18) |
| 3.3.2 | ✓ Safe - used by fix-libssl.sh |
| 3.3.4 | ✓ Safe - last known good version |
| 3.4.0+ | ✗ BROKEN - introduced X509 regression |
| 3.6.0 | ✗ BROKEN - current nixpkgs default |

### Solution (LD_PRELOAD approach)

The `intune.nix` module uses OpenSSL 3.3.2 from Arch Linux archives with **LD_PRELOAD** (not LD_LIBRARY_PATH).
LD_PRELOAD forces libraries to load BEFORE all symbol resolution, bypassing conflicts where ngtcp2 tries to resolve OPENSSL_3.5.0 symbols.

```bash
# In intune-portal-rosetta wrapper:
export LD_PRELOAD="${OPENSSL_ARCH}/lib/libcrypto.so.3:${OPENSSL_ARCH}/lib/libssl.so.3:${LD_PRELOAD:-}"
```

This is based on the [recolic fix-libssl.sh](https://github.com/recolic/microsoft-intune-archlinux/blob/master/fix-libssl.sh) approach:

```bash
# Downloads and extracts openssl 3.3.2
curl -L https://archive.archlinux.org/packages/o/openssl/openssl-3.3.2-1-x86_64.pkg.tar.zst | tar --zstd -x -C /tmp/.ossl332
sudo cp /tmp/.ossl332/usr/lib/libcrypto.so.3 /usr/lib/libcrypto-332.so
sudo cp /tmp/.ossl332/usr/lib/libssl.so.3 /usr/lib/libssl-332.so

# Run with LD_PRELOAD
env LD_PRELOAD=/usr/lib/libcrypto-332.so:/usr/lib/libssl-332.so intune-portal
```

## 10. Build & Deploy Process

### Quick Rebuild on Rocinante

The dotfiles directory is mounted from macOS at `/media/psf/Home/Documents/dotfiles`.

```bash
# From rocinante - rebuild and apply
cd /media/psf/Home/Documents/dotfiles
nix run nixpkgs#home-manager -- switch --flake .#rocinante

# Or create a helper script
cat > ~/rebuild.sh << 'EOF'
#!/bin/bash
export PATH="/nix/var/nix/profiles/default/bin:$PATH"
cd /media/psf/Home/Documents/dotfiles
nix run nixpkgs#home-manager -- switch --flake ".#rocinante"
EOF
chmod +x ~/rebuild.sh
```

### From behemoth (macOS host)

```bash
# Build only (verify config compiles)
just hm-build rocinante

# Or build via prlctl
prlctl exec Rocinante /nix/var/nix/profiles/default/bin/nix build \
  '/media/psf/Home/Documents/dotfiles#homeConfigurations.rocinante.activationPackage'
```

### After applying, test intune

```bash
# Check status
intune-status

# Clear old state (if needed)
rm -rf ~/.Microsoft ~/.cache/intune-portal ~/.config/intune ~/.local/share/intune-portal

# Run with Rosetta wrapper
intune-portal-rosetta
```

## Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `X509_REQ_set_version:passed invalid argument` | OpenSSL 3.4.0+ bug | Use openssl_3 (3.0.18) via LD_LIBRARY_PATH |
| `BadCertificate` / Code:1200 | OpenSSL 3.4.0+ bug | Same as above |
| `Terms of use error` / Internal Server Error | Wrong os-release | Set /etc/os-release to Ubuntu (Section 8) |
| `errorCode 1001, WL: error in client communication` | NVIDIA Wayland issue | Set `WEBKIT_DISABLE_DMABUF_RENDERER=1` |
| White screen before login | gnome-keyring issue | Create password-protected keyring with seahorse |
| Blank window after email entry | WEBKIT_DISABLE_COMPOSITING_MODE=1 | Remove/comment out this env var from broker wrapper |
| Password window blank (broker) | Broker wrapper missing libglvnd or has wrong libs | Use clean minimal wrapper (see below) |
| `KeyNotFound, Crypto key not found` | Missing opensc | Install opensc and insert YubiKey |
| SIGSEGV on Edge startup | tpm2-tss version mismatch | Downgrade tpm2-tss to 3.2.0-1 |

### November 2025 Regression (Issue #285)

After November 2025 Microsoft repo update, some users experienced:
- OneAuth fails before login (before entering username)
- Code:1001 / Code:1200 errors
- `JsonSyntaxException: Expected BEGIN_OBJECT but was STRING`
- Segfault in intune-portal

**Affected versions:** intune-portal 1.2508.17, broker 2.0.1
**Workaround:** The nixpkgs version (1.2503.10-noble) predates this regression and may work better.

### Debugging Commands

```bash
# Check broker service logs
sudo journalctl -u microsoft-identity-device-broker.service
journalctl --user -u microsoft-identity-broker.service

# Check intune agent logs
journalctl | grep intune-agent

# General system logs
journalctl -xe | grep -i intune

# Verify library loading
LD_DEBUG=libs intune-portal-rosetta 2>&1 | grep -i openssl
```

### Comprehensive Log Check for Blank Window Issues

When the login window appears but is blank, use these commands to identify EGL/Mesa/WebKitWebProcess issues:

```bash
# 1. Check for WebKitWebProcess crashes (most common cause of blank window)
journalctl --user -n 100 --no-pager | grep -E "(WebKit|EGL|mesa|broker)"

# 2. Check for coredumps from WebKitWebProcess
coredumpctl list --no-pager | grep -i webkit

# 3. If coredump exists, view details
coredumpctl info $(coredumpctl list --no-pager | grep -i webkit | tail -1 | awk '{print $5}')

# 4. Check system journal for EGL errors
sudo journalctl -n 200 --no-pager | grep -iE "(EGL|libgl|mesa|dri|broker)"

# 5. Check broker D-Bus activation
journalctl --user -u dbus -n 50 --no-pager

# 6. Check device broker systemd service
sudo systemctl status microsoft-identity-device-broker.service
sudo journalctl -u microsoft-identity-device-broker.service -n 50 --no-pager

# 7. Verify Nix wrapper contents
cat $(which microsoft-identity-broker-rosetta)
```

**Key EGL/Mesa issues to look for:**
- `EGL_BAD_PARAMETER` - EGL vendor config not found or invalid
- `Could not create default EGL display` - Mesa software rendering not configured
- `WebKitWebProcess ... terminated abnormally with signal 6/ABRT` - WebKit crashed (usually EGL-related)

**Note:** The Nix wrappers (`microsoft-identity-broker-rosetta`) include all necessary Mesa configuration. If issues persist, rebuild with `home-manager switch --flake .#rocinante`.

## Known Limitations

1. **CCID via USB passthrough** - Direct USB passthrough of YubiKey CCID interface doesn't work reliably in Parallels (LIBUSB_ERROR_TIMEOUT). Use "Share smart card readers" instead.

2. **GPG smart card** - `gpg --card-status` may not work even when PIV works. OpenPGP and PIV use different interfaces.

3. **Software rendering** - intune-portal uses llvmpipe (CPU-based rendering), which is slower than GPU but works.

4. **x86_64/ARM64 pcsclite socket mismatch** - Requires socket symlink (`/run/pcscd/pcscd` → `pcscd.comm`) because Nix-built x86_64 pcsclite ignores `PCSCLITE_CSOCK_NAME` env var.

5. **Polkit blocks Rosetta processes** - pcscd's polkit integration doesn't recognize Rosetta-emulated x86_64 processes as authorized. Use `--disable-polkit` systemd override.

6. **os-release must be Ubuntu** - intune-portal checks os-release and fails with credential errors on non-Ubuntu systems (see section 8).

7. **WebKitGTK lacks WebAuthn/FIDO2 support** - The broker's embedded WebKitGTK browser cannot show passkey/FIDO2 prompts. Use password authentication for broker login. Edge browser does support FIDO2 for other Microsoft services.

8. **Device broker requires manual systemd override** - Since it's a system service, home-manager cannot configure it. See section 7 for override instructions.
