# Rocinante -- Linux workstation (standalone home-manager)

{ lib, ... }:

with lib;
{
  system = "aarch64-linux";
  username = "andreym";
  homeDirectory = "/home/andreym";

  config = { config, pkgs, ... }: {
    # Home-manager state version
    home.stateVersion = "24.05";
    home.enableNixpkgsReleaseCheck = false;  # Using pkgs.main for some packages

    # Enable modules
    modules = {
      dotfilesDir = "/home/andreym/dotfiles";

      profiles.user = "andreym";

      shell = {
        default = "nushell";
        nushell.enable = true;
        git.enable = true;
        ssh.enable = true;
        direnv.enable = true;
        starship.enable = true;
        tmux.enable = true;
        bat.enable = true;
        lazygit.enable = true;
        ghostty.enable = true;
        gpg.enable = true;
        chezmoi.enable = true;
        openvpn.enable = true;
      };

      dev = {
        nix.enable = true;
        neovim.enable = true;
        jj.enable = true;
        go.enable = true;
        rust.enable = true;
        kubernetes.enable = true;
        claude.enable = true;
      };

      linux = {
        intune.enable = true;
        intune.debug = true;  # Enable verbose logging for debugging
        edge.enable = true;
      };
    };
  };
}
