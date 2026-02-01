# Pitfalls: Omarchy Linux VM Setup with Intune

This document catalogs known pitfalls from real experience setting up Omarchy Linux (Arch ARM) VMs on Parallels with Microsoft Intune enrollment. Each pitfall includes warning signs, prevention strategies, and the phase that should address it.

---

## 1. Parallels VM Setup for Linux ARM

### 1.1 Rosetta Not Enabled Before VM Creation

**Category:** VM Configuration
**Severity:** Blocking

**What Happens:**
x86_64 binaries (Intune, broker) fail to execute. Error: "exec format error" or build failures during Nix evaluation.

**Warning Signs:**
- `file /path/to/binary` shows "ELF 64-bit x86-64" but execution fails
- Nix build errors: "Cannot build... Required system: 'x86_64-linux'"

**Prevention Strategy:**
Enable Rosetta in VM settings BEFORE first boot:
- **Options > Advanced > "Use Rosetta to run x86-64 binaries"**

This cannot be enabled after VM creation without recreating the VM.

**Phase:** VM Creation (Phase 1)

---

### 1.2 Shared Folders Not Enabled

**Category:** VM Configuration
**Severity:** Blocking

**What Happens:**
Dotfiles not accessible at `/mnt/psf/Home/Documents/dotfiles`. Rosetta binary not available at `/mnt/psf/RosettaLinux/rosetta`.

**Warning Signs:**
- `/mnt/psf` directory is empty or doesn't exist
- `ls /mnt/psf/RosettaLinux/` returns "No such file or directory"

**Prevention Strategy:**
Enable in VM settings before first boot:
- **Options > Sharing > "Share Mac folders with Linux"**

Verify after boot: `ls /mnt/psf/Home`

**Phase:** VM Creation (Phase 1)

---

### 1.3 Insufficient Resources

**Category:** VM Configuration
**Severity:** Quality of Life

**What Happens:**
Slow Nix builds, compilation failures, OOM kills during WebKitGTK evaluation.

**Warning Signs:**
- Build processes killed unexpectedly
- Swap thrashing
- Compilation takes hours

**Prevention Strategy:**
Minimum recommended resources:
- **CPU:** 4+ cores
- **RAM:** 8192MB (4096MB absolute minimum)
- **Disk:** 64GB (LUKS encryption adds overhead)

**Phase:** VM Creation (Phase 1)

---

## 2. LUKS Encryption with Boot Configuration

### 2.1 Limine Bootloader Cannot Handle Encrypt Hook

**Category:** Bootloader
**Severity:** Blocking - System Unbootable

**What Happens:**
Boot fails with no LUKS passphrase prompt. Kernel panic: "VFS: Unable to mount root fs on unknown-block(0,0)".

**Warning Signs:**
- Omarchy installs Limine by default
- No passphrase prompt at boot
- System hangs or panics immediately

**Prevention Strategy:**
Use GRUB instead of Limine:
```bash
pacman -S grub efibootmgr
# Configure mkinitcpio HOOKS with 'encrypt'
grub-install --target=arm64-efi --efi-directory=/boot --bootloader-id=GRUB
```

The `encrypt` hook MUST be in mkinitcpio.conf:
```
HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt filesystems fsck)
```

**Phase:** Base OS Install (Phase 2)

---

### 2.2 ARM Kernel Named 'Image' Not 'vmlinuz-linux'

**Category:** Bootloader
**Severity:** Blocking - Silent Boot Failure

**What Happens:**
grub-mkconfig doesn't find matching initramfs. System boots without initramfs, so `encrypt` hook never runs.

**Warning Signs:**
- `grub-mkconfig` output shows "Found linux image" but NOT "Found initrd image"
- Boot proceeds without passphrase prompt
- Kernel panic after a few seconds

**Prevention Strategy:**
After installing kernel, create symlink:
```bash
cp /boot/Image /boot/vmlinuz-linux
```

Then regenerate GRUB config:
```bash
grub-mkconfig -o /boot/grub/grub.cfg
```

Verify output shows BOTH:
- "Found linux image: /boot/vmlinuz-linux"
- "Found initrd image: /boot/initramfs-linux.img"

**Phase:** Base OS Install (Phase 2)

---

### 2.3 Wrong UUID in GRUB Config

**Category:** Bootloader
**Severity:** Blocking - System Unbootable

**What Happens:**
GRUB can't find encrypted partition. Drops to initramfs rescue shell.

**Warning Signs:**
- Boot drops to "rootfs" shell
- Message about missing device

**Prevention Strategy:**
Get correct UUID and verify:
```bash
blkid -s UUID -o value /dev/sda2
grep "cryptdevice" /etc/default/grub
```

UUID format: `cryptdevice=UUID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:cryptroot`

**Phase:** Base OS Install (Phase 2)

