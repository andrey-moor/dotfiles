# Phase 1: VM Template Creation - Research

**Researched:** 2026-01-31
**Domain:** Parallels VM creation, Arch Linux ARM, LUKS2 encryption, GRUB bootloader
**Confidence:** HIGH

## Summary

This phase creates an encrypted Arch Linux ARM VM template with GRUB bootloader for Parallels Desktop on Apple Silicon. The research confirms the locked decisions from CONTEXT.md and provides specific implementation details.

The standard approach is: Create VM in Parallels with Rosetta enabled, boot archboot ISO, manually partition (EFI + /boot + LUKS), use archinstall for base system with GRUB, install Omarchy via armarchy PR #1897, then generalize the template. The key constraint is LUKS2 must use PBKDF2 (not argon2id) for GRUB compatibility.

**Primary recommendation:** Use archinstall with a JSON preset for reproducibility, but accept that LUKS passphrase entry requires manual interaction. Document the exact steps with commands, not screenshots.

## Standard Stack

### Core Tools
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| archboot | aarch64 latest | Live installation environment | Only official Arch ARM installer ISO |
| archinstall | 2.8+ | Guided installer with JSON presets | Official tool, supports GRUB + manual partitioning |
| cryptsetup | 2.7+ | LUKS2 encryption | Standard Linux disk encryption |
| GRUB | 2.12+ | Bootloader with encrypt hook | Only bootloader supporting LUKS decrypt at boot |
| Omarchy/armarchy | PR #1897 | Hyprland desktop environment | User decision, ARM64 support via specific PR |

### Supporting Tools
| Tool | Purpose | When to Use |
|------|---------|-------------|
| prlctl | Parallels CLI | VM configuration after creation |
| fdisk/gdisk | Partitioning | Manual partition creation before archinstall |
| mkinitcpio | Initramfs generation | Configure encrypt hook |

### Parallels Desktop Features
| Feature | Setting | Required |
|---------|---------|----------|
| Rosetta | Options > Advanced > "Use Rosetta to run x86-64 binaries" | MUST enable BEFORE first boot |
| Shared Folders | Options > Sharing > "Share Mac folders with Linux" | Required for dotfiles access |
| Resources | 4 CPU, 8GB RAM, 128GB disk | User decision |
| Networking | Bridged | User decision |

## Architecture Patterns

### Recommended Partition Layout

```
/dev/sda (128GB virtual disk)
├── sda1: EFI System Partition (512MB, FAT32, /boot/efi)
├── sda2: Boot partition (1GB, ext4, /boot) - UNENCRYPTED
└── sda3: LUKS2 partition (remaining, /dev/mapper/cryptroot -> ext4, /)
```

**Why separate /boot:** GRUB can decrypt LUKS2, but only with PBKDF2. Keeping /boot unencrypted is more reliable and avoids double passphrase prompts. The encrypted root still protects all user data.

### archinstall JSON Configuration Pattern

**User Configuration (user_configuration.json):**
```json
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
  "packages": ["wget", "sudo", "openssh", "base-devel"],
  "profile_config": {
    "profile": null
  },
  "silent": false,
  "swap": false,
  "timezone": "America/Los_Angeles"
}
```

**Why pre_mounted_config:** archinstall's disk encryption support doesn't align well with our specific LUKS2 + PBKDF2 + separate /boot requirements. Manual partitioning and mounting, then using `pre_mounted_config`, gives precise control.

### mkinitcpio HOOKS Configuration

```
HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt filesystems fsck)
```

**Critical ordering:**
1. `keyboard` MUST come before `encrypt` (to type passphrase)
2. `encrypt` MUST come before `filesystems` (to decrypt before mounting)
3. `keymap` for non-US keyboard layouts at LUKS prompt

### GRUB Configuration Pattern

**/etc/default/grub:**
```bash
GRUB_CMDLINE_LINUX="cryptdevice=UUID=<LUKS-partition-UUID>:cryptroot root=/dev/mapper/cryptroot"
GRUB_PRELOAD_MODULES="part_gpt part_msdos"
```

