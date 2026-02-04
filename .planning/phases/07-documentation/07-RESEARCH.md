# Phase 7: Documentation - Research

**Researched:** 2026-02-03
**Domain:** Technical documentation for Intune-compliant VM setup (guides, troubleshooting, procedures)
**Confidence:** HIGH

## Summary

Phase 7 creates documentation for the complete Omarchy Linux VM setup with Intune enrollment. The research reveals that substantial documentation already exists across the codebase from Phases 1-6 - the challenge is consolidation, not creation from scratch. The existing `hosts/stargazer/README.md` (384 lines) serves as a near-complete E2E guide. Additional docs exist in `docs/arch-arm-encrypted-install.md`, `docs/omarchy-grub-install.md`, and `docs/template-generalization.md`. The scripts themselves (`intune-health`, `intune-prerequisites`, `prerequisites.sh`) provide excellent troubleshooting context through their inline comments and error messages.

The documentation requirements (DOC-01 through DOC-04) map directly to the existing content with gaps primarily in: (1) systematic troubleshooting organized by symptom, (2) upgrade procedures for Omarchy and Intune packages, and (3) formal verification checklists. The upgrade procedures are particularly important given the workarounds in place (OpenSSL 3.3.2 pinning, Arch package archives).

**Primary recommendation:** Consolidate existing documentation into three deliverables: (1) enhance stargazer README with verification checklists embedded at each step, (2) create dedicated troubleshooting guide with symptom-to-solution mapping, (3) create upgrade procedures document focusing on the pinned packages and how to test updates.

## Standard Stack

Documentation tooling and formats used in this project:

### Core
| Tool | Purpose | Why Standard |
|------|---------|--------------|
| Markdown | Documentation format | Universal, version-controlled, renders in GitHub |
| Inline code blocks | Command examples | Copy-paste friendly, syntax highlighting |
| Tables | Reference data | Scannable, organized information |
| Collapsible sections | Optional details | Keeps main flow clean |

### Existing Documentation Assets
| Document | Lines | Purpose | Status |
|----------|-------|---------|--------|
| `hosts/stargazer/README.md` | 384 | E2E setup guide | Complete (Phase 3) |
| `docs/arch-arm-encrypted-install.md` | 378 | LUKS installation | Complete (Phase 1) |
| `docs/omarchy-grub-install.md` | 255 | Omarchy + GRUB preservation | Complete (Phase 1) |
| `docs/template-generalization.md` | 244 | Clone workflow | Complete (Phase 1) |
| `docs/intune-broker2.0.md` | 321 | Microsoft broker reference | Complete (reference) |
| `scripts/prerequisites.sh` | 233 | Rosetta + Nix setup | Complete (self-documenting) |
| `scripts/intune-prerequisites.sh` | 446 | Intune system config | Complete (self-documenting) |
| `modules/home/linux/intune.nix` | 656 | Nix module with wrappers | Complete (extensively commented) |

## Architecture Patterns

### Documentation Structure

```
hosts/stargazer/
├── README.md               # E2E guide (enhanced with checklists)
│
docs/
├── arch-arm-encrypted-install.md    # Template creation (existing)
├── omarchy-grub-install.md          # Omarchy + GRUB (existing)
├── template-generalization.md       # Clone workflow (existing)
├── intune-broker2.0.md              # Microsoft reference (existing)
├── TROUBLESHOOTING.md               # NEW: Symptom-based troubleshooting
└── UPGRADE-PROCEDURES.md            # NEW: Package update procedures
```

### Pattern 1: Verification Checklist Embedding

**What:** Embed verification checklists directly after each major section in the E2E guide, not as a separate document.

**Why:** Users verify as they go rather than backtracking. Failures are caught at the point of origin.

**Example (already in stargazer/README.md):**
```markdown
## 6. Run Prerequisites Script
...commands...

**Verification:**
- [ ] `cat /proc/sys/fs/binfmt_misc/rosetta` shows enabled
- [ ] `nix --version` outputs version number
- [ ] `ls /lib64/ld-linux-x86-64.so.2` shows symlink
```

