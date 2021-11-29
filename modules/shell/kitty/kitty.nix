{ config, options, pkgs, lib, ... }:

with lib;
with lib.my;
let cfg = config.modules.shell.kitty;
    # configDir = config.dotfiles.configDir;
    configDir = "${config.dotfiles.modulesDir}/shell/kitty/config";
in {
  options.modules.shell.kitty = with types; {
    enable = mkBoolOpt false;
  };

  config = mkIf cfg.enable {

    home-manager.users.${config.user.name}.programs.kitty = {
      enable = true;
      extraConfig = builtins.readFile "${configDir}/kitty.conf";
      # extraConfig = "$XDG_CONFIG_HOME/kitty/kitty.conf";
    };

    # home.configFile = {
    #  # Write it recursively so other modules can write files to it
    #   "kitty" = { source = configDir; recursive = true; };
    # };
  };
}
