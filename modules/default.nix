# modules/default.nix -- System-level module loader
#
# This module is imported at the system level (Darwin or NixOS).
# Home-manager modules are loaded separately via home-manager integration.
#
# Darwin modules guard their config with mkIf pkgs.stdenv.isDarwin.

{ lib, config, options, pkgs, inputs, ... }:

let
  # Import our custom lib functions (mapModulesRec' etc.)
  # Note: We can't use specialArgs.lib as nix-darwin's module system shadows it
  attrs = import ../lib/attrs.nix { inherit lib; };
  modules = import ../lib/modules.nix { inherit lib attrs; };
in {
  # Import darwin modules:
  # - ./darwin itself (default.nix) provides base Darwin config
  # - mapModulesRec' finds child modules (homebrew.nix, etc.)
  imports = [ ./darwin ] ++ modules.mapModulesRec' ./darwin import;

  options = with lib.types; {
    # User configuration - simplified for cross-platform use
    user = {
      name = lib.mkOpt str "andreym";
    };

    # System-level dotfiles path (also available in home-manager as modules.dotfilesDir)
    modules.dotfilesDir = lib.mkOption {
      type = str;
      default = "/Users/${config.user.name}/.dotfiles";
      description = "Path to the dotfiles repository";
    };
  };
}
