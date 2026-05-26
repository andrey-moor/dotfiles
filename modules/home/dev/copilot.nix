# modules/home/dev/copilot.nix -- GitHub Copilot CLI (terminal coding agent)
#
# Bleeding-edge via scarisey/copilot-cli-flake (auto-bumped weekly).
# Mirrors the claude-code-nix pattern -- nixpkgs lags 20+ versions.

{ lib, config, pkgs, inputs, ... }:

with lib;
let cfg = config.modules.dev.copilot;
in {
  options.modules.dev.copilot = {
    enable = mkEnableOption "GitHub Copilot CLI";
  };

  config = mkIf cfg.enable {
    home.packages = [
      inputs.copilot-cli-flake.packages.${pkgs.system}.default
    ];
  };
}
