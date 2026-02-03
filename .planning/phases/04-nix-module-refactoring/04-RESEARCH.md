# Phase 04: Nix Module Refactoring - Research

**Researched:** 2026-02-03
**Domain:** Nix module system, home-manager module patterns, code organization
**Confidence:** HIGH

## Summary

This phase refactors the `intune-rosetta.nix` module (currently 1048 lines) to be lean, well-designed, with named library path abstractions and unified architecture detection. The target is under 500 lines with clear section organization.

Research focused on:
1. Nix module patterns from this codebase (git.nix, kubernetes.nix, edge-rosetta.nix)
2. Architecture detection patterns via `stdenv.hostPlatform`
3. Library path organization strategies for maintainability
4. Best practices for documentation in Nix modules

**Primary recommendation:** Merge `intune-rosetta.nix` and `intune-nix.nix` concepts into a single unified module with mode-based detection (`native-x86_64` vs `rosetta`), category-based library groupings, and clear workaround documentation.

## Standard Stack

### Core: Nix Module Patterns (this codebase)

| Pattern | Usage | Example File |
|---------|-------|--------------|
| `let cfg = config.modules.<path>` | Standard config binding | All modules |
| `mkIf (cfg.enable && pkgs.stdenv.isLinux)` | Platform guard | `rosetta.nix:17` |
| `pkgs.stdenv.hostPlatform.isAarch64` | Architecture detection | `rosetta.nix:17` |
| `pkgs.stdenv.hostPlatform.isx86_64` | x86_64 detection | `intune-nix.nix:513` |
| `lib.optionalString cfg.debug` | Conditional string injection | `intune-rosetta.nix:242` |
| `lib.hm.dag.entryAfter` | Activation ordering | `intune-rosetta.nix:1026` |

### Supporting: Platform Detection

