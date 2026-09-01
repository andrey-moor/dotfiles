# home/dev/lmstudio.nix -- LM Studio: desktop app for running local LLMs

{ lib, config, pkgs, ... }:

with lib;
{
  config = {
    home.packages = [
      pkgs.main.lmstudio
    ];
  };
}
