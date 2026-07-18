# modules/home/dev/copilot.nix -- GitHub Copilot CLI (terminal coding agent)
#
# Bleeding-edge via scarisey/copilot-cli-flake (auto-bumped weekly) with an
# inline overrideAttrs that pins ahead of scarisey when upstream npm is newer.
#
# To bump to the latest npm release:
#   just bump-copilot
#
# That recipe queries the npm registry, prefetches the tarball hash, and
# rewrites copilot-pin.json. When scarisey catches up to >= the pinned
# version, the override silently becomes a no-op (guarded by equality).

{ lib, config, pkgs, inputs, ... }:

with lib;
let
  cfg = config.modules.dev.copilot;
  pin = builtins.fromJSON (builtins.readFile ./copilot-pin.json);
  base = inputs.copilot-cli-flake.packages.${pkgs.system}.default;
  copilot =
    if builtins.compareVersions base.version pin.version >= 0 then base
    else base.overrideAttrs (_old: {
      version = pin.version;
      src = pkgs.fetchurl {
        url = "https://registry.npmjs.org/@github/copilot/-/copilot-${pin.version}.tgz";
        sha256 = pin.hash;
      };
    });
in {
  options.modules.dev.copilot = {
    enable = mkEnableOption "GitHub Copilot CLI";
  };

  config = mkIf cfg.enable {
    home.packages = [ copilot ];
  };
}