### Pattern 2: Symptom-to-Solution Troubleshooting

**What:** Organize troubleshooting by user-observed symptoms, not by component.

**Why:** Users know what broke, not which component caused it.

**Structure:**
```markdown
## Symptom: No LUKS passphrase prompt after reboot

**What you see:**
- Boot hangs at "Loading initial ramdisk"
- Or: "Kernel panic - unable to mount root fs"

**Root cause:**
GRUB fix not applied, or Limine bootloader active instead of GRUB.

**Solution:**
1. Boot from archboot ISO
2. [Recovery steps...]

**Prevention:**
Always run `cp /boot/EFI/GRUB/grubaa64.efi /boot/EFI/BOOT/BOOTAA64.EFI` after armarchy.
```

### Pattern 3: Upgrade Runbook

**What:** Document package upgrade procedure with verification steps before/after.

**Why:** Pinned packages (OpenSSL 3.3.2, OpenSC 0.25.1 from Arch archives) have specific compatibility requirements. Upgrades need careful validation.

**Structure:**
```markdown
## Upgrading intune-portal

**Current version:** 1.2511.7
**Package source:** Microsoft .deb repackaged via Nix

### Pre-upgrade checklist
- [ ] Create VM snapshot: `prlctl snapshot $VM -n "Pre-Upgrade-$(date +%Y%m%d)"`
- [ ] Verify current enrollment: `intune-status`
- [ ] Note current compliance status

### Upgrade procedure
1. Update package hash in `packages/intune-portal/default.nix`
2. Rebuild: `nix run home-manager -- switch --flake .#stargazer -b backup`
3. Verify launch: `intune-portal-rosetta`

### Post-upgrade verification
- [ ] Portal launches without errors
- [ ] Can view device status
- [ ] Agent reports compliance: `intune-agent-rosetta && journalctl --user -u intune-agent --since "2 min ago"`

### Rollback
If verification fails:
1. `prlctl stop $VM --kill`
2. `prlctl snapshot-switch $VM --name "Pre-Upgrade-YYYYMMDD"`
```

### Anti-Patterns to Avoid

- **Separate verification doc:** Checklists belong inline with steps, not in a separate file users won't find
- **Component-organized troubleshooting:** Users don't know which component failed; organize by symptom
- **Undated procedures:** Upgrade docs without version context become stale; include package versions and dates
- **Duplicate content:** Reference existing docs rather than copying (e.g., "See docs/arch-arm-encrypted-install.md for template creation")

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Diagnostic output | Custom verification script | `intune-health` | Already comprehensive with hints |
| Component status | Manual checks | `intune-status` | Aggregates all info |
| Log viewing | Multiple journalctl | `intune-logs --all` | Combined view |
| Prerequisites validation | Manual file checks | `intune-prerequisites --check` | Existing check mode |
| Recovery from failed state | Manual cleanup | Snapshot restore | Clean slate guaranteed |

**Key insight:** The scripts created in Phases 2-5 already have extensive diagnostic output. Documentation should reference these scripts, not duplicate their checks in prose.

## Common Pitfalls

### Pitfall 1: Documentation Rot

**What goes wrong:** Docs become outdated as code changes, causing user confusion and support burden.

**Why it happens:** Documentation lives separately from code, no coupling between them.

**How to avoid:**
1. Keep docs close to code (hosts/stargazer/README.md, not wiki)
2. Include version numbers for packages (`intune-portal 1.2511.7`)
3. Date the documents (`Last updated: 2026-02-03`)
4. Cross-reference rather than duplicate

**Warning signs:**
- Users report steps don't match actual behavior
- Multiple versions of same procedure in different files

### Pitfall 2: Missing Context

**What goes wrong:** Troubleshooting guide provides solution but user doesn't understand why it works.

**Why it happens:** Documentation optimized for terseness over understanding.

**How to avoid:**
1. Include "Root cause" section explaining why the error occurs
2. Include "Prevention" section to avoid future occurrence
3. Link to deeper technical docs when relevant

### Pitfall 3: Single Perspective Documentation

**What goes wrong:** Guide assumes expert knowledge, confuses newcomers. Or oversimplifies, frustrates experts.

**Why it happens:** Writer has specific expertise level in mind.

**How to avoid:**
1. E2E guide: Assume minimal prior knowledge, step-by-step
2. Troubleshooting: Start with symptom (user knows), explain cause (for understanding)
3. Upgrade procedures: Assume operational familiarity, focus on verification

### Pitfall 4: Orphaned Documentation

**What goes wrong:** Docs scattered across multiple locations, users can't find relevant information.

**Why it happens:** Different phases created docs in different places without master index.

**How to avoid:**
1. Create clear entry point (`hosts/stargazer/README.md` as E2E guide)
2. Cross-reference related docs at appropriate points
3. Avoid creating new docs when existing docs can be enhanced

## Code Examples

### Verification Checklist Format

```markdown
## Section X: [Step Name]

