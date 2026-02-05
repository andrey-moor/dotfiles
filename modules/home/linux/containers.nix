# modules/home/linux/containers.nix -- Container services via systemd user units
#
# Provides a declarative way to run containers as systemd user services on Linux.
# Similar to NixOS's virtualisation.oci-containers but for home-manager.
# Uses podman (rootless) as the container runtime.

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.linux.containers;

  # Generate systemd service for a container
  mkContainerService = name: container: let
    runArgs = [ "${pkgs.podman}/bin/podman" "run" "--rm" "--name" name "--replace" ]
      ++ optional container.pull "--pull=always"
      ++ concatMap (p: [ "-p" p ]) container.ports
      ++ concatMap (v: [ "-v" v ]) container.volumes
      ++ optionals (container.network != null) (concatMap (n: [ "--network" n ]) (toList container.network))
      ++ concatLists (mapAttrsToList (k: v: [ "-e" "${k}=${v}" ]) container.environment)
      ++ concatLists (mapAttrsToList (k: v: [ "-l" "${k}=${v}" ]) container.labels)
      ++ optional (container.user != null) "--user=${container.user}"
      ++ optional (container.workdir != null) "--workdir=${container.workdir}"
      ++ optional (container.hostname != null) "--hostname=${container.hostname}"
      ++ optional container.privileged "--privileged"
      ++ container.extraArgs
      ++ [ container.image ]
      ++ container.cmd;
  in {
    Unit = {
      Description = "Container ${name}";
      After = [ "network.target" ];
    };
    Service = {
      Type = "simple";
      ExecStartPre = "-${pkgs.podman}/bin/podman stop ${name}";
      ExecStart = concatStringsSep " " runArgs;
      ExecStop = "${pkgs.podman}/bin/podman stop ${name}";
      Restart = "on-failure";
      RestartSec = "10s";
    };
    Install = {
      WantedBy = [ "default.target" ];
    };
  };

  containerOpts = { name, ... }: {
    options = {
      image = mkOption {
        type = types.str;
        description = "Container image to run";
        example = "redis:7-alpine";
      };

      cmd = mkOption {
        type = types.listOf types.str;
        default = [];
        description = "Command and arguments to pass to the container";
        example = [ "--appendonly" "yes" ];
      };

      ports = mkOption {
        type = types.listOf types.str;
        default = [];
        description = "Port mappings (host:container)";
        example = [ "6379:6379" "8080:80" ];
      };

      volumes = mkOption {
        type = types.listOf types.str;
        default = [];
        description = "Volume mounts (host:container or named volumes)";
        example = [ "/data/redis:/data" "myvolume:/var/lib/data" ];
      };

      environment = mkOption {
        type = types.attrsOf types.str;
        default = {};
        description = "Environment variables";
        example = { POSTGRES_PASSWORD = "secret"; };
      };

      labels = mkOption {
        type = types.attrsOf types.str;
        default = {};
        description = "Container labels";
        example = { "com.example.description" = "My service"; };
      };

      network = mkOption {
        type = types.nullOr (types.either types.str (types.listOf types.str));
        default = null;
        description = "Container network(s) to connect to";
        example = "my-network";
      };

      user = mkOption {
        type = types.nullOr types.str;
        default = null;
        description = "User to run as (uid:gid)";
        example = "1000:1000";
      };

      workdir = mkOption {
        type = types.nullOr types.str;
        default = null;
        description = "Working directory inside the container";
      };

      hostname = mkOption {
        type = types.nullOr types.str;
        default = null;
        description = "Container hostname";
      };

      privileged = mkOption {
        type = types.bool;
        default = false;
        description = "Run container in privileged mode";
      };

      autoStart = mkOption {
        type = types.bool;
        default = true;
        description = "Start container automatically on login";
      };

      pull = mkOption {
        type = types.bool;
        default = false;
        description = "Always pull image before starting";
      };

      extraArgs = mkOption {
        type = types.listOf types.str;
        default = [];
        description = "Extra arguments to pass to container run";
        example = [ "--cap-add=SYS_PTRACE" "--memory=512m" ];
      };
    };
  };

in {
  options.modules.linux.containers = {
    enable = mkEnableOption "Container services via podman";

    containers = mkOption {
      type = types.attrsOf (types.submodule containerOpts);
      default = {};
      description = "Container service definitions";
      example = literalExpression ''
        {
          redis = {
            image = "redis:7-alpine";
            ports = [ "6379:6379" ];
          };
        }
      '';
    };
  };

  config = mkIf cfg.enable (mkMerge [
    # Install podman
    {
      home.packages = [ pkgs.podman ];
    }

    # Create systemd user services for each container
    (mkIf (cfg.containers != {}) {
      systemd.user.services = mapAttrs' (name: container:
        nameValuePair "container-${name}" (mkContainerService name container)
      ) (filterAttrs (n: c: c.autoStart) cfg.containers);
    })
  ]);
}
