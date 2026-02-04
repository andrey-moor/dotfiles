# Milestone v1: Omarchy Linux VM Setup for Intune

**Status:** SHIPPED 2026-02-04
**Phases:** 1-7
**Total Plans:** 19 (18 executed + 1 skipped)

## Overview

This roadmap delivered a reproducible workflow for creating Intune-compliant Arch Linux ARM VMs on Apple Silicon. The journey started with manual VM template creation (LUKS encryption requires human passphrase), progressed through Rosetta/Nix infrastructure, system prerequisites, and Intune module development, then wrapped with automation scripts and documentation. Each phase built on the previous, following the boot-time dependency chain discovered in research.

## Phases

### Phase 1: VM Template Creation

**Goal**: Create an encrypted, generalized Arch Linux ARM VM template with GRUB bootloader and Omarchy desktop, ready for cloning.
**Depends on**: Nothing (first phase)
**Requirements**: VM-01, VM-02, VM-03, VM-04, VM-06, AUTO-01
**Success Criteria**:
  1. VM boots with LUKS passphrase prompt and decrypts successfully
  2. Rosetta is enabled in Parallels settings and /mnt/psf/RosettaLinux/rosetta exists
  3. Shared folders mount dotfiles at expected path (/mnt/psf/Home/Documents/dotfiles)
  4. SSH access works from macOS host using key authentication
  5. Template creation process is documented and can be followed by a new developer

Plans:
- [x] 01-01-PLAN.md - Restructure documentation (split rocinante-encrypted-install.md into focused docs)
- [x] 01-02-PLAN.md - Test LUKS+GRUB doc (follow arch-arm-encrypted-install.md, create snapshot)
- [x] 01-03-PLAN.md - Test Omarchy doc (follow omarchy-grub-install.md with GRUB preservation)
- [x] 01-04-PLAN.md - Generalize template and verify cloning

**Completed:** 2026-02-02

### Phase 2: Rosetta and Nix Infrastructure

**Goal**: Configure x86_64 emulation via Rosetta with binfmt that survives reboots, and install Nix with cross-architecture support.
**Depends on**: Phase 1
**Requirements**: VM-05, AUTO-04, NIX-01, NIX-02, INT-06
**Success Criteria**:
  1. After reboot, x86_64 binaries execute via Rosetta without manual intervention
  2. Nix builds x86_64 packages via extra-platforms configuration
  3. home-manager switch completes successfully from shared folder path
  4. os-release shows Ubuntu 22.04 for Intune compatibility
  5. Prerequisites script is idempotent (can be re-run safely)

Plans:
- [x] 02-01-PLAN.md - Create idempotent prerequisites.sh script
- [x] 02-02-PLAN.md - Validate script on fresh VM clone, test reboot survival

**Completed:** 2026-02-02

### Phase 3: VM Automation Scripts

**Goal**: Create comprehensive documentation for reproducible VM creation from .pvmp template, with stargazer as the canonical host.
**Depends on**: Phase 2
**Requirements**: AUTO-02, AUTO-03
**Success Criteria**:
  1. hosts/stargazer/README.md is single source of truth for VM setup
  2. Full workflow documented: .pvmp import → armarchy → GRUB fix → Nix → Intune
  3. GRUB fix prominently documented with warning
  4. prl-type.sh examples provided for typing commands into VM

Plans:
- [x] 03-01-PLAN.md - Restructure hosts/stargazer/README.md as comprehensive setup guide

**Completed:** 2026-02-02

### Phase 4: Nix Module Refactoring

**Goal**: Merge intune-rosetta.nix and intune-nix.nix into a unified module with architecture detection, category-based library paths, and clean organization.
**Depends on**: Phase 3
**Requirements**: NIX-03, NIX-04, NIX-05
**Success Criteria**:
  1. Single module handles both x86_64 and Rosetta architectures via detection
  2. Library paths use named variables (not inline paths) for maintainability
  3. Module is under 500 lines with clear section organization
  4. Existing stargazer/endurance/rocinante configurations still work after refactoring

Plans:
- [x] 04-01-PLAN.md - Create unified intune.nix with mode detection and library categories
- [x] 04-02-PLAN.md - Update host configs to use unified module
- [x] 04-03-PLAN.md - Validate builds on both architectures and archive old modules