[Procedure content...]

### Verification

Run these commands to verify the step completed successfully:

```bash
# Check 1: [Description]
command --flags
# Expected: [what should appear]

# Check 2: [Description]
another-command
# Expected: [what should appear]
```

**Checklist:**
- [ ] Check 1 passes
- [ ] Check 2 passes
- [ ] [Any additional manual verification]

**If checks fail:** See [link to troubleshooting section]
```

### Troubleshooting Entry Format

```markdown
### Problem: [Symptom in user's words]

**What you see:**
- Specific error message or behavior
- Where it appears (log, screen, etc.)

**Root cause:**
Why this happens - the underlying issue.

**Solution:**
1. Step one with command
   ```bash
   command here
   ```
2. Step two
3. Verification that it worked:
   ```bash
   verification-command
   # Expected: success indicator
   ```

**Prevention:**
How to avoid this in the future.

**Related:** [Links to other relevant sections]
```

### Upgrade Procedure Format

```markdown
## Upgrading [Component Name]

**Current version:** X.Y.Z
**Package source:** [where it comes from]
**Dependencies:** [what else might need updating]

### When to upgrade
- [Trigger condition, e.g., "When Microsoft releases new intune-portal version"]
- [Warning signs that upgrade is needed]

### Pre-upgrade checklist
- [ ] VM snapshot created
- [ ] Current state documented
- [ ] Rollback procedure reviewed

### Procedure
1. [Step with specific file/command]
2. [Step with verification]
3. [Step with potential failure point noted]

### Post-upgrade verification
- [ ] [Functional test 1]
- [ ] [Functional test 2]
- [ ] [Regression test]

### Rollback
If any verification fails:
1. [Immediate action]
2. [Restore command]
3. [Report issue location]

