---
phase: 05-intune-components
plan: 01
subsystem: intune
tags: [intune, dbus, pcscd, pkcs11, systemd, prerequisites, automation]

# Dependency graph
requires:
  - phase: 04
    provides: unified intune.nix module with mode detection
provides:
  - Intune system prerequisites automation script
  - intune-prerequisites Nix wrapper
  - intune-health diagnostic script
affects: [05-02, 05-03, enrollment, documentation]

# Tech tracking
tech-stack:
  added: []
  patterns: [idempotent-prerequisites-script, nix-wrapper-to-shell-script]

key-files:
  created:
    - scripts/intune-prerequisites.sh
  modified:
    - modules/home/linux/intune.nix

key-decisions:
  - "prereqHelper wrapper resolves DOTFILES or falls back to Parallels mount path"
  - "healthHelper uses critical vs optional failure distinction"
  - "Activation script checks device-broker status and suggests prerequisites"

patterns-established:
  - "Prerequisites scripts follow idempotent pattern with --check mode"
  - "Nix wrappers delegate to shell scripts in dotfiles repo for system-level work"

# Metrics
duration: 10min
completed: 2026-02-03
---

# Phase 5 Plan 1: Automate Intune Prerequisites Summary

**Created idempotent intune-prerequisites.sh script automating Section 8 of stargazer/README.md, plus Nix module wrappers and health check**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-02-03T17:32:00Z
- **Completed:** 2026-02-03T17:42:27Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created comprehensive intune-prerequisites.sh (389 lines) automating all 8 manual Intune setup sections
- Added prereqHelper Nix wrapper that invokes the script from dotfiles
- Added healthHelper for comprehensive layer-by-layer diagnostic checks
- Updated activation script to suggest running intune-prerequisites if device-broker not running

## Task Commits

Each task was committed atomically:

1. **Task 1: Create intune-prerequisites.sh script** - `d25d9ae` (feat)
2. **Task 2: Add Nix module wrappers** - `e5ca956` (feat)

**Plan metadata:** pending

## Files Created/Modified

- `scripts/intune-prerequisites.sh` - Idempotent script for D-Bus policy, device broker, pcscd, PKCS#11, ccid, PAM, keyring
- `modules/home/linux/intune.nix` - Added prereqHelper, healthHelper, updated activation script

## Decisions Made

- prereqHelper checks both DOTFILES env var and Parallels mount path (/mnt/psf/Home/Documents/dotfiles)
- healthHelper distinguishes critical vs optional failures (exit 1 only for critical)
- YubiKey checks are optional warnings (not failures if not inserted)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added healthHelper for diagnostics**

- **Found during:** Task 2 (Nix module updates)
- **Issue:** Plan mentioned 05-02-PLAN.md would implement health check, but having basic health check alongside prerequisites makes sense for immediate validation
- **Fix:** Added comprehensive healthHelper with critical/optional distinction
- **Files modified:** modules/home/linux/intune.nix
- **Verification:** Module evaluates, helper is in packages
- **Committed in:** e5ca956

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** healthHelper was planned for 05-02 but naturally fit here; 05-02 can now focus on enhanced diagnostics or validation.

## Issues Encountered

None - both tasks completed as specified.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- intune-prerequisites.sh ready for testing on stargazer VM
- intune-health command available for diagnostics
- Ready for 05-02-PLAN.md (enhanced diagnostics or validation)
- May need to adjust 05-02-PLAN.md scope since healthHelper already implemented

---
*Phase: 05-intune-components*
*Completed: 2026-02-03*