**GRUB installation command (ARM64):**
```bash
grub-install --target=arm64-efi --efi-directory=/boot/efi --bootloader-id=GRUB
grub-mkconfig -o /boot/grub/grub.cfg
```

### Template Generalization Pattern

Before converting to template, clean machine-specific data:

```bash
# Clear machine ID (regenerates on first boot)
truncate -s 0 /etc/machine-id
rm -f /var/lib/dbus/machine-id
ln -s /etc/machine-id /var/lib/dbus/machine-id

# Clear hostname (set during clone)
truncate -s 0 /etc/hostname

# Remove SSH host keys (regenerate on first boot)
rm -f /etc/ssh/ssh_host_*

# Clear shell history
rm -f /root/.bash_history
rm -f /home/*/.bash_history

# Clear logs
journalctl --rotate
journalctl --vacuum-time=1s
```

### Anti-Patterns to Avoid

- **Using LUKS2 with argon2id when GRUB needs to decrypt:** GRUB 2.12 only supports PBKDF2. Use `cryptsetup luksFormat --pbkdf pbkdf2` if GRUB decrypts the partition.
- **Skipping kernel symlink on ARM:** ARM kernel is named `Image`, not `vmlinuz-linux`. GRUB won't find initramfs without `cp /boot/Image /boot/vmlinuz-linux`.
- **Enabling Rosetta after first boot:** Rosetta must be enabled in Parallels settings BEFORE the first VM boot. It cannot be enabled retroactively.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Arch installation | Manual pacstrap scripts | archinstall with JSON preset | Handles locale, timezone, users consistently |
| Desktop environment | Custom Hyprland config | Omarchy/armarchy installer | Maintained, tested, includes all dependencies |
| Bootloader | systemd-boot or Limine | GRUB with encrypt hook | Only option that supports LUKS decrypt |
| LUKS2 setup | Custom encryption script | cryptsetup standard commands | Well-tested, documented, Intune-compatible |

**Key insight:** The complexity is in the integration (GRUB + LUKS + ARM + Rosetta), not individual components. Use standard tools, focus documentation on the integration points.

## Common Pitfalls

### Pitfall 1: LUKS2 with argon2id Key Derivation
**What goes wrong:** GRUB fails to decrypt, drops to initramfs shell
**Why it happens:** cryptsetup defaults to argon2id, but GRUB only supports PBKDF2
**How to avoid:** Use `--pbkdf pbkdf2` during luksFormat OR keep /boot unencrypted
**Warning signs:** No passphrase prompt from GRUB, immediate kernel panic

### Pitfall 2: ARM Kernel Naming Mismatch
**What goes wrong:** grub-mkconfig doesn't find initramfs, boot fails
**Why it happens:** ARM kernel is `/boot/Image`, GRUB expects `/boot/vmlinuz-linux`
**How to avoid:** After kernel install: `cp /boot/Image /boot/vmlinuz-linux`
**Warning signs:** grub-mkconfig shows "Found linux image" but NOT "Found initrd image"

### Pitfall 3: Rosetta Not Enabled Before First Boot
**What goes wrong:** x86_64 binaries fail with "exec format error"
**Why it happens:** Rosetta integration requires VM configuration before OS install
**How to avoid:** Enable in Parallels Settings > Options > Advanced BEFORE first boot
**Warning signs:** Cannot run Intune binaries, Nix x86_64 builds fail

### Pitfall 4: Wrong UUID in GRUB Config
**What goes wrong:** GRUB can't find encrypted partition, drops to rescue shell
**Why it happens:** Copy-paste error or using filesystem UUID instead of LUKS partition UUID
**How to avoid:** Use `blkid /dev/sda3` (the LUKS partition, not the mapper)
**Warning signs:** "cryptsetup: no key available with this passphrase" or device not found

