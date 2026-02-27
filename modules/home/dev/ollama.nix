# modules/home/dev/ollama.nix -- Ollama local LLM runner

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.ollama;
in {
  options.modules.dev.ollama = {
    enable = mkEnableOption "Ollama local LLM runner";
  };

  config = mkIf cfg.enable {
    home.packages = [
      pkgs.ollama
    ];
  };
}
