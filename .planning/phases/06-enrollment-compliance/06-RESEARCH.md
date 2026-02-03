# Phase 6: Enrollment and Compliance - Research

**Researched:** 2026-02-03
**Domain:** Microsoft Intune Linux enrollment, YubiKey PIV authentication, compliance verification
**Confidence:** HIGH (existing working implementation on stargazer, documented enrollment flow)

## Summary

This phase completes the project's core value: device enrollment with YubiKey authentication and verified compliance reporting. The research confirms that all infrastructure from Phases 1-5 is in place. The focus is on: (1) creating a fresh test VM from ArchBase-Template to validate the end-to-end workflow, (2) manually walking through Intune enrollment with YubiKey authentication, and (3) verifying compliance reporting via intune-agent logs.

The enrollment flow is well-documented in existing codebase (`docs/intune-broker2.0.md`) and proven on the stargazer VM. The user decision to use snapshot-based recovery (restore pre-Intune snapshot on failure) simplifies the iteration process. The reference VM created in this phase becomes a long-term asset for testing future updates.

**Primary recommendation:** Create a three-snapshot workflow: post-Omarchy (existing template), post-Nix-install, and pre-Intune. The pre-Intune snapshot is the recovery point for enrollment retries. Document exact log patterns that indicate success vs failure at each stage.

## Standard Stack

Components for Microsoft Intune enrollment with YubiKey authentication:

### Core (Already Implemented)

| Component | Version | Purpose | Status |
|-----------|---------|---------|--------|
| intune-portal | 1.2511.7 | Enrollment GUI | Phase 5 verified |
| microsoft-identity-broker | 2.0.4 | User SSO, D-Bus activated | Phase 5 verified |
| microsoft-identity-device-broker | 2.0.4 | Device attestation | Phase 5 verified |
| intune-agent | 1.2511.7 | Compliance reporting | Phase 5 verified |
| pcscd | system | Smart card daemon | Phase 5 verified |
| OpenSC | 0.25.1 (Arch) | PKCS#11 module | Phase 5 verified |

### Verification Tools

| Tool | Purpose | How to Use |
|------|---------|------------|
| `intune-health` | Pre-enrollment health check | Must exit 0 before starting enrollment |
| `intune-status` | Quick component status | Shows mode, processes, services |
| `intune-agent-rosetta` | Manual compliance check | Triggers immediate compliance report |
| `intune-logs` | Combined log viewer | `--all` for all logs, `--device` for device broker |
| `pcsc_scan -r` | YubiKey detection | Verify smart card reader visible |
| `ykman piv info` | YubiKey PIV status | Verify certificates loaded |

### Parallels VM Management

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `prlctl snapshot` | Create snapshot | Before each major milestone |
| `prlctl snapshot-switch` | Restore snapshot | On enrollment failure |
| `prlctl snapshot-list` | List snapshots | Find snapshot UUID |
| `prlctl clone` | Clone from template | Create fresh test VM |

## Architecture Patterns

### Enrollment Flow Sequence

```
                                    ENROLLMENT SEQUENCE
    ┌─────────────┐
    │   Fresh VM  │
    │ (from clone)│
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │ Snapshot 1  │  ← "NixInstalled" - after Nix + home-manager
    │ Nix Ready   │
    └──────┬──────┘
           │
           ▼
    ┌─────────────────┐
    │ intune-prereqs  │  ← D-Bus policy, pcscd, device broker
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │  intune-health  │  ← MUST exit 0 (hard gate)
    │   all pass      │
    └────────┬────────┘
             │
             ▼
    ┌─────────────┐
    │ Snapshot 2  │  ← "PreIntune" - RECOVERY POINT
    │ Ready       │
    └──────┬──────┘
           │
           ▼
    ┌─────────────────┐
    │ Insert YubiKey  │  ← Parallels smart card sharing enabled
    │   Verify PIN    │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────────────┐
    │   intune-portal-rosetta │
    │   Sign In button        │
    └────────────┬────────────┘
                 │
                 ▼
    ┌─────────────────────────┐
    │   Browser auth popup    │  ← WebKitGTK window
    │   Select YubiKey cert   │
    │   Enter YubiKey PIN     │
    └────────────┬────────────┘
                 │
                 ▼
    ┌─────────────────────────┐
    │   Enrollment wizard     │  ← Accept terms, register device
    └────────────┬────────────┘
                 │
                 ▼
    ┌─────────────────────────┐
    │   Compliance check      │  ← Auto-triggered by enrollment
    │   LUKS + password policy│
    └────────────┬────────────┘
                 │
                 ▼
    ┌─────────────────┐
    │   Device shows  │  ← "Compliant" in portal
    │   compliant     │
    └────────┬────────┘
             │
             ▼
    ┌─────────────┐
    │ Snapshot 3  │  ← "Enrolled" - reference state
    │ Complete    │
    └─────────────┘
```