| Pattern | When True | Source |
|---------|-----------|--------|
| `pkgs.stdenv.isLinux` | Any Linux system | [NixOS Discourse](https://discourse.nixos.org/t/stdenv-isdarwin-stdenv-isaarch64-vs-aarch64-darwin/37922) |
| `pkgs.stdenv.hostPlatform.isAarch64` | aarch64 architecture | Same |
| `pkgs.stdenv.hostPlatform.isx86_64` | x86_64 architecture | Same |
| File exists check | Dynamic detection | Bash in activation |

### Library Path Categories (proposed)

Based on analyzing the current `libPaths` attrset, libraries can be grouped by function:

| Category | Description | Example Packages |
|----------|-------------|------------------|
| `glibcLibs` | Core C runtime | glibc, libstdcxx |
| `systemLibs` | System integration | dbus, systemd, util-linux |
| `x11Libs` | X11/Wayland display | xorg.*, wayland, libxkbcommon |
| `gtkLibs` | GTK toolkit stack | gtk3, gdk-pixbuf, cairo, pango, atk, harfbuzz |
| `webkitLibs` | WebKitGTK dependencies | webkitgtk_4_1, libsoup_3, gstreamer |
| `tlsLibs` | TLS/crypto | gnutls, nettle, openssl |
| `pkcs11Libs` | Smart card | opensc, p11-kit, pcsclite, libfido2 |
| `mediaLibs` | Media handling | libpng, libjpeg, libwebp, lcms2 |
| `networkLibs` | HTTP/network | curl, libssh2, nghttp2, brotli |

## Architecture Patterns

### Recommended Module Structure

```
modules/home/linux/intune.nix
├── Header documentation block
│   └── Purpose, modes, usage, caveats
├── Module function signature
│   └── { lib, config, pkgs, ... }:
├── Architecture detection (let block)
│   ├── mode = if x86_64 then "native" else if rosetta then "rosetta" else null
│   └── pkgSource = if mode == "rosetta" then pkgsX86 else pkgs
├── Library path definitions (let block)
│   ├── Category groupings (glibcLibs, x11Libs, etc.)
│   ├── Composed application paths (intunePortalLibs = x11Libs ++ gtkLibs ++ ...)
│   └── Workaround section (opensslArch, openscArch) with TODO markers
├── Environment variable helpers
│   └── mesaEnvVars, webkitEnvVars, tlsEnvVars, pkcs11EnvVars, debugEnvVars
├── Wrapper scripts
│   └── intuneWrapper, brokerWrapper, agentWrapper
├── Helper scripts
│   └── logsHelper, statusHelper, diagHelper
├── Options declaration
│   └── enable, debug
└── Config implementation
    ├── mkIf guard with mode check
    ├── home.packages
    ├── xdg.dataFile / xdg.configFile
    ├── systemd.user.services / timers
    └── home.activation
```

### Pattern 1: Mode-Based Architecture Detection

**What:** Detect architecture once at module top, use mode enum throughout
**When to use:** When same module must handle multiple architectures
**Example:**

```nix
# Source: CONTEXT.md decisions
let
  # Detect operating mode once at top
  mode =
    if pkgs.stdenv.hostPlatform.isx86_64 then "native-x86_64"
    else if pkgs.stdenv.hostPlatform.isAarch64 && builtins.pathExists "/mnt/psf/RosettaLinux/rosetta"
    then "rosetta"
    else null;  # Future: native-arm64 when Microsoft ships arm64 packages

  isRosetta = mode == "rosetta";
  isNativeX86 = mode == "native-x86_64";

  # Package source varies by mode
  pkgSource = if isRosetta then pkgsX86 else pkgs;

  # Cross-arch x86_64 packages (only needed for Rosetta mode)
  pkgsX86 = import pkgs.path {
    system = "x86_64-linux";
    config.allowUnfree = true;
  };
in
```

### Pattern 2: Category-Based Library Groupings

**What:** Group libraries by functional category, compose for applications
**When to use:** When many libraries needed for LD_LIBRARY_PATH
**Example:**

```nix
# Source: CONTEXT.md decisions
let
  # ============================================================================
  # LIBRARY PATHS - WORKAROUND SECTION
  # TODO: Remove entire section when native arm64 Intune packages available
  # These libraries are needed because we run x86_64 binaries on Arch Linux
  # which doesn't have these in standard library paths.
  # ============================================================================

  # Core system libraries
  glibcLibs = [
    "${pkgSource.stdenv.cc.cc.lib}/lib"  # libstdc++
  ];

  systemLibs = [
    "${pkgSource.dbus.lib}/lib"
    "${pkgSource.glib.out}/lib"
    "${pkgSource.systemdLibs}/lib"
    "${pkgSource.util-linux.lib}/lib"
    "${pkgSource.zlib.out}/lib"
    "${pkgSource.zstd.out}/lib"
    "${pkgSource.icu.out}/lib"
    "${pkgSource.expat.out}/lib"
    "${pkgSource.pcre2.out}/lib"
  ];

  x11Libs = [
    "${pkgSource.xorg.libX11.out}/lib"
    "${pkgSource.xorg.libXext.out}/lib"
    # ... remaining X11 libs
    "${pkgSource.libxkbcommon.out}/lib"
  ];

  # Compose for specific applications
  intunePortalLibs = lib.concatStringsSep ":" (
    glibcLibs ++ systemLibs ++ x11Libs ++ gtkLibs ++ webkitLibs ++ tlsLibs
  );
in
```

### Pattern 3: Conditional Rosetta Support

**What:** Enable Rosetta module dependency only in Rosetta mode
**When to use:** Module depends on another conditional module
**Example:**

```nix
config = mkIf (cfg.enable && pkgs.stdenv.isLinux && mode != null) {
  # Enable Rosetta binfmt support (only for Rosetta mode)
  modules.linux.rosetta.enable = isRosetta;

  # Rest of config...
};
```

### Anti-Patterns to Avoid

- **Duplicated LD_LIBRARY_PATH strings:** Currently repeated 4 times in different wrappers. Use composed variable instead.
- **Inline architecture checks:** Don't scatter `pkgs.stdenv.hostPlatform.isAarch64` throughout. Detect once, use mode variable.
- **Unlabeled workarounds:** Mark temporary workarounds with TODO and explanation for future removal.
- **Options at bottom:** Options should be near top, after let block but before config (easier to find).

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Platform detection | Custom string parsing | `pkgs.stdenv.hostPlatform.*` | Covers edge cases, maintained |
| Conditional lists | Manual if/else | `lib.optionals condition list` | Cleaner, composable |
| Conditional strings | String interpolation | `lib.optionalString condition str` | Handles empty case |
| Config merging | Manual attrset merge | `lib.mkMerge [ {...} {...} ]` | Proper module system integration |
| Path joining | Manual `:` concatenation | `lib.concatStringsSep ":" list` | Cleaner, no trailing colons |

**Key insight:** The Nix module system and lib functions handle edge cases (empty lists, null values) that manual implementations often miss.

## Common Pitfalls

### Pitfall 1: Infinite Recursion in Platform Checks

**What goes wrong:** Using `lib.optionalAttrs pkgs.stdenv.isLinux { ... }` at top level
**Why it happens:** Module system needs to evaluate condition before config, creating circular dependency
**How to avoid:** Always use `lib.mkIf` for conditional config blocks, never `lib.optionalAttrs` at top level
**Warning signs:** "error: infinite recursion encountered" during evaluation

### Pitfall 2: LD_LIBRARY_PATH Order Matters

**What goes wrong:** Libraries loaded in wrong order cause symbol conflicts or crashes
**Why it happens:** Dynamic linker uses first matching library it finds
**How to avoid:** Critical libraries (OpenSSL 3.3.2, libglvnd) must come first in path
**Warning signs:** "symbol version OPENSSL_3.x.x not defined" errors

### Pitfall 3: Wrapper Script Environment Leakage

**What goes wrong:** Environment variables set in wrapper affect child processes unexpectedly
**Why it happens:** Mesa/WebKit env vars like LIBGL_ALWAYS_SOFTWARE break other apps
**How to avoid:** Set vars only for the specific binary, don't use global sessionVariables
**Warning signs:** Hyprland/Wayland compositor breaks, other apps use software rendering

### Pitfall 4: Cross-Arch Package Evaluation

**What goes wrong:** `pkgsX86` evaluates even when not needed (native x86_64)
**Why it happens:** Nix is lazy but pkgsX86 definition forces nixpkgs import
**How to avoid:** Wrap in conditional or use `lib.mkIf isRosetta` for the import
**Warning signs:** Slow evaluation on x86_64 hosts, unnecessary Rosetta package downloads

## Code Examples

Verified patterns from this codebase:

### Simple Module Pattern (from git.nix)

```nix
# Source: /Users/andreym/Documents/dotfiles/modules/home/shell/git.nix
{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.shell.git;
in {
  options.modules.shell.git = {
    enable = mkEnableOption "Git configuration";
    signingKey = mkOption {
      type = types.str;
      default = "";
      description = "GPG key ID for signing commits";
    };
  };

  config = mkIf cfg.enable {
    programs.git = { ... };
  };
}
```

### Platform-Guarded Module (from rosetta.nix)

```nix
# Source: /Users/andreym/Documents/dotfiles/modules/home/linux/rosetta.nix
config = mkIf (cfg.enable && pkgs.stdenv.isLinux && pkgs.stdenv.hostPlatform.isAarch64) {
  xdg.configFile."nix/nix.conf".text = ''
    extra-platforms = x86_64-linux
  '';
};
```

### Wrapper Script Pattern (from edge-rosetta.nix)

```nix
# Source: /Users/andreym/Documents/dotfiles/modules/home/linux/edge-rosetta.nix
edgeWrapper = pkgs.writeShellScriptBin "microsoft-edge-rosetta" ''
  exec ${pkgs.bubblewrap}/bin/bwrap \
    --setenv LIBGL_ALWAYS_SOFTWARE 1 \
    --setenv LD_LIBRARY_PATH "${libraries}:''${LD_LIBRARY_PATH:-}" \
    -- ${edgePackage}/bin/microsoft-edge "$@"
'';
```

### Category List Composition

```nix
# Source: Proposed pattern based on CONTEXT.md decisions
let
  x11Libs = map (p: "${p}/lib") [
    pkgSource.xorg.libX11.out
    pkgSource.xorg.libXext.out
    pkgSource.xorg.libXrender.out
  ];

  gtkLibs = map (p: "${p}/lib") [
    pkgSource.gtk3.out
    pkgSource.gdk-pixbuf.out
    pkgSource.cairo.out
  ];

  # Compose final path
  fullLibraryPath = lib.concatStringsSep ":" (x11Libs ++ gtkLibs ++ systemLibs);
in
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate intune-nix + intune-rosetta | Unified module with mode detection | This phase | Single module to maintain |
| Flat libPaths attrset | Category-based lib groupings | This phase | Clear purpose, easy removal |
| Inline architecture checks | Mode enum at top | This phase | Single source of truth |
| Duplicated LD_LIBRARY_PATH | Composed from categories | This phase | DRY, consistent |

**Deprecated/outdated in current code:**
- `intune.nix` (AUR-based): Not used, can be removed (uses system packages)
- Separate `-rosetta` suffix wrappers: Can unify when mode detection handles it

## Open Questions

### 1. Rosetta Detection Method

**What we know:** Current check is `builtins.pathExists "/mnt/psf/RosettaLinux/rosetta"`
**What's unclear:** Is this the best detection method? What if path changes?
**Recommendation:** Keep current path check, document in header. Path is Parallels-specific and unlikely to change. Alternative would be checking for binfmt registration in `/proc/sys/fs/binfmt_misc/rosetta` but that requires the module to already be running.

### 2. Error Handling for Unsupported Mode

**What we know:** If neither x86_64 nor Rosetta, mode is null
**What's unclear:** Should module error, warn, or silently disable?
**Recommendation:** Use `lib.mkIf (mode != null)` so config simply doesn't apply. Add activation warning if Rosetta mode expected but binary not found.

### 3. Line Count Target Feasibility

**What we know:** Current intune-rosetta.nix is 1048 lines, intune-nix.nix is 668 lines
**What's unclear:** Is 500 lines achievable with all functionality?
**Recommendation:** Target is achievable by:
  - Removing duplicate LD_LIBRARY_PATH strings (~100 lines saved)
  - Using list composition instead of manual concatenation (~50 lines)
  - Removing intune-nix.nix entirely (functionality merged)
  - Trimming verbose diagnostic helper scripts (~100 lines)

## Sources

### Primary (HIGH confidence)

- `/Users/andreym/Documents/dotfiles/modules/home/linux/intune-rosetta.nix` - Current implementation
- `/Users/andreym/Documents/dotfiles/modules/home/linux/intune-nix.nix` - x86_64 variant
- `/Users/andreym/Documents/dotfiles/modules/home/linux/rosetta.nix` - Rosetta binfmt module
- [Home Manager docs](https://context7.com/nix-community/home-manager) - Module patterns
- [Nix.dev](https://nix.dev/tutorials/module-system) - Module system

### Secondary (MEDIUM confidence)

- [NixOS Discourse - Platform Detection](https://discourse.nixos.org/t/stdenv-isdarwin-stdenv-isaarch64-vs-aarch64-darwin/37922) - `stdenv.hostPlatform` patterns
- [NixOS Wiki - Modules](https://nixos.wiki/wiki/NixOS_modules) - Module structure

### Tertiary (LOW confidence)

- [Nix.dev Style Guide](https://nix.dev/contributing/documentation/style-guide.html) - Documentation best practices (general, not Nix-specific)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Patterns from existing codebase, verified working
- Architecture: HIGH - Follows established codebase patterns, CONTEXT.md decisions locked
- Pitfalls: HIGH - Based on actual bugs encountered in current implementation

**Research date:** 2026-02-03
**Valid until:** 60 days (stable technology, locked decisions)
