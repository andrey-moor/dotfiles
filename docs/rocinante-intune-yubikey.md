# Rocinante: Intune + YubiKey Setup (Experimental)

Running Microsoft Intune Portal with YubiKey smart card authentication on Arch Linux ARM (aarch64) in Parallels with Rosetta x86_64 emulation.

## Current Status (December 2025)

| Component | nixpkgs Version | AUR/recolic Version | Notes |
|-----------|----------------|---------------------|-------|
| intune-portal | 1.2503.10-noble | 1.2511.7-1 | nixpkgs version used (pre-November regression) |
| microsoft-identity-broker | N/A | **2.0.3** (native) | Use recolic's native broker, NOT Java broker |
| openssl_3 | 3.0.18 | 3.3.2 | Both safe; nixpkgs intune-portal already links 3.0.18 |
| openssl (default) | 3.6.0 | 3.6.x | BROKEN - causes X509 errors |

### OpenSSL Architecture (Critical Understanding)

**The Nix intune-portal does NOT need LD_PRELOAD for OpenSSL:**
- nixpkgs intune-portal bundles OpenSSL 3.0.18 in its RUNPATH
- OpenSSL 3.0.18 predates the X509_REQ_set_version bug (introduced in 3.4.0+)
- Verified via: `readelf -d /nix/store/.../intune-portal | grep openssl-3.0.18`

**The AUR microsoft-identity-broker DOES need LD_PRELOAD:**
- The AUR native broker binary links system OpenSSL dynamically
- Arch Linux ships OpenSSL 3.6.0 which HAS the bug
- The broker wrapper (`/usr/bin/microsoft-identity-broker-wrapper`) must have LD_PRELOAD
- This is why the broker gets OpenSSL 3.3.2 via LD_PRELOAD in our wrapper

**Why LD_PRELOAD in intune-portal causes crashes:**
- Adding LD_PRELOAD to intune-portal overwrites its bundled 3.0.18
- Some dependencies (like ngtcp2 for HTTP/3) require OPENSSL_3.5.0 symbols
- OpenSSL 3.3.2 lacks these symbols → SIGSEGV crash on ngtcp2 init
- Solution: Don't use LD_PRELOAD in intune-portal, only in broker wrapper

### Critical: Identity Broker Setup

**Use the native brokers (2.0.3) from recolic, NOT the Java brokers (1.7.0):**

The native 2.0.3 broker dropped Java dependency and includes BOTH user and device broker.
The old Java device broker (1.7.0) is incompatible - it lacks D-Bus methods the native user broker expects,
causing "org.freedesktop.dbus.errors.UnknownMethod" errors.

**User Broker (native 2.0.3):**
- Binary: `/usr/bin/microsoft-identity-broker-2.0.3` + wrapper
- D-Bus activation: `/usr/share/dbus-1/services/com.microsoft.identity.broker1.service`
- **Mask the Java user service** to prevent conflicts:
  ```bash
  systemctl --user mask microsoft-identity-broker.service
  ```

**Device Broker (CRITICAL - must also be native 2.0.3):**
- Binary: `/usr/bin/microsoft-identity-device-broker-2.0.3` + wrapper
- The systemd service at `/usr/lib/systemd/system/microsoft-identity-device-broker.service` points to old Java broker
- **Create override to use native device broker:**
  ```bash
  sudo mkdir -p /etc/systemd/system/microsoft-identity-device-broker.service.d
  sudo tee /etc/systemd/system/microsoft-identity-device-broker.service.d/override.conf << 'EOF'
  [Service]
  Environment=
  ExecStart=
  ExecStart=/usr/bin/microsoft-identity-device-broker-wrapper
  WorkingDirectory=
  EOF
  sudo systemctl daemon-reload
  sudo systemctl restart microsoft-identity-device-broker.service
  ```

**Broker Wrapper Mesa Fix (CRITICAL for Rosetta):**

The broker opens an embedded WebKitGTK browser for login. Under Rosetta, this fails with
`Could not create default EGL display: EGL_BAD_PARAMETER` unless Mesa software rendering is configured.