### Snapshot Naming Convention (Claude's Discretion)

| Snapshot | Name | Description | When |
|----------|------|-------------|------|
| 1 | `NixInstalled-YYYYMMDD` | Nix, home-manager, chezmoi applied | After Section 7 of README |
| 2 | `PreIntune-YYYYMMDD` | All prerequisites done, intune-health passes | Before launching intune-portal |
| 3 | `Enrolled-YYYYMMDD` | Enrollment complete, compliance verified | After successful enrollment |

Example: `PreIntune-20260203`

### Recovery Pattern

```bash
# On enrollment failure:
prlctl stop $VM --kill
prlctl snapshot-switch $VM --name "PreIntune-YYYYMMDD"
prlctl start $VM
# Wait for boot, unlock LUKS, login
# Retry enrollment from clean state
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pre-enrollment validation | Custom checks | `intune-health` script | Already comprehensive, exit code 0/1 |
| Component status | Manual ps/systemctl | `intune-status` helper | Aggregates all component info |
| Log aggregation | Multiple journalctl | `intune-logs` helper | Combines all sources |
| State cleanup | Manual rm commands | Restore snapshot | Clean slate guaranteed |
| Compliance trigger | Manual polling | `intune-agent-rosetta` | Proper wrapper with env vars |

**Key insight:** The intune-health script was designed in Phase 5 specifically for this phase's pre-enrollment gate. All critical checks pass = exit 0 = ready to enroll.

## Common Pitfalls

### Pitfall 1: YubiKey Not Detected During Enrollment

**What goes wrong:** Certificate picker is empty, authentication fails with "no certificate found"

**Why it happens:**
- Parallels smart card sharing not enabled
- pcscd socket symlink missing
- YubiKey not inserted before launching intune-portal

**How to avoid:**
1. Enable Parallels smart card sharing BEFORE enrollment
2. Run `intune-prerequisites` to create socket symlink
3. Insert YubiKey and verify with `pcsc_scan -r` before launching portal

**Warning signs:**
- `pcsc_scan -r` shows no readers
- `intune-health` shows WARN for YubiKey checks

### Pitfall 2: D-Bus Policy Not Loaded

**What goes wrong:** Device broker fails to register on system bus, enrollment hangs

**Why it happens:** D-Bus policy file not installed or dbus-daemon not signaled

**How to avoid:**
1. Run `intune-prerequisites` (installs policy + signals dbus)
2. Verify with `busctl --system list | grep devicebroker`

**Warning signs:**
- `intune-health` shows FAIL for "Device broker on system bus"
- Device broker service running but not on D-Bus

### Pitfall 3: Compliance Check Fails on Password Policy

**What goes wrong:** Device shows "Not Compliant" despite LUKS encryption

**Why it happens:** PAM common-password file missing or not readable by intune-agent

**How to avoid:**
1. `intune-prerequisites` creates `/etc/pam.d/common-password`
2. Verify permissions: `sudo chmod 644 /etc/pam.d/common-password`

**Warning signs:**
- Compliance shows "Enforce a secure password" failure
- intune-agent logs show PAM read errors

### Pitfall 4: WebKitGTK Auth Window Blank

**What goes wrong:** Login popup appears but is completely white/blank

**Why it happens:** Mesa EGL/DMA-BUF issues under Rosetta emulation

**How to avoid:** The wrapper already sets `WEBKIT_DISABLE_DMABUF_RENDERER=1`. If still blank:
1. Verify home-manager switch completed successfully
2. Run `intune-status` to confirm wrapper is Nix-managed
3. Try with `LIBGL_ALWAYS_SOFTWARE=1` explicitly

**Warning signs:**
- White popup window
- EGL errors in logs

### Pitfall 5: Enrollment Succeeds but Compliance Never Updates

**What goes wrong:** Portal shows "Checking compliance..." indefinitely

**Why it happens:** intune-agent timer not enabled, or intune-agent failing silently

**How to avoid:**
1. Enable timer: `systemctl --user enable --now intune-agent.timer`
2. Trigger manual check: `intune-agent-rosetta`
3. Check logs: `journalctl --user -u intune-agent --since "5 minutes ago"`

**Warning signs:**
- Timer not in `systemctl --user list-timers`
- No recent intune-agent log entries

## Log Patterns (Claude's Discretion)

### Success Patterns

**Device broker startup (journalctl -u microsoft-identity-device-broker):**
```
INFO: Starting Microsoft Identity Device Broker
INFO: D-Bus connection established
INFO: Device identity loaded from /etc/ssl/private
INFO: Ready to serve requests
```

**User broker activation (journalctl --user, grep broker):**
```
Activated via D-Bus
Starting authentication flow
Certificate selected: <CN from YubiKey>
Token acquired successfully
```

**intune-agent compliance (journalctl --user -u intune-agent):**
```
Starting compliance check
Checking encryption: LUKS detected on /dev/vda3
Checking password policy: /etc/pam.d/common-password readable
Compliance status: Compliant
Uploading compliance report
Report uploaded successfully
```

### Failure Patterns

**Code:1200 - Credential invalid:**
```
MSAL error: AADSTS7000215
Error code: 1200
Description: The credential is invalid
```
→ Fix: Verify os-release is Ubuntu 22.04, OpenSSL 3.3.2 in LD_LIBRARY_PATH

**YubiKey not accessible:**
```
PKCS#11: No slot available
No certificates found
Unable to connect to smart card reader
```
→ Fix: Check pcscd socket symlink, verify Parallels smart card sharing

**D-Bus activation failure:**
```
Failed to activate com.microsoft.identity.broker1
No such unit: microsoft-identity-broker
D-Bus service not found
```
→ Fix: Verify ~/.local/share/dbus-1/services/ contains service file

### Health Check Thresholds (Claude's Discretion)

**Ready to enroll (`intune-health` exit 0):**
- Device broker running: REQUIRED
- Device broker on system bus: REQUIRED
- User broker service file exists: REQUIRED
- User broker D-Bus activates: REQUIRED (in graphical session)
- pcscd running: REQUIRED
- pcscd socket symlink: REQUIRED
- OpenSC module configured: REQUIRED
- OpenSC module file exists: REQUIRED
- YubiKey detected: OPTIONAL (warn only)
- PIV certificates accessible: OPTIONAL (warn only)

**Not ready to enroll (`intune-health` exit 1):**
- Any REQUIRED check fails

## Code Examples

### Pre-Enrollment Checklist Script

```bash
#!/usr/bin/env bash
# enrollment-checklist.sh - Run before attempting enrollment

