# modules/home/profiles/andreym.nix -- User-specific configuration for andreym

{ lib, config, pkgs, ... }:

with lib;
{
  config = mkIf (config.modules.profiles.user == "andreym") {
    # User-specific packages (Linux only - macOS uses Homebrew for GUI apps)
    home.packages = with pkgs; optionals pkgs.stdenv.isLinux [
      ghostty  # Preferred terminal (on macOS, managed via Homebrew cask)
    ];

    # Git configuration for this user
    modules.shell.git = {
      userName = "Andrey Moor";
      userEmail = "m@andreym.com";
      signingKey = "2370425883C97521";  # GPG signing subkey (on Yubikey)
    };

    # Jujutsu VCS (inherits from git config or override here)
    # modules.dev.jj is already configured with same defaults
  };
}
