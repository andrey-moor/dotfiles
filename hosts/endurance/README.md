# Endurance Setup

Encrypted Arch Linux ARM VM in Parallels with LUKS for Intune compliance.

## VM Template Creation

This section documents creating the base encrypted Arch Linux VM from scratch. The process is mostly automated via scripts.

If you already have a working VM, skip to [Prerequisites](#prerequisites).

### Quick Start (Automated)

**From macOS terminal:**

```bash
# 1. Download archboot ISO first
# Get latest from: https://archboot.com/iso/aarch64/latest/

# 2. Create and configure VM (automated)
cd ~/Documents/dotfiles
./scripts/create-arch-vm.sh ArchBase-Template 4 8192 131072 ~/Downloads/archboot-*.iso

# 3. Start VM
prlctl start ArchBase-Template
```

**In archboot console (after VM boots):**

```bash
# Single command installs everything
curl -fsSL https://raw.githubusercontent.com/andrey-moor/dotfiles/main/scripts/install-arch.sh | bash
```

**After reboot:**

```bash
# IMPORTANT: Change temporary LUKS passphrase
sudo cryptsetup luksChangeKey /dev/sda3
# Enter current: temppass
# Enter new passphrase (use a strong one!)

# Change user password
passwd
# Enter current: temppass
# Enter new password
```

That's it! The VM is ready for [Prerequisites](#prerequisites) setup.

---

### Manual Installation (If Automated Fails)

<details>
<summary>Click to expand manual steps</summary>

#### Step 1: Create VM in Parallels

**Download archboot ISO:**

Get the latest aarch64 archboot ISO from https://archboot.com (look for `archboot-*-aarch64.iso`).

**Create and configure VM:**

```bash
VM_NAME="ArchBase-Template"

# Create VM
prlctl create "$VM_NAME" --ostype linux-2.6 --distribution linux

# Set resources: 4 CPU cores, 8GB RAM, 128GB disk
prlctl set "$VM_NAME" --cpus 4 --memsize 8192
prlctl set "$VM_NAME" --device-set hdd0 --size 131072

# CRITICAL: Enable Rosetta BEFORE first boot
prlctl set "$VM_NAME" --rosetta-linux on

# Enable shared folders and bridged networking
prlctl set "$VM_NAME" --shf-host on
prlctl set "$VM_NAME" --device-set net0 --type bridged

# Attach ISO and set boot order
prlctl set "$VM_NAME" --device-set cdrom0 --image ~/Downloads/archboot-*.iso
prlctl set "$VM_NAME" --device-bootorder "cdrom0 hdd0"

# Start VM
prlctl start "$VM_NAME"
```

#### Step 2: Partition Disk

In archboot console:

```bash
# Partition: EFI (512MB) + /boot (1GB) + LUKS (remaining)
fdisk /dev/sda << 'EOF'
g
n
1

+512M
t
1
n
2

+1G
n
3


w
EOF

# Format EFI and boot
mkfs.fat -F32 /dev/sda1
mkfs.ext4 /dev/sda2
```

#### Step 3: LUKS Setup

```bash
# Create LUKS2 with argon2id (enter passphrase when prompted)
cryptsetup luksFormat --type luks2 \
  --cipher aes-xts-plain64 \
  --key-size 512 \
  --hash sha512 \
  --pbkdf argon2id \
  /dev/sda3

# Open and format
cryptsetup open /dev/sda3 cryptroot
mkfs.ext4 /dev/mapper/cryptroot
```

#### Step 4: Mount and Install

```bash
# Mount filesystems
mount /dev/mapper/cryptroot /mnt/archinstall
mkdir -p /mnt/archinstall/boot/efi
mount /dev/sda2 /mnt/archinstall/boot
mount /dev/sda1 /mnt/archinstall/boot/efi

# Run archinstall (interactive)
archinstall
# Choose: GRUB bootloader, NetworkManager, create user account
```

#### Step 5: Configure GRUB for LUKS

After archinstall, before rebooting:

```bash
arch-chroot /mnt/archinstall

# Get LUKS UUID and configure GRUB
LUKS_UUID=$(blkid -s UUID -o value /dev/sda3)
sed -i "s|^GRUB_CMDLINE_LINUX=.*|GRUB_CMDLINE_LINUX=\"cryptdevice=UUID=$LUKS_UUID:cryptroot root=/dev/mapper/cryptroot\"|" /etc/default/grub

# Ensure encrypt hook in mkinitcpio
sed -i 's/^HOOKS=.*/HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt filesystems fsck)/' /etc/mkinitcpio.conf
mkinitcpio -P

# ARM kernel symlink (GRUB expects vmlinuz-linux)
cp /boot/Image /boot/vmlinuz-linux

# Install and configure GRUB
grub-install --target=arm64-efi --efi-directory=/boot/efi --bootloader-id=GRUB
grub-mkconfig -o /boot/grub/grub.cfg

# Enable SSH
systemctl enable sshd

exit
reboot
```

</details>

---

### Verification

After first boot:

```bash
# Verify encrypted root
lsblk
# Should show: sda3 -> crypt -> cryptroot -> /

# Verify GRUB LUKS config
cat /proc/cmdline
# Should contain: cryptdevice=UUID=...:cryptroot

# Verify network and SSH
ip addr
systemctl status sshd
```

**If boot fails:**
- No passphrase prompt → encrypt hook missing from mkinitcpio
- Wrong password errors → LUKS_UUID mismatch in GRUB config
- Kernel not found → missing `/boot/vmlinuz-linux` symlink

---

## Prerequisites

After creating the base encrypted Arch Linux VM (see [VM Template Creation](#vm-template-creation) above):

**Quick Start:**

```bash
# From cloned repo (recommended):
/mnt/psf/Home/Documents/dotfiles/scripts/prerequisites.sh

# Or via curl:
curl -fsSL https://raw.githubusercontent.com/andrey-moor/dotfiles/main/scripts/prerequisites.sh | bash
```

This script handles steps 1-6 below automatically (Nix, Rosetta, x86_64 linker, os-release). Continue with step 7 after the script completes.

<details>
<summary>Manual Steps (if script fails)</summary>

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

</details>

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
