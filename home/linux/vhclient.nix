# home/linux/vhclient.nix -- VirtualHere USB client (rocinante)
#
# scripts/yubikey runs it from ~/.nix-profile/bin to borrow the YubiKey
# plugged into behemoth.

{
  pkgs,
  ...
}:

{
  home.packages = [
    (pkgs.callPackage ../../packages/vhclient { })
  ];
}
