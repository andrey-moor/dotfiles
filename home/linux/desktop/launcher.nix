# home/linux/desktop/launcher.nix -- vicinae, with fuzzel kept as the fallback
#
# vicinae brings clipboard history, emoji and a calculator, so no separate
# clipboard manager is needed unless its history proves insufficient (spec
# section 2). It is Qt6 and the first Qt6 client on vmwgfx behind the DMA-BUF
# patch, so this module is the one to check first when a login shows a blank
# launcher. fuzzel stays installed and unbound as the zero-dependency fallback.
#
# Schema notes, read against vicinae 0.29 src/server/src/config/config.hpp,
# whose structs are serialised in snake_case:
#   - the size lives at font.normal.size, not font.size
#   - theme is a pair of slots, theme.dark.name and theme.light.name
#   - the corner radius is launcher_window.rounding
#   - programs.vicinae.useLayerShell is a no-op from 0.17 on (layer shell is
#     the default and is switched off through launcher_window.layer_shell)
# Theme files are TOML from 0.15 on; the slot keys below are the ones
# extra/theme-template.toml documents.
{ config, pkgs, ... }:
let
  t = config.modules.desktop.theme.data;
in
{
  programs.vicinae = {
    enable = true;
    systemd.enable = true;
    settings = {
      font.normal.size = 11;
      # Both slots name the same theme: the palette already carries its mode,
      # so vicinae's own light/dark guess must not swap it for a built-in.
      theme.dark.name = "dotfiles";
      theme.light.name = "dotfiles";
      launcher_window.rounding = 0;
    };
    themes.dotfiles = {
      meta = {
        version = 1;
        name = "dotfiles";
        description = "Generated from themes/${t.name}.";
        variant = t.mode;
      };
      colors = {
        core = {
          background = t.colors.background;
          foreground = t.colors.foreground;
          secondary_background = t.colors.dark_background;
          border = t.colors.lighter_background;
          accent = t.colors.accent;
        };
        # vicinae wants a purple, which the Omarchy palette does not name.
        accents = {
          blue = t.colors.blue;
          green = t.colors.green;
          magenta = t.colors.magenta;
          orange = t.colors.orange;
          purple = t.colors.bright_magenta;
          red = t.colors.red;
          yellow = t.colors.yellow;
          cyan = t.colors.cyan;
        };
      };
    };
  };

  home.packages = [ pkgs.fuzzel ];
}
