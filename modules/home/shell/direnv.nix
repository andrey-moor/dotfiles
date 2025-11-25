# modules/home/shell/direnv.nix -- Direnv configuration (home-manager)

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.shell.direnv;
in {
  options.modules.shell.direnv = {
    enable = mkEnableOption "Direnv";
  };

  config = mkIf cfg.enable {
    programs.direnv = {
      enable = true;
      nix-direnv.enable = true;

      # Silent direnv output
      config = {
        global = {
          hide_env_diff = true;
        };
      };
    };

    home.sessionVariables = {
      DIRENV_LOG_FORMAT = "";
    };
  };
}
