# home/linux/desktop.nix -- the desktop roles, one module each (spec section 3.1)
{
  imports = [
    ./desktop/bar.nix
    ./desktop/notifications.nix
    ./desktop/launcher.nix
  ];
}
