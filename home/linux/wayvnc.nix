# home/linux/wayvnc.nix -- WayVNC server for Wayland remote access
#
# Provides VNC server for wlroots-based compositors (Hyprland).
# Uses password auth for macOS Screen Sharing compatibility.
# The resolution scripts live in wayvnc-resolution.nix (rocinante only).

{
  lib,
  config,
  pkgs,
  ...
}:

with lib;
let
  cfg = config.modules.linux.wayvnc;

  # Wrap wayvnc with nixGL for GPU support on non-NixOS systems
  # config.lib.nixGL.wrap is a no-op when nixGL isn't configured
  wayvncPkg = if cfg.gpu then config.lib.nixGL.wrap pkgs.wayvnc else pkgs.wayvnc;

  # Render the wayvnc config at service start so the password never
  # enters the nix store (the config file contains it in plaintext).
  renderConfig = pkgs.writeShellScript "wayvnc-render-config" ''
    set -euo pipefail
    dir="${config.xdg.configHome}/wayvnc"
    mkdir -p "$dir"
    umask 077
    rm -f "$dir/config"
    {
      echo "address=${cfg.address}"
      echo "port=${toString cfg.port}"
      echo "enable_auth=true"
      echo "username=${config.home.username}"
      echo "password=$(cat "${cfg.passwordFile}")"
      echo "rsa_private_key_file=${config.xdg.configHome}/wayvnc/rsa_key.pem"
      echo "relax_encryption=true"
    } > "$dir/config"
  '';

in
{
  options.modules.linux.wayvnc = {
    passwordFile = mkOption {
      type = types.path;
      description = "Path to a file containing the VNC password (e.g. a sops secret). Read at service start; never enters the nix store.";
    };

    port = mkOption {
      type = types.port;
      default = 5900;
      description = "Port to listen on";
    };

    address = mkOption {
      type = types.str;
      description = "Address to bind to";
    };

    monitor = mkOption {
      type = types.str;
      default = "HDMI-A-1";
      description = "Monitor name from hyprctl monitors";
    };

    gpu = mkOption {
      type = types.bool;
      default = true;
      description = "Enable GPU features (H.264 hardware encoding). Disable for VMs without DRM/DMA-BUF support.";
    };

    renderCursor = mkOption {
      type = types.bool;
      default = false;
      description = "Enable overlay cursor rendering";
    };

    maxFps = mkOption {
      type = types.int;
      default = 120;
      description = "Max frame rate (120 recommended to avoid bottleneck for 60fps)";
    };
  };

  config = mkIf pkgs.stdenv.hostPlatform.isLinux {
    home.packages = [
      wayvncPkg
    ];

    # Generate RSA key if missing (traditional format required by wayvnc/nettle)
    home.activation.wayvncKey = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      if [ ! -f "${config.xdg.configHome}/wayvnc/rsa_key.pem" ]; then
        mkdir -p "${config.xdg.configHome}/wayvnc"
        ${pkgs.openssl}/bin/openssl genrsa -traditional -out "${config.xdg.configHome}/wayvnc/rsa_key.pem" 4096
      fi
    '';

    systemd.user.services.wayvnc = {
      Unit = {
        Description = "WayVNC - VNC server for Wayland";
        After = [
          "graphical-session.target"
          "sops-nix.service"
        ];
        Wants = [ "sops-nix.service" ];
        PartOf = [ "graphical-session.target" ];
      };
      Service = {
        ExecStartPre = "${renderConfig}";
        ExecStart =
          "${wayvncPkg}/bin/wayvnc"
          + optionalString cfg.gpu " --gpu"
          + optionalString cfg.renderCursor " --render-cursor"
          + " --max-fps=${toString cfg.maxFps}";
        # wayvnc exits 0 (clean) when its captured output is removed (e.g. monitor
        # powered off), so "on-failure" never restarts it. Use "always" so it
        # self-heals once an output is available again.
        Restart = "always";
        RestartSec = 5;
      };
      Install.WantedBy = [ "graphical-session.target" ];
    };
  };
}
