# modules/nixos/desktop-theme.nix -- the host picks a theme by name
#
# The name travels to every home-manager user as modules.desktop.theme.name,
# so the compositor (rendered by desktop-hyprland.nix) and the user's role
# modules read one palette. lib/theme.nix does the lookup.
#
# desktop-hyprland.nix imports this module, and it is also where the default
# cursor size comes from: the compositor owns the monitor line, so it is the
# only place that knows the scale.
{
  lib,
  config,
  ...
}:

with lib;
let
  cfg = config.modules.nixos.desktop.theme;
in
{
  options.modules.nixos.desktop.theme = {
    name = mkOption {
      type = types.str;
      default = "catppuccin";
      description = "Directory name under themes/. Switching is this one word and a rebuild.";
    };

    cursorSize = mkOption {
      type = types.int;
      default = 24;
      description = "Cursor size in pixels. desktop-hyprland.nix raises the default to 32 at scale 2.";
    };
  };

  config = {
    # sharedModules sets this for every home-manager user on the host, so each
    # one must import home/linux/theme.nix, which declares the option. Only
    # andreym exists here, so that costs nothing.
    home-manager.sharedModules = [
      { modules.desktop.theme = { inherit (cfg) name cursorSize; }; }
    ];
  };
}
