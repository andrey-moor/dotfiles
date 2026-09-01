# home/shell/openvpn.nix -- OpenVPN client

{
  lib,
  pkgs,
  ...
}:

with lib;
{
  config = {
    home.packages = with pkgs; [
      openvpn
    ];
  };
}
