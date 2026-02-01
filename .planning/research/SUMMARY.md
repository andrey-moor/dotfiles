# Project Research Summary

**Project:** Omarchy Linux VM Setup Automation for Apple Silicon
**Domain:** Infrastructure Automation / VM Provisioning / Enterprise Compliance
**Researched:** 2026-01-31
**Confidence:** HIGH

## Executive Summary

This project automates the creation and configuration of Intune-compliant Arch Linux ARM VMs on Parallels Desktop for Apple Silicon. The research reveals a hybrid approach: manual VM template creation for LUKS-encrypted base images, followed by extensive automation for Intune integration via Nix/home-manager. The core technical challenge is running x86_64 Microsoft Intune binaries on aarch64-linux via Rosetta emulation while maintaining full system integration (D-Bus, smart cards, keyring).

The recommended implementation follows a template-and-clone pattern. Create a base encrypted VM template once (manual LUKS setup, GRUB bootloader, Omarchy desktop), then automate everything else via prlctl, Nix, and systemd. The critical insight from existing implementations (stargazer, endurance) is that Rosetta emulation requires precise library path management, systemd race condition mitigation, and extensive environment variable configuration to bridge the aarch64/x86_64 boundary.

Key risks center on boot-time race conditions (Rosetta binfmt registration before Parallels mounts appear), library version conflicts (OpenSSL 3.3.2 required, not 3.4+), and cross-architecture IPC (x86_64 processes accessing native aarch64 pcscd). These are all solved problems in the existing modules but require careful phase ordering: VM infrastructure first, Rosetta/Nix setup second, system prerequisites third, then Intune components last.

## Key Findings

### Recommended Stack

The stack splits cleanly between VM automation (Parallels prlctl), OS provisioning (Arch Linux ARM + Omarchy), x86_64 emulation (Rosetta), and package/configuration management (Nix/home-manager).

**Core technologies:**
- **Parallels Desktop 26.x + prlctl**: VM lifecycle management with CLI automation — clone-based workflow is more practical than Packer for LUKS scenarios
- **Arch Linux ARM + archboot**: Base OS with manual LUKS setup — no good kickstart equivalent, template approach required
- **Rosetta via binfmt_misc**: x86_64 emulation on aarch64 — requires systemd path watcher to handle mount timing race
- **GRUB bootloader**: Handles LUKS decrypt hook — Limine (Omarchy default) cannot prompt for encryption passphrase
- **Nix with extra-platforms**: Package management and cross-architecture builds — Determinate Nix preferred over standard installer
- **home-manager**: User-level configuration including Intune wrappers — cannot touch /etc, requires manual prerequisites
- **OpenSSL 3.3.2 from Arch archives**: Pinned version to avoid Code:1200 bug in 3.4+ — must be first in LD_LIBRARY_PATH
- **OpenSC 0.25.1 from Arch archives**: PKCS#11 module compatible with OpenSSL 3.3.2 — newer versions require OpenSSL 3.4.0 symbols
- **pcscd + ccid driver**: Smart card access with Parallels Proxy CCID support — requires polkit disable and socket symlink for Rosetta
- **Microsoft Intune components**: intune-portal, microsoft-identity-broker (user), microsoft-identity-device-broker (system) — all x86_64 binaries via Rosetta

### Expected Features

Based on analysis of the working stargazer implementation, features are well-defined and battle-tested.

**Must have (table stakes):**
- Device enrollment via intune-portal with WebKitGTK auth flows
- Compliance reporting via intune-agent systemd timer (hourly checks)
- LUKS full-disk encryption detected by compliance checks
- PAM password policy enforcement (12+ chars, complexity rules)
- Ubuntu 22.04 os-release spoofing for Intune compatibility
- D-Bus system/user broker services for SSO
- Credential storage via gnome-keyring integration
- Rosetta binfmt registration surviving reboots (path watcher solution)
- x86_64 dynamic linker symlink at /lib64/ld-linux-x86-64.so.2
- Shared folders for dotfiles access at /mnt/psf/Home/Documents/dotfiles

**Should have (competitive):**
- YubiKey/smart card authentication via PKCS#11 (pcscd + OpenSC + p11-kit)
- NSS browser integration for Edge/Chrome smart card support
- Debug mode toggle for verbose logging (modules.linux.intune.debug = true)
- Diagnostic helpers: intune-status, intune-logs, intune-pkcs11-diag
- Idempotent setup scripts that can be re-run safely
- VM snapshot automation for pre-enrollment checkpoints
- macOS prlctl wrapper for building from host

