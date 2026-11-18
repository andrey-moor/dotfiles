# home/linux/edge.nix -- Microsoft Edge Browser (x86_64)
#
# Installs Microsoft Edge browser natively on x86_64-linux.
#
# For YubiKey certificate auth in Edge, run: intune-nss-setup

{
  lib,
  pkgs,
  ...
}:

with lib;
{
  config = mkIf pkgs.stdenv.hostPlatform.isLinux {
    home.packages = [
      pkgs.microsoft-edge
    ];
  };
}
