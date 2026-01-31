# modules/home/default.nix -- Home-manager base configuration
#
# Note: Child modules (shell/, dev/, profiles/) are loaded by mkFlake.nix
# using mapModulesRec'. We don't import them here to avoid double-loading.

{ lib, config, pkgs, ... }:

with lib;
{
  options.modules = with types; {
    dotfilesDir = mkOption {
      type = str;
      default = "${config.home.homeDirectory}/.dotfiles";
      description = "Path to the dotfiles repository";
    };
  };

  config = {
    # Home-manager state version
    home.stateVersion = mkDefault "24.05";

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
