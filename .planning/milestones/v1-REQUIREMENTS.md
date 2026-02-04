# Requirements Archive: v1 Omarchy Linux VM Setup

**Archived:** 2026-02-04
**Status:** ✅ SHIPPED

This is the archived requirements specification for v1.
For current requirements, see `.planning/REQUIREMENTS.md` (created for next milestone).

---

# Requirements: Omarchy Linux VM Setup

**Defined:** 2026-01-31
**Core Value:** A developer can create an Intune-compliant Linux workstation on Apple Silicon by following documented steps, with automation for error-prone parts.

## v1 Requirements

Requirements for reproducible Omarchy VM setup with Intune enrollment.

### VM Foundation

- [x] **VM-01**: VM can be created via prlctl with LUKS encryption enabled
- [x] **VM-02**: Rosetta is enabled and functional for x86_64 binaries
- [x] **VM-03**: Shared folders mount dotfiles at /mnt/psf/Home/Documents/dotfiles
- [x] **VM-04**: SSH access works from macOS host to VM
- [x] **VM-05**: binfmt registration survives reboot (path watcher solution)
- [x] **VM-06**: GRUB bootloader with encrypt hook works with LUKS

### VM Template & Automation

- [x] **AUTO-01**: Documented process to create encrypted base template
- [x] **AUTO-02**: prlctl script to clone template to new VM
- [x] **AUTO-03**: Post-clone setup script configures VM settings
- [x] **AUTO-04**: Prerequisites script handles sudo-level setup (os-release, pcscd, etc)

### Nix/Home-Manager Setup

- [x] **NIX-01**: Nix installs with extra-platforms = x86_64-linux
- [x] **NIX-02**: home-manager switch applies configuration successfully
- [x] **NIX-03**: intune-rosetta module is lean and well-designed
- [x] **NIX-04**: Library paths use named abstraction (not inline paths)
- [x] **NIX-05**: Single module handles x86_64 vs Rosetta architecture

### Intune Core

- [x] **INT-01**: intune-portal launches and shows login window
- [x] **INT-02**: microsoft-identity-broker D-Bus service activates on demand
- [x] **INT-03**: microsoft-identity-device-broker systemd service runs
- [x] **INT-04**: Device can enroll with Microsoft Intune
- [x] **INT-05**: intune-agent reports compliance status (timer works)
- [x] **INT-06**: os-release spoofs Ubuntu 22.04 for Intune compatibility

### YubiKey/PKCS#11

- [x] **YK-01**: pcscd runs and detects YubiKey
- [x] **YK-02**: OpenSC PKCS#11 module loads certificates from YubiKey
- [x] **YK-03**: Enrollment can use YubiKey PIV certificate for authentication
- [~] **YK-04**: Edge browser recognizes YubiKey for authentication — **SKIPPED** (optional feature)

### Documentation

- [x] **DOC-01**: E2E setup guide from VM creation to enrolled device
- [x] **DOC-02**: Troubleshooting guide covers common issues
- [x] **DOC-03**: Upgrade procedures for Omarchy and Intune packages
- [x] **DOC-04**: Verification checklists for each setup phase

## v2 Requirements

Deferred to future. Tracked but not in current roadmap.

### Enhanced Automation

- **AUTO-05**: Packer template for automated base VM creation
- **AUTO-06**: Single-command provisioning from macOS
- **AUTO-07**: Automated compliance verification script

### Module Improvements

- **NIX-06**: Automated tests for module configuration
- **NIX-07**: NixOS full system configuration option

### Advanced Features

- **INT-07**: Automatic token refresh without re-enrollment
- **INT-08**: Conditional access policy handling

## Out of Scope

| Feature | Reason |
|---------|--------|
| Native x86_64 Linux (Rocinante) | Different architecture, separate module exists |
| macOS Intune enrollment | Not applicable to this project |
| Non-YubiKey enrollment | Org policy requires YubiKey |
| TPM-based encryption unlock | Not available in Parallels VMs |
| Limine bootloader with LUKS | Cannot handle encrypt hook, GRUB required |
| Automatic VM start on macOS login | User should control when VPN/Intune active |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| VM-01 | Phase 1 | ✅ Complete |
| VM-02 | Phase 1 | ✅ Complete |
| VM-03 | Phase 1 | ✅ Complete |
| VM-04 | Phase 1 | ✅ Complete |
| VM-05 | Phase 2 | ✅ Complete |
| VM-06 | Phase 1 | ✅ Complete |
| AUTO-01 | Phase 1 | ✅ Complete |
| AUTO-02 | Phase 3 | ✅ Complete |
| AUTO-03 | Phase 3 | ✅ Complete |
| AUTO-04 | Phase 2 | ✅ Complete |
| NIX-01 | Phase 2 | ✅ Complete |
| NIX-02 | Phase 2 | ✅ Complete |
| NIX-03 | Phase 4 | ✅ Complete |
| NIX-04 | Phase 4 | ✅ Complete |
| NIX-05 | Phase 4 | ✅ Complete |
| INT-01 | Phase 5 | ✅ Complete |
| INT-02 | Phase 5 | ✅ Complete |
| INT-03 | Phase 5 | ✅ Complete |
| INT-04 | Phase 6 | ✅ Complete |
| INT-05 | Phase 6 | ✅ Complete |
| INT-06 | Phase 2 | ✅ Complete |
| YK-01 | Phase 5 | ✅ Complete |
| YK-02 | Phase 5 | ✅ Complete |
| YK-03 | Phase 6 | ✅ Complete |
| YK-04 | Phase 6 | ⊘ Skipped |
| DOC-01 | Phase 7 | ✅ Complete |
| DOC-02 | Phase 7 | ✅ Complete |
| DOC-03 | Phase 7 | ✅ Complete |
| DOC-04 | Phase 7 | ✅ Complete |

**Coverage:**
- v1 requirements: 26 total
- Shipped: 25
- Skipped: 1 (YK-04 - optional feature)
- Unmapped: 0

---

## Milestone Summary

**Shipped:** 25 of 26 v1 requirements

**Adjusted:** None - all requirements implemented as originally specified

**Skipped:**
- YK-04 (Edge browser YubiKey) — optional feature, enrollment works without it

---
*Requirements defined: 2026-01-31*
*Archived: 2026-02-04 as part of v1 milestone completion*
