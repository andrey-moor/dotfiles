# modules/home/linux/edge.nix -- Microsoft Edge Browser (x86_64)
#
# Installs Microsoft Edge browser natively on x86_64-linux.
# For aarch64/Rosetta (bubblewrap + software rendering), see edge-rosetta.nix.
#
# For YubiKey certificate auth in Edge, run: intune-nss-setup

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.linux.edge;
in {
  options.modules.linux.edge = {
    enable = mkEnableOption "Microsoft Edge browser (x86_64)";
  };

  config = mkIf (cfg.enable && pkgs.stdenv.isLinux) {
    home.packages = [
      pkgs.microsoft-edge
    ];
  };
}
