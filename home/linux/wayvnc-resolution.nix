# home/linux/wayvnc-resolution.nix -- resolution scripts for rocinante's VNC
#
# cycle-resolution and set-resolution switch the monitor between its native
# mode and a remote-friendly one. They call `hyprctl keyword monitor`, which
# only a legacy hyprlang config accepts. Rocinante's Omarchy Hyprland has one,
# while stargazer's Lua config rejects it (see modules/nixos/vm-guest.nix).

{
  lib,
  config,
  pkgs,
  ...
}:

with lib;
let
  cfg = config.modules.linux.wayvnc;

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
in
{
  # The scripts read the monitor name from the wayvnc module.
  imports = [ ./wayvnc.nix ];

  options.modules.linux.wayvnc = {
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
  };

  config = mkIf pkgs.stdenv.hostPlatform.isLinux {
    home.packages = [
      cycleResolution
      setResolution
    ];
  };
}
