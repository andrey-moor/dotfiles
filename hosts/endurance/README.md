# Endurance Setup

Encrypted Arch Linux ARM VM in Parallels with LUKS for Intune compliance.

## VM Template Creation

This section documents creating the base encrypted Arch Linux VM from scratch. If you already have a working VM, skip to [Prerequisites](#prerequisites).

### Step 1: Create VM in Parallels

Create a new VM using Parallels with the correct settings. These settings MUST be configured before first boot.

**Download archboot ISO:**

Get the latest aarch64 archboot ISO from https://archboot.com (look for `archboot-*-aarch64.iso`).

**Create the VM via GUI:**

1. Parallels Desktop > File > New
2. Choose "Install Windows, Linux or macOS from an image"
3. Select the archboot ISO
4. Choose "Other Linux" as the OS type
5. Name: `ArchBase-Template` (or your preferred name)

**Configure VM settings (BEFORE first boot):**

```bash
VM_NAME="ArchBase-Template"

# Set resources: 4 CPU cores, 8GB RAM
prlctl set "$VM_NAME" --cpus 4 --memsize 8192

# Resize disk to 128GB (default is smaller)
prlctl set "$VM_NAME" --device-set hdd0 --size 131072

# CRITICAL: Enable Rosetta BEFORE first boot (cannot be enabled later)
prlctl set "$VM_NAME" --rosetta-linux on

# Enable shared folders (macOS home directory)
prlctl set "$VM_NAME" --shf-host on
prlctl set "$VM_NAME" --shf-host-defined home --enable

# Set bridged networking (VM gets own IP)
prlctl set "$VM_NAME" --device-set net0 --type bridged
```

**Verify settings:**

```bash
prlctl list -i "$VM_NAME" | grep -E "(cpu|memsize|rosetta|shf)"
```

### Step 2: Boot and Partition

Start the VM and boot from the archboot ISO.

```bash
prlctl start "$VM_NAME"
```

Once booted into the archboot environment, verify you have network connectivity:

```bash
ip addr
ping -c 3 archlinux.org
```

**Partition the disk:**

Create three partitions: EFI (512MB), /boot (1GB), and LUKS (remaining space).

```bash
# List disks - should show /dev/sda as the 128GB virtual disk
lsblk

# Partition with fdisk
fdisk /dev/sda
```

In fdisk:
```
g        # Create new GPT partition table
n        # New partition (EFI)
1        # Partition number 1
[Enter]  # Default first sector
+512M    # 512MB for EFI
t        # Change type
1        # Type 1 = EFI System

n        # New partition (boot)
2        # Partition number 2
[Enter]  # Default first sector
+1G      # 1GB for /boot

n        # New partition (LUKS root)
3        # Partition number 3
[Enter]  # Default first sector
[Enter]  # Use remaining space

w        # Write and exit
```

**Format EFI and boot partitions:**

```bash
mkfs.fat -F32 /dev/sda1
mkfs.ext4 /dev/sda2
```

### Step 3: LUKS Setup

Create LUKS2 encrypted partition with argon2id key derivation. Since /boot is unencrypted and separate, GRUB doesn't need to decrypt the LUKS partition - the initramfs encrypt hook handles decryption, which fully supports argon2id.

```bash
# Create LUKS2 partition with argon2id (you'll be prompted for passphrase)
cryptsetup luksFormat --type luks2 \
  --cipher aes-xts-plain64 \
  --key-size 512 \
  --hash sha512 \
  --pbkdf argon2id \
  /dev/sda3
```

**Open the encrypted partition and format:**

```bash
# Open the LUKS partition (enter passphrase)
cryptsetup open /dev/sda3 cryptroot

# Format as ext4
mkfs.ext4 /dev/mapper/cryptroot
```

### Step 4: Mount for archinstall

Mount the filesystems in the correct hierarchy for archinstall's pre_mounted_config mode.

```bash
# Mount root
mount /dev/mapper/cryptroot /mnt/archinstall

# Create mount points
mkdir -p /mnt/archinstall/boot
mkdir -p /mnt/archinstall/boot/efi

# Mount boot partitions
mount /dev/sda2 /mnt/archinstall/boot
mount /dev/sda1 /mnt/archinstall/boot/efi
```

**Verify mount layout:**

```bash
lsblk -f
# Should show:
# sda1 -> /mnt/archinstall/boot/efi (FAT32)
# sda2 -> /mnt/archinstall/boot (ext4)
# sda3 -> LUKS -> cryptroot -> /mnt/archinstall (ext4)
```

### Step 5: Run archinstall

Run archinstall with pre_mounted_config mode. This tells archinstall to use the already-mounted filesystems instead of partitioning itself.

```bash
archinstall --config <(cat << 'EOF'
{
  "archinstall-language": "English",
  "bootloader": "Grub",
  "config_version": "2.8.1",
  "debug": false,
  "disk_config": {
    "config_type": "pre_mounted_config",
    "mountpoint": "/mnt/archinstall"
  },
  "hostname": "template",
  "kernels": ["linux"],
  "locale_config": {
    "kb_layout": "us",
    "sys_enc": "UTF-8",
    "sys_lang": "en_US"
  },
  "network_config": {
    "type": "nm"
  },
  "ntp": true,
  "packages": ["wget", "sudo", "openssh", "base-devel", "git", "vim"],
  "profile_config": {
    "profile": null
  },
  "silent": false,
  "swap": false,
  "timezone": "America/Los_Angeles"
}
EOF
)
```

archinstall will prompt you to:
- Set a root password
- Create a user account (create a generic "user" account - you'll personalize later)
- Confirm installation

After archinstall completes, **do NOT reboot yet**. We need to configure GRUB for LUKS decryption.

### Step 6: Configure GRUB

archinstall installs GRUB but doesn't configure it for LUKS decryption. We need to add the cryptdevice parameter and ensure the initramfs has the encrypt hook.

**Chroot into the new system:**

```bash
arch-chroot /mnt/archinstall
```

**Get the LUKS partition UUID:**

```bash
LUKS_UUID=$(blkid -s UUID -o value /dev/sda3)
echo "LUKS UUID: $LUKS_UUID"
```

**Configure GRUB for LUKS:**

```bash
# Edit GRUB config
sed -i "s|^GRUB_CMDLINE_LINUX=.*|GRUB_CMDLINE_LINUX=\"cryptdevice=UUID=$LUKS_UUID:cryptroot root=/dev/mapper/cryptroot\"|" /etc/default/grub
```

**Verify mkinitcpio HOOKS:**

The encrypt hook must be present and in the correct order (keyboard before encrypt).

```bash
# Check current HOOKS
grep "^HOOKS" /etc/mkinitcpio.conf
```

If the encrypt hook is missing or keyboard comes after encrypt, edit the file:

```bash
# Should look like:
# HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt filesystems fsck)

# If needed, edit:
vim /etc/mkinitcpio.conf

# Regenerate initramfs
mkinitcpio -P
```

**Create ARM kernel symlink:**

On ARM64, the kernel is named `Image` but GRUB expects `vmlinuz-linux`. Create a symlink:

```bash
cp /boot/Image /boot/vmlinuz-linux
```

**Install and configure GRUB:**

```bash
# Install GRUB for ARM64 UEFI
grub-install --target=arm64-efi --efi-directory=/boot/efi --bootloader-id=GRUB

# Generate GRUB config
grub-mkconfig -o /boot/grub/grub.cfg
```

**Verify grub-mkconfig output:**

The output should show BOTH:
- `Found linux image: /boot/vmlinuz-linux`
- `Found initrd image: /boot/initramfs-linux.img`

If it doesn't find the initrd, the kernel symlink is missing or wrong.

**Enable SSH:**

```bash
systemctl enable sshd
```

**Exit chroot and unmount:**

```bash
exit
umount -R /mnt/archinstall
```

### Step 7: First Boot Verification

Reboot the VM and verify LUKS decryption works.

```bash
reboot
```

**What to expect:**

1. GRUB menu appears
2. System prompts for LUKS passphrase
3. After entering passphrase, system decrypts and boots
4. Login prompt appears (login as the user you created)

**Verification commands (after login):**

```bash
# Verify encrypted root is mounted
lsblk
# Should show: sda3 -> crypt -> cryptroot -> /

# Verify kernel command line has cryptdevice
cat /proc/cmdline
# Should contain: cryptdevice=UUID=...:cryptroot root=/dev/mapper/cryptroot

# Verify network works
ip addr
ping -c 3 archlinux.org

# Verify SSH is running
systemctl status sshd
```

**If boot fails:**

- No passphrase prompt: Check mkinitcpio HOOKS (encrypt hook missing or wrong order)
- Wrong password errors: Verify LUKS_UUID in /etc/default/grub matches `blkid /dev/sda3`
- Kernel not found: Check /boot/vmlinuz-linux symlink exists
- initramfs not found: Run `mkinitcpio -P` and `grub-mkconfig -o /boot/grub/grub.cfg`

---

## Prerequisites

After creating the base encrypted Arch Linux VM (see [VM Template Creation](#vm-template-creation) above):

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
nix run home-manager -- switch --flake .#endurance -b backup
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
