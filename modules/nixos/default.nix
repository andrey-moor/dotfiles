# modules/nixos/default.nix -- NixOS base configuration
#
# This module provides common NixOS settings shared across all NixOS hosts.
# Host-specific configuration goes in hosts/<hostname>/default.nix.

{ lib, config, pkgs, ... }:

with lib;
let
  # Import our custom lib functions for mkOpt helper
  customLib = import ../../lib/options.nix { inherit lib; };
in {
  # Options shared with Darwin (user configuration)
  options = with types; {
    user = {
      name = customLib.mkOpt str "andreym";
      homeDir = mkOption {
        type = str;
        default = "/home/${config.user.name}";
        description = "User home directory";
      };
      dataDir = mkOption {
        type = str;
        default = "${config.user.homeDir}/.local/share";
        description = "XDG data directory";
      };
    };

    modules.dotfilesDir = mkOption {
      type = str;
      default = "${config.user.homeDir}/.dotfiles";
      description = "Path to the dotfiles repository";
    };
  };

  config = {
    # NixOS state version
    system.stateVersion = "24.05";

    # Nix configuration
    nix.settings = {
      experimental-features = [ "nix-command" "flakes" ];
      trusted-users = [ "root" "@wheel" ];
    };

    # Note: allowUnfree is set in mkPkgs in lib/mkFlake.nix
    # Don't set nixpkgs.config here as we use an external pkgs instance

    # Basic system packages
    environment.systemPackages = with pkgs; [
      vim
      git
      curl
      wget
    ];

    # Enable SSH server (mkDefault allows OrbStack to override)
    services.openssh = {
      enable = mkDefault true;
      settings = {
        PermitRootLogin = mkDefault "no";
        PasswordAuthentication = mkDefault false;
      };
    };

    # Shells
    programs.zsh.enable = true;
    environment.shells = [ pkgs.nushell pkgs.zsh ];

    # Timezone (can be overridden per-host)
    time.timeZone = mkDefault "America/Los_Angeles";

    # Locale
    i18n.defaultLocale = "en_US.UTF-8";

    # Home-manager: back up existing files instead of failing
    home-manager.backupFileExtension = "backup";
  };
}
