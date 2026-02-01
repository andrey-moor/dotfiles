# STACK Research: Omarchy Linux VM Setup on Apple Silicon

Research on tooling and automation approaches for creating Intune-compliant Arch Linux ARM VMs on Parallels Desktop (Apple Silicon).

## 1. VM Automation (Parallels prlctl)

### Available Automation Commands

Parallels Desktop 26.x provides comprehensive CLI automation via `prlctl`:

```bash
# Create VM from scratch (limited for ARM Linux - no good templates)
prlctl create <name> -o linux --distribution arch

# Clone existing VM (recommended approach)
prlctl clone <source_vm> --name <new_name> [--dst <path>]

# Create linked clone from snapshot (space-efficient)
prlctl clone <source_vm> --name <new_name> --linked --id <snapshot_id>

# Snapshot management
prlctl snapshot <vm_name> -n "SnapshotName" -d "Description"
prlctl snapshot-list <vm_name> --tree
prlctl snapshot-switch <vm_name> --id <snapshot_id>

# VM configuration
prlctl set <vm_name> --rosetta-linux on
prlctl set <vm_name> --cpus 4 --memsize 8192
prlctl set <vm_name> shared_folders --shf-host-defined home

# Execute commands in guest
prlctl exec <vm_name> <command>
prlctl exec <vm_name> --user <user> --password <pass> <command>

# Register/unregister VMs
prlctl register /path/to/vm.pvm
prlctl unregister <vm_name>
```

### Recommended Workflow: Template + Clone

The most practical approach for reproducible VM creation:

1. **Create base template manually** (one-time):
   - Install Arch Linux ARM via archboot ISO with LUKS
   - Configure GRUB with encrypt hook
   - Install base packages (wget, sudo)
   - Generalize (clear machine-id, history)
   - Create snapshot: `prlctl snapshot stargazer -n "EncryptedBase-GRUB"`

2. **Export as compressed archive**:
   ```bash
   cd ~/Parallels
   tar -cvf - ArchBase-Template.pvm | zstd -T0 -19 > ArchBase-Template.pvm.tar.zst
   ```

3. **Clone for new VMs**:
   ```bash
   # Extract template
   zstd -d ArchBase-Template.pvm.tar.zst -c | tar -xvf -
   prlctl register ~/Parallels/ArchBase-Template.pvm

   # Clone
   prlctl clone ArchBase-Template --name "newvm" --regenerate-src-uuid
   prlctl set newvm --rosetta-linux on
   prlctl start newvm
   ```

### Packer Integration (Advanced)

Parallels has a Packer plugin for automated image creation:

```hcl
packer {
  required_plugins {
    parallels = {
      version = ">= 1.1.5"
      source  = "github.com/parallels/parallels"
    }
  }
}

source "parallels-iso" "archlinux" {
  guest_os_type           = "linux"
  iso_url                 = "https://release.archboot.com/aarch64/latest/iso/archboot-*.iso"
  iso_checksum            = "file:https://release.archboot.com/aarch64/latest/iso/sha256sum.txt"
  parallels_tools_flavor  = "lin-arm"
  ssh_username            = "root"
  ssh_password            = "password"
  boot_command            = ["..."]
  shutdown_command        = "shutdown -h now"
}
```

**Limitation**: Packer boot_command automation is difficult for LUKS setup because:
- Encryption passphrase entry is interactive
- fdisk/cryptsetup require careful timing
- archboot environment differs from standard installers

**Recommendation**: Packer is better suited for post-encryption provisioning using `parallels-pvm` builder with an existing encrypted template.

### What Can Be Automated vs Manual

| Step | Automatable | Notes |
|------|-------------|-------|
| VM creation | Yes | `prlctl create` or clone |
| Rosetta enable | Yes | `prlctl set --rosetta-linux on` |
| Shared folders | Yes | `prlctl set shared_folders --shf-host-defined home` |
| ISO boot | Yes | Via Packer or manual |
| LUKS passphrase entry | **No** | Interactive at boot |
| Partition/encryption setup | Partial | Can script, but requires passphrase |
| Base OS install | Partial | archboot has limited automation |
| Post-install config | Yes | Via `prlctl exec` or SSH |
| Nix/home-manager | Yes | Full automation via scripts |

## 2. Arch Linux ARM Installation Automation

### archboot Limitations

The archboot ISO for aarch64 does not support full unattended installation:
- No preseed/kickstart equivalent
- `archinstall` guided installer requires interaction
- LUKS passphrase must be entered manually

### archinstall JSON Configuration

archinstall supports JSON configs for semi-automated installs:

