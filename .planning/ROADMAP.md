# Roadmap: Omarchy Linux VM Setup

## Overview

This roadmap delivers a reproducible workflow for creating Intune-compliant Arch Linux ARM VMs on Apple Silicon. The journey starts with manual VM template creation (LUKS encryption requires human passphrase), progresses through Rosetta/Nix infrastructure, system prerequisites, and Intune module development, then wraps with automation scripts and documentation. Each phase builds on the previous, following the boot-time dependency chain discovered in research.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: VM Template Creation** - Encrypted base VM with GRUB bootloader ready for cloning
- [ ] **Phase 2: Rosetta and Nix Infrastructure** - x86_64 emulation and package management working
- [ ] **Phase 3: VM Automation Scripts** - Clone and setup scripts for reproducible VM creation
- [ ] **Phase 4: Nix Module Refactoring** - Clean, lean intune-rosetta module with proper abstractions
- [ ] **Phase 5: Intune Components** - Portal, brokers, and YubiKey integration functional
- [ ] **Phase 6: Enrollment and Compliance** - Device enrolls and reports compliance status
- [ ] **Phase 7: Documentation** - E2E guide, troubleshooting, and upgrade procedures

## Phase Details

### Phase 1: VM Template Creation
**Goal**: Create an encrypted, generalized Arch Linux ARM VM template with GRUB bootloader and Omarchy desktop, ready for cloning.
**Depends on**: Nothing (first phase)
**Requirements**: VM-01, VM-02, VM-03, VM-04, VM-06, AUTO-01
**Success Criteria** (what must be TRUE):
  1. VM boots with LUKS passphrase prompt and decrypts successfully
  2. Rosetta is enabled in Parallels settings and /mnt/psf/RosettaLinux/rosetta exists
  3. Shared folders mount dotfiles at expected path (/mnt/psf/Home/Documents/dotfiles)
  4. SSH access works from macOS host using key authentication
  5. Template creation process is documented and can be followed by a new developer
**Plans**: 4 plans (Wave 1 -> Wave 2 -> Wave 3 -> Wave 4)

Plans:
- [x] 01-01-PLAN.md - Restructure documentation (split rocinante-encrypted-install.md into focused docs)
- [x] 01-02-PLAN.md - Test LUKS+GRUB doc (follow arch-arm-encrypted-install.md, create snapshot)
- [x] 01-03-PLAN.md - Test Omarchy doc (follow omarchy-grub-install.md with GRUB preservation)
- [x] 01-04-PLAN.md - Generalize template and verify cloning

### Phase 2: Rosetta and Nix Infrastructure
**Goal**: Configure x86_64 emulation via Rosetta with binfmt that survives reboots, and install Nix with cross-architecture support.
**Depends on**: Phase 1
**Requirements**: VM-05, AUTO-04, NIX-01, NIX-02, INT-06
**Success Criteria** (what must be TRUE):
  1. After reboot, x86_64 binaries execute via Rosetta without manual intervention
  2. Nix builds x86_64 packages via extra-platforms configuration
  3. home-manager switch completes successfully from shared folder path
  4. os-release shows Ubuntu 22.04 for Intune compatibility
  5. Prerequisites script is idempotent (can be re-run safely)
**Plans**: 2 plans (Wave 1 -> Wave 2)

Plans:
- [ ] 02-01-PLAN.md - Create idempotent prerequisites.sh script
- [ ] 02-02-PLAN.md - Validate script on fresh VM clone, test reboot survival

### Phase 3: VM Automation Scripts
**Goal**: Create scripts for cloning template and post-clone configuration, enabling reproducible VM creation from macOS.
**Depends on**: Phase 2
**Requirements**: AUTO-02, AUTO-03
**Success Criteria** (what must be TRUE):
  1. prlctl script clones template to new VM with specified name
  2. Post-clone script configures VM settings (CPU, memory, shared folders)
  3. Scripts work from macOS without manual VM console access
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

### Phase 4: Nix Module Refactoring
**Goal**: Refactor intune-rosetta.nix to be lean, well-designed, with named abstractions for library paths and single architecture detection.
**Depends on**: Phase 3
**Requirements**: NIX-03, NIX-04, NIX-05
**Success Criteria** (what must be TRUE):
  1. Single module handles both x86_64 and Rosetta architectures via detection
  2. Library paths use named variables (not inline paths) for maintainability
  3. Module is under 500 lines with clear section organization
  4. Existing stargazer/endurance configurations still work after refactoring
**Plans**: TBD

Plans:
- [ ] 04-01: TBD

### Phase 5: Intune Components
**Goal**: Intune portal launches, brokers activate, and YubiKey is detected for authentication.
**Depends on**: Phase 4
**Requirements**: INT-01, INT-02, INT-03, YK-01, YK-02
**Success Criteria** (what must be TRUE):
  1. intune-portal launches and displays login window (not blank)
  2. microsoft-identity-broker D-Bus service activates when called
  3. microsoft-identity-device-broker systemd service starts and stays running
  4. pcscd detects YubiKey when inserted
  5. OpenSC PKCS#11 module can list certificates from YubiKey
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

### Phase 6: Enrollment and Compliance
**Goal**: Complete device enrollment with YubiKey authentication and verify compliance reporting works.
**Depends on**: Phase 5
**Requirements**: INT-04, INT-05, YK-03, YK-04
**Success Criteria** (what must be TRUE):
  1. Device enrolls with Microsoft Intune using YubiKey PIV certificate
  2. intune-agent systemd timer runs and reports compliance status
  3. Edge browser recognizes YubiKey for web authentication
  4. Compliance check passes (LUKS encryption detected, password policy met)
**Plans**: TBD

Plans:
- [ ] 06-01: TBD

### Phase 7: Documentation
**Goal**: Document the complete setup process, troubleshooting guides, and upgrade procedures.
**Depends on**: Phase 6
**Requirements**: DOC-01, DOC-02, DOC-03, DOC-04
**Success Criteria** (what must be TRUE):
  1. E2E guide covers VM creation through enrolled device
  2. Troubleshooting guide maps common symptoms to solutions
  3. Upgrade procedures document Omarchy and Intune package updates
  4. Verification checklists exist for each setup phase
**Plans**: TBD

Plans:
- [ ] 07-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. VM Template Creation | 4/4 | Complete | 2026-02-02 |
| 2. Rosetta and Nix Infrastructure | 0/2 | Planned | - |
| 3. VM Automation Scripts | 0/? | Not started | - |
| 4. Nix Module Refactoring | 0/? | Not started | - |
| 5. Intune Components | 0/? | Not started | - |
| 6. Enrollment and Compliance | 0/? | Not started | - |
| 7. Documentation | 0/? | Not started | - |

---
*Created: 2026-01-31*
*Last updated: 2026-02-02 (Phase 2 planned - 2 plans in 2 waves)*
*Requirements: 26 mapped*
