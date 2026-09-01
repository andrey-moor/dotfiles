# home/dev/ollama.nix -- Ollama local LLM runner

{
  lib,
  config,
  pkgs,
  ...
}:

with lib;
{
  config = {
    home.packages = [
      pkgs.ollama
    ];
  };
}