```json
{
  "audio_config": null,
  "bootloader": "grub-install",
  "config_version": "2.8.1",
  "disk_config": {
    "config_type": "manual_partitioning",
    "device_modifications": [...]
  },
  "hostname": "archvm",
  "locale_config": {
    "kb_layout": "us",
    "sys_enc": "UTF-8",
    "sys_lang": "en_US"
  },
  "mirror_config": {
    "mirror_regions": {"United States": [...]}
  },
  "disk_encryption": {
    "encryption_type": "luks",
    "encryption_password": "..."
  }
}
```

**Usage**:
```bash
archinstall --config /path/to/config.json --disk-layout /path/to/disk.json
```

**Limitation**: Even with JSON config, LUKS encryption password is stored in plaintext config file (security concern) and may still require confirmation.

### Recommended Semi-Automated Approach

Create a setup script that runs after manual LUKS setup:

```bash
#!/bin/bash
# post-luks-setup.sh - Run after LUKS partition is created and opened

DISK=/dev/sda
CRYPTDEV=/dev/mapper/cryptroot

# Format and mount
mkfs.btrfs $CRYPTDEV
mount $CRYPTDEV /mnt
mkdir -p /mnt/boot
mount ${DISK}1 /mnt/boot

# Configure mirrors
cat > /etc/pacman.d/mirrorlist << 'EOF'
Server = http://ca.us.mirror.archlinuxarm.org/$arch/$repo
Server = http://fl.us.mirror.archlinuxarm.org/$arch/$repo
EOF

# Install base system
pacstrap /mnt base linux linux-firmware btrfs-progs sudo networkmanager grub efibootmgr libpwquality wget

# Generate fstab
genfstab -U /mnt >> /mnt/etc/fstab

# Chroot and configure
arch-chroot /mnt /bin/bash << 'CHROOT'
# Timezone
ln -sf /usr/share/zoneinfo/America/Los_Angeles /etc/localtime
hwclock --systohc

# Locale
echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
locale-gen
echo "LANG=en_US.UTF-8" > /etc/locale.conf
echo "KEYMAP=us" > /etc/vconsole.conf

# mkinitcpio with encrypt hook
sed -i 's/^HOOKS=.*/HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt filesystems fsck)/' /etc/mkinitcpio.conf
mkinitcpio -P

# ARM kernel symlink for GRUB
cp /boot/Image /boot/vmlinuz-linux

# GRUB config - UUID will need manual substitution
# sed -i "s/GRUB_CMDLINE_LINUX=\"\"/GRUB_CMDLINE_LINUX=\"cryptdevice=UUID=<UUID>:cryptroot root=\/dev\/mapper\/cryptroot\"/" /etc/default/grub

# Install GRUB
grub-install --target=arm64-efi --efi-directory=/boot --bootloader-id=GRUB
grub-mkconfig -o /boot/grub/grub.cfg

# Enable services
systemctl enable NetworkManager
CHROOT
```

## 3. LUKS Encryption Setup Automation

### Standard cryptsetup Commands

```bash
# Create LUKS2 partition
cryptsetup luksFormat --type luks2 \
  --cipher aes-xts-plain64 \
  --key-size 512 \
  --hash sha512 \
  --iter-time 5000 \
  /dev/sda2

# Open encrypted partition
cryptsetup open /dev/sda2 cryptroot

# Get UUID for GRUB config
blkid -s UUID -o value /dev/sda2
```

### Automation Approaches

**Option 1: Keyfile (not recommended for Intune)**
```bash
# Create keyfile
dd if=/dev/urandom of=/root/keyfile bs=1024 count=4
chmod 400 /root/keyfile
cryptsetup luksAddKey /dev/sda2 /root/keyfile
```
- Reduces boot security
- May fail Intune compliance checks

**Option 2: TPM2 Auto-unlock (if available)**
```bash
# Using systemd-cryptenroll (requires TPM2)
systemd-cryptenroll --tpm2-device=auto /dev/sda2
```
- Parallels VMs don't have TPM2
- Not applicable for this use case

**Option 3: Password at boot (current approach)**
- Manual passphrase entry required
- Most secure for compliance
- Cannot be fully automated

### Intune Compliance Requirements

Intune requires dm-crypt/LUKS for disk encryption compliance:
- Must use LUKS (any version)
- No keyfile-only unlock (password required)
- PAM password policy compliance (12+ chars, complexity)

```bash
# Password policy for Intune
cat > /etc/security/pwquality.conf << 'EOF'
minlen = 12
dcredit = -1
ucredit = -1
lcredit = -1
ocredit = -1
EOF
```

## 4. Rosetta binfmt Registration (Survives Reboot)

### The Race Condition Problem

Parallels shared folders (including `/mnt/psf/RosettaLinux/rosetta`) are mounted by `prltoolsd` (Parallels Tools daemon), not systemd. This creates a timing issue:

