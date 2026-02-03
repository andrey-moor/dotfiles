# Phase 5: Intune Components - Context

**Gathered:** 2026-02-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Intune portal launches with login window, brokers activate and stay running, YubiKey is detected via pcscd, and PKCS#11 module can list certificates. This phase gets the authentication/identity stack working — actual enrollment is Phase 6.

</domain>

<decisions>
## Implementation Decisions

### Startup behavior
- Broker startup: Claude's discretion (auto-start vs on-demand based on Microsoft's expected patterns)
- Portal launcher: Claude's discretion (GUI/CLI/both — whatever's standard)
- Without YubiKey: Graceful degradation — services start cleanly, PIN prompt appears when user inserts key and retries auth
- pcscd: Always running at boot (not on-demand)

### YubiKey integration
- PKCS#11 module: Claude's discretion (OpenSC or Yubico module — whichever works best with Intune/Edge)
- PIN prompt: GUI dialog required (Entra auth happens in graphical window)
- Single enrollment key: One specific YubiKey required for enrollment (not interchangeable with regular key)
- Browser certificate: Edge should auto-detect certificates via system PKCS#11 module

### Error handling
- Service crashes: Auto-restart via systemd
- Portal errors: Focus on prevention through correct configuration (portal default errors acceptable)
- Logging: Claude's discretion (journald or dedicated logs)
- Health check: Include diagnostic script for quick status verification

### Verification workflow
- Approach: Health check script + documented manual steps
- Timing: Incremental per-component verification + final E2E verification
- Documentation: Both script and documented verification steps (script shows status, docs explain what to do if something fails)

### Claude's Discretion
- Broker startup mechanism (auto-start vs D-Bus activation)
- Portal launcher approach
- PKCS#11 module choice (OpenSC vs ykcs11)
- Logging destination

</decisions>

<specifics>
## Specific Ideas

- User may forget to insert YubiKey — system should handle this gracefully and prompt when needed
- Two YubiKeys exist but one is specifically for enrollment (company requirement)
- Prevention over recovery: correct config means portal blank screen shouldn't happen

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-intune-components*
*Context gathered: 2026-02-03*
