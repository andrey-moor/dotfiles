# modules/nixos/desktop-theme.nix -- the host picks a theme by name
#
# The name travels to every home-manager user as modules.desktop.theme.name,
# so the compositor (rendered by desktop-hyprland.nix) and the user's role
# modules read one palette. lib/theme.nix does the lookup.
{
  lib,
  config,
  ...
}:

with lib;
let
  cfg = config.modules.nixos.desktop.theme;
  scale = toInt (elemAt (splitString "," config.modules.nixos.desktop.monitor) 3);
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
      default = if scale >= 2 then 32 else 24;
      description = "Cursor size in pixels. Follows the monitor scale because Fusion hands the guest Retina pixels.";
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
