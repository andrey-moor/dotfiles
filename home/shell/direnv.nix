# home/shell/direnv.nix -- Direnv configuration (home-manager)

{
  lib,
  ...
}:

with lib;
{
  config = {
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