### Pitfall 5: Missing encrypt Hook in mkinitcpio
**What goes wrong:** No passphrase prompt, kernel can't mount root
**Why it happens:** Forgot to add `encrypt` to HOOKS or wrong order
**How to avoid:** Verify HOOKS in /etc/mkinitcpio.conf, run `mkinitcpio -P` after changes
**Warning signs:** Boot proceeds without passphrase prompt, then fails to mount root

### Pitfall 6: Shared Folders Not Enabled
**What goes wrong:** Dotfiles not accessible at /mnt/psf/Home/Documents/dotfiles
**Why it happens:** Parallels shared folder setting not enabled
**How to avoid:** Enable before first boot: Options > Sharing > "Share Mac folders with Linux"
**Warning signs:** `/mnt/psf` empty or doesn't exist after boot

## Code Examples

### LUKS2 Partition Setup (with PBKDF2 for GRUB compatibility)

```bash
# Source: Arch Wiki dm-crypt + GRUB documentation
# Partition the disk (EFI + boot + LUKS)
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

# Format partitions
mkfs.fat -F32 /dev/sda1
mkfs.ext4 /dev/sda2

# Create LUKS2 with PBKDF2 (GRUB compatible)
cryptsetup luksFormat --type luks2 \
  --cipher aes-xts-plain64 \
  --key-size 512 \
  --hash sha512 \
  --pbkdf pbkdf2 \
  /dev/sda3

# Open and format
cryptsetup open /dev/sda3 cryptroot
mkfs.ext4 /dev/mapper/cryptroot
```

