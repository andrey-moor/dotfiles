# home/linux/desktop/wallpaper.nix -- awww (swww's maintained successor)
#
# The wallpaper set is the theme's backgrounds, fetched by hash (lib/theme.nix).
# `desktop-wallpaper-next` cycles through them at runtime over awww's IPC. No
# theme daemon and no writes to ~/.config: the current index lives in
# $XDG_RUNTIME_DIR and resets at login.
{
  config,
  pkgs,
  lib,
  ...
}:
let
  cfg = config.modules.desktop.theme;

  # linkFarm gives the backgrounds stable names in one directory. Its entries
  # are symlinks, which is why the script's find also matches -type l. The name
  # comes from the fetchurl argument, because baseNameOf a store path carries
  # string context and linkFarm rejects that.
  dir =
    if cfg.wallpaperDir != null then
      cfg.wallpaperDir
    else
      pkgs.linkFarm "wallpapers-${cfg.data.name}" (
        map (p: {
          inherit (p) name;
          path = p;
        }) cfg.data.backgrounds
      );

  next = pkgs.writeShellApplication {
    name = "desktop-wallpaper-next";
    runtimeInputs = [
      pkgs.awww
      pkgs.coreutils
      pkgs.findutils
    ];
    text = builtins.replaceStrings [ "@DIR@" ] [ "${dir}" ] (
      builtins.readFile ./scripts/wallpaper-next.sh
    );
  };
in
{
  services.awww.enable = true;

  home.packages = [ next ];

  systemd.user.services.desktop-wallpaper = {
    Unit = {
      Description = "Set the theme's first wallpaper";
      # The daemon unit is named awww by home-manager's services/awww.nix.
      After = [ "awww.service" ];
      PartOf = [ "graphical-session.target" ];
      # Same guard as the daemon: outside a Wayland session there is nothing
      # to set, and the unit would only fail.
      ConditionEnvironment = "WAYLAND_DISPLAY";
    };
    Service = {
      Type = "oneshot";
      ExecStart = "${lib.getExe next} --first";
    };
    Install.WantedBy = [ "graphical-session.target" ];
  };
}
