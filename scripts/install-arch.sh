#!/usr/bin/env bash
# Automated Arch Linux ARM installation for Parallels VM
# Run this inside archboot live environment
#
# Usage: curl -fsSL <raw-url> | bash
#    or: bash install-arch.sh [config-url]

set -euo pipefail

CONFIG_BASE="${1:-https://raw.githubusercontent.com/andrey-moor/dotfiles/main/scripts}"

echo "=================================================="
echo " Arch Linux ARM Automated Installation"
echo " For Parallels VM with LUKS encryption"
echo "=================================================="
echo ""

# Check we're in live environment
if [[ ! -d /run/archiso ]] && [[ ! -f /etc/arch-release ]]; then
    echo "[!] This script should be run from archboot live environment"
    exit 1
fi

# Ensure network is up
echo "[*] Checking network..."
if ! ping -c 1 archlinux.org &>/dev/null; then
    echo "[!] No network connectivity. Trying DHCP..."
    dhcpcd || dhclient || echo "DHCP failed - check network manually"
    sleep 3
fi

# Download configs
echo "[*] Downloading archinstall configuration..."
cd /tmp
curl -fsSL "$CONFIG_BASE/archinstall-config.json" -o config.json
curl -fsSL "$CONFIG_BASE/archinstall-creds.json" -o creds.json

echo "[*] Configuration downloaded. Starting archinstall..."
echo ""
echo "    LUKS password will be: temppass"
echo "    User account: user / temppass"
echo "    Root password: temppass"
echo ""
echo "    CHANGE THESE AFTER INSTALLATION!"
echo ""
sleep 3

# Run archinstall
archinstall --config config.json --creds creds.json --silent

echo ""
echo "[*] archinstall completed. Applying ARM64 GRUB fixes..."

# Mount installed system if not already mounted
if [[ ! -d /mnt/archinstall/boot ]]; then
    echo "[!] /mnt/archinstall not found - archinstall may have failed"
    exit 1
fi

# ARM64 kernel symlink fix
# GRUB expects vmlinuz-linux but ARM uses Image
if [[ -f /mnt/archinstall/boot/Image ]] && [[ ! -f /mnt/archinstall/boot/vmlinuz-linux ]]; then
    echo "[*] Creating ARM64 kernel symlink..."
    cp /mnt/archinstall/boot/Image /mnt/archinstall/boot/vmlinuz-linux
fi

# Ensure encrypt hook is in mkinitcpio.conf
echo "[*] Verifying mkinitcpio HOOKS..."
if ! grep -q "encrypt" /mnt/archinstall/etc/mkinitcpio.conf; then
    echo "[*] Adding encrypt hook to mkinitcpio.conf..."
    sed -i 's/^HOOKS=.*/HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt filesystems fsck)/' \
        /mnt/archinstall/etc/mkinitcpio.conf
fi

# Chroot and regenerate initramfs + GRUB config
echo "[*] Regenerating initramfs and GRUB config..."
arch-chroot /mnt/archinstall /bin/bash -c '
    # Regenerate initramfs with encrypt hook
    mkinitcpio -P

    # Get LUKS UUID and update GRUB
    LUKS_UUID=$(blkid -s UUID -o value /dev/sda3)

    # Update GRUB config
    sed -i "s|^GRUB_CMDLINE_LINUX=.*|GRUB_CMDLINE_LINUX=\"cryptdevice=UUID=$LUKS_UUID:cryptroot root=/dev/mapper/cryptroot\"|" /etc/default/grub

    # Regenerate GRUB config
    grub-mkconfig -o /boot/grub/grub.cfg

    # Enable services
    systemctl enable sshd
    systemctl enable NetworkManager
'

# Eject CD and prepare for reboot
echo ""
echo "=================================================="
echo " Installation Complete!"
echo "=================================================="
echo ""
echo " The VM will boot with LUKS encryption."
echo ""
echo " Default credentials (CHANGE IMMEDIATELY):"
echo "   LUKS passphrase: temppass"
echo "   User: user / temppass"
echo "   Root: root / temppass"
echo ""
echo " After reboot:"
echo "   1. Enter LUKS passphrase: temppass"
echo "   2. Login as user"
echo "   3. Change LUKS passphrase:"
echo "      sudo cryptsetup luksChangeKey /dev/sda3"
echo "   4. Change user password:"
echo "      passwd"
echo ""
echo " Ready to reboot? Run: reboot"
echo ""
