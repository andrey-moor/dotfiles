# modules/nixos/docker.nix -- Docker container runtime
#
# Enables Docker daemon with common settings for development.

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.nixos.docker;
in {
  options.modules.nixos.docker = {
    enable = mkEnableOption "Docker container runtime";

    users = mkOption {
      type = types.listOf types.str;
      default = [];
      description = "Users to add to the docker group";
    };

    storageDriver = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Docker storage driver (e.g., overlay2, btrfs)";
      example = "overlay2";
    };
  };

  config = mkIf cfg.enable {
    virtualisation.docker = {
      enable = true;
      enableOnBoot = true;

      # Storage driver (if specified)
      storageDriver = cfg.storageDriver;

      # Daemon configuration
      daemon.settings = {
        # Enable BuildKit for faster builds
        features.buildkit = true;
        # Log rotation
        log-driver = "json-file";
        log-opts = {
          max-size = "10m";
          max-file = "3";
        };
      };
    };

    # Add users to docker group
    users.groups.docker.members = cfg.users;

    # Docker tools
    environment.systemPackages = with pkgs; [
      docker-compose
    ];
  };
}
