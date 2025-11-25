# modules/home/default.nix -- Home-manager base configuration
#
# Note: Child modules (shell/, dev/, profiles/) are loaded by mkFlake.nix
# using mapModulesRec'. We don't import them here to avoid double-loading.

{ lib, config, pkgs, ... }:

with lib;
{
  options = with types; {
    modules = {};
  };

  config = {
    # Home-manager state version
    home.stateVersion = mkDefault "24.05";

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

      # Dotfile management
      chezmoi

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
