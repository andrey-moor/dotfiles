# modules/darwin/default.nix -- Darwin (macOS) base configuration
#
# Imported by hosts/behemoth. The single macOS user is named once, as
# `system.primaryUser`. Every other darwin module reads it from there.

{ config, pkgs, ... }:

let
  user = config.system.primaryUser;
  inherit (config.users.users.${user}) home;
in
{
  config = {
    # Note: Nix configuration is handled by Determinate Nix
    # Set determinateNix.enable = true in host config. Its module turns
    # nix-darwin's own Nix management off and owns /etc/nix/nix.custom.conf
    # To add extra caches, use determinateNix.customSettings.substituters

    # Note: nixpkgs.config.allowUnfree is set in flake.nix mkPkgs

    # Home-manager: back up existing files instead of failing
    home-manager.backupFileExtension = "backup";

    # Darwin state version (6 is required for nix-darwin 25.05+)
    system.stateVersion = 6;

    # Primary user for homebrew and other user-specific options
    system.primaryUser = "andreym";

    # Shells
    programs.zsh.enable = true;
    environment.shells = [ pkgs.nushell ];
    environment.systemPackages = [ pkgs.nushell ];

    # XDG base directories (set at launchd level so nushell finds its config)
    # Note: launchd doesn't expand $HOME, so we use the explicit path
    launchd.user.envVariables.XDG_CONFIG_HOME = "${home}/.config";

    # User account configuration. nix-darwin applies `shell` only to users in
    # `knownUsers`, and it needs the uid to recognise the account. 501 is the
    # first account macOS Setup Assistant creates. Without this pair the login
    # shell silently stays zsh on a fresh Mac.
    users.knownUsers = [ user ];
    users.users.${user} = {
      name = user;
      uid = 501;
      home = "/Users/${user}";
      shell = pkgs.nushell;
    };

    # macOS system preferences
    system.defaults = {
      # Dock settings
      dock = {
        show-recents = false;
        mru-spaces = false;
        tilesize = 43;
      };

      # Finder settings
      finder = {
        AppleShowAllExtensions = true;
        FXEnableExtensionChangeWarning = false;
        FXPreferredViewStyle = "Nlsv"; # list view
        QuitMenuItem = true;
        ShowPathbar = true;
        ShowStatusBar = true;
      };

      # Global settings
      NSGlobalDomain = {
        AppleInterfaceStyle = "Dark";
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

    # Security settings (Touch ID for sudo, including inside tmux)
    security.pam.services.sudo_local.touchIdAuth = true;
    security.pam.services.sudo_local.reattach = true;
  };
}
