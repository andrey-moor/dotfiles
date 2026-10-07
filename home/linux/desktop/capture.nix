# home/linux/desktop/capture.nix -- screenshots, colour picker, screen recording
#
# grim + slurp select, satty annotates and copies, hyprpicker picks a colour,
# wf-recorder records with CPU encoding because vmwgfx has no video encoder.
{ pkgs, ... }:
let
  tool =
    name: text:
    pkgs.writeShellApplication {
      inherit name text;
      runtimeInputs = with pkgs; [
        grim
        slurp
        satty
        wl-clipboard
        wf-recorder
        libnotify
        coreutils
        procps
      ];
    };
in
{
  programs.satty = {
    enable = true;
    settings.general = {
      fullscreen = true;
      early-exit = true;
      copy-command = "wl-copy";
      save-after-copy = true;
      output-filename = "~/Pictures/Screenshots/%Y-%m-%d_%H-%M-%S.png";
    };
  };

  home.packages = [
    pkgs.hyprpicker
    # notify-send is already a runtime input of the tools below. Installing it
    # puts the command on the shell PATH too.
    pkgs.libnotify
    (tool "desktop-capture-region" (builtins.readFile ./scripts/capture-region.sh))
    (tool "desktop-capture-screen" "grim - | satty --filename -")
    (tool "desktop-capture-record" ''
      if pkill -INT -x wf-recorder; then
        notify-send "Recording saved" "$HOME/Videos"
        exit 0
      fi
      mkdir -p ~/Videos
      region="$(slurp)" || exit 0
      notify-send "Recording" "Alt+Print stops it"
      exec wf-recorder -g "$region" -f ~/Videos/"$(date +%Y-%m-%d_%H-%M-%S)".mp4
    '')
  ];

  xdg.userDirs = {
    enable = true;
    createDirectories = true;
  };

  # satty writes output-filename with a plain write and never creates the
  # parent, and Screenshots is not an XDG user directory.
  home.file."Pictures/Screenshots/.keep".text = "";
}
