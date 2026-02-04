# Plan: Fix 3 Tech Debt Items from Milestone Audit

## Overview
Fix all three tech debt items identified in the v1 milestone audit. All are simple text changes.

---

## Task 1: Fix All Three Tech Debt Items

### Changes Required

#### 1. scripts/prerequisites.sh (lines 231-232)
Change `endurance` → `stargazer`:
- Line 231: `.#endurance` → `.#stargazer`
- Line 232: `hosts/endurance/README.md` → `hosts/stargazer/README.md`

#### 2. scripts/intune-prerequisites.sh (line 83)
Make broker version pattern version-agnostic:
- Change: `'*microsoft-identity-broker-2.0.4'`
- To: `'*microsoft-identity-broker-*'`

#### 3. docs/TROUBLESHOOTING.md (line 48)
Remove `--verbose` flag (not implemented, not needed):
- Change: `intune-health --verbose`
- To: `intune-health`

### Validation
```bash
# Verify changes
grep -n "stargazer" scripts/prerequisites.sh
grep -n "broker-\*" scripts/intune-prerequisites.sh
grep -n "intune-health" docs/TROUBLESHOOTING.md
```

---

## Success Criteria
- [ ] prerequisites.sh references stargazer (not endurance)
- [ ] intune-prerequisites.sh uses version-agnostic broker pattern
- [ ] TROUBLESHOOTING.md shows `intune-health` without --verbose flag