**Completed:** 2026-02-03

### Phase 5: Intune Components

**Goal**: Intune portal launches, brokers activate, and YubiKey is detected for authentication.
**Depends on**: Phase 4
**Requirements**: INT-01, INT-02, INT-03, YK-01, YK-02
**Success Criteria**:
  1. intune-portal launches and displays login window (not blank)
  2. microsoft-identity-broker D-Bus service activates when called
  3. microsoft-identity-device-broker systemd service starts and stays running
  4. pcscd detects YubiKey when inserted
  5. OpenSC PKCS#11 module can list certificates from YubiKey

Plans:
- [x] 05-01-PLAN.md — Automate Intune system prerequisites (D-Bus policy, pcscd, PKCS#11)
- [x] 05-02-PLAN.md — Implement comprehensive intune-health diagnostic script
- [x] 05-03-PLAN.md — Validate on stargazer VM and update documentation

**Completed:** 2026-02-03

### Phase 6: Enrollment and Compliance

**Goal**: Complete device enrollment with YubiKey authentication and verify compliance reporting works.
**Depends on**: Phase 5
**Requirements**: INT-04, INT-05, YK-03, YK-04
**Success Criteria**:
  1. Device enrolls with Microsoft Intune using YubiKey PIV certificate
  2. intune-agent systemd timer runs and reports compliance status
  3. Edge browser recognizes YubiKey for web authentication (skipped - optional)
  4. Compliance check passes (LUKS encryption detected, password policy met)

Plans:
- [x] 06-01-PLAN.md — Create fresh VM from template, apply Nix and prerequisites
- [x] 06-02-PLAN.md — Enroll device with YubiKey and verify compliance
- [~] 06-03-PLAN.md — Edge browser YubiKey setup (skipped - optional)

**Completed:** 2026-02-03

### Phase 7: Documentation

**Goal**: Document the complete setup process, troubleshooting guides, and upgrade procedures.
**Depends on**: Phase 6
**Requirements**: DOC-01, DOC-02, DOC-03, DOC-04
**Success Criteria**:
  1. E2E guide covers VM creation through enrolled device
  2. Troubleshooting guide maps common symptoms to solutions
  3. Upgrade procedures document Omarchy and Intune package updates
  4. Verification checklists exist for each setup phase

Plans:
- [x] 07-01-PLAN.md — Enhanced E2E guide with verification checklists
- [x] 07-02-PLAN.md — Consolidated troubleshooting guide (symptom-based)
- [x] 07-03-PLAN.md — Upgrade procedures for Intune packages and pinned dependencies

**Completed:** 2026-02-04

---

## Milestone Summary

**Key Decisions:**

- Use GRUB instead of Limine for LUKS compatibility (Limine can't handle encrypt hook)
- Template-and-clone approach for VM creation (LUKS passphrase is manual)
- OpenSSL 3.3.2 pinned to avoid Code:1200 broker bug
- Clone from EncryptedBase-GRUB snapshot, run armarchy fresh (simpler than generalization)
- Critical GRUB fix: copy grubaa64.efi to fallback boot path (armarchy installs Limine there)
- Retry loop for Rosetta binfmt boot survival (systemd conditions don't work with async mounts)
- Mode detection enum at module top (native-x86_64, rosetta, null)
- Category-based lib groupings for easy removal when arm64 Intune arrives
- Test-clone-first approach for all risky upgrades

**Issues Resolved:**

- Boot race condition: Parallels mounts /mnt/psf async after prltoolsd.service completes
- Dynamic linker broken symlink: glibc.out required (default -bin output has no libs)
- WebKitGTK blank screen: WEBKIT_DISABLE_DMABUF_RENDERER=1 required for Rosetta
- pcscd polkit blocking x86_64 processes: Disabled polkit for pcscd

**Technical Debt Cleared:**

- Prerequisites.sh reference to endurance → stargazer (fixed in quick task 001)
- Hardcoded broker version in intune-prerequisites.sh → version-agnostic (fixed in quick task 001)
- intune-health --verbose flag in docs but not implemented → removed from docs (fixed in quick task 001)

---

*For current project status, see .planning/ROADMAP.md (will be created for next milestone)*
*Archived: 2026-02-04*