**Defer (v2+):**
- Full NixOS system configuration (current approach is home-manager only)
- Single-command VM provisioning from scratch
- Automated compliance verification testing
- Packer integration for complete automation (LUKS passphrase remains manual requirement)
- Template management via Nix (like NixOS image builders)

### Architecture Approach

The architecture is a layered stack with clear separation between host (macOS), VM infrastructure (Parallels), OS layer (native aarch64), emulation layer (Rosetta), and application layer (x86_64 Intune components). The key pattern is comprehensive wrapper scripts that set ~60+ library paths via LD_LIBRARY_PATH to provide complete x86_64 dependency chains.

**Major components:**
1. **VM Template Layer** — Pre-configured encrypted Arch Linux ARM base with GRUB, Omarchy desktop, generalized for cloning. Created once manually, then stored as compressed archive.
2. **Rosetta Integration Layer** — systemd-binfmt with path watcher to handle mount timing, glibc dynamic linker symlink, Nix extra-platforms configuration. Bridges aarch64/x86_64 execution.
3. **Intune Application Layer** — x86_64 binaries (intune-portal, brokers, agent) wrapped with environment configuration, D-Bus service activation, systemd timer for compliance. All via home-manager.
4. **Credential Layer** — gnome-keyring (native aarch64) for storage, pcscd (native aarch64) for smart cards, cross-architecture IPC via Unix sockets and polkit bypass.
5. **Prerequisites Layer** — System-level setup (os-release, D-Bus policy, pcscd config, PAM policy) that must be done before home-manager, requires sudo.

**Critical patterns:**
- **Boot-time dependency chain:** LUKS decrypt → prltoolsd mounts → Rosetta available → binfmt registration → nix-daemon can build x86_64
- **Cross-architecture IPC:** x86_64 applications access native aarch64 services (pcscd, D-Bus, keyring) via standard Unix mechanisms
- **Library path composition:** Modular env blocks (mesaEnvVars, webkitEnvVars, tlsEnvVars) composed into wrappers, with OpenSSL 3.3.2 always first
- **Systemd service activation:** D-Bus auto-activates user broker from ~/.local/share/dbus-1/services/, device broker runs as system service with HOME=/root override

### Critical Pitfalls

These are the top pitfalls that WILL block progress if not addressed proactively.

1. **Rosetta binfmt race condition (boot-time)** — systemd-binfmt runs before Parallels mounts /mnt/psf/RosettaLinux/rosetta, so binfmt entry fails to register. Solution: systemd path watcher that triggers binfmt restart when Rosetta binary appears. Without this, x86_64 binaries work after manual systemctl restart but fail after reboot.

2. **OpenSSL 3.4+ breaks identity broker (Code:1200 errors)** — OpenSSL 3.4.0+ has X509_REQ_set_version bug causing authentication failures during device registration. Solution: Pin OpenSSL 3.3.2 from Arch archives and ensure it's FIRST in LD_LIBRARY_PATH. This cascades to OpenSC version requirement (0.25.1, not 0.26.1).

3. **Limine bootloader cannot handle LUKS** — Omarchy installer defaults to Limine, which cannot prompt for LUKS passphrase at boot. System hangs with no decrypt prompt. Solution: Use GRUB with encrypt hook in mkinitcpio, and create vmlinuz-linux symlink for ARM kernel (named 'Image' by default).

4. **pcscd polkit blocks Rosetta processes** — Polkit authorization fails for x86_64 emulated processes trying to access pcscd. YubiKey not detected from Intune components. Solution: Disable polkit for pcscd service (--disable-polkit flag), create /run/pcscd/pcscd symlink to pcscd.comm for socket path compatibility.

5. **os-release detection rejects non-Ubuntu** — Intune components check /etc/os-release and refuse to work on Arch Linux. Generic Microsoft errors during authentication. Solution: Spoof Ubuntu 22.04 os-release before attempting enrollment.

6. **prlctl exec creates root-owned files** — Commands executed from macOS via prlctl exec run as root in the VM, creating permission chaos in user directories. Solution: Wrap commands with `su user -c '...'` or use SSH instead of prlctl exec for user operations.

7. **WebKitGTK blank windows without DMABUF disable** — Login popups appear completely blank due to EGL/DMA-BUF acceleration failure under Rosetta. Solution: Set WEBKIT_DISABLE_DMABUF_RENDERER=1 and use Mesa llvmpipe software rendering (LIBGL_ALWAYS_SOFTWARE=1).