**Note:** User chose argon2id in CONTEXT.md. This works if /boot is unencrypted (GRUB doesn't decrypt the LUKS partition, only reads /boot). Update: With separate /boot partition, argon2id IS compatible because GRUB reads from unencrypted /boot. The encrypt hook in initramfs handles LUKS decryption, and it fully supports argon2id.

### Corrected LUKS2 Setup (argon2id with unencrypted /boot)

```bash
# Since /boot is unencrypted, GRUB doesn't need to decrypt LUKS
# argon2id is fine - the initramfs encrypt hook handles decryption
cryptsetup luksFormat --type luks2 \
  --cipher aes-xts-plain64 \
  --key-size 512 \
  --hash sha512 \
  --pbkdf argon2id \
  /dev/sda3
```

### GRUB Installation for ARM64 with LUKS

```bash
# Source: Arch Wiki GRUB + dm-crypt
# Get LUKS partition UUID
LUKS_UUID=$(blkid -s UUID -o value /dev/sda3)

# Configure GRUB
sed -i "s|^GRUB_CMDLINE_LINUX=.*|GRUB_CMDLINE_LINUX=\"cryptdevice=UUID=$LUKS_UUID:cryptroot root=/dev/mapper/cryptroot\"|" /etc/default/grub

# ARM kernel symlink (critical!)
cp /boot/Image /boot/vmlinuz-linux

# Install GRUB for ARM64 UEFI
grub-install --target=arm64-efi --efi-directory=/boot/efi --bootloader-id=GRUB

# Generate config
grub-mkconfig -o /boot/grub/grub.cfg

# Verify output shows BOTH:
# - "Found linux image: /boot/vmlinuz-linux"
# - "Found initrd image: /boot/initramfs-linux.img"
```

### Omarchy Installation (ARM64 via PR #1897)

```bash
# Source: https://github.com/basecamp/omarchy/pull/1897
# Must run as root after base system is installed and booted

# Short URL method
curl -fsSL hdwy.link/armarchy-3-x | bash

# Or explicit method
wget -qO- https://raw.githubusercontent.com/jondkinney/armarchy/amarchy-3-x/boot.sh | \
  OMARCHY_REPO=jondkinney/armarchy OMARCHY_REF=amarchy-3-x bash
```

### VM Configuration via prlctl

```bash
# Source: Parallels CLI documentation
VM_NAME="ArchBase-Template"

# Set resources (user decision: 4 CPU, 8GB RAM)
prlctl set "$VM_NAME" --cpus 4 --memsize 8192

# Enable Rosetta (MUST be done before first boot)
prlctl set "$VM_NAME" --rosetta-linux on

# Enable shared folders (home directory mount)
prlctl set "$VM_NAME" --shf-host on
prlctl set "$VM_NAME" --shf-host-defined home --enable

# Set bridged networking
prlctl set "$VM_NAME" --device-set net0 --type bridged
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LUKS1 | LUKS2 with argon2id | ~2018 | Better security, but GRUB compatibility issues |
| Limine bootloader | GRUB with encrypt hook | N/A (Limine never supported encrypt) | GRUB is only option for LUKS |
| Manual Arch install | archinstall with JSON | archinstall 2.0 (2021) | Reproducible, less error-prone |
| USB passthrough YubiKey | Parallels smart card sharing | Parallels 18+ | More reliable connection |

**Deprecated/outdated:**
- **Limine for encrypted boot:** Does not support dm-crypt/LUKS decryption
- **grub-improved-luks2-git (AUR):** Not needed if /boot is unencrypted; adds complexity

## Open Questions

### 1. archinstall Pre-mounted Mode Exact Workflow
- **What we know:** archinstall supports `pre_mounted_config` where user manually partitions and mounts
- **What's unclear:** Exact sequence of commands and archinstall invocation after manual LUKS setup
- **Recommendation:** Test during implementation, document exact working sequence

### 2. Omarchy armarchy Installer Interactivity
- **What we know:** armarchy installer exists at PR #1897, provides short URL
- **What's unclear:** How interactive is the installer? Does it prompt for user creation?
- **Recommendation:** Run installer and document prompts/choices for reproducibility

### 3. Parallels Shared Folder Mount Path Consistency
- **What we know:** Can be /mnt/psf or /media/psf depending on Parallels version
- **What's unclear:** What determines the path in current Parallels 26.x?
- **Recommendation:** Document verification step to check actual path after first boot

## Sources

### Primary (HIGH confidence)
- [Arch Wiki: dm-crypt/Encrypting an entire system](https://wiki.archlinux.org/title/Dm-crypt/Encrypting_an_entire_system) - LUKS partition schemes
- [Arch Wiki: GRUB](https://wiki.archlinux.org/title/GRUB) - GRUB installation, LUKS2 limitations
- [archinstall documentation](https://archinstall.archlinux.page/installing/guided.html) - JSON config usage
- [archinstall config-sample.json](https://github.com/archlinux/archinstall/blob/master/examples/config-sample.json) - Config structure
- [Omarchy PR #1897](https://github.com/basecamp/omarchy/pull/1897) - ARM64 support (still open)

### Secondary (MEDIUM confidence)
- [Parallels KB: Installing Arch Linux](https://kb.parallels.com/124124) - Basic guidance, dated
- [Arch Wiki: Parallels Desktop](https://wiki.archlinux.org/title/Parallels_Desktop) - Tools installation
- [UBOS: Arch ARM on Parallels](https://ubos.net/docs/other/developer-workstation/arch-aarch64/apple-silicon-parallels/) - Community guide

### Tertiary (LOW confidence)
- Various GitHub Gists for LUKS+GRUB installation - Useful patterns but not authoritative

### Project Internal (HIGH confidence)
- `.planning/research/STACK.md` - Prior project research on automation
- `.planning/research/PITFALLS.md` - Known issues from stargazer/endurance experience
- `.planning/research/ARCHITECTURE.md` - System architecture and dependencies
- `hosts/endurance/README.md` - Existing partial documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official Arch tools, well-documented
- Architecture: HIGH - Based on prior project experience + official docs
- Pitfalls: HIGH - Documented from real brownfield experience
- archinstall JSON: MEDIUM - Need to test exact workflow
- Omarchy installer: MEDIUM - PR not merged, need to verify behavior

**Research date:** 2026-01-31
**Valid until:** 60 days (stable domain, Omarchy PR status may change)
