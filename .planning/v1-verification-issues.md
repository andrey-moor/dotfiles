# v1 E2E Verification Issues

**Testing:** hosts/stargazer/README.md workflow
**Started:** 2026-02-04
**Tester:** Manual walkthrough

## Progress

| Section | Status | Notes |
|---------|--------|-------|
| §1 Import Template | ✅ fixed | GUI import, VM settings documented |
| §2 First Boot | ✅ pass | No changes needed |
| §3 Change LUKS Passphrase | ✅ fixed | Added reboot verification |
| §4 Install Omarchy | ✅ fixed | curl, PT mount, Ctrl+C, PR link |
| §5 Restore GRUB | ✅ fixed | Omarchy confirm, resolution tip |
| §6 Prerequisites | ✅ fixed | Git clone workflow |
| §7 Home-Manager | ✅ fixed | Path updated |
| §8 Intune Setup | ✅ pass | No changes needed |
| §9 Enroll Device | ✅ pass | Successfully enrolled |

## Issues

### [DOCS] #9: Section 7 - Update dotfiles path
**Section:** §7 Home-Manager
**Problem:** Path references old `/mnt/psf/...` mount path
**Fix needed:** Update to use `~/dotfiles` (or `$DOTFILES` variable)

---

### [DOCS] #8: Section 6 - prerequisites.sh shows wrong path in next steps
**Section:** §6 Prerequisites
**Problem:** After running prerequisites.sh, the "next steps" output shows `/mnt/psf/...` path instead of detecting actual dotfiles location
**Fix needed:** Update prerequisites.sh to use `$DOTFILES` or detect the path it was run from for the next steps message

---

### [DOCS] #7: Section 6 - Clone dotfiles instead of mount
**Section:** §6 Prerequisites
**Problem:** Current guide assumes shared folder mount. Should use git clone for proper setup.
**Fix needed:**
1. Add git clone step: `git clone <repo> ~/dotfiles` (or configured path)
2. Run prerequisites.sh from cloned local path
3. Update instructions to use local path throughout
4. Make shared folder optional (convenience for dev, not required)

---

### [DOCS] #6: Section 5 - Add Omarchy confirmation + resolution fix
**Section:** §5 Restore GRUB Bootloader
**Problem:** No confirmation that Omarchy loaded successfully. Resolution may be poor.
**Fix needed:**
1. Add step to confirm Omarchy/Hyprland is running before GRUB fix
2. Add resolution tip from PR comments: If resolution is poor, go to Parallels VM → Hardware → Graphics → select "Scaled", then relaunch Hyprland
- Link to PR comments for details: https://github.com/basecamp/omarchy/pull/1897

---

### [DOCS] #5: Section 4 - Add Ctrl+C instruction after armarchy
**Section:** §4 Install Omarchy
**Problem:** After armarchy completes, user may not know how to get back to root terminal
**Fix needed:** Add explicit note: "Press Ctrl+C after armarchy completes to return to root terminal"

---

### [DOCS] #4: Section 4 - Add Parallels tools mount note
**Section:** §4 Install Omarchy
**Problem:** armarchy requires Parallels tools to be mounted (from PR notes)
**Fix needed:** Add note that Parallels tools CD must be mounted before running armarchy
- Actions menu → Install Parallels Tools (or mount manually)

---

### [DOCS] #3: Section 4 - wget missing + add PR link
**Section:** §4 Install Omarchy
**Problems:**
1. `wget` not installed by default on fresh Arch — use `curl` instead
2. Missing link to ARM64 PR for context
**Fix needed:**
- Replace `wget` with `curl -O` or `curl -L`
- Add link: https://github.com/basecamp/omarchy/pull/1897

---

### [DOCS] #2: Section 3 - Add reboot verification step
**Section:** §3 Change LUKS Passphrase
**Problem:** No verification that password change worked
**Fix needed:** Add step to reboot VM and verify new LUKS passphrase works before proceeding

---

### [DOCS] #1: Section 1 - Rework import instructions
**Section:** §1 Import Template
**Problem:** prlctl commands mentioned don't exist. Overly complex.
**Fix needed:**
- Manual GUI import only (double-click `arch-base-template.pvmp`)
- Remove non-existent prlctl commands
- Document recommended VM settings from working Stargazer:
  - CPU: 8 cores
  - Memory: 32GB
  - Network: Bridged (virtio)
  - Rosetta Linux: ON
  - Shared folder: `dotfiles` → `/Users/andreym/Documents/dotfiles` (rw)
  - EFI Secure boot: OFF
  - 3D acceleration: highest
  - Automatic sharing smart cards: ON (for YubiKey)

## Research Items

### [RESEARCH] Can we move from Parallels to another hypervisor?
**Context:** Parallels is paid/proprietary. Worth investigating alternatives.
**To explore:**
- UTM (free, QEMU-based, Apple Silicon native)
- VMware Fusion (free for personal use now?)
- QEMU direct
- What breaks? Rosetta integration, shared folders, prlctl automation

---

## Summary

- Total issues: 9 ✅ ALL FIXED
- Blockers: 0
- Bugs: 0
- Docs fixes: 8 → fixed in commit a4deb8b
- Enhancements: 1 → fixed in commit a4deb8b

**Verification complete:** 2026-02-04
**Enrollment tested:** ✅ Success
- Enhancements: 0

---
*Update this file as you test. When done, we'll review and create fixes.*
