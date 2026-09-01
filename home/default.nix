# home/default.nix -- Home-manager base, loaded on every host
#
# Feature modules live in home/{shell,dev,linux,profiles}; hosts pull them in
# through the bundles in home/{core,dev,darwin,linux}.nix (see flake.nix).

{
  lib,
  dotfilesDir,
  pkgs,
  ...
}:

with lib;
{
  config = {
    # Home-manager state version
    home.stateVersion = mkDefault "24.05";

    # Export DOTFILES for shell scripts (nushell nix-switch/nix-update,
    # linux/intune.nix) on every host, regardless of enabled modules.
    home.sessionVariables.DOTFILES = dotfilesDir;

    # Enable home-manager CLI (needed for standalone home-manager on Linux)
    programs.home-manager.enable = true;

    # XDG base directories (also sets XDG_CONFIG_HOME, etc.)
    xdg.enable = true;

    # Common packages for all home-manager users
    home.packages = with pkgs; [
      # Core utilities
      coreutils
      findutils
      ripgrep
      fd
      jq
      yq-go
      tree
      htop
      curl
      wget
      unzip

      # Task runner
      just
    ];

    # Session variables
    home.sessionVariables = {
      EDITOR = "nvim";
      VISUAL = "nvim";
    };
  };
}