echo "=== Pre-Enrollment Checklist ==="

# 1. Health check (hard gate)
echo -e "\n1. Running intune-health..."
if ! intune-health; then
    echo "ERROR: intune-health failed. Fix issues before enrolling."
    exit 1
fi

# 2. YubiKey presence
echo -e "\n2. Checking YubiKey..."
if ! pcsc_scan -r 2>/dev/null | grep -qi yubikey; then
    echo "WARNING: YubiKey not detected. Insert YubiKey before proceeding."
    read -p "YubiKey inserted? [y/N] " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] || exit 1
fi

# 3. PIV certificate
echo -e "\n3. Checking PIV certificate..."
if ykman piv info 2>/dev/null | grep -q "Slot 9a"; then
    echo "[OK] PIV authentication certificate present"
else
    echo "WARNING: No PIV authentication certificate in slot 9a"
fi

# 4. Intune timer
echo -e "\n4. Checking intune-agent timer..."
if ! systemctl --user is-enabled intune-agent.timer >/dev/null 2>&1; then
    echo "Enabling intune-agent timer..."
    systemctl --user enable --now intune-agent.timer
fi

echo -e "\n=== Checklist Complete ==="
echo "Ready to enroll. Run: intune-portal-rosetta"
```

### Snapshot Management Commands

```bash
# Create snapshot before enrollment attempt
VM="TestVM"
DATE=$(date +%Y%m%d)

# Create PreIntune snapshot
prlctl snapshot "$VM" -n "PreIntune-$DATE" -d "Ready for Intune enrollment attempt"

# List snapshots to get UUID
prlctl snapshot-list "$VM"

# On failure, restore (VM must be stopped)
prlctl stop "$VM" --kill
prlctl snapshot-switch "$VM" --name "PreIntune-$DATE"
prlctl start "$VM"
```

### Compliance Verification Commands

```bash
# After enrollment, verify compliance

# 1. Trigger immediate compliance check
intune-agent-rosetta

