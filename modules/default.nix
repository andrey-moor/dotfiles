# modules/default.nix -- System-level module loader (Darwin only)
#
# This module is imported at the system level for Darwin hosts.
# NixOS modules are loaded separately in mkNixosHost.
# Home-manager modules are loaded separately via home-manager integration.
#
# NOTE: This module is only used by Darwin hosts. NixOS hosts load
# modules/nixos directly from mkNixosHost in lib/mkFlake.nix.

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
      homeDir = lib.mkOption {
        type = str;
        default = if pkgs.stdenv.isDarwin
          then "/Users/${config.user.name}"
          else "/home/${config.user.name}";
        description = "User home directory (platform-aware)";
      };
      dataDir = lib.mkOption {
        type = str;
        default = "${config.user.homeDir}/.local/share";
        description = "XDG data directory";
      };
    };

    # System-level dotfiles path (also available in home-manager as modules.dotfilesDir)
    modules.dotfilesDir = lib.mkOption {
      type = str;
      default = "${config.user.homeDir}/.dotfiles";
      description = "Path to the dotfiles repository";
    };
  };
}
