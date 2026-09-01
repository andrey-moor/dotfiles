# home/shell/openvpn.nix -- OpenVPN client

{ lib, config, pkgs, ... }:

with lib;
{
  config = {
    home.packages = with pkgs; [
      openvpn
    ];
  };
}
