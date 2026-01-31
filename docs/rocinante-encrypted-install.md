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

# Note:
Only luks password matters here - user password will be set during omarchy installation

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

pacman -S wget

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

### Step 9: Configure Rosetta for x86_64 Emulation

The Nix configuration uses x86_64-linux packages (for Microsoft Intune) that run via Rosetta emulation. Set this up before installing Nix:

```bash
# Register Rosetta as binfmt handler for x86_64 ELF binaries
# NOTE: Rosetta is mounted at /mnt/psf/RosettaLinux/ (not /media/psf/)
sudo tee /etc/binfmt.d/rosetta.conf << 'EOF'
:rosetta:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x3e\x00:\xff\xff\xff\xff\xff\xfe\xfe\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/mnt/psf/RosettaLinux/rosetta:PFC
EOF

# Activate binfmt configuration
sudo systemctl restart systemd-binfmt

# Verify Rosetta is registered
cat /proc/sys/fs/binfmt_misc/rosetta
# Should show: enabled, interpreter /mnt/psf/RosettaLinux/rosetta
```

### Step 10: Install Nix with x86_64 Support

```bash
# Install Nix with extra-platforms for Rosetta x86_64 support
# The --extra-conf flag adds configuration to /etc/nix/nix.conf
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | \
  sh -s -- install --extra-conf "extra-platforms = x86_64-linux"

# Source Nix
. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh

# Verify extra-platforms is configured
nix show-config | grep extra-platforms
# Should show: extra-platforms = x86_64-linux
```

**Alternative (post-install):** If Nix is already installed without `--extra-conf`:
```bash
# Add extra-platforms to custom config (Determinate Nix reads this)
sudo tee /etc/nix/nix.custom.conf << 'EOF'
extra-platforms = x86_64-linux
EOF

# Restart nix-daemon to pick up new config
sudo systemctl restart nix-daemon
```

### Step 11: Apply Home-Manager Configuration

```bash
# The dotfiles are mounted from macOS host via Parallels shared folders
cd /mnt/psf/Home/Documents/dotfiles

# Apply home-manager configuration for the host (e.g., rocinante, stargazer)
# Use -b backup to back up existing config files that would be overwritten
nix run nixpkgs#home-manager -- switch --flake .#rocinante -b backup
```

**Note:** The `-b backup` flag backs up any existing config files (from armarchy) that home-manager needs to manage. These are saved as `*.backup` files.

### Step 12: Apply Chezmoi Configuration

Home-manager installs packages and declarative configs. Chezmoi manages mutable user configs (neovim, nushell, etc.) that change frequently:

```bash
# Apply chezmoi-managed configs (neovim, nushell, etc.)
chezmoi apply

# Verify configs were applied
ls ~/.config/nvim
ls ~/.config/nushell
```

The chezmoi module automatically sets `sourceDir` to the dotfiles chezmoi directory via the Parallels shared folder mount.

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

# Generalize
# Generalize hostname (or keep stargazer if you prefer)
  echo "archbase" > /etc/hostname

  # Clear machine-id (regenerates on next boot)
  rm -f /etc/machine-id
  touch /etc/machine-id

  # Clear pacman cache
  pacman -Scc --noconfirm

  # Clear history
  rm -f /root/.bash_history
  history -c

  # Verify encryption is working
  cryptsetup status cryptroot

  # Shutdown cleanly
  shutdown -h now

  Then on macOS:

  # Snapshot at clean state
  prlctl snapshot "stargazer" -n "EncryptedBase-GRUB" -d "Clean LUKS+GRUB base before omarchy"

  # Check size
  du -sh ~/Parallels/stargazer.pvm

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

### Nix Build Fails: "Required system: x86_64-linux"

If `home-manager switch` fails with:
```
error: Cannot build '...drv'.
Required system: 'x86_64-linux' with features {}
Current system: 'aarch64-linux' with features {...}
```

This means Nix isn't configured to build x86_64 packages via Rosetta:

```bash
# 1. Check if Rosetta binfmt is registered
cat /proc/sys/fs/binfmt_misc/rosetta
# If not found, register it (note: /mnt/psf not /media/psf):
sudo tee /etc/binfmt.d/rosetta.conf << 'EOF'
:rosetta:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x3e\x00:\xff\xff\xff\xff\xff\xfe\xfe\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/mnt/psf/RosettaLinux/rosetta:PFC
EOF
sudo systemctl restart systemd-binfmt

# 2. Check if Nix has extra-platforms configured
nix show-config | grep extra-platforms
# If not configured or missing x86_64-linux:
sudo tee /etc/nix/nix.custom.conf << 'EOF'
extra-platforms = x86_64-linux
EOF
sudo systemctl restart nix-daemon

# 3. Verify Rosetta works
/mnt/psf/RosettaLinux/rosetta /bin/true && echo "Rosetta works"
```

**Note:** The Determinate Nix installer uses `/etc/nix/nix.custom.conf` for user customizations - don't modify `/etc/nix/nix.conf` directly as it will be overwritten.

## References

- [Arch Wiki - dm-crypt/Encrypting an entire system](https://wiki.archlinux.org/title/Dm-crypt/Encrypting_an_entire_system)
- [Arch Wiki - GRUB](https://wiki.archlinux.org/title/GRUB)
- [Arch Wiki - PAM](https://wiki.archlinux.org/title/PAM)
- [archboot](https://release.archboot.com/)
- [Arch Linux ARM Mirrors](https://archlinuxarm.org/about/mirrors)
- [Armarchy (Omarchy for ARM64)](https://github.com/basecamp/omarchy/pull/1897)
- [Omarchy v3.2.0](https://github.com/basecamp/omarchy/releases/tag/v3.2.0)
- [Determinate Nix Installer](https://docs.determinate.systems/determinate-nix/)
- [Determinate Nix Advanced Installation](https://docs.determinate.systems/guides/advanced-installation/)
