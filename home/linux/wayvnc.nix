# home/linux/wayvnc.nix -- WayVNC server for Wayland remote access
#
# Provides VNC server for wlroots-based compositors (Hyprland).
# Uses password auth for macOS Screen Sharing compatibility.
# Includes resolution cycle script to find best remote resolution.

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

  # Resolution cycle script - rotates through options
  cycleResolution = pkgs.writeShellScriptBin "cycle-resolution" ''
    MONITOR="${cfg.monitor}"
    STATE_FILE="$HOME/.cache/resolution-index"

    # Resolution options to cycle through
    RESOLUTIONS=(
      "${cfg.nativeResolution}"    # Native 4K
      "${cfg.remoteResolution}"    # Remote-friendly
    )

    # Get current index
    INDEX=0
    if [[ -f "$STATE_FILE" ]]; then
      INDEX=$(cat "$STATE_FILE")
    fi

    # Next index
    NEXT=$(( (INDEX + 1) % ''${#RESOLUTIONS[@]} ))
    echo "$NEXT" > "$STATE_FILE"

    RES="''${RESOLUTIONS[$NEXT]}"
    echo "Switching to: $RES"
    hyprctl keyword monitor "$MONITOR,$RES,0x0,1"
  '';

  # Set specific resolution
  setResolution = pkgs.writeShellScriptBin "set-resolution" ''
    MONITOR="${cfg.monitor}"
    if [[ -z "$1" ]]; then
      echo "Usage: set-resolution <resolution>"
      echo "Examples:"
      echo "  set-resolution 3840x2160@60"
      echo "  set-resolution 1920x1080@60"
      echo "  set-resolution native"
      echo "  set-resolution remote"
      exit 1
    fi

    case "$1" in
      native) RES="${cfg.nativeResolution}" ;;
      remote) RES="${cfg.remoteResolution}" ;;
      *) RES="$1" ;;
    esac

    echo "Setting resolution: $RES"
    hyprctl keyword monitor "$MONITOR,$RES,0x0,1"
  '';

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
      default = "0.0.0.0";
      description = "Address to bind to";
    };

    monitor = mkOption {
      type = types.str;
      default = "HDMI-A-1";
      description = "Monitor name from hyprctl monitors";
    };

    nativeResolution = mkOption {
      type = types.str;
      default = "3840x2160@60";
      description = "Native monitor resolution";
    };

    remoteResolution = mkOption {
      type = types.str;
      default = "1920x1080@60";
      description = "Preferred remote resolution (used by set-resolution remote)";
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

  config = mkIf pkgs.stdenv.isLinux {
    home.packages = [
      wayvncPkg
      cycleResolution
      setResolution
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
