# Multi-Platform Nix Dotfiles Refactoring

## Overview

Refactor the dotfiles repository to support two primary platforms:
- **macOS (behemoth)**: nix-darwin + home-manager as module
- **Linux (rocinante)**: standalone home-manager only

NixOS support is deprioritized - remove NixOS-specific modules to simplify.

## Inspiration

- [dustinlyons/nixos-config](https://github.com/dustinlyons/nixos-config) - clean platform separation
- [hlissner/dotfiles](https://github.com/hlissner/dotfiles) - structured approach with lib/ functions

## Current Issues

1. **`lib/mkFlake.nix`** only builds `nixosConfigurations`
2. **`modules/default.nix`** has NixOS-specific config hardcoded (boot, fileSystems, users)
3. **Modules use system-level options** instead of portable home-manager style

## Target Architecture

```
dotfiles/
├── flake.nix
├── lib/
│   ├── default.nix
│   ├── mkFlake.nix              # + mkDarwinHost, mkHomeConfig
│   ├── modules.nix
│   ├── options.nix
│   └── attrs.nix
├── hosts/
│   ├── behemoth/                # macOS (nix-darwin + HM)
│   └── rocinante/               # Linux (standalone HM)
├── modules/
│   ├── default.nix              # Platform-aware root loader
│   ├── darwin/                  # Darwin-only
│   │   ├── default.nix          # Darwin base config
│   │   └── homebrew.nix         # Homebrew integration
│   └── home/                    # Home-manager (shared)
│       ├── default.nix          # HM base
│       ├── shell/               # git, nushell, fish, direnv
│       ├── dev/                 # nix, rust, etc
│       └── profiles/            # user profiles
```

---

## Implementation Phases

### Phase 1: Clean Up - Remove NixOS Modules

Delete NixOS-specific files:

```
modules/desktop/           # wayland, gdm, X11
modules/services/docker.nix
modules/services/ssh.nix   # if NixOS-specific
modules/system/fs.nix
modules/system/security.nix
modules/profiles/hardware/
hosts/rocinante/disk.nix
```

### Phase 2: Create Directory Structure

```bash
mkdir -p modules/darwin modules/home/shell modules/home/dev modules/home/profiles
```

### Phase 3: Extend lib/mkFlake.nix

Add platform detection and builders:

```nix
# Detect host type from system string
hostType = system:
  if lib.hasSuffix "darwin" system then "darwin"
  else "home";  # Linux = standalone home-manager

# Build Darwin configuration
mkDarwinHost = name: host:
  inputs.darwin.lib.darwinSystem {
    system = host.system;
    specialArgs = { inherit inputs; inherit (self) lib; };
    modules = [
      inputs.home-manager.darwinModules.home-manager
      { home-manager.useGlobalPkgs = true; home-manager.useUserPackages = true; }
      # ... host modules
    ];
  };

# Build standalone home-manager configuration
mkHomeConfiguration = name: host:
  inputs.home-manager.lib.homeManagerConfiguration {
    pkgs = mkPkgs host.system;
    extraSpecialArgs = { inherit inputs; inherit (self) lib; };
    modules = [ /* ... */ ];
  };
```

Output structure:
```nix
{
  darwinConfigurations.behemoth = mkDarwinHost "behemoth" hosts.behemoth;
  homeConfigurations.rocinante = mkHomeConfiguration "rocinante" hosts.rocinante;
}
```

### Phase 4: Create Darwin Base Modules

**`modules/darwin/default.nix`:**
```nix
{ lib, config, pkgs, inputs, ... }:

{
  imports = lib.mapModulesRec' ./. import;

  config = {
    services.nix-daemon.enable = true;

    nix.settings = {
      experimental-features = [ "nix-command" "flakes" ];
      trusted-users = [ "root" config.user.name ];
    };

    system.stateVersion = 5;

    # Darwin user setup
    users.users.${config.user.name} = {
      name = config.user.name;
      home = "/Users/${config.user.name}";
    };
  };
}
```

**`modules/darwin/homebrew.nix`:**
```nix
{ lib, config, inputs, ... }:

with lib;
let cfg = config.modules.darwin.homebrew;
in {
  options.modules.darwin.homebrew.enable = lib.mkBoolOpt false;

  config = mkIf cfg.enable {
    nix-homebrew = {
      enable = true;
      enableRosetta = true;
      user = config.user.name;
      taps = {
        "homebrew/homebrew-core" = inputs.homebrew-core;
        "homebrew/homebrew-cask" = inputs.homebrew-cask;
        "homebrew/homebrew-bundle" = inputs.homebrew-bundle;
      };
      mutableTaps = false;
    };

    homebrew = {
      enable = true;
      onActivation.cleanup = "zap";
      casks = [];  # GUI apps
      brews = [];  # CLI tools
    };
  };
}
```

### Phase 5: Migrate Shell/Dev to Home-Manager Style

Convert modules to use `programs.*` and `home.packages`:

| Current | New | Pattern |
|---------|-----|---------|
| `modules/shell/git.nix` | `modules/home/shell/git.nix` | `programs.git.enable = true` |
| `modules/shell/nushell.nix` | `modules/home/shell/nushell.nix` | `programs.nushell.enable = true` |
| `modules/shell/fish.nix` | `modules/home/shell/fish.nix` | `programs.fish.enable = true` |
| `modules/shell/direnv.nix` | `modules/home/shell/direnv.nix` | `programs.direnv.enable = true` |
| `modules/dev/nix.nix` | `modules/home/dev/nix.nix` | `home.packages = [ pkgs.nil ]` |
| `modules/dev/rust.nix` | `modules/home/dev/rust.nix` | `home.packages = [ fenix... ]` |

**Example - git.nix (home-manager style):**
```nix
{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.shell.git;
in {
  options.modules.shell.git.enable = lib.mkBoolOpt false;

  config = mkIf cfg.enable {
    programs.git = {
      enable = true;
      lfs.enable = true;
      userName = "Andrey M";
      userEmail = "...";
    };

    home.packages = with pkgs; [
      gh
      git-crypt
    ];
  };
}
```

### Phase 6: Refactor Root Module Loader

**`modules/default.nix`:**
```nix
{ lib, config, options, pkgs, inputs, ... }:

with lib;
let
  isDarwin = pkgs.stdenv.isDarwin;
in
{
  imports =
    # Always import home modules
    lib.mapModulesRec' ./home import
    # Import darwin modules only on macOS
    ++ lib.optional isDarwin (import ./darwin);

  options = with types; {
    modules = {};
    user = lib.mkOpt attrs { name = ""; };
  };

  config = {
    user = {
      name = mkDefault "andreym";
      description = mkDefault "Primary user";
    };

    # Cross-platform nix settings (for darwin, HM uses nix.settings differently)
    nixpkgs.config.allowUnfree = true;
  };
}
```

### Phase 7: Update Host Configurations

**`hosts/behemoth/default.nix` (macOS):**
```nix
{ lib, ... }:

{
  system = "aarch64-darwin";

  modules = {
    profiles.user = "andreym";

    darwin.homebrew.enable = true;

    shell = {
      default = "nushell";
      nushell.enable = true;
      fish.enable = true;
      git.enable = true;
      direnv.enable = true;
    };

    dev = {
      nix.enable = true;
    };
  };

  config = { config, ... }: {
    networking.hostName = "behemoth";
    networking.computerName = "Behemoth";

    home-manager.users.${config.user.name} = {
      home.stateVersion = "24.05";
    };
  };
}
```

**`hosts/rocinante/default.nix` (Linux - standalone HM):**
```nix
{ lib, ... }:

{
  system = "x86_64-linux";  # or aarch64-linux
  homeDirectory = "/home/andreym";

  modules = {
    profiles.user = "andreym";

    shell = {
      default = "nushell";
      nushell.enable = true;
      fish.enable = true;
      git.enable = true;
      direnv.enable = true;
    };

    dev = {
      nix.enable = true;
    };
  };

  config = {
    home.stateVersion = "24.05";
  };
}
```

### Phase 8: Test and Verify

```bash
# Check flake validity
nix flake check

# Build Darwin config
nix build .#darwinConfigurations.behemoth.system

# Build home-manager config
nix build .#homeConfigurations.rocinante.activationPackage

# Deploy on macOS
darwin-rebuild switch --flake .#behemoth

# Deploy on Linux (standalone HM)
home-manager switch --flake .#rocinante
```

---

## Files Summary

### Create
| File | Purpose |
|------|---------|
| `modules/darwin/default.nix` | Darwin base config |
| `modules/darwin/homebrew.nix` | Homebrew integration |
| `modules/home/default.nix` | Home-manager base |
| `modules/home/shell/default.nix` | Shell loader |
| `modules/home/shell/git.nix` | Git (HM style) |
| `modules/home/shell/nushell.nix` | Nushell (HM style) |
| `modules/home/shell/fish.nix` | Fish (HM style) |
| `modules/home/shell/direnv.nix` | Direnv (HM style) |
| `modules/home/dev/default.nix` | Dev loader |
| `modules/home/dev/nix.nix` | Nix tools |

### Modify
| File | Changes |
|------|---------|
| `lib/mkFlake.nix` | Add mkDarwinHost, mkHomeConfiguration |
| `modules/default.nix` | Platform-aware imports, remove NixOS code |
| `hosts/behemoth/default.nix` | Full Darwin config |
| `hosts/rocinante/default.nix` | Convert to standalone HM |

### Delete
| File | Reason |
|------|--------|
| `modules/desktop/` | NixOS-only (wayland, GDM) |
| `modules/services/docker.nix` | NixOS virtualisation |
| `modules/services/ssh.nix` | NixOS services |
| `modules/system/fs.nix` | NixOS boot/fs |
| `modules/system/security.nix` | NixOS security |
| `modules/profiles/hardware/` | NixOS hardware |
| `hosts/rocinante/disk.nix` | Disko (NixOS) |

---

## Design Decisions

1. **No NixOS support** for now - simplifies significantly, can add back later
2. **Home-manager primary** for all user config - portable across platforms
3. **Keep hlissner-style options** (`modules.shell.default`) - familiar pattern
4. **Naming**: rocinante = Linux, behemoth = macOS
5. **Home-manager integration**:
   - Darwin: as nix-darwin module (`home-manager.darwinModules.home-manager`)
   - Linux: standalone (`homeManagerConfiguration`)
