# Rocinante -- x86_64 Linux workstation (Omarchy, standalone home-manager)

{ lib, ... }:

with lib;
{
  system = "x86_64-linux";
  username = "andreym";
  homeDirectory = "/home/andreym";

  config = { config, pkgs, inputs, ... }: {
    # Home-manager state version
    home.stateVersion = "24.05";
    home.enableNixpkgsReleaseCheck = false;  # Using pkgs.main for some packages

    # nixGL for GPU acceleration with Nix apps on non-NixOS
    targets.genericLinux.nixGL = {
      packages = inputs.nixgl.packages;
      defaultWrapper = "mesa";  # AMD GPU
    };

    # Additional packages
    home.packages = [
      (pkgs.azure-cli.withExtensions [
        pkgs.azure-cli-extensions.bastion
        pkgs.azure-cli-extensions.ssh
      ])
      pkgs.dnsutils
      pkgs.tailscale
      (config.lib.nixGL.wrap pkgs.mesa-demos)  # provides glxinfo, glxgears, etc.
    ];

    # Enable modules
    modules = {
      dotfilesDir = "${config.home.homeDirectory}/dotfiles";

      profiles.user = "andreym";

      shell = {
        default = "nushell";
        nushell.enable = true;
        git.enable = true;
        ssh.enable = true;
        direnv.enable = true;
        atuin.enable = true;
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
        vscode.enable = true;
        jj.enable = true;
        go.enable = true;
        rust.enable = true;
        kubernetes.enable = true;
        claude.enable = true;
        python.enable = true;
        bazel.enable = true;
        terraform.enable = true;
      };

      linux = {
        edge.enable = true;
        firefox.enable = true;
        lan-mouse.enable = true;
        intune.enable = true;
        intune.debug = true;  # Enable verbose logging for debugging
        wayvnc = {
          enable = true;
          password = "rocinante";
        };
      };
    };
  };
}
