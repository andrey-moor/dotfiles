# home/linux/desktop/lock.nix -- hyprlock, swaylock as the fallback
#
# ext-session-lock: the compositor keeps the screen locked if the locker dies.
# PAM: modules/nixos/himmelblau.nix gives hyprlock and swaylock the Hello PIN
# path and nothing else. The single input field takes the PIN.
{
  config,
  lib,
  pkgs,
  ...
}:
let
  t = config.modules.desktop.theme.data;

  # Palette entries are "#rrggbb". hyprlang parses a colour as an int and
  # accepts only the 0x, rgb() and rgba() forms (src/config.cpp,
  # configStringToInt), so a bare "#" value is a parse error. Same conversion
  # the generated Lua header does in modules/nixos/desktop-hyprland.nix.
  rgb = hex: "rgb(${lib.removePrefix "#" hex})";
in
{
  programs.hyprlock = {
    enable = true;
    settings = {
      general = {
        hide_cursor = true;
        ignore_empty_input = true;
      };
      # Repeatable hyprlang sections are lists in home-manager's schema.
      background = [
        {
          path = "screenshot";
          blur_passes = 2;
          color = rgb t.colors.background;
        }
      ];
      input-field = [
        {
          size = "320, 48";
          outline_thickness = 2;
          rounding = 0;
          outer_color = rgb t.colors.accent;
          inner_color = rgb t.colors.background;
          font_color = rgb t.colors.foreground;
          placeholder_text = "<i>Hello PIN</i>";
          fail_text = "<i>Wrong PIN</i>";
          position = "0, -40";
          halign = "center";
          valign = "center";
        }
      ];
      label = [
        {
          text = "$TIME";
          color = rgb t.colors.foreground;
          font_size = 48;
          font_family = "JetBrainsMono Nerd Font";
          position = "0, 120";
          halign = "center";
          valign = "center";
        }
      ];
    };
  };

  home.packages = [ pkgs.swaylock ];
}
