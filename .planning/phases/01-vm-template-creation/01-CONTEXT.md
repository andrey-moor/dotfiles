# Phase 1: VM Template Creation - Context

**Gathered:** 2026-01-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Create an encrypted, generalized Arch Linux ARM VM template with GRUB bootloader and Omarchy desktop, ready for cloning. The template serves as a base image — personalization happens post-clone.

</domain>

<decisions>
## Implementation Decisions

### VM Configuration
- Resources: 4 CPU cores, 8GB RAM (standard dev workload)
- Shared folders: Mount full macOS home directory (access to dotfiles and other files)
- Rosetta: Enable in template (not post-clone)
- Network: Bridged networking (VM gets own IP, better for SSH access)

### Disk/Encryption Setup
- Partition scheme: EFI + /boot + LUKS (separate unencrypted /boot for GRUB reliability)
- LUKS: Version 2 with argon2id key derivation
- Filesystem: ext4 inside LUKS (simple, fast, good tooling)
- Disk size: 128GB

### Base System State
- Installation method: archinstall script with preset answers
- Desktop: Omarchy (Hyprland) — use PR #1897 for ARM64 support
- User account: Generic "user" account (personalized during clone)
- Services: SSH + NetworkManager enabled (display manager configured later via Nix)

### Template Documentation
- Location: hosts/endurance/README.md (discoverable next to Nix config)
- Style: Conceptual explanations followed by exact commands
- Screenshots: Text-only (easier to maintain)

### Claude's Discretion
- Troubleshooting placement (inline vs separate section)
- Exact archinstall preset configuration
- GRUB configuration details for LUKS2

</decisions>

<specifics>
## Specific Ideas

- Omarchy ARM64 support: Must use https://github.com/basecamp/omarchy/pull/1897
- Template should be minimal enough that Nix/home-manager (Phase 2) handles the real configuration
- SSH must work for prlctl exec commands from macOS host

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-vm-template-creation*
*Context gathered: 2026-01-31*
