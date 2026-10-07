# home/linux/desktop.nix -- the desktop roles, one module each (spec section 3.1)
{
  imports = [
    # Every role below reads modules.desktop.theme.data.
    ./theme.nix
    ./desktop/bar.nix
    ./desktop/notifications.nix
    ./desktop/launcher.nix
    ./desktop/lock.nix
    ./desktop/idle.nix
    ./desktop/polkit.nix
    ./desktop/wallpaper.nix
    ./desktop/capture.nix
    ./desktop/clipboard.nix
    ./desktop/osd.nix
    ./desktop/apps.nix
    ./desktop/webapps.nix
    ./desktop/look.nix
  ];
}
