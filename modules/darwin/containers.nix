# modules/darwin/containers.nix -- Container runtime and services via launchd
#
# Provides a declarative way to run containers as launchd services on macOS.
# Similar to NixOS's virtualisation.oci-containers but for Darwin.
# Supports OrbStack (via homebrew) or Podman (via nixpkgs) as the container runtime.

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.darwin.containers;

  # Runtime-specific configuration
  runtimeConfig = {
    orbstack = {
      bin = "/usr/local/bin/docker";  # OrbStack symlinks here
      path = "/usr/local/bin:/usr/bin:/bin";
    };
    podman = {
      bin = "${pkgs.podman}/bin/podman";
      path = "${pkgs.podman}/bin:/usr/local/bin:/usr/bin:/bin";
    };
  };

  runtime = runtimeConfig.${cfg.runtime};

  # Generate launchd service for a container
  mkContainerService = name: container: let
    runArgs = [ runtime.bin "run" "--rm" "--name" name ]
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
    serviceConfig = {
      ProgramArguments = runArgs;
      KeepAlive = container.autoStart;
      RunAtLoad = container.autoStart;
      StandardOutPath = "${cfg.logDir}/container-${name}.log";
      StandardErrorPath = "${cfg.logDir}/container-${name}.err";
      EnvironmentVariables.PATH = runtime.path;
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
        description = "Start container automatically on boot/login";
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
  options.modules.darwin.containers = {
    enable = mkEnableOption "Container runtime and services";

    runtime = mkOption {
      type = types.enum [ "orbstack" "podman" ];
      default = "orbstack";
      description = ''
        Container runtime to use.
        - orbstack: OrbStack (installed via homebrew cask)
        - podman: Podman (installed via nixpkgs)
      '';
    };

    logDir = mkOption {
      type = types.str;
      default = "/tmp";
      description = "Directory for container logs";
    };

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
          postgres = {
            image = "postgres:16";
            ports = [ "5432:5432" ];
            environment = {
              POSTGRES_PASSWORD = "dev";
              POSTGRES_DB = "myapp";
            };
            volumes = [ "pg-data:/var/lib/postgresql/data" ];
          };
        }
      '';
    };
  };

  config = mkIf cfg.enable (mkMerge [
    # OrbStack: install via homebrew cask
    (mkIf (cfg.runtime == "orbstack") {
      homebrew.casks = [ "orbstack" ];
    })

    # Podman: install via nixpkgs
    (mkIf (cfg.runtime == "podman") {
      environment.systemPackages = [ pkgs.podman ];
    })

    # Create launchd agents for each container
    (mkIf (cfg.containers != {}) {
      launchd.user.agents = mapAttrs' (name: container:
        nameValuePair "container-${name}" (mkContainerService name container)
      ) cfg.containers;
    })
  ]);
}
