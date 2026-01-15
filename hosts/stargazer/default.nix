# Stargazer -- OrbStack build VM for monorepo

{ lib, ... }:

with lib;
{
  system = "aarch64-linux";
  username = "andreym";
  homeDirectory = "/home/andreym";

  config = { config, pkgs, ... }: {
    home.stateVersion = "24.05";
    home.enableNixpkgsReleaseCheck = false;

    modules = {
      # OrbStack mounts macOS /Users at same path
      dotfilesDir = "/Users/andreym/Documents/dotfiles";

      profiles.user = "andreym";

      shell = {
        default = "nushell";
        nushell.enable = true;
        git.enable = true;
        ssh.enable = true;
        direnv.enable = true;  # Critical for monorepo .envrc
        starship.enable = true;
        tmux.enable = true;
        bat.enable = true;
        lazygit.enable = true;
        gpg.enable = true;
        chezmoi.enable = true;
      };

      dev = {
        nix.enable = true;
        neovim.enable = true;
        jj.enable = true;
        bazel.enable = true;     # PRIMARY: monorepo build system
        go.enable = true;        # For Go services
        rust.enable = true;      # For consensus/storage services
        terraform.enable = true; # For infra deployments
      };
    };

    # Additional packages for monorepo builds
    home.packages = with pkgs; [
      # Python (Bazel hermetic, but useful for scripts)
      python310
      uv

      # Node.js (Bazel hermetic, but useful for scripts)
      nodejs_20
      nodePackages.pnpm

      # Protocol Buffers
      protobuf

      # Azure authentication
      azure-cli

      # Pre-commit hooks
      pre-commit

      # Build utilities
      gnumake
      cmake
      pkg-config
    ];
  };
}
