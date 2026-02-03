---
phase: 04-nix-module-refactoring
plan: 01
subsystem: intune
tags: [nix, home-manager, intune, rosetta, architecture-detection]

# Dependency graph
requires:
  - phase: 02-rosetta-binfmt
    provides: Rosetta binfmt module for x86_64 binary emulation
provides:
  - Unified intune.nix module with mode detection
  - Category-based library path organization
  - Single fullLibraryPath variable for all wrappers
affects: [04-02, 04-03, host-configs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mode detection enum (native-x86_64 | rosetta | null)"
    - "Category-based library groupings (glibcLibs, systemLibs, x11Libs, etc.)"
    - "Composed fullLibraryPath from categories"

key-files:
  created: []
  modified:
    - "modules/home/linux/intune.nix"

key-decisions:
  - "Merged intune-rosetta.nix and intune-nix.nix concepts into single module"
  - "Mode detection at module top, pkgSource resolves based on mode"
  - "Library paths organized by category for easy removal when arm64 arrives"
  - "Wrapper suffix (-rosetta vs empty) based on mode"

patterns-established:
  - "Architecture detection: mode = if x86_64 then 'native-x86_64' else if aarch64+rosetta then 'rosetta' else null"
  - "Category lib groupings: glibcLibs, systemLibs, x11Libs, gtkLibs, webkitLibs, tlsLibs, pkcs11Libs, mediaLibs, networkLibs, renderingLibs"

# Metrics
duration: 4min
completed: 2026-02-03
---

# Phase 04 Plan 01: Unified Intune Module Summary

**Unified intune.nix with mode detection (native-x86_64/rosetta), category-based library paths, and single fullLibraryPath variable reducing 1716 combined lines to 485**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-03T15:22:09Z
- **Completed:** 2026-02-03T15:26:56Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Created unified intune.nix replacing both intune-rosetta.nix (1048 lines) and intune-nix.nix (668 lines) concepts
- Implemented mode detection enum at module top (native-x86_64, rosetta, future native-arm64)
- Organized library paths by category with TODO markers for future arm64 removal
- Eliminated duplicate LD_LIBRARY_PATH strings by using single fullLibraryPath variable

## Task Commits

1. **Task 1: Create unified intune.nix with mode detection and library categories** - `45578b6` (refactor)

## Files Created/Modified

- `modules/home/linux/intune.nix` - Unified Intune module with architecture detection

## Decisions Made

1. **Mode detection at top** - Single point of architecture detection, everything downstream uses mode/isRosetta/isNativeX86 variables
2. **Category-based lib groupings** - Libraries organized by function (glibcLibs, systemLibs, x11Libs, gtkLibs, webkitLibs, tlsLibs, pkcs11Libs, mediaLibs, networkLibs, renderingLibs)
3. **Wrapper suffix pattern** - `-rosetta` suffix for Rosetta mode wrappers, empty for native x86_64
4. **Trimmed header** - Reduced verbose ASCII art diagram to concise summary to stay under 500 lines

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Unified module ready for host migration (04-02-PLAN.md)
- Old intune-rosetta.nix and intune-nix.nix can be removed after host configs updated
- Module option changed from `modules.linux.intune-rosetta` to `modules.linux.intune`

---
*Phase: 04-nix-module-refactoring*
*Completed: 2026-02-03*