**Patch the user broker wrapper** (add before `exec` line in `/usr/bin/microsoft-identity-broker-wrapper`):
```bash
# Mesa software rendering for WebKitGTK embedded browser
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export GDK_BACKEND=x11
# NOTE: Do NOT set WEBKIT_DISABLE_COMPOSITING_MODE=1 - causes blank login window!
export WEBKIT_DISABLE_DMABUF_RENDERER=1
# EGL vendor config (required for WebKitGTK WebProcess)
export __EGL_VENDOR_LIBRARY_DIRS="/nix/store/...-mesa-.../share/glvnd/egl_vendor.d"
export LIBGL_DRIVERS_PATH="/nix/store/...-mesa-.../lib/dri"
export MESA_LOADER_DRIVER_OVERRIDE=llvmpipe
```

Find Mesa path and apply with:
```bash
MESA_PATH=$(dirname $(dirname $(find /nix/store -name "libgbm.so.1" -path "*mesa*" 2>/dev/null | head -1)))
sudo sed -i '/^exec /i # Mesa software rendering for WebKitGTK embedded browser\nexport LIBGL_ALWAYS_SOFTWARE=1\nexport GALLIUM_DRIVER=llvmpipe\nexport GDK_BACKEND=x11\nexport WEBKIT_DISABLE_DMABUF_RENDERER=1\nexport __EGL_VENDOR_LIBRARY_DIRS="'"$MESA_PATH"'/share/glvnd/egl_vendor.d"\nexport LIBGL_DRIVERS_PATH="'"$MESA_PATH"'/lib/dri"\nexport MESA_LOADER_DRIVER_OVERRIDE=llvmpipe\n' /usr/bin/microsoft-identity-broker-wrapper
```

**Note:** The `intune.nix` module includes an activation script that applies this patch automatically.

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

# 4. Verify broker wrapper has LD_PRELOAD for OpenSSL 3.3.2
grep "LD_PRELOAD" /usr/bin/microsoft-identity-broker-wrapper
# Should show: export LD_PRELOAD="/nix/store/.../openssl-arch-3.3.2/lib/libcrypto.so.3:..."

# 5. Restart device broker with clean state
sudo systemctl daemon-reload
sudo systemctl restart microsoft-identity-device-broker.service

# 6. Verify broker is running through wrapper (check for LD_PRELOAD in env)
BROKER_PID=$(pgrep -f microsoft-identity-broker-2.0.3 | head -1)
if [ -n "$BROKER_PID" ]; then
  cat /proc/$BROKER_PID/environ | tr '\0' '\n' | grep LD_PRELOAD
fi

# 7. Launch intune-portal (use minimal wrapper without LD_LIBRARY_PATH overrides)
~/.local/bin/intune-portal-minimal
# Or the Nix wrapper:
intune-portal-rosetta
```

**Key diagnostic checks:**
```bash
# Check OpenSSL version intune-portal uses (should show 3.0.18)
readelf -d $(which intune-portal) | grep openssl

# Check broker has OpenSSL 3.3.2 loaded
cat /proc/$(pgrep -f microsoft-identity-broker-2.0.3)/environ | tr '\0' '\n' | grep LD_PRELOAD

# Check broker logs
sudo journalctl -u microsoft-identity-device-broker.service -n 50
```

**Key References:**
- [recolic/microsoft-intune-archlinux](https://github.com/recolic/microsoft-intune-archlinux) - Arch Linux fixes and workarounds
- [Issue #285](https://github.com/microsoft/linux-package-repositories/issues/285) - November 2025 regression (closed)
- [Issue #254](https://github.com/microsoft/linux-package-repositories/issues/254) - OpenSSL 3.4.0+ bug report

## Current Test Setup (Dec 26, 2025)

**Verified working:**
- Rosetta binfmt: ✓ enabled (restart `systemd-binfmt` after reboot if needed)
- os-release: ✓ Ubuntu 22.04 (required)
- User broker: ✓ native 2.0.3 via D-Bus activation (Java service masked)
- Device broker: ✓ native 2.0.3 via systemd override (replaces Java 1.7.0)
- YubiKey: ✓ detected via Parallels smart card sharing
- pcscd: ✓ socket at `/run/pcscd/pcscd.comm` + symlink
- gnome-keyring: ✓ running (password-protected keyring required)
- openssl: ✓ nixpkgs intune-portal links 3.0.18 (safe version)
- Microsoft Edge: ✓ YubiKey FIDO2/Passkey works (PIN prompt appears)

**Note:** Direct Edge access to `portal.manage.microsoft.com` may return "Access Denied" if org policy requires device enrollment through Intune Portal first.

**Nix packages (intune.nix):**
- intune-portal, intune-portal-rosetta wrapper
- gnome-keyring, seahorse, libsecret
- yubikey-manager (ykman), pcsc-tools
- x86_64: mesa, glib-networking, opensc, pcsclite, openssl_3

**Debug script:** `~/intune-debug.sh` captures all logs

**To test:**
```bash
# Terminal 1: Start log capture
~/intune-debug.sh

