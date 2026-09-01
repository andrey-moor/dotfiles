{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.shell.atuin;
in {
  options.modules.shell.atuin = {
    enable = mkEnableOption "Atuin shell history";
  };

  config = mkIf cfg.enable {
    programs.atuin = {
      enable = true;
      enableBashIntegration = true;
      enableZshIntegration = true;
      enableNushellIntegration = false;  # config/nushell/config.nu runs `atuin init nu` itself
      daemon.enable = true;
      settings = {
        sync.records = false;
      };
    };
  };
}
