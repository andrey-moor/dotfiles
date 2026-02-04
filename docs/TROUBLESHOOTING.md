# Troubleshooting Guide

> **Last updated:** 2026-02-03
> **Applies to:** Stargazer and similar Intune-enrolled Arch Linux ARM VMs on Parallels

Quick diagnosis: Run `intune-health` to identify most common issues automatically.

## Table of Contents

1. [Boot Issues](#boot-issues)
   - [No LUKS Passphrase Prompt](#no-luks-passphrase-prompt)
   - [Limine Boots Instead of GRUB](#limine-boots-instead-of-grub)
   - [Kernel Panic: Unable to Mount Root FS](#kernel-panic-unable-to-mount-root-fs)
   - [Wrong UUID in GRUB Config](#wrong-uuid-in-grub-config)
2. [VM Issues](#vm-issues)
   - [Clone Won't Start](#clone-wont-start)
   - [Shared Folders Not Visible](#shared-folders-not-visible)
   - [No Network After Reboot](#no-network-after-reboot)
3. [Rosetta and Nix Issues](#rosetta-and-nix-issues)
   - [Rosetta binfmt Not Registered](#rosetta-binfmt-not-registered)
   - [x86_64 Binaries Fail to Execute](#x86_64-binaries-fail-to-execute)
   - [Nix Build Fails for x86_64 Packages](#nix-build-fails-for-x86_64-packages)
4. [Intune Issues](#intune-issues)
   - [Device Broker Fails with D-Bus Error](#device-broker-fails-with-d-bus-error)
   - [Enrollment Fails with Keyring Error](#enrollment-fails-with-keyring-error)
   - [Portal Shows Blank Screen](#portal-shows-blank-screen)
   - [Authentication Fails](#authentication-fails)
5. [YubiKey Issues](#yubikey-issues)
   - [YubiKey Not Detected](#yubikey-not-detected)
   - [Certificate Not Shown in Picker](#certificate-not-shown-in-picker)
   - [PIN Rejected](#pin-rejected)

---

## Quick Diagnosis

Before diving into specific issues, run:

```bash
intune-health
```

This checks all critical components and provides hints for failures. Exit code 0 = all critical checks pass.

For more detail:

```bash
intune-health --verbose
intune-logs --all | tail -50
```

---

## Boot Issues

### No LUKS Passphrase Prompt

**What you see:**
- Boot hangs at "Loading initial ramdisk..."
- Or: Boots directly to login without asking for passphrase
- Or: Boots to Limine menu instead of GRUB

**Root cause:**
GRUB EFI binary was replaced by Limine during armarchy installation, or never installed correctly.

**Solution:**

1. Boot from archboot ISO in Parallels
2. Open the encrypted partition:
   ```bash
   cryptsetup open /dev/vda2 cryptroot
   ```
3. Mount filesystems:
   ```bash
   mount /dev/mapper/cryptroot /mnt
   mount /dev/vda1 /mnt/boot
   ```
4. Restore GRUB:
   ```bash
   cp /mnt/boot/EFI/GRUB/grubaa64.efi /mnt/boot/EFI/BOOT/BOOTAA64.EFI
   ```
5. Unmount and reboot:
   ```bash
   umount -R /mnt
   reboot
   ```

**Prevention:**
After running armarchy, ALWAYS run `sudo cp /boot/EFI/GRUB/grubaa64.efi /boot/EFI/BOOT/BOOTAA64.EFI` BEFORE rebooting.

**Related:** [Setup Step 5: Restore GRUB Bootloader](../hosts/stargazer/README.md#5-restore-grub-bootloader)

---

### Limine Boots Instead of GRUB

**What you see:**
- Black screen with "Limine" text
- Menu shows "Arch Linux" without LUKS support
- System boots without asking for disk passphrase

**Root cause:**
armarchy installs Limine bootloader to the fallback EFI path, overwriting GRUB.

**Solution:**
Same as [No LUKS Passphrase Prompt](#no-luks-passphrase-prompt) above.

**Prevention:**
Create a snapshot before running armarchy. If you forget the GRUB fix, restore the snapshot.

---

### Kernel Panic: Unable to Mount Root FS

**What you see:**
- "Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)"
- System halts completely

**Root cause:**
Either GRUB config has wrong UUID, or 'encrypt' hook missing from initramfs.

**Solution:**

1. Boot from archboot ISO
2. Check if you can decrypt manually:
   ```bash
   cryptsetup open /dev/vda2 cryptroot
   ls /dev/mapper/cryptroot  # Should exist
   ```
3. If decryption works, the issue is GRUB config. Mount and check:
   ```bash
   mount /dev/mapper/cryptroot /mnt
   mount /dev/vda1 /mnt/boot
   cat /mnt/boot/grub/grub.cfg | grep cryptdevice
   ```
4. UUID should match `blkid /dev/vda2`

**Prevention:**
During initial setup, verify UUIDs match before first reboot.

**Related:** [docs/arch-arm-encrypted-install.md](arch-arm-encrypted-install.md)

---

### Wrong UUID in GRUB Config

**What you see:**
- GRUB menu appears
- Selecting entry fails with cryptdevice errors

**Root cause:**
GRUB config was generated with incorrect partition UUID.

**Solution:**

1. At GRUB menu, press `e` to edit
2. Find the line with `cryptdevice=UUID=...`
3. Note the incorrect UUID
4. Boot from ISO and fix:
   ```bash
   # Get correct UUID
   blkid /dev/vda2

   # Mount and edit
   cryptsetup open /dev/vda2 cryptroot
   mount /dev/mapper/cryptroot /mnt
   mount /dev/vda1 /mnt/boot

   # Edit grub.cfg with correct UUID
   nano /mnt/boot/grub/grub.cfg
   ```

**Prevention:**
After grub-mkconfig, verify UUID matches with `blkid`.

---

## VM Issues

### Clone Won't Start

**What you see:**
- Parallels shows error starting VM
- "Unable to open disk image" or similar

**Root cause:**
Usually permissions issue or corrupted clone operation.

**Solution:**

1. Check VM exists:
   ```bash
   prlctl list -a
   ```
2. If listed but won't start, check configuration:
   ```bash
   prlctl list -i vmname
   ```
3. Try stopping and starting:
   ```bash
   prlctl stop vmname --kill
   prlctl start vmname
   ```
4. If persistent, delete and re-clone from template

**Prevention:**
Ensure source VM is stopped before cloning.

---

### Shared Folders Not Visible

**What you see:**
- `/mnt/psf` exists but is empty
- `ls /mnt/psf/dotfiles` returns "No such file or directory"

**Root cause:**
Parallels Tools hasn't mounted shared folders yet (happens async after boot).

**Solution:**

1. Wait 15-30 seconds after login:
   ```bash
   sleep 15 && ls /mnt/psf/
   ```
2. Check prltoolsd is running:
   ```bash
   systemctl status prltoolsd
   ```
3. If not running, start it:
   ```bash
   sudo systemctl start prltoolsd
   ```
4. Verify shared folders enabled in Parallels VM config

**Prevention:**
Scripts that need shared folders should include retry loops (see prerequisites.sh pattern).

---

### No Network After Reboot

**What you see:**
- `ping google.com` fails
- `ip addr` shows no IP on main interface

**Root cause:**
Network manager not configured or interface name changed.

**Solution:**

1. Check interface name:
   ```bash
   ip link
   ```
2. Start network:
   ```bash
   sudo systemctl start NetworkManager
   sudo nmcli device connect enp0s5
   ```
3. Enable for future boots:
   ```bash
   sudo systemctl enable NetworkManager
   ```

**Prevention:**
Omarchy should configure this automatically. If issues persist, check armarchy completed successfully.

---

## Rosetta and Nix Issues

### Rosetta binfmt Not Registered

**What you see:**
- `cat /proc/sys/fs/binfmt_misc/rosetta` shows "No such file"
- x86_64 binaries fail with "cannot execute binary file: Exec format error"

**Root cause:**
Rosetta binfmt registration didn't survive reboot, or was never set up.

**Solution:**

1. Check if Rosetta binary exists:
   ```bash
   ls /mnt/psf/RosettaLinux/rosetta
   ```
2. If missing, enable in Parallels: VM Config -> Options -> Rosetta Linux
3. Re-register binfmt:
   ```bash
   sudo systemctl restart systemd-binfmt
   ```
4. Verify:
   ```bash
   cat /proc/sys/fs/binfmt_misc/rosetta
   ```

**Prevention:**
The prerequisites.sh script sets up a systemd path unit to re-register on boot. If this keeps failing, check `/etc/systemd/system/rosetta-binfmt.path`.

**Related:** [Setup Step 6: Run Prerequisites Script](../hosts/stargazer/README.md#6-run-prerequisites-script)

---

### x86_64 Binaries Fail to Execute

**What you see:**
- Running x86_64 binary shows "Exec format error" or segfault
- `file binary` shows "ELF 64-bit LSB executable, x86-64"

**Root cause:**
Either Rosetta not registered, or dynamic linker missing.

**Solution:**

1. Check Rosetta binfmt:
   ```bash
   cat /proc/sys/fs/binfmt_misc/rosetta
   ```
2. Check dynamic linker symlink:
   ```bash
   ls -la /lib64/ld-linux-x86-64.so.2
   ```
3. If symlink missing, create it:
   ```bash
   sudo ln -sf /mnt/psf/RosettaLinux/rosetta /lib64/ld-linux-x86-64.so.2
   ```

**Prevention:**
Run prerequisites.sh which sets up both Rosetta and the dynamic linker symlink.

---

### Nix Build Fails for x86_64 Packages

**What you see:**
- `nix build` fails with "unsupported system: x86_64-linux"
- Home-manager switch fails on x86_64 packages

**Root cause:**
Nix extra-platforms not configured.

**Solution:**

1. Check nix.conf:
   ```bash
   cat /etc/nix/nix.conf | grep extra-platforms
   ```
2. Should show: `extra-platforms = x86_64-linux`
3. If missing, add it:
   ```bash
   echo "extra-platforms = x86_64-linux" | sudo tee -a /etc/nix/nix.conf
   sudo systemctl restart nix-daemon
   ```

**Prevention:**
The prerequisites.sh script configures this automatically.

---

## Intune Issues

### Device Broker Fails with D-Bus Error

**What you see:**
- `intune-health` shows device broker FAIL
- Error: "Failed to connect to bus"
- systemd shows broker in failed state

**Root cause:**
D-Bus policy for microsoft-identity-device-broker not installed or D-Bus not reloaded.

**Solution:**

1. Check policy file exists:
   ```bash
   ls /etc/dbus-1/system.d/com.microsoft.identity.devicebroker1.conf
   ```
2. Reload D-Bus:
   ```bash
   sudo systemctl reload dbus
   ```
3. Restart broker:
   ```bash
   sudo systemctl restart microsoft-identity-device-broker
   ```
4. Verify:
   ```bash
   systemctl status microsoft-identity-device-broker
   ```

**Prevention:**
Run `intune-prerequisites` which installs the D-Bus policy and reloads D-Bus.

**Related:** [Setup Step 8: Intune Setup](../hosts/stargazer/README.md#8-intune-setup)

---

### Enrollment Fails with Keyring Error

**What you see:**
- Portal shows "Object does not exist at path /org/freedesktop/secrets/collection/login"
- Enrollment wizard fails at token storage step

**Root cause:**
Login keyring doesn't exist or isn't set as default.

**Solution:**

1. Open Seahorse:
   ```bash
   seahorse &
   ```
2. Create keyring:
   - File -> New -> Password Keyring
   - Name: `login` (exactly this name)
   - Set a password
3. Set as default:
   - Right-click the new keyring
   - Select "Set as Default"
4. Retry enrollment

**Prevention:**
Always create the login keyring via Seahorse before enrollment. The `intune-prerequisites` script sets up the keyring pointer, but the actual keyring must be created via GUI.

---

### Portal Shows Blank Screen

**What you see:**
- `intune-portal-rosetta` launches but window is blank/white
- No login UI appears

**Root cause:**
Usually library path issues or broker communication failure.

**Solution:**

1. Check broker is running:
   ```bash
   systemctl status microsoft-identity-device-broker
   ```
2. Check D-Bus user service:
   ```bash
   ls ~/.local/share/dbus-1/services/
   ```
3. Try running with debug:
   ```bash
   intune-portal-rosetta 2>&1 | tee /tmp/portal-debug.log
   ```
4. Look for library loading errors in output

**Prevention:**
Run `intune-health` before launching portal to verify all components.

---

### Authentication Fails

**What you see:**
- Sign-in button clicked but nothing happens
- Or: Error "Unable to authenticate" after entering credentials

**Root cause:**
Usually microsoft-identity-broker (user-session broker) not activating.

**Solution:**

1. Check user broker can be activated:
   ```bash
   dbus-send --session --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames | grep microsoft
   ```
2. Check D-Bus service file:
   ```bash
   ls ~/.local/share/dbus-1/services/com.microsoft.identity.broker1.service
   ```
3. Restart portal and try again

**Prevention:**
Verify `intune-health` passes before attempting sign-in.

---

## YubiKey Issues

### YubiKey Not Detected

**What you see:**
- `intune-health` shows YubiKey warning
- `ykman list` returns empty
- `pkcs11-tool --list-slots` shows no slots

**Root cause:**
Either YubiKey not inserted, Parallels not sharing USB, or pcscd not running.

**Solution:**

1. Verify YubiKey inserted in Mac
2. Check Parallels sharing:
   - VM Config -> Hardware -> USB & Bluetooth
   - Enable "Share smart card readers with Linux"
3. Check pcscd:
   ```bash
   sudo systemctl status pcscd
   sudo systemctl start pcscd
   ```
4. List devices:
   ```bash
   ykman list
   ```

**Prevention:**
Configure Parallels smart card sharing during initial VM setup.

**Related:** [Setup Step 8.3: Configure Parallels Smart Card Sharing](../hosts/stargazer/README.md#83-configure-parallels-smart-card-sharing)

---

### Certificate Not Shown in Picker

**What you see:**
- YubiKey detected (`ykman list` works)
- But certificate picker during sign-in is empty

**Root cause:**
OpenSC PKCS#11 module not loading certificates, or wrong module version.

**Solution:**

1. Test PKCS#11 directly:
   ```bash
   pkcs11-tool --module /run/current-system/sw/lib/opensc-pkcs11.so --list-objects
   ```
2. If no objects, try with YubiKey PKCS#11:
   ```bash
   pkcs11-tool --module /run/current-system/sw/lib/libykcs11.so --list-objects
   ```
3. If neither works, check YubiKey has PIV certificates:
   ```bash
   ykman piv info
   ```

**Prevention:**
Verify YubiKey has PIV certificates provisioned before attempting enrollment.

---

### PIN Rejected

**What you see:**
- Certificate appears in picker
- PIN entered but rejected with "incorrect PIN"
- Or: YubiKey locks after too many attempts

**Root cause:**
Either wrong PIN entered, or YubiKey locked out.

**Solution:**

1. For wrong PIN: Check you're entering PIV PIN, not FIDO2 PIN
2. For lockout, check remaining retries:
   ```bash
   ykman piv access retries
   ```
3. If locked (0 retries), use PUK to reset:
   ```bash
   ykman piv access unblock-pin
   ```
4. If PUK also exhausted, reset PIV applet (loses all certificates!):
   ```bash
   ykman piv reset
   ```

**Prevention:**
Default PIN: 123456. Default PUK: 12345678. Change these during YubiKey setup.

---

## Still Stuck?

If none of these solutions work:

1. Check logs for more detail:
   ```bash
   journalctl -b --since "30 minutes ago" | grep -i error
   intune-logs --all
   ```

2. Create a VM snapshot of current state (for later analysis)

3. If it's a blocking issue, consider restoring from a known-good snapshot and retrying the failed step

4. For persistent issues, check the relevant detailed documentation:
   - [Template creation](arch-arm-encrypted-install.md)
   - [Omarchy + GRUB](omarchy-grub-install.md)
   - [Microsoft broker reference](intune-broker2.0.md)
