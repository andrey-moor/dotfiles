# Rocinante: Encrypted Arch ARM Installation

Manual installation of Arch Linux ARM with LUKS disk encryption for Microsoft Intune compliance, followed by Armarchy (Omarchy for ARM64) installer.

## Why Encryption is Required

Microsoft Intune requires dm-crypt/LUKS disk encryption for device compliance. Pre-built VM images (like armarchy PR #1897) bypass the standard archinstall process where LUKS would normally be configured, resulting in non-compliant devices.

## Prerequisites

- **Parallels Desktop for Mac** (Apple Silicon) with Rosetta enabled
- **archboot ISO** for ARM64:
  - Download: https://release.archboot.com/aarch64/latest/iso/
  - Check directory for current version (e.g., `archboot-2025.12.xx-aarch64.iso`)
- Network connection during installation
- 64GB+ disk space for VM (encrypted)
- 8GB+ RAM recommended (4GB minimum)

## Installation Steps

### Step 1: Create VM and Configure Parallels

1. Download the archboot ISO from https://release.archboot.com/aarch64/latest/iso/
2. Create new Parallels VM:
   - **Type**: "Install Windows or another OS from a DVD or image file"
   - Select the archboot ISO
   - **OS Type**: Other Linux
3. Configure before first boot:
   - **CPU**: 4+ cores recommended
   - **RAM**: 4096MB minimum, 8192MB recommended
   - **Disk**: 64GB (will be encrypted)
   - **Options → Advanced**: Enable **"Use Rosetta to run x86-64 binaries"**
   - **Options → Sharing**: Enable **"Share Mac folders with Linux"**
4. Start VM and boot into archboot live environment

### Step 2: Verify Network

```bash
# Check network interface
ip link

# Test connectivity
ping -c 3 archlinux.org

# If no network, configure manually:
# ip link set enp0s5 up
# dhcpcd enp0s5
```

### Step 3: Identify Disk and Partition

```bash
# List block devices - note your disk name
lsblk

# Parallels typically uses:
# - /dev/sda (SCSI emulation - most common)
# - /dev/vda (virtio - less common)

# Set variable for rest of guide (adjust if different)
DISK=/dev/sda

# Create partitions
# Partition 1: EFI System Partition (512MB)
# Partition 2: LUKS encrypted root (rest of disk)
fdisk $DISK

# In fdisk:
# g (create GPT table)
# n, 1, default, +512M (EFI partition)
# t, 1 (change type to EFI System)
# n, 2, default, default (root partition - rest of disk)
# w (write and exit)

# Format EFI partition
mkfs.fat -F32 ${DISK}1
```

### Step 4: Setup LUKS Encryption

```bash
# Setup LUKS2 encryption with recommended options
cryptsetup luksFormat --type luks2 \
  --cipher aes-xts-plain64 \
  --key-size 512 \
  --hash sha512 \
  --iter-time 5000 \
  ${DISK}2

# Enter and confirm encryption passphrase
# Use a STRONG passphrase - you'll need it at every boot

# Open the encrypted partition
cryptsetup open ${DISK}2 cryptroot
# Enter passphrase

# Format the decrypted volume
mkfs.btrfs /dev/mapper/cryptroot

# Mount filesystems
mount /dev/mapper/cryptroot /mnt
mkdir -p /mnt/boot
mount ${DISK}1 /mnt/boot
```

### Step 5: Configure Mirrors and Install Base System

The archboot aarch64 ISO uses **Arch Linux ARM** (ALARM) repositories, not standard Arch Linux.
The mirror URL format is `$arch/$repo` (not `$repo/os/$arch`).

```bash
# Configure Arch Linux ARM mirrors (US mirrors for best speed)
cat > /etc/pacman.d/mirrorlist << 'EOF'
Server = http://ca.us.mirror.archlinuxarm.org/$arch/$repo
Server = http://fl.us.mirror.archlinuxarm.org/$arch/$repo
Server = http://mirror.archlinuxarm.org/$arch/$repo
EOF

# Verify mirror connectivity (should return HTTP 200)
curl -I http://ca.us.mirror.archlinuxarm.org/aarch64/core/core.db

# Install base packages
pacstrap /mnt base linux linux-firmware btrfs-progs sudo networkmanager libpwquality

# Generate fstab
genfstab -U /mnt >> /mnt/etc/fstab

# Chroot into new system
arch-chroot /mnt

# Set timezone (adjust to your location)
# List available: ls /usr/share/zoneinfo/
ln -sf /usr/share/zoneinfo/America/Los_Angeles /etc/localtime
hwclock --systohc

# Set locale
echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
locale-gen
echo "LANG=en_US.UTF-8" > /etc/locale.conf

# Set hostname
echo "rocinante" > /etc/hostname

# Set root password (temporary - armarchy will create user)
passwd
```

### Step 6: Configure PAM Password Policy (Intune Requirement)

Intune requires password complexity. Configure this **before** running armarchy:

```bash
# Create password quality config
cat > /etc/security/pwquality.conf << 'EOF'
# Microsoft Intune compliance requirements
# Minimum 12 characters, at least 1 of each: uppercase, lowercase, digit, symbol
minlen = 12
dcredit = -1
ucredit = -1
lcredit = -1
ocredit = -1
EOF
```

**Important:** When armarchy prompts for your password, use one that meets requirements:
- 12+ characters
- At least 1 uppercase (A-Z)
- At least 1 lowercase (a-z)
- At least 1 digit (0-9)
- At least 1 symbol (!@#$%^&*...)

### Step 7: Configure Bootloader with LUKS Support

```bash
# Install bootloader packages
pacman -S grub efibootmgr

# Configure mkinitcpio for encryption
# Edit /etc/mkinitcpio.conf, set HOOKS exactly as follows (order matters!):
HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt filesystems fsck)

# The 'encrypt' hook MUST come after 'block' and before 'filesystems'
# Use sed to set it:
sed -i 's/^HOOKS=.*/HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt filesystems fsck)/' /etc/mkinitcpio.conf

# Create vconsole.conf (required by consolefont hook)
echo "KEYMAP=us" > /etc/vconsole.conf

# Regenerate initramfs
mkinitcpio -P

# IMPORTANT: On ARM, the kernel is named 'Image', not 'vmlinuz-linux'
# GRUB's grub-mkconfig looks for vmlinuz-linux to find matching initramfs
# Without this copy, GRUB won't load the initramfs and encryption will fail!
cp /boot/Image /boot/vmlinuz-linux

# Find UUID of encrypted partition
blkid -s UUID -o value /dev/sda2
# Note the UUID (e.g., xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)

# Configure GRUB for encryption
# Edit /etc/default/grub, set GRUB_CMDLINE_LINUX with your UUID:
# (Replace <your-uuid> with actual UUID from blkid above)
sed -i 's/GRUB_CMDLINE_LINUX=""/GRUB_CMDLINE_LINUX="cryptdevice=UUID=<your-uuid>:cryptroot root=\/dev\/mapper\/cryptroot"/' /etc/default/grub

# Verify the setting
grep "GRUB_CMDLINE_LINUX=" /etc/default/grub

# Install GRUB
grub-install --target=arm64-efi --efi-directory=/boot --bootloader-id=GRUB

# Generate GRUB config - verify it finds BOTH vmlinuz-linux AND initramfs-linux.img
grub-mkconfig -o /boot/grub/grub.cfg
# Should show:
#   Found linux image: /boot/vmlinuz-linux
#   Found initrd image: /boot/initramfs-linux.img

# Verify initrd is in grub.cfg (critical!)
grep "initrd" /boot/grub/grub.cfg
# Should show: initrd /initramfs-linux.img

# Enable NetworkManager
systemctl enable NetworkManager

# Exit chroot and reboot
exit
umount -R /mnt
reboot
```

**Important Notes:**
- The `cp /boot/Image /boot/vmlinuz-linux` step is critical on ARM - without it, grub-mkconfig won't find the initramfs and LUKS decryption will fail silently (kernel panic with "unable to mount root fs")
- After `grub-mkconfig`, verify you see both "Found linux image" AND "Found initrd image" in the output
- If `grep "initrd"` shows no output, the initramfs won't be loaded and boot will fail

### Step 8: Run Armarchy Installer

After reboot (enter LUKS passphrase at boot):

```bash
# Login as root

# Armarchy v3.x for ARM64 (Omarchy for Apple Silicon Parallels VMs)
# Based on Omarchy v3.2.0 (December 2025)
# Source: https://github.com/basecamp/omarchy/pull/1897
curl -fsSL hdwy.link/armarchy-3-x | bash
```

The installer will:
- Create a non-root user with sudo (use a compliant password!)
- Install Hyprland desktop environment
- Configure system settings
- Reboot into graphical desktop

### Step 9: Apply Nix Configuration

After armarchy completes and you're logged into the desktop:

```bash
# Install Nix (Determinate installer - enables flakes by default)
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install

# Source Nix
. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh

# The dotfiles are mounted from macOS host via Parallels shared folders
cd /media/psf/Home/Documents/dotfiles

# Apply home-manager configuration for rocinante
nix run nixpkgs#home-manager -- switch --flake .#rocinante
```

## Post-Install Verification

### Verify Encryption

```bash
# Check LUKS status
sudo cryptsetup status cryptroot

# Should show:
#   type:    LUKS2
#   cipher:  aes-xts-plain64
#   keysize: 512 bits
#   device:  /dev/sda2

# Check block devices
lsblk -f

# Should show /dev/sda2 as crypto_LUKS with cryptroot underneath
```

### Verify Password Policy

```bash
# Check pwquality config
cat /etc/security/pwquality.conf

# Test password validation (will reject weak passwords)
pwscore <<< "weak"        # Should fail
pwscore <<< "MySecure#Pass123"  # Should pass
```

### Verify Intune Compliance

After applying Nix configuration and enrolling in Intune:

```bash
# Check disk encryption (what Intune sees)
lsblk -o NAME,FSTYPE,SIZE,MOUNTPOINT | grep -E "(crypt|luks)"

# The root filesystem should be on dm-crypt/LUKS
```

## Troubleshooting

### Boot Fails After Installation

1. Boot from archboot ISO again
2. Open encrypted partition: `cryptsetup open /dev/sda2 cryptroot`
3. Mount: `mount /dev/mapper/cryptroot /mnt && mount /dev/sda1 /mnt/boot`
4. Chroot: `arch-chroot /mnt`
5. Check GRUB config and mkinitcpio hooks

### Wrong UUID in GRUB Config

```bash
# Get correct UUID
blkid /dev/sda2

# Edit GRUB config
vim /etc/default/grub

# Regenerate GRUB
grub-mkconfig -o /boot/grub/grub.cfg
```

### Missing 'encrypt' Hook

```bash
# Check mkinitcpio.conf
grep HOOKS /etc/mkinitcpio.conf

# Should include 'encrypt' after 'block' and before 'filesystems'
# Regenerate if needed
mkinitcpio -P
```

### No Network After Reboot

```bash
# Check NetworkManager status
systemctl status NetworkManager

# If not running
sudo systemctl enable --now NetworkManager

# Connect to network
nmcli device wifi list
nmcli device wifi connect "SSID" password "password"
```

### Kernel Panic: Unable to Mount Root FS (No Passphrase Prompt)

If boot fails with "Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)" and you never see a LUKS passphrase prompt:

```bash
# Boot from archboot ISO, mount and chroot
cryptsetup open /dev/sda2 cryptroot
mount /dev/mapper/cryptroot /mnt
mount /dev/sda1 /mnt/boot
arch-chroot /mnt

# Check if vmlinuz-linux exists (required for grub-mkconfig to find initramfs)
ls -la /boot/vmlinuz*
# If missing, copy from ARM kernel:
cp /boot/Image /boot/vmlinuz-linux

# Check if initrd is in grub.cfg
grep "initrd" /boot/grub/grub.cfg
# If no output, initramfs is not being loaded!

# Regenerate GRUB config
grub-mkconfig -o /boot/grub/grub.cfg
# Verify output shows BOTH:
#   Found linux image: /boot/vmlinuz-linux
#   Found initrd image: /boot/initramfs-linux.img

# Verify initrd is now in config
grep "initrd" /boot/grub/grub.cfg
```

**Root cause:** On ARM, the kernel is named `Image` not `vmlinuz-linux`. Without `vmlinuz-linux`, grub-mkconfig doesn't find the matching initramfs, so GRUB boots the kernel without the initramfs. Without the initramfs, the `encrypt` hook never runs.

### Mirror Connection Failures During pacstrap

If `pacstrap` fails with "Could not connect to server" or 404 errors:

```bash
# Verify network connectivity
ping -c 2 ca.us.mirror.archlinuxarm.org

# Test mirror directly
curl -I http://ca.us.mirror.archlinuxarm.org/aarch64/core/core.db

# If using wrong mirror format, fix it:
# WRONG (standard Arch): $repo/os/$arch
# RIGHT (Arch Linux ARM): $arch/$repo

# Full mirror list available at:
# https://github.com/archlinuxarm/PKGBUILDs/blob/master/core/pacman-mirrorlist/mirrorlist
```

## References

- [Arch Wiki - dm-crypt/Encrypting an entire system](https://wiki.archlinux.org/title/Dm-crypt/Encrypting_an_entire_system)
- [Arch Wiki - GRUB](https://wiki.archlinux.org/title/GRUB)
- [Arch Wiki - PAM](https://wiki.archlinux.org/title/PAM)
- [archboot](https://release.archboot.com/)
- [Arch Linux ARM Mirrors](https://archlinuxarm.org/about/mirrors)
- [Armarchy (Omarchy for ARM64)](https://github.com/basecamp/omarchy/pull/1897)
- [Omarchy v3.2.0](https://github.com/basecamp/omarchy/releases/tag/v3.2.0)
