# modules/home/linux/wayvnc.nix -- WayVNC server for Wayland remote access
#
# Provides VNC server for wlroots-based compositors (Hyprland).
# Uses password auth for macOS Screen Sharing compatibility.
# Includes resolution cycle script to find best remote resolution.

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.linux.wayvnc;

  # Wrap wayvnc with nixGL for GPU support on non-NixOS systems
  # config.lib.nixGL.wrap is a no-op when nixGL isn't configured
  wayvncPkg = if cfg.gpu
    then config.lib.nixGL.wrap pkgs.wayvnc
    else pkgs.wayvnc;

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

in {
  options.modules.linux.wayvnc = {
    enable = mkEnableOption "WayVNC server for Wayland remote access";

    password = mkOption {
      type = types.str;
      description = "VNC password for authentication";
      example = "secret";
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
      description = "Enable GPU features (H.264 hardware encoding)";
    };

    maxFps = mkOption {
      type = types.int;
      default = 120;
      description = "Max frame rate (120 recommended to avoid bottleneck for 60fps)";
    };
  };

  config = mkIf (cfg.enable && pkgs.stdenv.isLinux) {
    home.packages = [
      wayvncPkg
      cycleResolution
      setResolution
    ];

    xdg.configFile."wayvnc/config".text = ''
      address=${cfg.address}
      port=${toString cfg.port}
      enable_auth=true
      username=${config.home.username}
      password=${cfg.password}
      rsa_private_key_file=${config.xdg.configHome}/wayvnc/rsa_key.pem
      relax_encryption=true
    '';

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
        After = [ "graphical-session.target" ];
        PartOf = [ "graphical-session.target" ];
      };
      Service = {
        ExecStart = "${wayvncPkg}/bin/wayvnc"
          + optionalString cfg.gpu " --gpu"
          + " --max-fps=${toString cfg.maxFps}";
        Restart = "on-failure";
        RestartSec = 5;
      };
      Install.WantedBy = [ "graphical-session.target" ];
    };
  };
}
