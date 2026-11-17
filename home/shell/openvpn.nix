# home/shell/openvpn.nix -- OpenVPN client

{
  pkgs,
  ...
}:

{
  home.packages = with pkgs; [
    openvpn
  ];
}
