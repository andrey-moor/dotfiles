# Omarchy Linux VM Setup for Intune

## What This Is

A reproducible setup process for creating Omarchy Linux VMs on Parallels (Apple Silicon) with full Microsoft Intune enrollment via YubiKey. This includes documentation, automation scripts, and a unified Nix module that handles the complexity of running x86_64 Intune binaries on aarch64-linux via Rosetta emulation.

## Core Value

A developer can create an Intune-compliant Linux workstation on Apple Silicon by following documented steps, with automation for error-prone parts and clean Nix modules for the complex bits.

## Current State

**v1 shipped 2026-02-04** — See `.planning/MILESTONES.md` for details.

**Codebase:**
- Unified `intune.nix` module (485 lines) with architecture detection
- `prerequisites.sh` for system-level Rosetta/Nix setup
- `intune-prerequisites.sh` for Intune-specific system config
- `intune-health` diagnostic script for verification
- 3,000+ lines of documentation (E2E guide, troubleshooting, upgrades)

**Tech Stack:**
- Host: macOS on Apple M4 Max
- VM: Parallels Desktop with aarch64-linux (Arch Linux ARM + Omarchy)
- Emulation: Rosetta for x86_64 Microsoft binaries
- Intune stack: intune-portal 1.2511.7, microsoft-identity-broker 2.0.4
- Pinned: OpenSSL 3.3.2 (Code:1200 fix), OpenSC 0.25.1

**Working Reference:**
- stargazer VM is fully enrolled and functional
- endurance VM is production Intune device

## Requirements

### Validated (v1)

- ✓ VM can be created via prlctl with LUKS encryption — v1
- ✓ Rosetta enabled and functional for x86_64 binaries — v1
- ✓ Shared folders mount dotfiles at /mnt/psf/Home/Documents/dotfiles — v1
- ✓ SSH access works from macOS host to VM — v1
- ✓ binfmt registration survives reboot (retry loop solution) — v1
- ✓ GRUB bootloader with encrypt hook works with LUKS — v1
- ✓ Documented process to create encrypted base template — v1
- ✓ Clone and setup scripts for reproducible VM creation — v1
- ✓ Prerequisites script handles sudo-level setup — v1
- ✓ Nix installs with extra-platforms = x86_64-linux — v1
- ✓ home-manager switch applies configuration successfully — v1
- ✓ Unified intune.nix module with architecture detection — v1
- ✓ Library paths use named abstraction — v1
- ✓ intune-portal launches and shows login window — v1
- ✓ microsoft-identity-broker D-Bus service activates — v1
- ✓ microsoft-identity-device-broker systemd service runs — v1
- ✓ Device can enroll with Microsoft Intune — v1
- ✓ intune-agent reports compliance status — v1
- ✓ os-release spoofs Ubuntu 22.04 for Intune compatibility — v1
- ✓ pcscd runs and detects YubiKey — v1
- ✓ OpenSC PKCS#11 module loads certificates from YubiKey — v1
- ✓ Enrollment can use YubiKey PIV certificate — v1
- ✓ E2E setup guide from VM creation to enrolled device — v1
- ✓ Troubleshooting guide covers common issues — v1
- ✓ Upgrade procedures documented — v1

### Active (v2 candidates)

- [ ] Packer template for automated base VM creation
- [ ] Single-command provisioning from macOS
- [ ] Automated compliance verification script
- [ ] Automated tests for module configuration
- [ ] NixOS full system configuration option

### Out of Scope

- Native x86_64 Linux setup (Rocinante) — different architecture, separate module exists
- macOS Intune enrollment — not applicable
- Non-YubiKey enrollment methods — policy requires YubiKey
- Limine bootloader with LUKS — cannot handle encrypt hook, GRUB required
- TPM-based encryption unlock — not available in Parallels VMs

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use GRUB instead of Limine | Limine encrypt hook issues unresolved | ✓ Good — works reliably |
| Template-and-clone approach | LUKS passphrase requires human input | ✓ Good — simple workflow |
| Clone from EncryptedBase-GRUB | Fresh armarchy per VM is simpler than generalization | ✓ Good — clean VMs |
| OpenSSL 3.3.2 pinned | Fixes Code:1200 broker bug in newer OpenSSL | ✓ Good — enrollment works |
| Retry loop for binfmt | systemd conditions don't work with async mounts | ✓ Good — survives reboot |
| Mode detection enum | Clear architecture handling in unified module | ✓ Good — maintainable |
| Category-based lib paths | Easy removal when arm64 Intune arrives | ✓ Good — future-proof |
| Test-clone-first upgrades | Never upgrade production directly | ✓ Good — safe process |

## Constraints

- **Encryption**: LUKS full-disk encryption required for Intune compliance
- **Authentication**: YubiKey PIV certificate required for enrollment (org policy)
- **Architecture**: Must work on aarch64-linux with x86_64 emulation via Rosetta
- **Tooling**: Automation must work via prlctl and/or SSH from macOS host

---
*Last updated: 2026-02-04 after v1 milestone*
