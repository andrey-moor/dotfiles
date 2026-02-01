# Features Research: Omarchy Linux VM with Intune

This document analyzes expected features for a production Intune-enrolled Linux workstation,
with emphasis on distinguishing table stakes (must-have) from differentiators (nice-to-have)
and identifying anti-features (things to deliberately avoid).

## Reference Implementation

Working reference: **stargazer** VM is enrolled and functional.
Current modules analyzed:
- `intune-rosetta.nix` (1000+ lines)
- `intune-nix.nix` (670 lines)
- `intune.nix` (230 lines)
- `edge-rosetta.nix`, `edge.nix`
- `rosetta.nix`

---

## 1. Intune Features

### Table Stakes (Must Have)

| Feature | Description | Current Implementation |
|---------|-------------|------------------------|
| Device enrollment | Register device with Microsoft Intune | intune-portal with D-Bus broker |
| Compliance reporting | Periodic compliance status to Microsoft | intune-agent systemd timer (hourly) |
| LUKS disk encryption | Full-disk encryption for compliance | Manual prerequisite (archboot) |
| Password policy | PAM password complexity rules | `/etc/pam.d/common-password` |
| os-release spoofing | Fake Ubuntu 22.04 for Intune compatibility | Manual `/etc/os-release` override |
| Device broker | System-level D-Bus service for attestation | systemd service + wrapper |
| User broker | User-level D-Bus service for SSO | xdg.dataFile D-Bus service |
| Credential storage | Secure credential management | gnome-keyring integration |
| OpenSSL 3.3.2 | Pinned version (Code:1200 bug workaround) | Arch Linux archive package |

### Differentiators (Nice to Have)

| Feature | Description | Current Implementation |
|---------|-------------|------------------------|
| YubiKey/smart card auth | PKCS#11 certificate authentication | p11-kit, OpenSC, pcscd integration |
| NSS browser integration | Edge/Chrome smart card support | intune-nss-setup helper |
| Debug mode toggle | Verbose logging for troubleshooting | `modules.linux.intune.debug = true` |
| Diagnostic helpers | `intune-status`, `intune-logs`, `intune-pkcs11-diag` | Shell script wrappers |
| Version management | Custom packages for latest versions | packages/intune-portal, microsoft-identity-broker |

### Anti-Features (Deliberately Avoid)

| Anti-Feature | Reason |
|--------------|--------|
| Global `LIBGL_ALWAYS_SOFTWARE` | Breaks Hyprland/Wayland compositors |
| Global `GDK_BACKEND=x11` | Breaks Wayland apps |
| Patching ELF binaries | x86_64 binaries run via Rosetta |
| Automatic dbus restart | Can destabilize running session |
| Root-level D-Bus policy in /etc | Use /usr/share to avoid dbus restart |
| intune-portal in systemd service | GUI app, must run interactively |

---

## 2. VM Automation Tooling

### Table Stakes (Must Have)

| Feature | Description | Current Implementation |
|---------|-------------|------------------------|
| prlctl integration | VM control from macOS host | `prlctl start/stop/exec` |
| Shared folders | Dotfiles access from VM | `/mnt/psf/Home/Documents/dotfiles` |
| SSH access | Remote shell access | Via Tailscale or VM network |
| Rosetta binfmt | x86_64 binary execution on aarch64 | systemd-binfmt + path unit |
| VM template | Reproducible base VM creation | `ArchBase-Template.pvm.tar.zst` |

### Differentiators (Nice to Have)

| Feature | Description | Current Implementation |
|---------|-------------|------------------------|
| prlctl exec wrapper | Run commands in VM from macOS | README shell commands |
| Rosetta path watcher | Auto-register binfmt when mount appears | rosetta-binfmt.path/service |
| Idempotent setup scripts | Re-runnable setup commands | Partially (intune-setup helper) |
| VM snapshot automation | Pre-enrollment checkpoint | Not implemented |
| Parallels CCID patching | Smart card reader passthrough | Manual sed in Info.plist |

### Anti-Features (Deliberately Avoid)

| Anti-Feature | Reason |
|--------------|--------|
| prlctl exec for file creation | Creates root-owned files in user dirs |
| Hardcoded Nix store paths | Store paths change on rebuild |
| Mount-based systemd dependencies | Parallels mounts not visible to systemd |
| Automatic VM start on macOS login | User should control when VPN/Intune active |

---

## 3. Nix Module Design

### Table Stakes (Must Have)

| Feature | Description | Current Implementation |
|---------|-------------|------------------------|
| Enable toggle | `modules.linux.intune.enable` | Standard mkEnableOption |
| Platform guard | Only activate on Linux | `mkIf (cfg.enable && pkgs.stdenv.isLinux)` |
| Architecture awareness | Different modules for x86_64 vs Rosetta | intune.nix vs intune-rosetta.nix |
| Wrapper scripts | Consistent env var setup | writeShellScriptBin with LD_LIBRARY_PATH |
| D-Bus service files | Proper activation | xdg.dataFile for user services |
| Systemd integration | Timer for compliance agent | systemd.user.services/timers |
| Activation scripts | Post-switch verification | lib.hm.dag.entryAfter |

### Differentiators (Nice to Have)

| Feature | Description | Current Implementation |
|---------|-------------|------------------------|
| Cross-architecture pkgsX86 | Native x86_64 packages on aarch64 | `import pkgs.path { system = "x86_64-linux" }` |
| Library path abstraction | Named libPaths record | `libPaths = { mesa = ...; gtk3 = ...; }` |
| Modular env var composition | Composable env blocks | `mesaEnvVars`, `webkitEnvVars`, `tlsEnvVars` |
| Custom package overlays | Latest versions from Microsoft | packages/intune-portal, microsoft-identity-broker |
| Arch Linux archive fetching | Pinned ABI-compatible binaries | opensslArch, openscArch derivations |
| Comprehensive diagnostic tools | Layer-by-layer debugging | intune-pkcs11-diag script |

