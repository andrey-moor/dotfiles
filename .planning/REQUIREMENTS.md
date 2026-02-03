# Requirements: Omarchy Linux VM Setup

**Defined:** 2026-01-31
**Core Value:** A developer can create an Intune-compliant Linux workstation on Apple Silicon by following documented steps, with automation for error-prone parts.

## v1 Requirements

Requirements for reproducible Omarchy VM setup with Intune enrollment.

### VM Foundation

- [ ] **VM-01**: VM can be created via prlctl with LUKS encryption enabled
- [ ] **VM-02**: Rosetta is enabled and functional for x86_64 binaries
- [ ] **VM-03**: Shared folders mount dotfiles at /mnt/psf/Home/Documents/dotfiles
- [ ] **VM-04**: SSH access works from macOS host to VM
- [ ] **VM-05**: binfmt registration survives reboot (path watcher solution)
- [ ] **VM-06**: GRUB bootloader with encrypt hook works with LUKS

### VM Template & Automation

- [ ] **AUTO-01**: Documented process to create encrypted base template
- [ ] **AUTO-02**: prlctl script to clone template to new VM
- [ ] **AUTO-03**: Post-clone setup script configures VM settings
- [ ] **AUTO-04**: Prerequisites script handles sudo-level setup (os-release, pcscd, etc)

### Nix/Home-Manager Setup

- [ ] **NIX-01**: Nix installs with extra-platforms = x86_64-linux
- [ ] **NIX-02**: home-manager switch applies configuration successfully
- [ ] **NIX-03**: intune-rosetta module is lean and well-designed
- [ ] **NIX-04**: Library paths use named abstraction (not inline paths)
- [ ] **NIX-05**: Single module handles x86_64 vs Rosetta architecture

### Intune Core

- [ ] **INT-01**: intune-portal launches and shows login window
- [ ] **INT-02**: microsoft-identity-broker D-Bus service activates on demand
- [ ] **INT-03**: microsoft-identity-device-broker systemd service runs
- [ ] **INT-04**: Device can enroll with Microsoft Intune
- [ ] **INT-05**: intune-agent reports compliance status (timer works)
- [ ] **INT-06**: os-release spoofs Ubuntu 22.04 for Intune compatibility

### YubiKey/PKCS#11

- [ ] **YK-01**: pcscd runs and detects YubiKey
- [ ] **YK-02**: OpenSC PKCS#11 module loads certificates from YubiKey
- [ ] **YK-03**: Enrollment can use YubiKey PIV certificate for authentication
- [ ] **YK-04**: Edge browser recognizes YubiKey for authentication

### Documentation

- [ ] **DOC-01**: E2E setup guide from VM creation to enrolled device
- [ ] **DOC-02**: Troubleshooting guide covers common issues
- [ ] **DOC-03**: Upgrade procedures for Omarchy and Intune packages
- [ ] **DOC-04**: Verification checklists for each setup phase

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
| VM-01 | Phase 1 | Pending |
| VM-02 | Phase 1 | Pending |
| VM-03 | Phase 1 | Pending |
| VM-04 | Phase 1 | Pending |
| VM-05 | Phase 2 | Pending |
| VM-06 | Phase 1 | Pending |
| AUTO-01 | Phase 1 | Pending |
| AUTO-02 | Phase 3 | Complete |
| AUTO-03 | Phase 3 | Complete |
| AUTO-04 | Phase 2 | Pending |
| NIX-01 | Phase 2 | Pending |
| NIX-02 | Phase 2 | Pending |
| NIX-03 | Phase 4 | Pending |
| NIX-04 | Phase 4 | Pending |
| NIX-05 | Phase 4 | Pending |
| INT-01 | Phase 5 | Pending |
| INT-02 | Phase 5 | Pending |
| INT-03 | Phase 5 | Pending |
| INT-04 | Phase 6 | Pending |
| INT-05 | Phase 6 | Pending |
| INT-06 | Phase 2 | Pending |
| YK-01 | Phase 5 | Pending |
| YK-02 | Phase 5 | Pending |
| YK-03 | Phase 6 | Pending |
| YK-04 | Phase 6 | Pending |
| DOC-01 | Phase 7 | Pending |
| DOC-02 | Phase 7 | Pending |
| DOC-03 | Phase 7 | Pending |
| DOC-04 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 26 total
- Mapped to phases: 26
- Unmapped: 0

---
*Requirements defined: 2026-01-31*
*Last updated: 2026-02-02 (Phase 3 complete)*
