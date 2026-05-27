# modules/home/dev/copilot.nix -- GitHub Copilot CLI (terminal coding agent)
#
# Bleeding-edge via scarisey/copilot-cli-flake (auto-bumped weekly) with an
# inline overrideAttrs that forces the latest upstream when scarisey hasn't
# caught up yet. Mirrors the claude-code-nix pattern.
#
# To bump the pinned-ahead version:
#   nix-prefetch-url --type sha256 \
#     https://registry.npmjs.org/@github/copilot/-/copilot-<NEW>.tgz
#   ...then update both `version` and `hash` below.

{ lib, config, pkgs, inputs, ... }:

with lib;
let
  cfg = config.modules.dev.copilot;
  pinnedAhead = "1.0.54";
  pinnedAheadHash = "1indbw8cl0p9h99xmn080wzf170cc7vbbi7h7jcxjnd9yq4nshjs";
  base = inputs.copilot-cli-flake.packages.${pkgs.system}.default;
  copilot =
    if base.version == pinnedAhead then base
    else base.overrideAttrs (_old: {
      version = pinnedAhead;
      src = pkgs.fetchurl {
        url = "https://registry.npmjs.org/@github/copilot/-/copilot-${pinnedAhead}.tgz";
        sha256 = pinnedAheadHash;
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
