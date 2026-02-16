# modules/home/linux/lan-mouse.nix -- LAN Mouse for keyboard/mouse sharing
#
# Shares keyboard and mouse between machines over the network.
# Config requires manual fingerprint exchange -- use the GUI or edit
# ~/.config/lan-mouse/config.toml directly.

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.linux.lan-mouse;

  lanMousePkg = if cfg.gpu
    then config.lib.nixGL.wrap pkgs.lan-mouse
    else pkgs.lan-mouse;

in {
  options.modules.linux.lan-mouse = {
    enable = mkEnableOption "LAN Mouse for keyboard/mouse sharing";

    port = mkOption {
      type = types.port;
      default = 4242;
      description = "Port for LAN Mouse communication";
    };

    gpu = mkOption {
      type = types.bool;
      default = true;
      description = "Wrap GTK frontend with nixGL for GPU support on non-NixOS";
    };
  };

  config = mkIf (cfg.enable && pkgs.stdenv.isLinux) {
    home.packages = [ lanMousePkg ];

    systemd.user.services.lan-mouse = {
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
