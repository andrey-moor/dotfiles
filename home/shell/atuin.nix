{
  lib,
  config,
  pkgs,
  ...
}:

with lib;
{
  config = {
    programs.atuin = {
      enable = true;
      enableBashIntegration = true;
      enableZshIntegration = true;
      enableNushellIntegration = false; # config/nushell/config.nu runs `atuin init nu` itself
      daemon.enable = true;
      settings = {
        sync.records = false;
      };
    };
  };
}
