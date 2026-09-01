# home/shell/lazygit.nix -- Lazygit TUI configuration

{ lib, config, pkgs, ... }:

with lib;
{
  config = {
    programs.lazygit = {
      enable = true;
      settings = {
        gui = {
          theme = {
            lightTheme = false;
          };
        };
      };
    };
  };
}