8. **ARM kernel naming breaks GRUB config generation** — ARM kernel is named 'Image' not 'vmlinuz-linux', so grub-mkconfig doesn't find matching initramfs. System boots without initramfs, encrypt hook never runs. Solution: Copy /boot/Image to /boot/vmlinuz-linux before grub-mkconfig.

## Implications for Roadmap

Based on research, the optimal phase structure follows the critical dependency chain discovered in architecture research. The key insight is that certain steps MUST be manual (LUKS setup), certain steps MUST be system-level with sudo (prerequisites), and certain steps CAN be fully automated via Nix/home-manager (Intune integration).

### Phase 1: VM Template Creation
**Rationale:** This is a one-time manual process that creates the foundation. LUKS encryption cannot be fully automated due to passphrase requirements (Intune compliance). Template approach is more practical than rebuilding from scratch each time.

**Delivers:** Encrypted, generalized Arch Linux ARM VM template with GRUB bootloader, Omarchy desktop, compliant password policy, ready for cloning.

**Addresses:**
- LUKS disk encryption (FEATURES: table stakes)
- Password policy configuration (FEATURES: table stakes)
- Base OS with desktop environment (FEATURES: table stakes)

**Avoids:**
- Pitfall: Limine bootloader (use GRUB)
- Pitfall: ARM kernel naming (create vmlinuz-linux symlink)
- Pitfall: Insufficient resources (document minimum specs)
- Pitfall: Missing Rosetta/shared folders enablement (configure in Parallels settings)

**Research needed:** Minimal — archboot process is well-documented, GRUB + LUKS is standard pattern.

### Phase 2: Rosetta and Nix Setup
**Rationale:** x86_64 emulation and package management must be configured before Intune components can be built. This phase handles the aarch64/x86_64 boundary and ensures binfmt survives reboots.

**Delivers:** Working Rosetta emulation with systemd path watcher, Nix installation with extra-platforms, x86_64 dynamic linker in place.

**Addresses:**
- Rosetta binfmt registration (STACK: core technology)
- x86_64 binary execution on aarch64 (ARCHITECTURE: emulation layer)
- Nix package management for cross-arch builds (STACK: core technology)

**Avoids:**
- Pitfall: Rosetta binfmt race condition (implement path watcher)
- Pitfall: x86_64 dynamic linker missing (symlink glibc from Nix)
- Pitfall: Mount path variation (detect /mnt/psf vs /media/psf)

**Research needed:** LOW — Existing implementation in stargazer/endurance is proven solution. Standard systemd patterns.

### Phase 3: System Prerequisites
**Rationale:** These require sudo and must be done before home-manager. They create the system-level integration points (os-release, D-Bus policy, pcscd) that Intune components depend on.

**Delivers:** Ubuntu os-release spoof, pcscd configuration with Parallels CCID support, D-Bus policy for device broker, PAM password policy readable by agent.

**Addresses:**
- os-release spoofing (FEATURES: table stakes, Intune compatibility)
- pcscd configuration (FEATURES: YubiKey support)
- D-Bus system bus integration (ARCHITECTURE: credential layer)
- PAM password policy enforcement (FEATURES: table stakes, compliance)

**Avoids:**
- Pitfall: os-release detection failure (spoof Ubuntu 22.04)
- Pitfall: pcscd polkit blocks (disable polkit, create socket symlink)
- Pitfall: D-Bus policy missing (install to /usr/share, not /etc)
- Pitfall: PAM policy not readable (chmod 644)

**Research needed:** LOW — Well-documented in stargazer setup. May need phase research for YubiKey/CCID configuration nuances.

### Phase 4: Home-Manager Intune Module
**Rationale:** This is where the bulk of complexity lives. The intune-rosetta.nix module (1000+ lines) provides wrappers, environment configuration, D-Bus services, and systemd timers. This phase requires careful library path management and environment variable composition.

**Delivers:** Nix module with enable toggle, wrapper scripts for intune-portal/brokers/agent, D-Bus service files, systemd timer, diagnostic helpers.

**Addresses:**
- intune-portal with WebKitGTK wrappers (FEATURES: table stakes, enrollment)
- microsoft-identity-broker user service (FEATURES: table stakes, SSO)
- intune-agent timer (FEATURES: table stakes, compliance reporting)
- OpenSSL 3.3.2 + OpenSC 0.25.1 from archives (STACK: core technologies)
- Library path composition (ARCHITECTURE: critical pattern)
- Debug mode and diagnostic tools (FEATURES: differentiators)

