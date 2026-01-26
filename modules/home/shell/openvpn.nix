# modules/home/shell/openvpn.nix -- OpenVPN client

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.shell.openvpn;
in {
  options.modules.shell.openvpn = {
    enable = mkEnableOption "OpenVPN client";
  };

  config = mkIf cfg.enable {
    home.packages = with pkgs; [
      openvpn
    ];
  };
}
