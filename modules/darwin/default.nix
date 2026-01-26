# modules/darwin/default.nix -- Darwin (macOS) base configuration
#
# Note: This module is only loaded on Darwin via the module system.
# No need for mkIf guards.

{ lib, config, pkgs, inputs, ... }:

with lib;
{
  config = {
    # Note: Nix configuration is handled by Determinate Nix
    # Set nix.enable = false in host config when using Determinate Nix
    # To add extra caches, use /etc/nix/nix.custom.conf

    # Note: nixpkgs.config.allowUnfree is set in mkFlake.nix mkPkgs

    # Home-manager: back up existing files instead of failing
    home-manager.backupFileExtension = "backup";

    # Darwin state version (6 is required for nix-darwin 25.05+)
    system.stateVersion = 6;

    # Primary user for homebrew and other user-specific options
    system.primaryUser = config.user.name;

    # Shells
    programs.zsh.enable = true;
    environment.shells = [ pkgs.nushell ];
    environment.systemPackages = [ pkgs.nushell ];

    # XDG base directories (set at launchd level so nushell finds its config)
    # Note: launchd doesn't expand $HOME, so we use the explicit path
    launchd.user.envVariables.XDG_CONFIG_HOME = "/Users/${config.user.name}/.config";

    # User account configuration
    users.users.${config.user.name} = {
      name = config.user.name;
      home = "/Users/${config.user.name}";
      shell = pkgs.nushell;
    };

    # macOS system preferences
    system.defaults = {
      # Dock settings
      dock = {
        show-recents = false;
        mru-spaces = false;
      };

      # Finder settings
      finder = {
        AppleShowAllExtensions = true;
        FXEnableExtensionChangeWarning = false;
        QuitMenuItem = true;
        ShowPathbar = true;
        ShowStatusBar = true;
      };

      # Global settings
      NSGlobalDomain = {
        AppleShowAllExtensions = true;
        InitialKeyRepeat = 15;
        KeyRepeat = 2;
        NSAutomaticCapitalizationEnabled = false;
        NSAutomaticSpellingCorrectionEnabled = false;
      };

      # Trackpad
      trackpad = {
        Clicking = true;
        TrackpadRightClick = true;
      };
    };

    # Security settings (Touch ID for sudo)
    security.pam.services.sudo_local.touchIdAuth = true;
  };
}
