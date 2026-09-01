# Arch Linux ARM with LUKS Encryption Installation

Manual installation of Arch Linux ARM with LUKS disk encryption on Apple Silicon (Parallels Desktop). This guide covers base system installation with GRUB bootloader configured for LUKS2 decryption.

## Why Encryption is Required

Microsoft Intune requires dm-crypt/LUKS disk encryption for device compliance. This guide creates an encrypted base system that meets compliance requirements.

## Prerequisites

- **Parallels Desktop for Mac** on Apple Silicon
- **archboot ISO** for ARM64:
  - Download from: https://release.archboot.com/aarch64/latest/iso/
  - Check directory for current version (e.g., `archboot-2025.12.xx-aarch64.iso`)
- Network connection during installation
- 64GB+ disk space for VM (128GB recommended)
- 8GB+ RAM recommended (4GB minimum)

## Step 1: Create VM

Use the automated VM creation script:

```bash
# From macOS host, run the VM creation script
./scripts/create-arch-vm.sh
```

Or create manually in Parallels:

1. **Type**: "Install Windows or another OS from a DVD or image file"
2. Select the archboot ISO
3. **OS Type**: Other Linux
4. Configure before first boot:
   - **CPU**: 4+ cores recommended
   - **RAM**: 8192MB (4096MB minimum)
   - **Disk**: 128GB (will be encrypted)
   - **Options > Advanced**: Enable **"Use Rosetta to run x86-64 binaries"**
   - **Options > Sharing**: Enable **"Share Mac folders with Linux"**
5. Start VM and boot into archboot live environment

## Step 2: Verify Network

```bash
# Check network interface
ip link

# Test connectivity
ping -c 3 archlinux.org

# If no network, configure manually:
# ip link set enp0s5 up
# dhcpcd enp0s5
```

## Step 3: Partition Disk

The disk layout uses two partitions: EFI System Partition and LUKS-encrypted root.

```bash
# List block devices - note your disk name
lsblk

# Parallels typically uses:
# - /dev/sda (SCSI emulation - most common)
# - /dev/vda (virtio - less common)

# Set variable for rest of guide (adjust if different)
DISK=/dev/sda

# Create partitions using fdisk
fdisk $DISK

# In fdisk:
# g         (create new GPT partition table)
# n, 1, default, +512M    (EFI partition - 512MB)
# t, 1      (change type to EFI System)
# n, 2, default, default  (root partition - rest of disk)
# w         (write changes and exit)

# Format EFI partition
mkfs.fat -F32 ${DISK}1
```

## Step 4: Setup LUKS Encryption

LUKS2 with argon2id key derivation provides strong encryption for Intune compliance.

**Template passphrase strategy**: During template creation, use a known passphrase (e.g., `4815162342`). After cloning, change it with `cryptsetup luksChangeKey`.

```bash
# Setup LUKS2 encryption
cryptsetup luksFormat --type luks2 \
  --cipher aes-xts-plain64 \
  --key-size 512 \
  --hash sha512 \
  --iter-time 5000 \
  ${DISK}2

# Enter and confirm encryption passphrase

# Open the encrypted partition
cryptsetup open ${DISK}2 cryptroot
# Enter passphrase

# Format the decrypted volume with btrfs
mkfs.btrfs /dev/mapper/cryptroot

# Mount filesystems
mount /dev/mapper/cryptroot /mnt
mkdir -p /mnt/boot
mount ${DISK}1 /mnt/boot
```

**Note**: The LUKS passphrase is separate from any user password - user accounts are created later.

## Step 5: Install Base System

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

# Set hostname (template name - will be changed in clones)
echo "archbase" > /etc/hostname

# Set root password (temporary - for recovery purposes)
passwd
```

## Step 6: Configure PAM Password Policy

Microsoft Intune requires password complexity. Configure this before creating user accounts:

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

**Important:** Any user passwords must meet these requirements:
- 12+ characters
- At least 1 uppercase (A-Z)
- At least 1 lowercase (a-z)
- At least 1 digit (0-9)
- At least 1 symbol (!@#$%^&*...)

## Step 7: Configure GRUB Bootloader

GRUB must be configured with the `encrypt` hook to prompt for LUKS passphrase at boot.

```bash
# Install bootloader packages
pacman -S grub efibootmgr

# Configure mkinitcpio for encryption
# Edit /etc/mkinitcpio.conf - set HOOKS exactly as follows (order matters!)
# The 'encrypt' hook MUST come after 'block' and before 'filesystems'
# The 'keyboard' hook MUST come before 'encrypt' (so you can type passphrase)

sed -i 's/^HOOKS=.*/HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt filesystems fsck)/' /etc/mkinitcpio.conf

# Verify HOOKS setting
grep "^HOOKS=" /etc/mkinitcpio.conf

# Create vconsole.conf (required by consolefont hook)
echo "KEYMAP=us" > /etc/vconsole.conf

# Regenerate initramfs
mkinitcpio -P

# CRITICAL: On ARM, the kernel is named 'Image', not 'vmlinuz-linux'
# GRUB's grub-mkconfig looks for vmlinuz-linux to find matching initramfs
# Without this symlink, GRUB won't load the initramfs and boot will fail!
ln -sf /boot/Image /boot/vmlinuz-linux

# Find UUID of encrypted partition
blkid -s UUID -o value /dev/sda2
# Note the UUID (e.g., xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)

