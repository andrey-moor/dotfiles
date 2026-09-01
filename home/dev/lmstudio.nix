# home/dev/lmstudio.nix -- LM Studio: desktop app for running local LLMs

{
  lib,
  pkgs,
  ...
}:

with lib;
{
  config = {
    home.packages = [
      pkgs.main.lmstudio
    ];
  };
}
