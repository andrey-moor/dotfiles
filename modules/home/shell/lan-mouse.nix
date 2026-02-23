# modules/home/shell/lan-mouse.nix -- LAN Mouse for keyboard/mouse sharing
#
# Shares keyboard and mouse between machines over the network.
# Generates ~/.config/lan-mouse/config.toml declaratively.
# Fingerprints are exchanged on first connect via the GUI prompt.

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.shell.lan-mouse;
  tomlFormat = pkgs.formats.toml { };

  lanMousePkg = if (cfg.gpu && pkgs.stdenv.isLinux)
    then config.lib.nixGL.wrap pkgs.lan-mouse
    else pkgs.lan-mouse;

  # Build the config.toml attrset
  configToml = {
    port = cfg.port;
    release_bind = cfg.releaseBind;
  } // optionalAttrs (cfg.authorizedFingerprints != [ ]) {
    authorized_fingerprints = cfg.authorizedFingerprints;
  } // optionalAttrs (cfg.clients != [ ]) {
    clients = map (c: {
      hostname = c.hostname;
      ips = c.ips;
      position = c.position;
    } // optionalAttrs (c.port != null) {
      port = c.port;
    } // optionalAttrs c.activateOnStartup {
      activate_on_startup = true;
    }) cfg.clients;
  };

in {
  options.modules.shell.lan-mouse = {
    enable = mkEnableOption "LAN Mouse for keyboard/mouse sharing";

    port = mkOption {
      type = types.port;
      default = 4242;
      description = "Port for LAN Mouse communication";
    };

    gpu = mkOption {
      type = types.bool;
      default = true;
      description = "Wrap GTK frontend with nixGL for GPU support (Linux only)";
    };

    releaseBind = mkOption {
      type = types.listOf types.str;
      default = [ "KeyLeftCtrl" "KeyLeftShift" "KeyF" ];
      description = "Key combination to release mouse capture";
    };

    authorizedFingerprints = mkOption {
      type = types.listOf types.str;
      default = [ ];
      description = "Pre-authorized client fingerprints (optional, usually exchanged via GUI)";
    };

    clients = mkOption {
      default = [ ];
      description = "Client machines to connect to";
      type = types.listOf (types.submodule {
        options = {
          position = mkOption {
            type = types.enum [ "left" "right" "top" "bottom" ];
            description = "Position of this client relative to the current machine";
          };
          hostname = mkOption {
            type = types.str;
            description = "Hostname of the client machine";
          };
          ips = mkOption {
            type = types.listOf types.str;
            description = "IP addresses of the client machine";
          };
          port = mkOption {
            type = types.nullOr types.port;
            default = null;
            description = "Override port for this client (defaults to global port)";
          };
          activateOnStartup = mkOption {
            type = types.bool;
            default = false;
            description = "Automatically activate this client on startup";
          };
        };
      });
    };
  };

  config = mkIf cfg.enable {
    home.packages = [ lanMousePkg ];

    # Generate config.toml
    xdg.configFile."lan-mouse/config.toml".source =
      tomlFormat.generate "lan-mouse-config.toml" configToml;

    # Systemd user service (Linux only)
    systemd.user.services.lan-mouse = mkIf pkgs.stdenv.isLinux {
      Unit = {
        Description = "LAN Mouse - keyboard/mouse sharing";
        After = [ "graphical-session.target" ];
        PartOf = [ "graphical-session.target" ];
      };
      Service = {
        ExecStart = "${pkgs.lan-mouse}/bin/lan-mouse --daemon --port ${toString cfg.port}";
        Restart = "on-failure";
        RestartSec = 5;
      };
      Install.WantedBy = [ "graphical-session.target" ];
    };
  };
}