---

## 3. Rosetta binfmt Registration (Race Conditions)

### 3.1 binfmt Not Registered on Boot

**Category:** System Services
**Severity:** Major - Breaks All x86_64 Binaries

**What Happens:**
`systemd-binfmt` runs before Parallels mounts `/mnt/psf`. Rosetta interpreter path doesn't exist, so binfmt entry isn't created.

**Warning Signs:**
- x86_64 binaries fail after reboot but work after manual restart
- `cat /proc/sys/fs/binfmt_misc/rosetta` returns "No such file"
- `systemctl status systemd-binfmt` shows it ran successfully (but too early)

**Prevention Strategy:**
Create systemd path unit to watch for Rosetta mount:
```bash
# /etc/systemd/system/rosetta-binfmt.path
[Unit]
Description=Watch for Rosetta binary to appear

[Path]
PathExists=/mnt/psf/RosettaLinux/rosetta
Unit=rosetta-binfmt.service

[Install]
WantedBy=multi-user.target
```

```bash
# /etc/systemd/system/rosetta-binfmt.service
[Unit]
Description=Register Rosetta binfmt after mount

[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl restart systemd-binfmt
RemainAfterExit=yes
```

**Phase:** Rosetta Setup (Phase 3)

---

### 3.2 Mount Path Varies by Configuration

**Category:** System Services
**Severity:** Medium

**What Happens:**
Rosetta binary at different paths on different setups:
- `/mnt/psf/RosettaLinux/rosetta` (newer Parallels/Arch)
- `/media/psf/RosettaLinux/rosetta` (some configurations)

**Warning Signs:**
- binfmt config points to wrong path
- Works on one VM but not another

**Prevention Strategy:**
Check actual mount point:
```bash
ls /mnt/psf/RosettaLinux/ || ls /media/psf/RosettaLinux/
```

Use correct path in `/etc/binfmt.d/rosetta.conf`.

**Phase:** Rosetta Setup (Phase 3)

---

## 4. Intune Enrollment on Non-Ubuntu Linux

### 4.1 os-release Detection Failure

**Category:** Intune Compatibility
**Severity:** Blocking - Cannot Enroll

**What Happens:**
Intune portal or broker check `/etc/os-release` and reject non-Ubuntu systems. Error: "Terms of use" or "Internal Server Error" during login.

**Warning Signs:**
- Authentication popup shows generic Microsoft error
- Logs show distribution check failing
- Code:1200 errors in broker

**Prevention Strategy:**
Spoof Ubuntu os-release:
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

Backup original first: `cp /usr/lib/os-release /usr/lib/os-release.arch.bak`

**Phase:** Intune Prerequisites (Phase 5)

---

### 4.2 OpenSSL 3.4+ Breaks Identity Broker

**Category:** Library Compatibility
**Severity:** Blocking - Auth Fails

**What Happens:**
OpenSSL 3.4.0+ has X509_REQ_set_version bug causing "Code:1200 - credential is invalid" errors.

**Warning Signs:**
- Broker authentication fails with Code:1200
- Error occurs during device registration, not login
- Works on older distros but not Arch (which has newer OpenSSL)

**Prevention Strategy:**
Provide OpenSSL 3.3.2 via LD_LIBRARY_PATH in wrapper scripts. The Nix module fetches from Arch archives:
```nix
opensslArch = pkgs.stdenv.mkDerivation {
  pname = "openssl-arch";
  version = "3.3.2";
  src = pkgs.fetchurl {
    url = "https://archive.archlinux.org/packages/o/openssl/openssl-3.3.2-1-x86_64.pkg.tar.zst";
    # ...
  };
};
```

Wrapper sets: `export LD_LIBRARY_PATH="${opensslArch}/lib:..."`

**Phase:** Nix Module Development (Phase 6)

---

### 4.3 WebKitGTK Blank Window Without DMABUF Disable

**Category:** Graphics/Rendering
**Severity:** Major - UI Unusable

**What Happens:**
Intune portal and broker login windows appear blank or show rendering artifacts. EGL/DMA-BUF acceleration fails under Rosetta.

**Warning Signs:**
- Login popup is completely white/blank
- WebKit debug shows EGL errors
- Works on native x86_64 but not ARM via Rosetta

**Prevention Strategy:**
Set environment variable in wrapper:
```bash
export WEBKIT_DISABLE_DMABUF_RENDERER=1
```

Do NOT set `WEBKIT_DISABLE_COMPOSITING_MODE=1` - this causes blank windows!

Also set Mesa software rendering:
```bash
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export MESA_LOADER_DRIVER_OVERRIDE=llvmpipe
```

**Phase:** Nix Module Development (Phase 6)

---

### 4.4 PAM Password Policy Not Readable