# 2. View compliance logs
journalctl --user -u intune-agent --since "5 minutes ago" --no-pager

# 3. Check for specific compliance items
journalctl --user -u intune-agent --since "1 hour ago" | grep -E "LUKS|encryption|password|compliant"

# 4. View in Intune portal
# Navigate to Device status section in intune-portal
```

### Fresh VM Clone Workflow

```bash
# Clone from ArchBase-Template
TEMPLATE="ArchBase-Template"  # Or "ArchBase-LUKS-GRUB" if using .pvmp
VM="IntuneFreshTest"
DATE=$(date +%Y%m%d)

# Stop template if running
prlctl stop "$TEMPLATE" 2>/dev/null || true

# Clone from existing template snapshot
prlctl clone "$TEMPLATE" --name "$VM"

# Configure VM
prlctl set "$VM" --cpus 4 --memsize 8192
prlctl set "$VM" --rosetta-linux on
prlctl set "$VM" --shf-host on

# Start VM (will prompt for LUKS passphrase)
prlctl start "$VM"

# After boot, first snapshot
prlctl snapshot "$VM" -n "OmarchyBase-$DATE" -d "Fresh clone after LUKS unlock"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Password fallback | YubiKey-only auth | User decision | No password option in enrollment |
| Unenroll + cleanup | Snapshot restore | User decision | Cleaner recovery, no state leakage |
| Ad-hoc VM creation | Template-and-clone | Phase 1 | Reproducible baseline |
| Manual component checks | `intune-health` script | Phase 5 | Automated pre-enrollment gate |

**Current best practice for this project:**
- Three-snapshot milestone approach (Nix, PreIntune, Enrolled)
- `intune-health` as hard gate before enrollment
- Snapshot restore (not unenroll) for recovery
- Reference VM becomes permanent testing asset

## Open Questions

### 1. Exact Edge Browser NSS Setup Timing

**What we know:** Edge requires NSS module setup for YubiKey certificate auth (`intune-nss-setup` or manual modutil commands)

**What's unclear:** Should this be done before enrollment or after? Does intune-portal auth flow use NSS or only Edge?

**Recommendation:** intune-portal uses WebKitGTK (p11-kit), not NSS. Edge needs NSS setup for post-enrollment web SSO. Can be done after enrollment as verification step.

### 2. Compliance Check Timing

**What we know:** intune-agent timer runs 5min after login, then hourly.

**What's unclear:** How quickly does compliance status update after enrollment? Does it require manual trigger?

**Recommendation:** After enrollment completes, run `intune-agent-rosetta` manually to trigger immediate compliance check. Don't rely on timer for initial verification.

### 3. Registration.toml Location

**What we know:** Intune stores device registration state somewhere.

**What's unclear:** Exact location of registration.toml and what happens if it's corrupted.

**Recommendation:** After successful enrollment, document location of state files for reference. If corrupt, restore PreIntune snapshot rather than manual cleanup.

## Sources

### Primary (HIGH confidence)

- Existing `modules/home/linux/intune.nix` - All helper scripts and wrappers
- `docs/intune-broker2.0.md` - Microsoft's broker 2.0 documentation
- `docs/rocinante-intune-yubikey.md` - YubiKey integration patterns
- `hosts/stargazer/README.md` - Complete setup workflow (680 lines)
- `.planning/phases/05-intune-components/05-RESEARCH.md` - Phase 5 research (component details)
- `.planning/phases/05-intune-components/05-03-SUMMARY.md` - Stargazer live validation

### Secondary (MEDIUM confidence)

- [Microsoft Intune App for Linux](https://learn.microsoft.com/en-us/mem/intune/user-help/microsoft-intune-app-linux) - Official install docs (Ubuntu-focused)
- Parallels CLI documentation - Snapshot commands

### Tertiary (LOW confidence)

- WebSearch results were empty for specific Intune compliance log patterns
- Log patterns in this document are based on codebase analysis and training knowledge

## Metadata

**Confidence breakdown:**
- Enrollment flow: HIGH - Proven on stargazer, documented in broker2.0.md
- Snapshot workflow: HIGH - Standard Parallels CLI, documented in README
- Compliance verification: MEDIUM - intune-agent wrapper exists, log patterns inferred
- Log patterns: MEDIUM - Based on component analysis, not live capture
- Edge NSS setup: MEDIUM - Documented but timing unclear

**Research date:** 2026-02-03
**Valid until:** 90+ days (stable workflow, Microsoft components unchanged)
