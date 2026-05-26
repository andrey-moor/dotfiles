# modules/home/dev/copilot.nix -- GitHub Copilot CLI (terminal coding agent)

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.copilot;
in {
  options.modules.dev.copilot = {
    enable = mkEnableOption "GitHub Copilot CLI";
  };

  config = mkIf cfg.enable {
    home.packages = [
      pkgs.main.github-copilot-cli
    ];
  };
}