**Category:** Compliance Check
**Severity:** Medium - Compliance Fails

**What Happens:**
Intune agent checks `/etc/pam.d/common-password` for password complexity. On Arch, this file doesn't exist or has wrong permissions.

**Warning Signs:**
- Compliance status shows "Enforce a secure password" failure
- intune-agent runs but device stays non-compliant

**Prevention Strategy:**
Create the file with correct permissions:
```bash
sudo tee /etc/pam.d/common-password << 'EOF'
password requisite pam_pwquality.so retry=3 dcredit=-1 ocredit=-1 ucredit=-1 lcredit=-1 minlen=12
password required pam_unix.so sha512 shadow try_first_pass use_authtok
EOF
sudo chmod 644 /etc/pam.d/common-password
```

User password must actually meet requirements (12+ chars, mixed case, digit, symbol).

**Phase:** Intune Prerequisites (Phase 5)

---

## 5. YubiKey/PKCS#11 Setup Under Rosetta

### 5.1 pcscd Polkit Blocks Rosetta Processes

**Category:** Smart Card Access
**Severity:** Blocking - No YubiKey Access

**What Happens:**
Polkit authorization fails for Rosetta-emulated processes trying to access pcscd. YubiKey detection fails.

**Warning Signs:**
- `pcsc_scan` works from native aarch64 but not x86_64
- Polkit authentication prompts appear and fail
- OpenSC tools can't see YubiKey

**Prevention Strategy:**
Disable polkit for pcscd:
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

**Phase:** YubiKey Setup (Phase 7)

---

### 5.2 x86_64 pcsclite Expects Different Socket Path

**Category:** Smart Card Access
**Severity:** Blocking - Socket Connection Fails

**What Happens:**
x86_64 pcsclite library looks for `/run/pcscd/pcscd` but ARM64 pcscd creates `/run/pcscd/pcscd.comm`.

**Warning Signs:**
- Native tools work, Rosetta tools fail
- Error: "Cannot connect to PC/SC daemon"
- Socket exists at .comm but tools look for no extension

**Prevention Strategy:**
Create symlink via tmpfiles.d:
```bash
echo 'L /run/pcscd/pcscd - - - - /run/pcscd/pcscd.comm' | sudo tee /etc/tmpfiles.d/pcscd-symlink.conf
sudo systemd-tmpfiles --create /etc/tmpfiles.d/pcscd-symlink.conf
```

**Phase:** YubiKey Setup (Phase 7)

---

### 5.3 OpenSC Version Mismatch with OpenSSL

**Category:** Library Compatibility
**Severity:** Blocking - PKCS#11 Fails

**What Happens:**
Nix OpenSC 0.26.1 requires OPENSSL_3.4.0 symbols, but we use Arch OpenSSL 3.3.2 for broker compatibility. Symbol not found errors.

**Warning Signs:**
- OpenSC fails to load with "symbol not found: OPENSSL_3.4.0"
- Works with system OpenSC but not Nix OpenSC

**Prevention Strategy:**
Use OpenSC 0.25.1 from Arch archives (built before OpenSSL 3.4.0):
```nix
openscArch = pkgs.stdenv.mkDerivation {
  pname = "opensc-arch";
  version = "0.25.1";
  src = pkgs.fetchurl {
    url = "https://archive.archlinux.org/packages/o/opensc/opensc-0.25.1-1-x86_64.pkg.tar.zst";
    # ...
  };
};
```

**Phase:** Nix Module Development (Phase 6)

---

### 5.4 USB CCID Passthrough Unreliable

**Category:** Hardware Access
**Severity:** Medium - Intermittent Failures

**What Happens:**
USB passthrough of YubiKey (CCID mode) is unreliable. Connection drops, device not recognized.

**Warning Signs:**
- YubiKey works sometimes, fails other times
- USB disconnect/reconnect events in dmesg
- CCID driver errors

