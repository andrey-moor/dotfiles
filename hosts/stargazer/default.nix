# Stargazer -- Linux workstation (standalone home-manager)
# Parallels VM on Apple Silicon with LUKS encryption

{ lib, ... }:

with lib;
{
  system = "aarch64-linux";
  username = "andreym";
  homeDirectory = "/home/andreym";

  config = { config, pkgs, inputs, ... }: {
    # Home-manager state version
    home.stateVersion = "24.05";
    home.enableNixpkgsReleaseCheck = false;  # Using pkgs.main for some packages

    # nixGL for GPU acceleration with Nix apps on non-NixOS
    # Required for ghostty and other OpenGL apps to work with virtio_gpu
    targets.genericLinux.nixGL = {
      packages = inputs.nixgl.packages;
      defaultWrapper = "mesa";  # virtio_gpu in Parallels
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
        bazel.enable = true;
        python.enable = true;
        terraform.enable = true;
      };

      linux = {
        intune.enable = true;
        intune.debug = true;  # Enable verbose logging for debugging
        edge-rosetta.enable = true;
        firefox.enable = true;
        wayvnc.enable = true;
        wayvnc.password = "stargazer";
        wayvnc.monitor = "Virtual-1";
        wayvnc.gpu = false;
        wayvnc.renderCursor = true;

        containers = {
          enable = true;
          containers.litellm = {
            image = "ghcr.io/berriai/litellm:main-latest";
            ports = [ "4000:4000" ];
            pull = true;
            volumes = [
              "${config.modules.dotfilesDir}/config/litellm/config.yaml:/app/config.yaml:ro"
              "${config.home.homeDirectory}/.local/share/litellm:/root/.config/litellm"  # Persist auth tokens
            ];
            cmd = [ "--config" "/app/config.yaml" "--num_workers" "4" ];
          };
        };
      };
    };
  };
}
