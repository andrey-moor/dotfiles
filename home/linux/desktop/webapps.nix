# home/linux/desktop/webapps.nix -- web apps as desktop entries (spec section 6)
#
# chromium is installed for `--app=` only. The list starts empty and grows when
# the owner misses one. `--class` lets window rules target the app.
{ pkgs, lib, ... }:
let
  mkWebApp =
    {
      name,
      url,
      icon,
    }:
    {
      inherit name icon;
      exec = "${pkgs.chromium}/bin/chromium --app=${url} --class=${name}";
      terminal = false;
      type = "Application";
      categories = [ "Network" ];
    };

  webApps = { };
in
{
  home.packages = [ pkgs.chromium ];
  xdg.desktopEntries = lib.mapAttrs (_: mkWebApp) webApps;
}
