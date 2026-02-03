# Phase 5: Intune Components - Research

**Researched:** 2026-02-03
**Domain:** Microsoft Intune/Identity stack on Linux + YubiKey PKCS#11
**Confidence:** HIGH (existing working implementation in codebase, verified on stargazer)

## Summary

This phase activates the Intune authentication stack: intune-portal GUI, identity brokers (user and device), pcscd smart card daemon, and PKCS#11/OpenSC module for YubiKey certificate access. The implementation is largely complete in the existing `modules/home/linux/intune.nix` module; this phase focuses on verification, health checking, and ensuring all components work together.

The existing codebase has a fully working implementation validated on the stargazer VM. The research confirms that the current architecture is correct: D-Bus activation for user broker, systemd service for device broker, always-running pcscd, and OpenSC for PKCS#11.

**Primary recommendation:** Implement a comprehensive health check script that validates each component layer (systemd services, D-Bus activation, pcscd, PKCS#11) with clear pass/fail status and remediation hints.

## Standard Stack

The established components for Microsoft Intune on Linux with YubiKey authentication:

### Core

| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| intune-portal | 1.2511.7 | Device enrollment GUI | Microsoft's official Linux client |
| microsoft-identity-broker | 2.0.4 | User SSO authentication | Microsoft's identity stack for Linux |
| microsoft-identity-device-broker | 2.0.4 | Device attestation (root) | Required for device registration |
| pcscd | system | Smart card daemon | PC/SC standard for all smart card access |
| OpenSC | 0.25.1 (Arch) | PKCS#11 module | Industry standard, works with all PIV cards |
| p11-kit | nixpkgs | PKCS#11 module discovery | Standard module configuration layer |

### Supporting

| Component | Purpose | When to Use |
|-----------|---------|-------------|
| gnome-keyring | Credential storage | Always (MSAL stores tokens here) |
| Mesa llvmpipe | Software rendering | Required for Rosetta (no GPU passthrough) |
| WebKitGTK 4.1 | Auth flow popups | Embedded browser for login UI |
| pcsc-tools | Diagnostics | `pcsc_scan` to verify reader detection |
| yubikey-manager | YubiKey diagnostics | `ykman` to check PIV state |

### Alternatives Considered

| Standard Choice | Alternative | Tradeoff |
|-----------------|-------------|----------|
| OpenSC PKCS#11 | ykcs11 (Yubico) | OpenSC works with multiple vendors, ykcs11 is YubiKey-specific. OpenSC is better for generic PIV compliance. |
| D-Bus activation (user broker) | systemd user service | D-Bus activation is Microsoft's design - broker activates when intune-portal calls it. No unnecessary background process. |
| pcscd always-running | Socket activation | User decision: always running preferred for reliability with YubiKey auth timing. |

## Architecture Patterns

### Component Interaction Flow

```
intune-portal (x86_64) ─────D-Bus───────> microsoft-identity-broker (user)
        │                                         │
        │                                         │ PKCS#11
        │                                         v
        │                              OpenSC ──> pcscd ──> YubiKey
        │                                         │
        │                                         │ gnome-keyring
        │                                         v
        │                              Token storage
        │
        └──────D-Bus───────> microsoft-identity-device-broker (system/root)
                                         │
                                         v
                              Device attestation keys
                              (/etc/ssl/private/drs*, stk*)
```

### D-Bus Service Architecture

**User Broker (Session Bus):**
```ini
# ~/.local/share/dbus-1/services/com.microsoft.identity.broker1.service
[D-BUS Service]
Name=com.microsoft.identity.broker1
Exec=/nix/store/xxx/bin/microsoft-identity-broker-rosetta
```

D-Bus daemon auto-starts the broker when intune-portal makes a call. No systemd user service needed.

**Device Broker (System Bus):**
- Runs as systemd system service (not D-Bus activated)
- Requires D-Bus policy file in `/usr/share/dbus-1/system.d/`
- ExecStart overridden to use Nix wrapper with LD_LIBRARY_PATH

### pcscd Communication Pattern

```
x86_64 application
        │
        │ pcsclite client library (x86_64)
        │ PCSCLITE_CSOCK_NAME=/run/pcscd/pcscd.comm
        v
pcscd socket (/run/pcscd/pcscd.comm)
        │
        │ Native aarch64 pcscd daemon
        │ ccid driver (patched with Parallels Proxy CCID)
        v
YubiKey (via Parallels smart card sharing)
```

**Critical:** x86_64 apps expect socket at `/run/pcscd/pcscd`, but aarch64 pcscd creates `/run/pcscd/pcscd.comm`. Symlink required.

### Anti-Patterns to Avoid

- **Running user broker as systemd service:** Microsoft designed it for D-Bus activation only. A persistent service is unnecessary and wastes resources.
- **Using ykcs11 for Intune:** While ykcs11 works, OpenSC is the established pattern in this codebase with verified ABI compatibility.
- **Socket-activated pcscd for Intune:** User decision: always running is more reliable for auth flows.
- **Restarting dbus-daemon:** Never `systemctl restart dbus` - it breaks the session. Use `pkill -HUP dbus-daemon` to reload policies.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Status checking | Custom scripts per component | Existing `intune-status` helper | Already comprehensive, mode-aware |
| Log aggregation | Manual journalctl | Existing `intune-logs` helper | Already combines portal/broker/device logs |
| PKCS#11 diagnostics | ad-hoc pkcs11-tool commands | `intune-pkcs11-diag` pattern | Layer-by-layer verification |
| D-Bus service file | Manual creation | Nix `writeTextFile` derivation | Already in intune.nix |
| Library paths | Inline in each wrapper | `fullLibraryPath` variable | Single source of truth |

**Key insight:** The existing intune.nix module already has extensive helper scripts. Phase 5 should enhance the health check script, not replace the existing infrastructure.

## Common Pitfalls

### Pitfall 1: D-Bus Policy Missing for Device Broker

**What goes wrong:** Device broker service starts but can't register on system bus. Intune portal shows auth errors.

**Why it happens:** The D-Bus policy file `com.microsoft.identity.devicebroker1.conf` isn't installed to `/usr/share/dbus-1/system.d/`.

**How to avoid:** Prerequisites script must copy policy file and signal dbus-daemon:
```bash
BROKER_PKG=$(find /nix/store -maxdepth 1 -name '*microsoft-identity-broker-2.0.4' -type d | head -1)
sudo cp "$BROKER_PKG/share/dbus-1/system.d/com.microsoft.identity.devicebroker1.conf" /usr/share/dbus-1/system.d/
sudo pkill -HUP dbus-daemon
```

**Warning signs:**
- `busctl --system list | grep devicebroker` returns empty
- Device broker logs show D-Bus permission denied

### Pitfall 2: pcscd Socket Path Mismatch

**What goes wrong:** x86_64 OpenSC can't find pcscd. YubiKey not detected.

**Why it happens:** x86_64 pcsclite expects `/run/pcscd/pcscd`, native aarch64 pcscd creates `/run/pcscd/pcscd.comm`.

**How to avoid:** Create tmpfiles symlink:
```bash
echo 'L /run/pcscd/pcscd - - - - /run/pcscd/pcscd.comm' | sudo tee /etc/tmpfiles.d/pcscd-symlink.conf
sudo systemd-tmpfiles --create
```

**Warning signs:**
- `pcsc_scan` from native works, x86_64 apps fail
- OpenSC errors about connecting to pcscd

### Pitfall 3: Polkit Blocking Rosetta Processes

**What goes wrong:** pcscd refuses access from x86_64/Rosetta processes.

**Why it happens:** Polkit can't properly authenticate Rosetta-emulated binaries.

**How to avoid:** Disable polkit for pcscd:
```bash
# /etc/systemd/system/pcscd.service.d/override.conf
[Service]
ExecStart=
ExecStart=/usr/bin/pcscd --foreground --auto-exit --disable-polkit
```

**Warning signs:**
- Polkit authentication prompts appear
- x86_64 pkcs11-tool can't list slots

### Pitfall 4: OpenSSL Version Mismatch

**What goes wrong:** Code:1200 "credential is invalid" during broker auth.

**Why it happens:** OpenSSL 3.4.0+ has an X509_REQ_set_version bug affecting broker CSR generation.

**How to avoid:** OpenSSL 3.3.2 (from Arch archives) MUST be first in LD_LIBRARY_PATH. Already handled in intune.nix.

**Warning signs:**
- Authentication fails after successful YubiKey PIN entry
- Broker logs show certificate-related errors

### Pitfall 5: User Broker Not D-Bus Activating

**What goes wrong:** Intune portal can't reach user broker, shows auth popup errors.

**Why it happens:** D-Bus service file not in `~/.local/share/dbus-1/services/` or points to wrong binary.

**How to avoid:** Verify service file exists and Exec path is valid:
```bash
cat ~/.local/share/dbus-1/services/com.microsoft.identity.broker1.service
# Verify the Exec path exists
ls -la $(grep Exec ~/.local/share/dbus-1/services/com.microsoft.identity.broker1.service | cut -d= -f2)
```

**Warning signs:**
- `busctl --user call com.microsoft.identity.broker1 ...` hangs or errors
- No broker process spawns when launching intune-portal

## Code Examples

### Health Check Script Pattern

```bash
#!/usr/bin/env bash
# intune-health-check: Comprehensive validation of Intune components

set -euo pipefail
PASS="[PASS]"
FAIL="[FAIL]"
WARN="[WARN]"

check() {
    local name="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo "$PASS $name"
        return 0
    else
        echo "$FAIL $name"
        return 1
    fi
}

# === SYSTEMD SERVICES ===
echo "=== Systemd Services ==="
check "device-broker running" systemctl is-active microsoft-identity-device-broker

# === D-BUS SERVICES ===
echo ""
echo "=== D-Bus Services ==="
check "device-broker on system bus" busctl --system list | grep -q devicebroker
check "user-broker service file exists" test -f ~/.local/share/dbus-1/services/com.microsoft.identity.broker1.service

# === PCSCD / YUBIKEY ===
echo ""
echo "=== Smart Card (pcscd) ==="
check "pcscd running" systemctl is-active pcscd.service || systemctl is-active pcscd.socket
check "pcscd socket symlink" test -L /run/pcscd/pcscd

# === PKCS#11 ===
echo ""
echo "=== PKCS#11 Module ==="
OPENSC_MODULE=$(grep -r "opensc-pkcs11.so" ~/.config/pkcs11/modules/ /etc/pkcs11/modules/ 2>/dev/null | head -1 | sed 's/.*module: //')
check "OpenSC module configured" test -n "$OPENSC_MODULE"
check "OpenSC module exists" test -f "$OPENSC_MODULE"

# === YUBIKEY (optional - only if inserted) ===
echo ""
echo "=== YubiKey (if inserted) ==="
if pcsc_scan -r 2>/dev/null | grep -q "Yubikey\|PIV"; then
    check "YubiKey detected by pcscd" true
    check "PIV certificates accessible" pkcs11-tool --module "$OPENSC_MODULE" --list-objects --type cert 2>/dev/null | grep -q "Certificate"
else
    echo "$WARN YubiKey not inserted - skipping certificate checks"
fi
```

### D-Bus Service Verification

```bash
# Verify user broker D-Bus activation works
busctl --user call com.microsoft.identity.broker1 \
    /com/microsoft/identity/broker1 \
    org.freedesktop.DBus.Peer Ping

# Check if service file is properly configured
dbus-send --session --print-reply --dest=org.freedesktop.DBus \
    /org/freedesktop/DBus org.freedesktop.DBus.ListActivatableNames \
    | grep -q "com.microsoft.identity.broker1"
```

### PKCS#11 Certificate Listing

```bash
# Find the OpenSC module path from p11-kit config
OPENSC_MODULE=$(p11-kit list-modules 2>/dev/null | grep -A1 "opensc" | grep "path:" | awk '{print $2}')

# List certificates on YubiKey
pkcs11-tool --module "$OPENSC_MODULE" --list-objects --type cert

# Alternative: use p11tool from GnuTLS
p11tool --list-certificates "pkcs11:model=YubiKey"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Java broker (microsoft-identity-broker 1.x) | Native broker (2.0.x) | Broker 2.0.2, Sept 2024 | No JVM dependency, D-Bus activation instead of systemd service |
| Entra Registration | Entra Join | Broker 2.0.2, Sept 2024 | Device trust vs user profile, prerequisite for platformSSO |
| systemd user service for broker | D-Bus activation only | Broker 2.0.2 | No persistent broker process |

**Deprecated/outdated:**
- **microsoft-identity-broker.service (user)**: No longer exists. Broker 2.0 uses D-Bus activation only.
- **Java-based broker**: Completely replaced by native broker.
- **OpenSSL 3.4.0+**: Broken for broker CSR generation. Must use 3.3.2.

## Open Questions

### 1. Exact Health Check Exit Codes

**What we know:** Script should check each layer and report status.

**What's unclear:** Should script exit non-zero on any failure, or only critical failures?

**Recommendation:** Exit 0 if all critical components pass (device broker, pcscd). Exit 1 if any critical failure. Warn-only for optional components (YubiKey not inserted).

### 2. intune-portal Desktop File

**What we know:** Package includes a .desktop file for GNOME/KDE launchers.

**What's unclear:** Should we create a custom .desktop that uses our wrapper, or rely on PATH?

**Recommendation:** Create wrapper desktop file pointing to `intune-portal-rosetta` wrapper. Edge case: some DEs may find both files.

## Sources

### Primary (HIGH confidence)

- Existing `modules/home/linux/intune.nix` - Verified working implementation
- Existing `hosts/endurance/README.md` - Documented setup procedures
- Existing `.planning/research/ARCHITECTURE.md` - Component interaction diagrams
- Microsoft Broker 2.0 changelog (`docs/intune-broker2.0.md`) - Official Microsoft documentation

### Secondary (MEDIUM confidence)

- [OpenSC Wiki - Using pkcs11-tool](https://github.com/OpenSC/OpenSC/wiki/Using-OpenSC) - Verified PKCS#11 commands
- [p11-kit module configuration](https://p11-glue.github.io/p11-glue/p11-kit/manual/pkcs11-conf.html) - Module file syntax
- [D-Bus daemon configuration](https://dbus.freedesktop.org/doc/dbus-daemon.1.html) - Policy file format
- [Yubico YKCS11 documentation](https://developers.yubico.com/yubico-piv-tool/YKCS11/) - Alternative PKCS#11 module

### Tertiary (LOW confidence)

- None - all critical claims verified with existing working implementation

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH - Verified working on stargazer VM, documented in codebase
- Architecture: HIGH - Detailed diagrams in ARCHITECTURE.md, validated patterns
- Pitfalls: HIGH - All derived from actual debugging sessions documented in PITFALLS.md

**Research date:** 2026-02-03
**Valid until:** 90+ days (stable Microsoft components, no major updates expected)

## Recommendations for Claude's Discretion Items

Based on research, these are the recommended choices for items left to Claude's discretion:

### Broker Startup Mechanism
**Recommendation: D-Bus activation (no auto-start)**

Rationale: This is Microsoft's intended design for Broker 2.0. The user broker only needs to run when intune-portal or Edge calls it. D-Bus activation is more efficient and already implemented correctly in the Nix module.

### Portal Launcher Approach
**Recommendation: CLI wrapper + desktop file**

Rationale: Keep existing `intune-portal-rosetta` CLI wrapper (already works). Add a .desktop file that invokes the wrapper for GUI launcher integration. Both are useful - CLI for debugging, desktop for daily use.

### PKCS#11 Module Choice
**Recommendation: OpenSC (current implementation)**

Rationale: OpenSC is already working and validated. It's the industry standard for PIV cards and has verified ABI compatibility with the Arch OpenSSL 3.3.2. Switching to ykcs11 would require re-testing the entire auth flow with no clear benefit.

### Logging Destination
**Recommendation: journald + optional file for portal**

Rationale:
- Device broker: journald via systemd (automatic)
- User broker: journald via D-Bus activation (automatic)
- intune-portal: tee to file when debug=true (already implemented)

The existing `intune-logs` helper already aggregates these sources. No changes needed.
