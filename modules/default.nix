# modules/default.nix -- System-level module loader
#
# This module is imported at the system level (Darwin or NixOS).
# Home-manager modules are loaded separately via home-manager integration.
#
# Darwin modules guard their config with mkIf pkgs.stdenv.isDarwin.

{ lib, config, options, pkgs, inputs, ... }:

{
  # Import darwin modules:
  # - ./darwin itself (default.nix) provides base Darwin config
  # - mapModulesRec' finds child modules (homebrew.nix, etc.)
  imports = [ ./darwin ] ++ lib.mapModulesRec' ./darwin import;

  options = with lib.types; {
    # User configuration - simplified for cross-platform use
    user = {
      name = lib.mkOpt str "andreym";
    };
  };
}