### Version history
| Date | Version | Notes |
|------|---------|-------|
| 2026-02-03 | 1.2511.7 | Current, working |
```

## Existing Documentation Gap Analysis

### DOC-01: E2E Guide (VM creation to enrolled device)

**Current state:** `hosts/stargazer/README.md` (384 lines) covers full workflow
**Gap:** Missing formal verification checklists at each section
**Recommendation:** Enhance existing README with embedded checklists, not new document

### DOC-02: Troubleshooting Guide

**Current state:** Scattered troubleshooting in various READMEs:
- `hosts/stargazer/README.md` - Section "Troubleshooting" (8 issues)
- `docs/arch-arm-encrypted-install.md` - Section "Troubleshooting" (5 issues)
- `docs/omarchy-grub-install.md` - Section "Troubleshooting" (4 issues)
- `docs/template-generalization.md` - Section "Troubleshooting" (3 issues)
- `intune-health` script - Hints for each failure
**Gap:** Not symptom-organized, duplicated across files
**Recommendation:** Create `docs/TROUBLESHOOTING.md` that consolidates all issues by symptom

### DOC-03: Upgrade Procedures

**Current state:** None documented
**Gap:** Critical gap - OpenSSL 3.3.2, OpenSC 0.25.1 are pinned for compatibility
**Recommendation:** Create `docs/UPGRADE-PROCEDURES.md` covering:
- Omarchy (armarchy updates) - major version upgrades
- intune-portal - Microsoft package updates
- microsoft-identity-broker - Microsoft package updates
- OpenSSL pinned version - when/how to update
- Arch archive packages - testing newer versions

### DOC-04: Verification Checklists

**Current state:** Informal verification commands in READMEs
**Gap:** Not formatted as checklists, not comprehensive
**Recommendation:** Embed checklists in `hosts/stargazer/README.md` at each major section

## Proposed Deliverables

### Plan 07-01: Enhanced E2E Guide with Checklists

Enhance `hosts/stargazer/README.md`:
1. Add formal verification checklist after each major section
2. Add "If this fails" links to troubleshooting sections
3. Add timestamps/version info to header
4. Ensure checklist format is consistent
5. Add pre-flight checklist before starting

### Plan 07-02: Consolidated Troubleshooting Guide

Create `docs/TROUBLESHOOTING.md`:
1. Extract all troubleshooting from existing docs
2. Reorganize by symptom (not component)
3. Add root cause and prevention for each
4. Cross-reference to relevant setup steps
5. Include log pattern examples for diagnosis

### Plan 07-03: Upgrade Procedures

Create `docs/UPGRADE-PROCEDURES.md`:
1. Document Omarchy upgrade procedure
2. Document Intune package upgrade procedure
3. Document pinned package upgrade/testing procedure
4. Include version history table
5. Include rollback procedures for each

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Wiki documentation | Git-versioned markdown | Industry standard | Versioned with code |
| Separate checklists | Embedded verification | Best practice | Users don't skip |
| Component-based troubleshooting | Symptom-based | UX research | Users can self-diagnose |
| Ad-hoc upgrades | Documented runbooks | DevOps practice | Reproducible, safe |

## Open Questions

### 1. Verification Checklist Granularity

**What we know:** Need checklists at each major section
**What's unclear:** How granular? Per command? Per section? Per phase?
**Recommendation:** Per section (numbered headers in README), with commands grouped logically

### 2. Troubleshooting Index Strategy

**What we know:** Issues span boot, Nix, Intune, YubiKey domains
**What's unclear:** One file or multiple? How to organize for discoverability?
**Recommendation:** Single TROUBLESHOOTING.md with clear section headers and table of contents at top

### 3. Upgrade Testing Environment

**What we know:** Upgrades need testing before production
**What's unclear:** Should docs prescribe specific test VM? Reference VM from Phase 6?
**Recommendation:** Reference the IntuneFreshTest VM (or similar) created in Phase 6 as the upgrade testing environment

## Sources

### Primary (HIGH confidence)

- `hosts/stargazer/README.md` - Existing E2E guide, 384 lines
- `docs/arch-arm-encrypted-install.md` - LUKS installation, 378 lines
- `docs/omarchy-grub-install.md` - Omarchy + GRUB, 255 lines
- `docs/template-generalization.md` - Clone workflow, 244 lines
- `modules/home/linux/intune.nix` - Nix module source, 656 lines
- `scripts/prerequisites.sh` - Setup script, 233 lines
- `scripts/intune-prerequisites.sh` - Intune config, 446 lines
- `.planning/phases/06-enrollment-compliance/06-RESEARCH.md` - Enrollment patterns

### Secondary (MEDIUM confidence)

- `docs/intune-broker2.0.md` - Microsoft broker reference (external source)
- Phase 1-6 PLAN and SUMMARY files - Implementation context

### Tertiary (LOW confidence)

- WebSearch results were empty (service unavailable)
- Documentation patterns based on training knowledge and industry standards

## Metadata

**Confidence breakdown:**
- Documentation structure: HIGH - Based on existing codebase analysis
- Gap analysis: HIGH - Direct comparison of requirements vs existing docs
- Troubleshooting patterns: MEDIUM - Based on existing scripts and common issues encountered in phases
- Upgrade procedures: MEDIUM - Novel content, based on package management understanding

**Research date:** 2026-02-03
**Valid until:** 90+ days (documentation patterns stable)
