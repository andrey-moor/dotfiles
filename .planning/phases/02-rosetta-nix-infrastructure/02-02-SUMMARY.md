---
phase: 02-rosetta-nix-infrastructure
plan: 02
subsystem: infra
tags: [validation, rosetta, binfmt, boot-survival, home-manager]

# Dependency graph
requires:
  - phase: 02-rosetta-nix-infrastructure
    plan: 01
    provides: prerequisites.sh script
provides:
  - Validated prerequisites.sh works on fresh VM clone
  - Rosetta binfmt survives reboot (VM-05 requirement)
  - home-manager switch works from shared folder (NIX-02 requirement)
affects: [03-vm-automation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Retry loop for async mount race conditions (30s polling)
    - prlctl exec with su for user context in remote execution

key-files:
  created: []
  modified:
    - scripts/prerequisites.sh

key-decisions:
  - "Retry loop over ConditionPathExists - prltoolsd mounts async after service script completes"
  - "glibc.out required for dynamic linker - default -bin output has no libs"

patterns-established:
  - "Async mount handling: poll for file existence rather than systemd conditions"
  - "prlctl exec with su for proper user environment (USER, HOME set correctly)"

# Metrics
duration: ~2h (including debugging boot race condition)
completed: 2026-02-02
---

# Phase 2 Plan 2: Script Validation Summary

**Validated prerequisites.sh on fresh VM clone with critical reboot survival test passing after fixing boot race condition**

## Performance

- **Duration:** ~2 hours (including debugging)
- **Started:** 2026-02-02
- **Completed:** 2026-02-02
- **Tasks:** 5
- **Files modified:** 1

## Accomplishments

- Cloned ArchBase-Template from Omarchy snapshot to Phase02-Test VM
- Ran prerequisites.sh successfully on fresh clone
- Fixed boot race condition: replaced ConditionPathExists with retry loop
- Verified reboot survival: Rosetta binfmt shows "enabled" after reboot
- Ran home-manager switch successfully via prlctl exec with su
- Cleaned up Phase02-Test VM

## Task Commits

1. **glibc.out fix** - `e101085` (fix) - Use glibc.out for dynamic linker symlink
2. **Retry loop fix** - `54e77fd` (fix) - Use retry loop for Rosetta binfmt boot survival

## Files Modified

- `scripts/prerequisites.sh` - Fixed boot race condition with 30s retry loop

## Decisions Made

- **Retry loop over ConditionPathExists:** Parallels mounts /mnt/psf asynchronously AFTER prltoolsd.service script completes. ConditionPathExists evaluates too early. Retry loop polls for 30 seconds.
- **glibc.out output:** Default `nix build nixpkgs#pkgsCross.gnu64.glibc` returns `-bin` output which only has binaries. Need `.out` to get lib directory with ld-linux-x86-64.so.2.

## Deviations from Plan

- **Cloning:** Used Omarchy snapshot instead of EncryptedBase-GRUB (Omarchy was already installed in that snapshot)
- **Mount path:** Test VM used /mnt/psf/dotfiles not /mnt/psf/Home/Documents/dotfiles (different shared folder config in template)
- **Boot fix iterations:** Took 4 attempts to solve boot race condition before landing on retry loop

## Issues Encountered

1. **Dynamic linker broken symlink** - Fixed by using glibc.out instead of glibc
2. **Boot race condition** - Path watcher alone didn't work because:
   - Attempt 1: PathExists unit - inotify doesn't work reliably on FUSE mounts
   - Attempt 2: After=mount-unit + ConditionPathExists - Mount unit created dynamically, timing race
   - Attempt 3: After=prltoolsd.service + ConditionPathExists - prltoolsd creates mounts async AFTER script completes
   - **Solution:** Remove conditions, use 30s polling retry loop

## User Setup Required

None - script handles all infrastructure setup.

## Phase 2 Success Criteria

- [x] After reboot, x86_64 binaries execute via Rosetta without manual intervention
- [x] Nix builds x86_64 packages via extra-platforms configuration
- [x] home-manager switch completes successfully from shared folder path
- [x] os-release shows Ubuntu 22.04 for Intune compatibility
- [x] Prerequisites script is idempotent (can be re-run safely)

## Next Phase Readiness

- Phase 2 complete: Rosetta + Nix infrastructure validated
- prerequisites.sh ready for production use
- Phase 3 (VM Automation Scripts) can proceed - clone and post-clone scripts

---
*Phase: 02-rosetta-nix-infrastructure*
*Completed: 2026-02-02*
