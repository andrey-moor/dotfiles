# Omarchy Linux VM Setup for Intune

## What This Is

A reproducible setup process for creating Omarchy Linux VMs on Parallels (Apple Silicon) with full Microsoft Intune enrollment via YubiKey. This includes documentation, automation scripts, and clean Nix modules that handle the complexity of running x86_64 Intune binaries on aarch64-linux via Rosetta emulation.

## Core Value

A developer can create an Intune-compliant Linux workstation on Apple Silicon by following documented steps, with automation for error-prone parts and clean Nix modules for the complex bits.

## Requirements

### Validated

- Rosetta binfmt registration for x86_64 emulation — existing
- intune-portal x86_64 wrapper with proper library paths — existing
- microsoft-identity-broker D-Bus service activation — existing
- microsoft-identity-device-broker systemd service — existing
- Edge browser with Mesa llvmpipe software rendering — existing
- YubiKey PIV certificate authentication via PKCS#11 — existing

### Active

- [ ] VM creation automation with LUKS encryption
- [ ] binfmt registration that survives reboot (race condition fix)
- [ ] Documented e2e setup from VM creation to enrollment
- [ ] Nix module cleanup (lean, well-designed intune-rosetta)
- [ ] Permission-safe nix switch (works from both prlctl and SSH)
- [ ] D-Bus/keyring credential storage reliability
- [ ] Bootloader investigation (Limine with encrypt hook vs GRUB)
- [ ] Omarchy update/upgrade story documented

### Out of Scope

- Native x86_64 Linux setup (Rocinante) — different architecture, separate module exists
- macOS Intune enrollment — not applicable
- Non-YubiKey enrollment methods — policy requires YubiKey

## Context

**Working Reference:**
- stargazer VM is fully enrolled and functional
- Current nix modules work but have pain points
- Documentation exists in docs/ but is scattered

**Technical Environment:**
- Host: macOS on Apple M4 Max
- VM: Parallels Desktop with aarch64-linux (Arch Linux ARM)
- Emulation: Rosetta for x86_64 Microsoft binaries
- Intune stack: intune-portal 1.2511.7, broker 2.0.4

**Known Pain Points:**
1. binfmt_misc for Rosetta not registered on boot (race condition with Parallels mount)
2. Running `nix switch` from prlctl exec runs as root, causing permission issues
3. D-Bus session bus and keyring not always available for Intune components
4. GRUB required for encrypt hook (couldn't get Limine working with LUKS)

**External Dependencies:**
- Omarchy ARM64 PR: https://github.com/basecamp/omarchy/pull/1897
- Microsoft Intune Linux requirements
- Parallels shared folder mounts for Rosetta binary

## Constraints

- **Encryption**: LUKS full-disk encryption required for Intune compliance
- **Authentication**: YubiKey PIV certificate required for enrollment (org policy)
- **Architecture**: Must work on aarch64-linux with x86_64 emulation via Rosetta
- **Tooling**: Automation must work via prlctl and/or SSH from macOS host

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use shared folder mount for dotfiles during setup | Instant sync, no git workflow needed | - Pending |
| Use GRUB instead of Limine | Limine encrypt hook issues unresolved | - Pending |
| Custom Nix packages for Intune binaries | Reproducible, versioned, not AUR-dependent | - Pending |
| OpenSSL 3.3.2 from Arch archives | Fixes Code:1200 broker bug in newer OpenSSL | - Pending |

---
*Last updated: 2026-01-31 after initialization*
