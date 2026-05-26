# modules/home/dev/lmstudio.nix -- LM Studio: desktop app for running local LLMs

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.lmstudio;
in {
  options.modules.dev.lmstudio = {
    enable = mkEnableOption "LM Studio -- desktop app for running local LLMs";
  };

  config = mkIf cfg.enable {
    home.packages = [
      pkgs.main.lmstudio
    ];
  };
}
