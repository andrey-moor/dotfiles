# Phase 1: VM Template Creation - Context

**Gathered:** 2026-02-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Create an encrypted, generalized Arch Linux ARM VM template with working bootloader (GRUB or Limine) and Omarchy desktop, ready for cloning. The template serves as a base image — personalization happens post-clone. Intune compliance requires disk encryption.

</domain>

<decisions>
## Implementation Decisions

### Installation Approach
- Source: archboot ISO (boots to shell, manual install)
- Process: Semi-manual with Claude typing assist via `prlctl send-key-event`
- Sequence: (1) LUKS setup → (2) Base Arch install → (3) Omarchy from PR #1897
- Claude can type commands when user requests, including LUKS passphrase if user provides it (never hardcoded)

### VM Configuration
- Resources: 4 CPU cores, 8GB RAM (standard dev workload)
- Shared folders: Mount full macOS home directory (access to dotfiles and other files)
- Rosetta: Enable in template (not post-clone)
- Network: DHCP automatic via dhcpcd or NetworkManager
- Disk size: 128GB

### Disk/Encryption Setup
- Partition scheme: EFI + LUKS (2-partition, EFI mounted at /boot per docs/rocinante-encrypted-install.md)
- LUKS: Version 2 with argon2id key derivation
- Filesystem: btrfs inside LUKS (modern, snapshots, used in proven rocinante install)

### Bootloader
- **Research needed**: Limine (Omarchy default) vs GRUB for LUKS on ARM64
- Research should determine which is more compatible with LUKS2 + argon2id on ARM64

### Omarchy Installation
- Use PR #1897: https://github.com/basecamp/omarchy/pull/1897 (ARM64 support)
- Install method: `curl | bash` from PR branch
- Installed AFTER base Arch + LUKS is working

### Template State
- User account: Generic "user" account (personalized during clone)
- Services: SSH + NetworkManager enabled
- Template should be minimal — Nix/home-manager (Phase 2) handles real configuration

### Documentation
- Location: hosts/endurance/README.md (discoverable next to Nix config)
- Style: Step-by-step guide with Claude typing assist suggestions
- Format: Text-only (easier to maintain)

### Claude's Discretion
- Troubleshooting placement (inline vs separate section)
- Exact partitioning commands for archboot
- mkinitcpio HOOKS configuration for LUKS

</decisions>

<specifics>
## Specific Ideas

- Claude typing assist: Use prl-type.sh and VM-KEYBOARD.md for send-key-event automation
- LUKS passphrase: User provides at runtime, never stored in scripts (can be changed post-clone via `cryptsetup luksChangeKey`)
- Omarchy ARM64: Must use PR #1897, not mainline
- Template minimal: SSH must work for prlctl exec commands from macOS host

</specifics>

<lessons_learned>
## Lessons Learned (2026-02-02)

### prl-type.sh Bug Fix
The original prl-type.sh had a race condition with shifted characters (uppercase, symbols like `:@#$`). The shift key was pressed but the next key was sent before the VM registered shift, resulting in unshifted characters (e.g., `:` became `;`).

**Fix:** Added `sleep "$SLEEP"` after pressing shift in `send_shifted_key()` function.

**Testing approach:**
1. Run: `./scripts/prl-type.sh "TEST: @#$ /dev/sda2"`
2. Verify with screenshot: `prlctl capture <VM> --file /tmp/test.png`
3. Check that colons, uppercase, and symbols appear correctly

### Input Methods
Users can choose between:
1. **Manual typing** in Parallels VM console window — most reliable
2. **Scripted via prl-type.sh** — convenient for Claude assist, requires working script

When automation fails, fall back to manual typing. The docs should mention both options.

### LUKS Passphrase Management
- Template uses a known passphrase (e.g., `4815162342`)
- After cloning, change it: `sudo cryptsetup luksChangeKey /dev/sda2`
- This allows automation during template creation while maintaining security for real VMs

</lessons_learned>

<deferred>
## Deferred Ideas

- Full automation of VM creation (the archinstall scripting approach we abandoned)
- Clone scripts for VM duplication — Phase 3

</deferred>

---

*Phase: 01-vm-template-creation*
*Context gathered: 2026-02-01*
