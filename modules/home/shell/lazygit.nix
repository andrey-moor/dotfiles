# modules/home/shell/lazygit.nix -- Lazygit TUI configuration

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.shell.lazygit;
in {
  options.modules.shell.lazygit = {
    enable = mkEnableOption "Lazygit terminal UI for git";
  };

  config = mkIf cfg.enable {
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
