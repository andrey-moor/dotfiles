# modules/home/dev/codex.nix -- OpenAI Codex CLI

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.codex;
in {
  options.modules.dev.codex = {
    enable = mkEnableOption "OpenAI Codex CLI";
  };

  config = mkIf cfg.enable {
    home.packages = [
      pkgs.codex
    ];
  };
}
