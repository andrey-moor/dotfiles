# Phase 5: Intune Components - Verification

**Verified:** 2026-02-03
**Status:** COMPLETE (All goals achieved)

## Phase Goal

> "Intune portal launches, brokers activate, and YubiKey is detected for authentication."

## Success Criteria Verification

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | intune-portal launches and displays login window (not blank) | ✅ VERIFIED | `intune-portal-rosetta` wrapper exists in `intune.nix:287-300` with full library path and Mesa/WebKitGTK environment; validated live on stargazer (05-03-SUMMARY) |
| 2 | microsoft-identity-broker D-Bus service activates when called | ✅ VERIFIED | User broker D-Bus service configured via `xdg.dataFile` at line 586-588; `intune-health` validates D-Bus activation at line 459 |
| 3 | microsoft-identity-device-broker systemd service starts and stays running | ✅ VERIFIED | `intune-prerequisites.sh` installs service with `Restart=always` (lines 115-127); `intune-health` validates at line 433 |
| 4 | pcscd detects YubiKey when inserted | ✅ VERIFIED | `intune-prerequisites.sh` configures pcscd (lines 140-187), ccid driver patch (lines 240-264); health check validates at line 469 |
| 5 | OpenSC PKCS#11 module can list certificates from YubiKey | ✅ VERIFIED | User config at `intune.nix:591-594`, system config in `intune-prerequisites.sh:190-233`; health check at line 506 uses `pkcs11-tool --list-objects` |

## Code Implementation Verification

### 1. intune-portal wrapper

**File:** `modules/home/linux/intune.nix`
**Lines:** 287-300

The wrapper includes all necessary environment variables:
- `fullLibraryPath` - Comprehensive library path with OpenSSL 3.3.2 first
- `mesaEnvVars` - Software rendering for Rosetta
- `webkitEnvVars` - WebKitGTK X11 mode
- `tlsEnvVars` - TLS certificates and GIO modules  
- `pkcs11EnvVars` - PKCS#11/YubiKey support

**Verification:** Wrapper exists, includes all required environment setup, executes `intunePkg/bin/intune-portal`.

### 2. microsoft-identity-broker D-Bus service

**File:** `modules/home/linux/intune.nix`
**Lines:** 344-353 (service definition), 586-588 (installation)

D-Bus service file created with:
- Name: `com.microsoft.identity.broker1`
- Exec: Points to `userBrokerWrapper` with correct library paths

Installation via `xdg.dataFile` places service at `~/.local/share/dbus-1/services/`.

**Verification:** Service file definition exists, installation hook exists, points to Nix wrapper.

### 3. microsoft-identity-device-broker systemd service

**File:** `scripts/intune-prerequisites.sh`
**Lines:** 81-135

Service override includes:
- ExecStart pointing to Nix wrapper
- Environment variables for MSAL (HOME, XDG_CONFIG_HOME, XDG_CACHE_HOME)
- Restart=always with RestartSec=5
- WantedBy=multi-user.target

**Verification:** Prerequisites script creates systemd override with auto-restart.

### 4. pcscd and YubiKey detection

**File:** `scripts/intune-prerequisites.sh`
**Lines:** 140-187 (pcscd), 240-264 (ccid driver)

Configured:
- Socket symlink `/run/pcscd/pcscd` -> `/run/pcscd/pcscd.comm`
- pcscd polkit disabled (required for Rosetta processes)
- ccid driver patched for Parallels Proxy CCID (VID 0x203A, PID 0xFFFD)

**Verification:** Script handles pcscd socket, polkit, and ccid driver configuration.

### 5. OpenSC PKCS#11 module

**File:** `modules/home/linux/intune.nix`
**Lines:** 591-594 (user config)

User-level PKCS#11 module config:
- Module path: `${openscArch}/lib/pkcs11/opensc-pkcs11.so`
- Uses Arch OpenSC 0.25.1 for Rosetta compatibility

**File:** `scripts/intune-prerequisites.sh`
**Lines:** 190-233 (system config)

System-level PKCS#11 modules:
- `opensc-x86.module` - Nix OpenSC for Rosetta apps
- `opensc.module` - System OpenSC for native apps

**Verification:** Both user and system PKCS#11 configurations exist.

## Helper Scripts Verification

| Script | Purpose | Location | Verified |
|--------|---------|----------|----------|
| `intune-health` | Comprehensive component validation | `intune.nix:390-529` | ✅ 130+ lines with critical/optional checks |
| `intune-prerequisites` | Wrapper invoking shell script | `intune.nix:531-547` | ✅ Resolves DOTFILES path, invokes script |
| `intune-status` | Quick status overview | `intune.nix:374-388` | ✅ Shows processes, services, versions |
| `intune-logs` | Unified log viewer | `intune.nix:359-372` | ✅ Aggregates portal/broker/device logs |

## Documentation Verification

**File:** `hosts/stargazer/README.md`

- Section 8: Documents `intune-prerequisites` as primary setup method ✅
- Section 9: Documents `intune-health` as verification method ✅
- Manual commands: Preserved in collapsible details block ✅
- Overview: Updated to show complete workflow ✅

## Package Verification

| Package | File | Version | Purpose |
|---------|------|---------|---------|
| intune-portal | `packages/intune-portal/default.nix` | 1.2511.7-noble | Enrollment UI |
| microsoft-identity-broker | `packages/microsoft-identity-broker/default.nix` | 2.0.4 | SSO/device brokers |

Both packages:
- Fetch from Microsoft's Ubuntu 24.04 repo
- Extract without patching (x86_64 ELF, run via Rosetta)
- Include D-Bus service files and systemd units

## Live Validation (from 05-03-SUMMARY)

Per 05-03-SUMMARY.md, all criteria validated live on stargazer VM:

| Test | Result |
|------|--------|
| home-manager switch | Success |
| intune-prerequisites | All sections configured |
| intune-health | All critical components pass |
| intune-portal launch | Login window displayed (user verified) |
| YubiKey detection | Detected via pcscd (user verified) |
| Certificate listing | Verified (user verified) |

## Must-Haves Checklist

- [x] `intune-portal` wrapper with correct library paths and environment
- [x] `microsoft-identity-broker` D-Bus service file in user session
- [x] `microsoft-identity-device-broker` systemd service with Nix wrapper
- [x] `pcscd` configuration (socket symlink, polkit override)
- [x] `ccid` driver patch for Parallels Proxy CCID
- [x] OpenSC PKCS#11 module configuration (user and system)
- [x] `intune-health` diagnostic script
- [x] `intune-prerequisites` automation script
- [x] Documentation updated with automated approach

## Conclusion

**Phase 5 is COMPLETE.** All success criteria are met with verified code implementations:

1. Portal wrapper exists with full environment configuration
2. User broker D-Bus activation configured via home-manager
3. Device broker systemd service installs via prerequisites script
4. pcscd configured with socket symlink and polkit disabled
5. OpenSC PKCS#11 module configured at both user and system level

The phase delivers automation (`intune-prerequisites`) and verification (`intune-health`) scripts that replace the previous manual setup steps.

---
*Phase: 05-intune-components*
*Verified: 2026-02-03*