# Terminal 2: Run intune
intune-portal-rosetta 2>&1 | tee /tmp/intune-logs-*/intune-portal.log
```

**If issues, check:**
- `/tmp/intune-logs-*/` for all captured logs
- `journalctl --user -u microsoft-identity-broker.service`
- `sudo journalctl -u microsoft-identity-device-broker.service`

## Overview

| Component | Challenge | Solution |
|-----------|-----------|----------|
| intune-portal | x86_64-only package | Rosetta emulation via binfmt_misc |
| WebKitGTK GUI | EGL errors (no GPU) | x86_64 Mesa with llvmpipe software rendering |
| Network/TLS | GIO TLS backend missing | x86_64 glib-networking |
| OpenSSL 3.4.0+ | X509 bug causes auth failures | nixpkgs intune-portal already links 3.0.18 |
| YubiKey CCID | USB passthrough issues | Parallels "Share smart card readers" |
| PIV certificates | Browser can't find certs | OpenSC + NSS PKCS#11 module |
| Identity Broker | Java user broker conflicts with native | Use native 2.0.3, mask Java systemd service |
| Device Broker | Systemd service points to old Java 1.7.0 | Create systemd override to use native 2.0.3 |
| Broker WebKit UI | EGL_BAD_PARAMETER under Rosetta | Patch broker wrapper with Mesa software rendering |

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

## 7. Microsoft Identity Broker (Manual Setup)

The identity broker requires manual configuration for x86_64 Java under Rosetta.

### Install AUR Packages

```bash
yay -S microsoft-identity-broker jdk11-openjdk-amd64
```

### Create Device Broker User

```bash
sudo useradd -r -s /usr/bin/nologin -d /var/lib/microsoft-identity-broker microsoft-identity-broker
```

### D-Bus Policy (Device Broker)

```bash
sudo tee /usr/share/dbus-1/system.d/com.microsoft.identity.devicebroker1.conf << 'EOF'
<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <policy user="microsoft-identity-broker">
    <allow own="com.microsoft.identity.devicebroker1"/>
    <allow send_destination="com.microsoft.identity.devicebroker1"/>
  </policy>
  <policy context="default">
    <allow send_destination="com.microsoft.identity.devicebroker1"/>
  </policy>
</busconfig>
EOF
sudo chmod 644 /usr/share/dbus-1/system.d/com.microsoft.identity.devicebroker1.conf
sudo systemctl reload dbus
```

### Configure Device Broker Service (System)

Edit `/usr/lib/systemd/system/microsoft-identity-device-broker.service`:

```ini
Environment="JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64"
Environment="JAVA_OPTS=-Xint -XX:+UseSerialGC -Xmx256m"
Environment="LD_LIBRARY_PATH=/nix/store/.../alsa-lib/lib:/nix/store/.../gtk+3/lib:..."
```

Key: Add x86_64 Nix store library paths for GTK, glib, Mesa, alsa-lib, X11 libs.

### Configure Identity Broker Service (User)

Edit `/usr/lib/systemd/user/microsoft-identity-broker.service`:

```ini
Environment="JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64"
Environment="JAVA_OPTS=-Xint -XX:+UseSerialGC -Xmx512m"
Environment="LD_LIBRARY_PATH=..."  # Same x86_64 libs as device broker
Environment="GDK_PIXBUF_MODULE_FILE=/nix/store/.../gdk-pixbuf/.../loaders.cache"
Environment="LIBGL_ALWAYS_SOFTWARE=1"
Environment="GALLIUM_DRIVER=llvmpipe"
Environment="GDK_BACKEND=x11"
```

### Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl start microsoft-identity-device-broker
systemctl --user daemon-reload
systemctl --user start microsoft-identity-broker
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

### From behemoth (macOS host)

```bash
# Dry-run build to verify config (no actual build)
just rocinante-build

