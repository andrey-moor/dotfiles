# Phase 4: Nix Module Refactoring - Context

**Gathered:** 2026-02-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Refactor intune-rosetta.nix to be lean, well-designed, with named abstractions for library paths and single architecture detection. This is a code cleanup phase — the module should work identically to before, just with better structure.

**Out of scope:** Fixing Intune enrollment issues, adding new functionality. Those are Phases 5-6.

</domain>

<decisions>
## Implementation Decisions

### Section organization
- Single file with architecture detection at the top
- Organized by function: detection → library paths → wrappers → services → binfmt
- Reading top-to-bottom follows the dependency chain
- Rosetta-specific pieces (binfmt) live in clearly-marked conditional sections

### Library path abstractions
- Use category-based groupings: `glibcLibs`, `x11Libs`, `qtLibs`, etc.
- Packages compose from categories (e.g., `intunePortalLibs = glibcLibs ++ x11Libs ++ qtLibs ++ [...]`)
- Keep as internal let bindings (not exposed as module options)
- Clearly mark entire section as workaround with TODO for future arm64 removal
- Makes it obvious what's needed for what purpose and easy to rip out later

### Architecture detection
- Auto-detect using mode enum: `native-x86_64`, `rosetta`, (future: `native-arm64`)
- x86_64-linux → native-x86_64 mode
- aarch64-linux + rosetta binary exists → rosetta mode
- Future: arm64 packages available → native-arm64 mode (skips library workarounds)
- Detection happens once at top, everything downstream uses the mode

### Code documentation
- Audience: Future me/team — explain WHY decisions were made, not obvious WHAT
- Comprehensive header block explaining module purpose, modes, and usage
- Each workaround gets context about why it exists

### Testing approach
- Phase 4 = refactor only, not fix enrollment
- Verify builds on both arches (stargazer/rosetta, rocinante/native)
- Existing hosts switch successfully with same behavior
- Snapshot before/after for regression safety

### Claude's Discretion
- Section header comment style (banners vs minimal)
- Options placement (grouped at top vs with implementation)
- Mode visibility (expose as read-only option or keep internal)
- Fallback behavior when Rosetta not found
- Library path variable naming conventions
- Workaround documentation style (inline vs collected section)
- Whether to include companion README alongside module

</decisions>

<specifics>
## Specific Ideas

- "Structure it so we can refactor later when arm64 Intune packages arrive"
- Library paths section should be self-contained and easy to remove entirely
- Mode enum approach allows easy addition of native-arm64 when available
- The refactor is about maintainability, not changing behavior

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-nix-module-refactoring*
*Context gathered: 2026-02-03*
