# home/linux/theme.nix -- home-manager side of the theme
#
# Role modules read modules.desktop.theme.data. catppuccin/nix is not
# enabled: its ports read their palette through import-from-derivation,
# which needs an aarch64-linux build and so breaks evaluation on behemoth
# and in the x86_64 flake check. The palette here is the single source.
{
  lib,
  config,
  pkgs,
  ...
}:

with lib;
let
  cfg = config.modules.desktop.theme;
  theme = import ../../lib/theme.nix { inherit pkgs; };
in
{
  options.modules.desktop.theme = {
    name = mkOption {
      type = types.str;
      default = "catppuccin";
      description = "Theme directory under themes/.";
    };

    cursorSize = mkOption {
      type = types.int;
      default = 24;
      description = "Cursor size in pixels.";
    };

    wallpaperDir = mkOption {
      type = types.nullOr types.path;
      default = null;
      description = "Directory of wallpapers to cycle. Null means the theme's own backgrounds.";
    };

    data = mkOption {
      type = types.attrs;
      readOnly = true;
      default = theme cfg.name;
      description = "The lib/theme.nix result for the chosen name.";
    };
  };

  config = {
    home.pointerCursor = {
      enable = true;
      gtk.enable = true;
      size = cfg.cursorSize;
      package = pkgs.catppuccin-cursors.mochaDark;
      name = "catppuccin-mocha-dark-cursors";
    };
  };
}
