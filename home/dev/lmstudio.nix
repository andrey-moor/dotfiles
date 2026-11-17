# home/dev/lmstudio.nix -- LM Studio: desktop app for running local LLMs

{
  pkgs,
  ...
}:

{
  home.packages = [
    pkgs.main.lmstudio
  ];
}