# Configure GRUB for encryption
# Replace <your-uuid> with actual UUID from blkid above
LUKS_UUID=$(blkid -s UUID -o value /dev/sda2)
sed -i "s/GRUB_CMDLINE_LINUX=\"\"/GRUB_CMDLINE_LINUX=\"cryptdevice=UUID=${LUKS_UUID}:cryptroot root=\/dev\/mapper\/cryptroot\"/" /etc/default/grub

# Verify the setting
grep "GRUB_CMDLINE_LINUX=" /etc/default/grub

# Install GRUB to EFI
grub-install --target=arm64-efi --efi-directory=/boot --bootloader-id=GRUB

# Generate GRUB config - verify it finds BOTH vmlinuz-linux AND initramfs-linux.img
grub-mkconfig -o /boot/grub/grub.cfg
# Should show:
#   Found linux image: /boot/vmlinuz-linux
#   Found initrd image: /boot/initramfs-linux.img

# Verify initrd is in grub.cfg (critical!)
grep "initrd" /boot/grub/grub.cfg
# Should show: initrd /initramfs-linux.img

# Enable NetworkManager for post-boot networking
systemctl enable NetworkManager

# Exit chroot and reboot
exit
umount -R /mnt
reboot
```

**Critical Notes:**
- The `ln -sf /boot/Image /boot/vmlinuz-linux` step is essential on ARM
- Without it, grub-mkconfig won't find the initramfs
- If boot fails, the initramfs wasn't loaded (check this first)

## Verification

After reboot, verify the encrypted system works:

### During Boot
1. GRUB menu should appear
2. LUKS passphrase prompt should appear
3. Enter passphrase - system should boot to login prompt

### After Login
```bash
# Verify LUKS status
sudo cryptsetup status cryptroot
# Should show:
#   type:    LUKS2
#   cipher:  aes-xts-plain64
#   keysize: 512 bits
#   device:  /dev/sda2

# Check block devices
lsblk -f
# Should show /dev/sda2 as crypto_LUKS with cryptroot underneath

# Verify network
ip addr
ping -c 2 archlinux.org
```

## Troubleshooting

### Kernel Panic: Unable to Mount Root FS (No Passphrase Prompt)

If boot fails with "Kernel panic - not syncing: VFS: Unable to mount root fs" and no LUKS passphrase prompt appears:

```bash
# Boot from archboot ISO, mount and chroot
cryptsetup open /dev/sda2 cryptroot
mount /dev/mapper/cryptroot /mnt
mount /dev/sda1 /mnt/boot
arch-chroot /mnt

# Check if vmlinuz-linux exists
ls -la /boot/vmlinuz*
# If missing, create symlink:
ln -sf /boot/Image /boot/vmlinuz-linux

# Check if initrd is in grub.cfg
grep "initrd" /boot/grub/grub.cfg
# If no output, regenerate GRUB config:
grub-mkconfig -o /boot/grub/grub.cfg

# Verify it now shows:
#   Found linux image: /boot/vmlinuz-linux
#   Found initrd image: /boot/initramfs-linux.img
```

**Root cause:** On ARM, the kernel is named `Image` not `vmlinuz-linux`. Without `vmlinuz-linux`, grub-mkconfig doesn't find the matching initramfs.

### Wrong UUID in GRUB Config

```bash
# Get correct UUID
blkid /dev/sda2

# Edit GRUB config
vim /etc/default/grub
# Fix the cryptdevice=UUID=... line

# Regenerate GRUB
grub-mkconfig -o /boot/grub/grub.cfg
```

### Missing 'encrypt' Hook

```bash
# Check mkinitcpio.conf
grep "^HOOKS=" /etc/mkinitcpio.conf

# Should include 'encrypt' after 'block' and before 'filesystems'
# Also: 'keyboard' must come before 'encrypt'

# Fix if needed:
sed -i 's/^HOOKS=.*/HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt filesystems fsck)/' /etc/mkinitcpio.conf

# Regenerate initramfs
mkinitcpio -P
```

### Mirror Connection Failures During pacstrap

```bash
# Verify network connectivity
ping -c 2 ca.us.mirror.archlinuxarm.org

# Test mirror directly
curl -I http://ca.us.mirror.archlinuxarm.org/aarch64/core/core.db

# If using wrong mirror format, fix it:
# WRONG (standard Arch): $repo/os/$arch
# RIGHT (Arch Linux ARM): $arch/$repo
```

### No Network After Reboot

```bash
# Check NetworkManager status
systemctl status NetworkManager

# If not running
sudo systemctl enable --now NetworkManager

# Check connection
nmcli device status
nmcli connection show
```

## Next Steps

Once LUKS+GRUB boot is working, proceed to:
- [omarchy-grub-install.md](omarchy-grub-install.md) - Install Omarchy desktop while preserving GRUB bootloader

## References

- [Arch Wiki - dm-crypt/Encrypting an entire system](https://wiki.archlinux.org/title/Dm-crypt/Encrypting_an_entire_system)
- [Arch Wiki - GRUB](https://wiki.archlinux.org/title/GRUB)
- [Arch Wiki - mkinitcpio](https://wiki.archlinux.org/title/Mkinitcpio)
- [archboot](https://release.archboot.com/)
- [Arch Linux ARM Mirrors](https://archlinuxarm.org/about/mirrors)
