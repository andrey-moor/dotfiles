# Custom Nix library extending nixpkgs.lib
# Provides utilities for NixOS configuration management
#
# Usage in flake:
#   lib = import ./lib { inherit nixpkgs; };
#
# Functions are available in two ways:
#   1. Direct: lib.mergeAttrs', lib.mapModules, lib.mkOpt
#   2. Namespaced: lib.attrs.mergeAttrs', lib.modules.mapModules
#
# Note: This lib extends nixpkgs.lib, so all nixpkgs lib functions
# are also available (lib.mkIf, lib.optionals, etc.)
{ nixpkgs }:

let
  inherit (nixpkgs) lib;

  # Import all sub-libraries
  attrs = import ./attrs.nix { inherit lib; };
  modules = import ./modules.nix { inherit lib attrs; };
  options = import ./options.nix { inherit lib; };
  mkFlake = import ./mkFlake.nix { inherit lib modules; };

  # Our custom functions - avoid naming conflicts with nixpkgs lib
  # (nixpkgs lib has lib.modules, lib.options, lib.types, etc.)
  customLib = attrs // modules // options // {
    inherit mkFlake;
    # Preserve namespaced access with 'my' prefix to avoid conflicts
    my = {
      inherit attrs modules options;
    };
  };
in
  # Merge nixpkgs lib with our custom functions
  # Our flat functions (mapModules, mkOpt, etc.) are added at top level
  # Namespaced functions available via lib.my.modules, lib.my.options, etc.
  lib // customLib
