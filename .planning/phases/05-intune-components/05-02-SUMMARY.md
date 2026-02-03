---
phase: 05-intune-components
plan: 02
subsystem: infra
tags: [intune, health-check, diagnostics, systemd, dbus, pcscd, pkcs11]

# Dependency graph
requires:
  - phase: 05-intune-components
    plan: 01
    provides: intune-prerequisites.sh script
provides:
  - intune-health helper script for comprehensive component validation
  - Layer-by-layer diagnostic checks with pass/fail status
  - Remediation hints for each failure type
  - Critical vs optional failure distinction
affects: [05-intune-components, linux-intune-module]

# Tech tracking
tech-stack:
  added: []
  patterns: [health-check-with-remediation-hints, critical-vs-optional-failures]

key-files:
  created: []
  modified:
    - modules/home/linux/intune.nix

key-decisions:
  - "Exit 0 if all critical components pass, exit 1 on any critical failure"
  - "YubiKey checks are optional (warn-only) since hardware may not be inserted"
  - "Health check references intune-prerequisites for common fixes"

patterns-established:
  - "Health check pattern: check() function with critical/optional flag"
  - "Hint pattern: actionable remediation suggestion after each failure"

# Metrics
duration: 8min
completed: 2026-02-03
---

# Phase 5 Plan 02: Intune Health Check Summary

**Comprehensive health check script validates systemd services, D-Bus registration, pcscd, and PKCS#11 with actionable remediation hints**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-03T15:45:00Z
- **Completed:** 2026-02-03T15:53:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Added `intune-health` helper script with layer-by-layer validation
- Clear pass/fail/warn output with colored status indicators
- Remediation hints for each failure type
- Critical vs optional failures are distinguished (exit 0 vs exit 1)
- YubiKey checks are optional (warn only when not inserted)
- intune-status now references intune-health for detailed diagnostics

## Task Commits

Both tasks were committed in a single atomic commit (same file, related changes):

1. **Task 1: Implement intune-health helper script** - `e5ca956` (feat)
2. **Task 2: Update intune-status to reference intune-health** - `e5ca956` (feat)

## Files Modified
- `modules/home/linux/intune.nix` - Added healthHelper script (~130 lines), updated statusHelper to reference intune-health, added prereqHelper wrapper

## Decisions Made
- Exit codes: 0 for all critical pass, 1 for any critical failure (per research recommendations)
- YubiKey checks are optional because hardware may not be inserted during health check
- Combined D-Bus service file check and D-Bus activation test (both critical)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - module evaluated successfully on first attempt.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Health check script ready for use
- Prerequisites script can be invoked via `intune-prerequisites` command
- Ready for plan 03 (desktop integration)

---
*Phase: 05-intune-components*
*Completed: 2026-02-03*