### Anti-Features (Deliberately Avoid)

| Anti-Feature | Reason |
|--------------|--------|
| Monolithic wrapper scripts | 100+ lines of env vars = unmaintainable |
| Duplicated library paths | DRY violation, sync bugs |
| Implicit module dependencies | Use explicit `mkIf cfg.enable` |
| System-level home-manager options | home-manager cannot touch /etc |
| Nix store paths in README instructions | Paths change, use `readlink -f ~/.nix-profile/bin/` |

### Current Pain Points

| Issue | Description | Mitigation |
|-------|-------------|------------|
| binfmt race condition | Rosetta mount not ready at boot | rosetta-binfmt.path watcher |
| Permission issues | prlctl exec as root | Manual chown after setup |
| Bootloader complexity | LUKS + btrfs + systemd-boot | Template VM approach |
| Module size | intune-rosetta.nix is 1000+ lines | Could split into submodules |
| Manual prerequisites | 12+ steps in README | Partial automation via intune-setup |

---

## 4. Developer Workflow

### Table Stakes (Must Have)

| Feature | Description | Current Implementation |
|---------|-------------|------------------------|
| SSH to VM | Direct shell access | Tailscale SSH or VM network |
| Shared dotfiles | Edit on macOS, apply in VM | Parallels shared folders |
| home-manager switch | Apply configuration changes | `nix run home-manager -- switch --flake .#host` |
| chezmoi apply | Apply mutable configs | `chezmoi apply` (neovim, nushell) |
| Status commands | Check component health | `intune-status`, systemctl status |

### Differentiators (Nice to Have)

| Feature | Description | Current Implementation |
|---------|-------------|------------------------|
| macOS prlctl wrapper | Build from host | `prlctl exec VM "cd ... && nix run ..."` |
| Debug mode | Verbose logging toggle | `intune-rosetta.debug = true` |
| Log tailing | Unified log view | `intune-logs` helper |
| PKCS#11 diagnostics | Layer-by-layer testing | `intune-pkcs11-diag` |
| NSS setup automation | Browser smart card config | `intune-nss-setup` |

### Anti-Features (Deliberately Avoid)

| Anti-Feature | Reason |
|--------------|--------|
| Requiring GUI for all operations | Should work headless for automation |
| Storing secrets in dotfiles | Use gnome-keyring or external secret manager |
| Assuming pcscd always running | Use socket activation |
| Breaking changes without migration path | Document upgrade steps |

---

## 5. Architecture Variants

### x86_64-linux (Native)

Used by: rocinante (Arch Linux workstation)

| Aspect | Approach |
|--------|----------|
| Binaries | Native x86_64 |
| Library loading | System + Nix LD_LIBRARY_PATH |
| OpenSSL | Arch 3.3.2 override |
| Module | `intune.nix` or `intune-nix.nix` |

### aarch64-linux (Rosetta)

Used by: stargazer, endurance (Parallels VMs on Apple Silicon)

| Aspect | Approach |
|--------|----------|
| Binaries | x86_64 via Rosetta binfmt |
| Library loading | Full Nix x86_64 library chain |
| OpenSSL | Arch 3.3.2 (x86_64) |
| Graphics | Mesa llvmpipe software rendering |
| Module | `intune-rosetta.nix` |
| Extra complexity | SIGTRAP ignore for Edge crashpad |

---

## 6. Feature Priority Matrix

### P0 - Launch Blockers

1. Device enrollment works (intune-portal)
2. Compliance reporting (intune-agent timer)
3. LUKS encryption detected
4. Password policy configured

### P1 - Essential Quality

1. Rosetta binfmt auto-registration
2. Reproducible setup process
3. Clear troubleshooting docs
4. Debug mode for issue diagnosis

### P2 - Developer Experience

1. Status/diagnostic commands
2. Log tailing helpers
3. PKCS#11/YubiKey support
4. NSS browser integration

### P3 - Future Improvements

1. Single-command VM provisioning
2. Automated compliance verification
3. Module consolidation/refactoring
4. NixOS full system configuration option

---

## 7. Open Questions

1. **Module consolidation**: Should intune-rosetta.nix and intune-nix.nix be unified with architecture detection?
2. **Setup automation**: How much of the 12-step README can be automated via nix/home-manager?
3. **Template management**: Should VM templates be built via nix (like NixOS images)?
4. **Upgrade path**: How to handle Microsoft package version bumps cleanly?
5. **Testing strategy**: How to verify Intune enrollment works without manual portal interaction?

---

## 8. Summary

### What Works Well

- Comprehensive Intune support with YubiKey integration
- Modular approach with enable toggles
- Rich diagnostic tooling
- Cross-architecture support via Rosetta

### What Needs Improvement

- Manual setup steps still required (12+ commands)
- Module size/complexity (1000+ lines)
- Documentation lives in README vs code comments
- No automated testing of enrollment flow

### Key Decisions for New Implementation

1. **Table stakes first**: Focus on enrollment and compliance before advanced features
2. **Automation over documentation**: Each manual step is a bug
3. **Wrapper hygiene**: Keep LD_LIBRARY_PATH manageable and documented
4. **Architecture abstraction**: Single module with platform detection preferred
5. **Defensive defaults**: Don't break Wayland, don't assume hardware
