# home/linux/desktop/webapps.nix -- web apps as desktop entries (spec section 6)
#
# chromium is installed for `--app=` only. The list starts empty and grows when
# the owner misses one. `--class` lets window rules target the app.
{ pkgs, lib, ... }:
let
  # The attribute key is the class: it is already a bare identifier, while the
  # display name may carry spaces. The URL is quoted so that spaces and shell
  # metacharacters survive. A literal `%` in a URL must be written `%%`, which
  # is the desktop file escape.
  mkWebApp =
    key:
    {
      name,
      url,
      icon,
    }:
    {
      inherit name icon;
      exec = "${pkgs.chromium}/bin/chromium --app=\"${url}\" --class=${key}";
      terminal = false;
      type = "Application";
      categories = [ "Network" ];
      settings.StartupWMClass = key;
    };

  webApps = { };
in
{
  home.packages = [ pkgs.chromium ];
  xdg.desktopEntries = lib.mapAttrs mkWebApp webApps;
}