**Prevention Strategy:**
Use Parallels smart card sharing instead of USB passthrough:
1. Enable in Parallels: **Hardware > USB & Bluetooth > "Share smart card readers with Linux"**
2. Add Parallels Proxy CCID to ccid driver config:
```bash
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

**Phase:** YubiKey Setup (Phase 7)

---

### 5.5 x86_64 Dynamic Linker Missing

**Category:** Rosetta Runtime
**Severity:** Blocking - x86_64 Binaries Fail

**What Happens:**
x86_64 binaries can't find `/lib64/ld-linux-x86-64.so.2` (standard x86_64 dynamic linker path).

**Warning Signs:**
- Error: "No such file or directory" when running x86_64 binary
- Rosetta registered but binaries still fail

**Prevention Strategy:**
Symlink glibc dynamic linker from Nix:
```bash
GLIBC_PATH=$(nix build --no-link --print-out-paths nixpkgs#pkgsCross.gnu64.glibc)
sudo mkdir -p /lib64
sudo chmod 755 /lib64
sudo ln -sf "$GLIBC_PATH/lib/ld-linux-x86-64.so.2" /lib64/
```

**Phase:** Rosetta Setup (Phase 3)

---

## 6. D-Bus Session Bus and Keyring Availability

### 6.1 prlctl exec Runs as Root

**Category:** Remote Execution
**Severity:** Major - Permission Chaos

**What Happens:**
Commands run via `prlctl exec` from macOS run as root. Files created in user directories get root ownership. Nix profile paths don't resolve correctly.

**Warning Signs:**
- Permission denied errors after running prlctl exec
- ~/.config files owned by root
- Nix commands fail with store permission errors

**Prevention Strategy:**
1. Use SSH instead of prlctl exec for user operations
2. If using prlctl exec, wrap with `su user -c '...'`:
   ```bash
   prlctl exec VM "su andreym -c '. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh && cd /mnt/psf/Home/Documents/dotfiles && nix run home-manager -- switch --flake .#endurance'"
   ```
3. After prlctl exec, fix permissions:
   ```bash
   sudo chown -R $USER:$USER ~/.config ~/.local
   ```

**Phase:** Documentation (all phases mention this)

---

### 6.2 Keyring Not Unlocked for Systemd Services

**Category:** Credential Storage
**Severity:** Medium - Auth Fails Silently

**What Happens:**
Intune agent (systemd timer) can't access gnome-keyring. Credential storage/retrieval fails.

**Warning Signs:**
- intune-agent runs but compliance never updates
- Broker can't read cached credentials
- Works interactively but not via timer

**Prevention Strategy:**
1. Set login keyring as default (unlocked at login):
   ```bash
   echo -n login > ~/.local/share/keyrings/default
   ```

2. Set environment in systemd service:
   ```ini
   [Service]
   Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=%t/bus
   Environment=GNOME_KEYRING_CONTROL=%t/keyring
   ```

3. Ensure service runs After graphical-session.target

**Phase:** Nix Module Development (Phase 6)

---

### 6.3 D-Bus Policy for Device Broker

**Category:** D-Bus Configuration
**Severity:** Blocking - Broker Can't Start

**What Happens:**
Device broker fails to register D-Bus name. Service crashes with "Connection refused" or similar.

**Warning Signs:**
- `systemctl status microsoft-identity-device-broker` shows D-Bus error
- intune-portal can't connect to broker
- Works after manual D-Bus reload

**Prevention Strategy:**
Install D-Bus policy to system location (NOT /etc, use /usr/share):
```bash
BROKER_PKG=$(find /nix/store -maxdepth 1 -name '*microsoft-identity-broker-*' -type d | head -1)
sudo cp "$BROKER_PKG/share/dbus-1/system.d/com.microsoft.identity.devicebroker1.conf" /usr/share/dbus-1/system.d/
sudo chmod 644 /usr/share/dbus-1/system.d/com.microsoft.identity.devicebroker1.conf
```

Reload D-Bus without restarting:
```bash
sudo pkill -HUP dbus-daemon
```

**Phase:** Intune Prerequisites (Phase 5)

---

### 6.4 Device Broker HOME Environment

**Category:** Service Configuration
**Severity:** Medium - Initialization Fails

**What Happens:**
Device broker (system service) can't initialize MSAL cache because HOME isn't set.

**Warning Signs:**
- Broker starts but auth fails
- Logs show MSAL initialization errors
- Works when run manually as root

**Prevention Strategy:**
Add environment to systemd override:
```ini
[Service]
ExecStart=
ExecStart=/path/to/microsoft-identity-device-broker-rosetta
Environment=HOME=/root
Environment=XDG_CONFIG_HOME=/root/.config
Environment=XDG_CACHE_HOME=/root/.cache
```

**Phase:** Intune Prerequisites (Phase 5)

---

## Summary: Critical Path Pitfalls

These pitfalls WILL block progress if not handled:

| Pitfall | Phase | Detection |
|---------|-------|-----------|
| Rosetta not enabled before VM creation | 1 | x86_64 binaries fail |
| Limine can't do encrypt hook | 2 | No passphrase prompt |
| ARM kernel named 'Image' | 2 | No initrd in grub.cfg |
| binfmt race with Parallels mount | 3 | Works after restart only |
| os-release not Ubuntu | 5 | Auth errors during login |
| OpenSSL 3.4+ breaks broker | 6 | Code:1200 errors |
| pcscd polkit blocks Rosetta | 7 | YubiKey not detected |
| pcscd socket path mismatch | 7 | "Cannot connect to PC/SC" |

---

*Document created from brownfield experience with stargazer and endurance VMs.*
*Last updated: 2026-01-31*