**Avoids:**
- Pitfall: OpenSSL 3.4+ breaks broker (pin 3.3.2, ensure first in LD_LIBRARY_PATH)
- Pitfall: OpenSC version mismatch (use 0.25.1 from archives)
- Pitfall: WebKitGTK blank windows (DMABUF disable, Mesa software rendering)
- Pitfall: Keyring not unlocked for systemd services (set GNOME_KEYRING_CONTROL, use login keyring)

**Research needed:** MEDIUM — Core implementation exists in intune-rosetta.nix, but may need refinement for reusability. Phase research could investigate module consolidation strategies and wrapper hygiene patterns.

### Phase 5: Device Broker System Service
**Rationale:** The device broker runs as a system service (root) with different requirements than user services. It needs D-Bus policy, systemd override to point to Nix wrapper, and HOME environment set. This phase bridges system and user contexts.

**Delivers:** systemd override for microsoft-identity-device-broker pointing to Nix wrapper, HOME=/root environment, D-Bus policy installed.

**Addresses:**
- Device attestation (FEATURES: table stakes, enrollment)
- System-level broker integration (ARCHITECTURE: Intune application layer)

**Avoids:**
- Pitfall: Device broker HOME environment missing (set in systemd override)
- Pitfall: D-Bus policy causing restart (install to /usr/share, reload with pkill -HUP)
- Pitfall: prlctl exec permission issues (document su wrapper pattern)

**Research needed:** LOW — Pattern established in endurance setup. Standard systemd override mechanism.

### Phase 6: VM Automation and Cloning
**Rationale:** With a working template and Nix module, create automation scripts for cloning and post-clone setup. This phase delivers the "push-button" VM creation workflow.

**Delivers:** Shell scripts for template extraction, prlctl clone, initial boot setup, home-manager switch from macOS host.

**Addresses:**
- VM creation/clone automation (STACK: prlctl integration)
- Shared folders access (FEATURES: table stakes, dotfiles)
- prlctl exec wrapper patterns (FEATURES: differentiators, developer workflow)
- Snapshot automation (FEATURES: nice-to-have)

**Avoids:**
- Pitfall: prlctl exec runs as root (use su wrapper in all scripts)
- Pitfall: Hardcoded Nix store paths (use readlink -f or environment detection)

**Research needed:** LOW — prlctl commands well-documented. May benefit from Packer exploration if full automation desired (Phase 7 stretch goal).

### Phase 7: Documentation and Testing
**Rationale:** Capture tribal knowledge from implementation, create troubleshooting guides, document upgrade paths. This phase ensures the solution is maintainable.

**Delivers:** Setup documentation, troubleshooting guide mapping symptoms to pitfalls, upgrade procedure for Intune package versions.

**Addresses:**
- Developer workflow documentation (FEATURES: differentiators)
- Diagnostic helper usage (FEATURES: differentiators)
- Testing strategy for enrollment flow (FEATURES: open questions)

**Avoids:**
- Pitfall: Documentation lives in README vs code comments (embed in Nix modules)
- Pitfall: Breaking changes without migration path (document upgrade steps)

**Research needed:** MINIMAL — Documentation of existing implementation.

### Phase Ordering Rationale

1. **Dependency chain:** VM template → Rosetta/Nix → System prerequisites → Intune module → Device broker → Automation wrapping. Each phase depends on previous completion.

2. **Manual vs automated split:** Phase 1 is inherently manual (LUKS passphrase), Phases 2-5 can be partially automated via scripts, Phase 6 creates full automation around the manual core.

3. **Sudo boundary:** Phase 3 and 5 require system-level changes (sudo), Phase 4 is pure home-manager (user-level). This matches the architecture pattern of system prerequisites before user configuration.

4. **Complexity management:** Phase 4 is the most complex (1000+ line module) and benefits from having all infrastructure in place first. Debugging wrapper issues is easier when OS, Rosetta, and system services are known-good.