1. `systemd-binfmt.service` runs early in boot
2. Parallels shared folders mount later via prltoolsd
3. binfmt registration fails because Rosetta binary doesn't exist yet
4. Result: x86_64 binaries fail to execute after reboot

### Solution: systemd Path Unit

Use a path unit to watch for the Rosetta binary and trigger binfmt re-registration:

```bash
# /etc/binfmt.d/rosetta.conf
:rosetta:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x3e\x00:\xff\xff\xff\xff\xff\xfe\xfe\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/mnt/psf/RosettaLinux/rosetta:PFC
```

```ini
# /etc/systemd/system/rosetta-binfmt.path
[Unit]
Description=Watch for Rosetta binary to appear

[Path]
PathExists=/mnt/psf/RosettaLinux/rosetta
Unit=rosetta-binfmt.service

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/rosetta-binfmt.service
[Unit]
Description=Register Rosetta binfmt after mount

[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl restart systemd-binfmt
RemainAfterExit=yes
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable rosetta-binfmt.path
```

### How It Works

1. `rosetta-binfmt.path` is enabled and starts at boot
2. Path unit uses inotify to watch for `/mnt/psf/RosettaLinux/rosetta`
3. When Parallels mounts shared folders, the rosetta binary appears
4. Path unit triggers `rosetta-binfmt.service`
5. Service restarts `systemd-binfmt`, which now finds the binary
6. binfmt_misc registration succeeds

### Alternative: Timer-based Retry (Less Elegant)

```ini
# /etc/systemd/system/rosetta-binfmt-retry.timer
[Unit]
Description=Retry Rosetta binfmt registration

[Timer]
OnBootSec=30s
OnUnitActiveSec=60s

[Install]
WantedBy=timers.target
```

### Verification

```bash
# Check if binfmt is registered
cat /proc/sys/fs/binfmt_misc/rosetta
# Should show: enabled, interpreter /mnt/psf/RosettaLinux/rosetta

# Test x86_64 binary execution
file /mnt/psf/RosettaLinux/rosetta  # Should show x86-64
echo 'int main() { return 0; }' | gcc -x c - -o /tmp/test_x86 -m64 2>/dev/null || \
  /mnt/psf/RosettaLinux/rosetta /bin/true && echo "Rosetta works"
```

### x86_64 Dynamic Linker Setup

Rosetta-translated binaries need the x86_64 glibc dynamic linker:

```bash
# Build glibc for x86_64 via Nix
GLIBC_PATH=$(nix build --no-link --print-out-paths nixpkgs#pkgsCross.gnu64.glibc)

# Create standard path
sudo mkdir -p /lib64
sudo chmod 755 /lib64
sudo ln -sf "$GLIBC_PATH/lib/ld-linux-x86-64.so.2" /lib64/
```

### Nix Configuration for x86_64 Support

```bash
# Determinate Nix uses nix.custom.conf for user settings
echo "extra-platforms = x86_64-linux" | sudo tee -a /etc/nix/nix.custom.conf
sudo systemctl restart nix-daemon

# Verify
nix show-config | grep extra-platforms
# Should show: extra-platforms = x86_64-linux
```

## Summary: Automation Matrix

| Component | Fully Automatable | Semi-Automatable | Manual Only |
|-----------|-------------------|------------------|-------------|
| VM creation/clone | Yes | - | - |
| Rosetta enable | Yes | - | - |
| Parallels settings | Yes | - | - |
| Disk partitioning | - | Script after boot | - |
| LUKS encryption setup | - | Script (needs passphrase) | - |
| LUKS passphrase at boot | - | - | Yes |
| Base OS install | - | archinstall + JSON | - |
| GRUB + encrypt hook | - | Script in chroot | - |
| Omarchy install | Yes | - | - |
| Nix install | Yes | - | - |
| binfmt registration | Yes | - | - |
| Home-manager switch | Yes | - | - |
| Intune enrollment | - | - | Yes (interactive) |

## Recommended Implementation Order

1. **Create base template** (manual, one-time)
   - archboot ISO boot
   - Manual LUKS setup with passphrase
   - Run post-LUKS automation script
   - Install Omarchy via armarchy
   - Generalize and snapshot

2. **Automate cloning** (script)
   - Extract template archive
   - Clone with prlctl
   - Configure VM settings

3. **Automate post-clone setup** (script via SSH or prlctl exec)
   - Rosetta binfmt path unit
   - Nix installation
   - Home-manager switch
   - Intune prerequisites (os-release, D-Bus, etc.)

4. **Manual final steps**
   - Intune portal enrollment
   - YubiKey PIV setup
   - Verification

---

*Research completed: 2026-01-31*
*Based on: Parallels Desktop 26.2.1, archboot aarch64, existing stargazer/endurance VMs*