# Apply on rocinante via prlctl (requires VM running)
just rocinante-switch
```

### From rocinante (in VM)

```bash
# Pull latest dotfiles
cd ~/dotfiles && git pull

# Apply home-manager configuration
home-manager switch --flake .#rocinante

# Or if home-manager not in PATH
nix run home-manager -- switch --flake .#rocinante
```

### After applying, test intune

```bash
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

# 7. Verify broker wrapper has correct Mesa paths
cat /usr/bin/microsoft-identity-broker-wrapper | grep -E "(EGL|MESA|LIBGL)"

# 8. Check that EGL vendor config exists
ls -la $(grep __EGL_VENDOR_LIBRARY_DIRS /usr/bin/microsoft-identity-broker-wrapper | cut -d'"' -f2)

# 9. Verify Mesa EGL vendor JSON is valid
cat $(grep __EGL_VENDOR_LIBRARY_DIRS /usr/bin/microsoft-identity-broker-wrapper | cut -d'"' -f2)/50_mesa.json
```

**Key EGL/Mesa issues to look for:**
- `EGL_BAD_PARAMETER` - EGL vendor config not found or invalid
- `Could not create default EGL display` - Mesa software rendering not configured
- `WebKitWebProcess ... terminated abnormally with signal 6/ABRT` - WebKit crashed (usually EGL-related)
- Empty `__EGL_VENDOR_LIBRARY_DIRS` - Points to mesa-libgbm instead of full mesa (no 50_mesa.json)

**Fix for EGL vendor path:**
The broker wrapper must point to a full mesa package (not mesa-libgbm) that has `share/glvnd/egl_vendor.d/50_mesa.json`:
```bash
# Find correct mesa path (must have egl_vendor.d with 50_mesa.json)
find /nix/store -path "*mesa*/share/glvnd/egl_vendor.d/50_mesa.json" 2>/dev/null | head -1

# Update broker wrapper with correct path
MESA_PATH=$(dirname $(dirname $(dirname $(find /nix/store -path "*mesa*/share/glvnd/egl_vendor.d/50_mesa.json" 2>/dev/null | head -1))))
sudo sed -i "s|__EGL_VENDOR_LIBRARY_DIRS=.*|__EGL_VENDOR_LIBRARY_DIRS=\"${MESA_PATH}/share/glvnd/egl_vendor.d\"|" /usr/bin/microsoft-identity-broker-wrapper
sudo sed -i "s|LIBGL_DRIVERS_PATH=.*|LIBGL_DRIVERS_PATH=\"${MESA_PATH}/lib/dri\"|" /usr/bin/microsoft-identity-broker-wrapper
```

## Known Limitations

1. **CCID via USB passthrough** - Direct USB passthrough of YubiKey CCID interface doesn't work reliably in Parallels (LIBUSB_ERROR_TIMEOUT). Use "Share smart card readers" instead.

2. **GPG smart card** - `gpg --card-status` may not work even when PIV works. OpenPGP and PIV use different interfaces.

3. **Software rendering** - intune-portal uses llvmpipe (CPU-based rendering), which is slower than GPU but works.

4. **x86_64/ARM64 pcsclite socket mismatch** - Requires socket symlink (`/run/pcscd/pcscd` → `pcscd.comm`) because Nix-built x86_64 pcsclite ignores `PCSCLITE_CSOCK_NAME` env var.

5. **Polkit blocks Rosetta processes** - pcscd's polkit integration doesn't recognize Rosetta-emulated x86_64 processes as authorized. Use `--disable-polkit` systemd override.

6. **JVM under Rosetta** - Requires `-Xint -XX:+UseSerialGC` to avoid JIT/GC crashes.

7. **os-release must be Ubuntu** - intune-portal checks os-release and fails with credential errors on non-Ubuntu systems (see section 8).

8. **WebKitGTK lacks WebAuthn/FIDO2 support** - The broker's embedded WebKitGTK browser cannot show passkey/FIDO2 prompts. Use password authentication for broker login. Edge browser does support FIDO2 for other Microsoft services.