5. **Pitfall avoidance sequence:** Boot-time pitfalls (Phase 1-2), system integration pitfalls (Phase 3), application layer pitfalls (Phase 4-5), operational pitfalls (Phase 6-7).

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3:** YubiKey/CCID integration details — Parallels Proxy CCID driver patching and pcscd cross-architecture IPC patterns may need dedicated research if expanding beyond current solution.
- **Phase 4:** Nix module refactoring — If consolidating intune-rosetta.nix and intune-nix.nix into single module with architecture detection, need research on Nix conditional patterns and library path abstraction strategies.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Arch Linux installation with LUKS is well-documented, archboot process standard.
- **Phase 2:** systemd path units and Nix installation are established patterns with abundant documentation.
- **Phase 5:** systemd service overrides are straightforward, existing implementation provides complete pattern.
- **Phase 6:** prlctl automation is CLI-based with good documentation, template cloning is proven workflow.
- **Phase 7:** Documentation phase, no technical research needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Based on working implementation in stargazer/endurance VMs. All stack components tested and proven. Parallels prlctl commands verified, Arch ARM + Rosetta combination validated, Nix/home-manager approach battle-tested. |
| Features | HIGH | Derived from analysis of 1900+ lines of existing Nix modules (intune-rosetta.nix, intune-nix.nix, etc.). Feature set represents actual working implementation, not speculation. Priority matrix clear from brownfield experience. |
| Architecture | HIGH | Component diagram and dependency maps extracted from real system. Boot-time dependency chain verified through troubleshooting race conditions. Cross-architecture IPC patterns proven through YubiKey integration. Systemd integration patterns established. |
| Pitfalls | HIGH | All pitfalls documented from actual failures encountered during stargazer/endurance setup. Warning signs, prevention strategies, and phases are based on real troubleshooting experience. Solutions verified to work in production. |

**Overall confidence:** HIGH

This is a greenfield automation project for a brownfield solution. The underlying system (Intune on Arch ARM via Rosetta) is proven and documented in existing modules. The research task is understanding what exists and structuring an automation roadmap around it. No speculative technology choices or unproven integrations.

### Gaps to Address

Despite high confidence, some areas need attention during implementation:

- **Module consolidation strategy:** Current implementation has separate intune-rosetta.nix (1000+ lines) and intune-nix.nix (670 lines) for different architectures. Roadmap should decide whether to unify with architecture detection or keep separate. May need phase research for Nix conditional patterns.

- **Upgrade path for Intune packages:** Microsoft releases new versions of intune-portal and brokers. Current implementation uses custom derivations fetching from Microsoft repos. Need strategy for version bumps and testing upgrades without breaking working VMs.

- **Packer integration feasibility:** Research identified Packer plugin for Parallels but noted LUKS passphrase makes full automation impractical. If stretch goal is complete automation, need deeper research into Packer parallels-pvm builder with encrypted template.

- **Testing enrollment flow:** Open question from features research — how to verify Intune enrollment works without manual portal interaction? May need exploration of Microsoft Graph API for enrollment status checking during development.

- **Parallels version compatibility:** Current research based on Parallels Desktop 26.x. Rosetta mount paths and CCID passthrough may vary between versions. Documentation should note version requirements.

## Sources

### Primary (HIGH confidence)
- Existing implementation: `/Users/andreym/Documents/dotfiles/modules/home/linux/intune-rosetta.nix` (1000+ lines, working in stargazer VM)
- Existing implementation: `/Users/andreym/Documents/dotfiles/modules/home/linux/intune-nix.nix` (670 lines)
- Existing implementation: `/Users/andreym/Documents/dotfiles/modules/home/linux/intune.nix` (230 lines)
- Existing implementation: `/Users/andreym/Documents/dotfiles/hosts/endurance/`, `/Users/andreym/Documents/dotfiles/hosts/stargazer/`
- Parallels Desktop documentation: prlctl command reference (verified via prlctl --help)
- Arch Linux documentation: archboot, archinstall, mkinitcpio with encrypt hook
- systemd documentation: binfmt_misc, path units, D-Bus activation
- Nix manual: cross-compilation, extra-platforms, pkgsCross

### Secondary (MEDIUM confidence)
- Microsoft Intune for Linux documentation: enrollment process, compliance requirements
- OpenSSL changelogs: 3.4.0 regression notes (X509_REQ_set_version API change)
- Omarchy/Armarchy installer: hdwy.link/armarchy-3-x scripts
- Parallels Tools documentation: shared folders, Rosetta integration

### Tertiary (LOW confidence)
- Packer Parallels plugin documentation: parallels-iso and parallels-pvm builders (not tested with LUKS)
- Community reports: OpenSC 0.25.1 vs 0.26.1 OpenSSL symbol requirements (verified against Arch archives but not official OpenSC notes)

---
*Research completed: 2026-01-31*
*Ready for roadmap: yes*
