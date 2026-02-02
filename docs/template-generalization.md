# VM Template Generalization and Cloning

Generalize an Omarchy VM into a reusable template and create clones. Generalization removes machine-specific identifiers so each clone gets unique IDs on first boot.

## Prerequisites

- Working Omarchy system with GRUB+LUKS from [omarchy-grub-install.md](omarchy-grub-install.md)
- VM boots and decrypts successfully
- Hyprland desktop works

## Step 1: Generalize the System

Remove machine-specific identifiers before creating the template.

```bash
# Login to the VM (as root or with sudo)

# Set hostname to generic template name
echo "archbase" > /etc/hostname

# Clear machine-id (will regenerate on first boot of each clone)
# IMPORTANT: truncate, don't delete - file must exist but be empty
truncate -s 0 /etc/machine-id

# Remove SSH host keys (will regenerate on first boot)
rm -f /etc/ssh/ssh_host_*

# Clear pacman cache to reduce template size
pacman -Scc --noconfirm

# Clear shell history
rm -f /root/.bash_history
rm -f /home/*/.bash_history
rm -f /home/*/.zsh_history
history -c

# Clear temporary files
rm -rf /tmp/*
rm -rf /var/tmp/*

# Clear logs (optional, reduces size)
journalctl --vacuum-time=1s

# Verify encryption is working
cryptsetup status cryptroot

# Shutdown cleanly
shutdown -h now
```

## Step 2: Create Template Snapshot

After shutdown, create the final template snapshot from macOS host.

```bash
# Create template snapshot
prlctl snapshot "YourVMName" -n "Template-Ready-$(date +%Y-%m-%d)" -d "Generalized LUKS+GRUB+Omarchy template"

# Verify snapshot
prlctl snapshot-list "YourVMName"

# Check template size
du -sh ~/Parallels/YourVMName.pvm
```

**Naming convention**: Use `Template-Ready-YYYY-MM-DD` for easy identification.

## Step 3: Clone from Template

Create a new VM from the template.

```bash
# Clone the VM
# --name: Name for the new clone
# Full clone (independent copy):
prlctl clone "YourVMName" --name "NewVMName"

# Or linked clone (shares base disk, smaller):
prlctl clone "YourVMName" --name "NewVMName" --linked

# Start the clone
prlctl start "NewVMName"
```

**Full vs Linked Clone**:
- **Full clone**: Complete independent copy, larger disk usage, can delete template
- **Linked clone**: Shares base disk with template, smaller, template must be kept

## Step 4: Configure Clone

After booting the clone, configure machine-specific settings.

### Set New Hostname
```bash
# Set unique hostname
echo "your-new-hostname" | sudo tee /etc/hostname

# Update /etc/hosts if needed
sudo vim /etc/hosts
# Add: 127.0.1.1 your-new-hostname
```

### Verify Machine ID Regenerated
```bash
# Machine ID should be regenerated on first boot
cat /etc/machine-id
# Should show a new UUID (32 hex characters)
```

### Regenerate SSH Host Keys
```bash
# If not auto-generated, create new keys
sudo ssh-keygen -A

# Verify keys exist
ls -la /etc/ssh/ssh_host_*
```

### Change LUKS Passphrase

For security, change the template passphrase to a unique one.

```bash
# Change LUKS passphrase
sudo cryptsetup luksChangeKey /dev/sda2

# Prompts:
# - Enter current passphrase (template passphrase)
# - Enter new passphrase
# - Confirm new passphrase
```

### Configure User Account (if needed)
```bash
# If you want to change the username created by armarchy:
# 1. Create new user
sudo useradd -m -G wheel -s /bin/bash newuser
sudo passwd newuser

# 2. Copy desktop config (optional)
sudo cp -r /home/olduser/.config /home/newuser/
sudo chown -R newuser:newuser /home/newuser/

# 3. Remove old user (after verifying new user works)
sudo userdel -r olduser
```

## Verification

Verify the clone is properly individualized.

```bash
# Verify hostname is unique
hostname

# Verify machine-id is unique (compare to template if possible)
cat /etc/machine-id

# Verify SSH host keys exist and are different from template
ls -la /etc/ssh/ssh_host_*

# Verify LUKS works with new passphrase
# (reboot and test decryption)
sudo reboot
```

After reboot, confirm:
1. LUKS passphrase prompt appears
2. New passphrase works
3. Hostname is correct
4. Desktop loads properly

## Troubleshooting

### Clone Fails to Boot

```bash
# Boot from archboot ISO
cryptsetup open /dev/sda2 cryptroot
mount /dev/mapper/cryptroot /mnt
mount /dev/sda1 /mnt/boot
arch-chroot /mnt

# Check GRUB config
grep "cryptdevice" /etc/default/grub

# Regenerate initramfs and GRUB
mkinitcpio -P
grub-mkconfig -o /boot/grub/grub.cfg
```

### Machine ID Not Regenerating

```bash
# If machine-id is empty but not regenerating:
sudo systemd-machine-id-setup

# Verify
cat /etc/machine-id
```

### SSH Host Keys Not Generated

```bash
# Generate all key types
sudo ssh-keygen -A

# Restart SSH
sudo systemctl restart sshd
```

### Revert Clone to Template State

```bash
# From macOS host - restore clone to template snapshot
prlctl snapshot-list "NewVMName"
prlctl snapshot-switch "NewVMName" -i "{snapshot-uuid}"
```

## References

- [Parallels CLI Reference - prlctl](https://download.parallels.com/desktop/v18/docs/en_US/Parallels%20Desktop%20Pro%20Edition%20Command-Line%20Reference.pdf)
- [Arch Wiki - Machine ID](https://wiki.archlinux.org/title/Machine-id)
- [cryptsetup man page](https://man.archlinux.org/man/cryptsetup.8)
