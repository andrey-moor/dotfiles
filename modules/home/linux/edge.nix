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

  # Override Edge version when upstream removes the nixpkgs-pinned deb
  edgePackage = pkgs.microsoft-edge.overrideAttrs (old: rec {
    version = "145.0.3800.70";
    src = builtins.fetchurl {
      url = "https://packages.microsoft.com/repos/edge/pool/main/m/microsoft-edge-stable/microsoft-edge-stable_${version}-1_amd64.deb";
      sha256 = "sha256-gUyh9AD1ntnZb2iLRwKLxy0PxY0Dist73oT9AC2pFQI=";
    };
  });
in {
  options.modules.linux.edge = {
    enable = mkEnableOption "Microsoft Edge browser (x86_64)";
  };

  config = mkIf (cfg.enable && pkgs.stdenv.isLinux) {
    home.packages = [
      edgePackage
    ];
  };
}
