{ config, options, pkgs, lib, ... }:

with lib;
with lib.my;
let cfg = config.modules.shell.tmux;
    configDir = "${config.dotfiles.modulesDir}/shell/tmux/config";
in {
  options.modules.shell.tmux = with types; {
    enable = mkBoolOpt false;
  };

  config = mkIf cfg.enable {

    home-manager.users.${config.user.name}.programs.tmux = {
      enable = true;

      shortcut = "l";

      plugins = with pkgs.tmuxPlugins; [
        pain-control
        nord # theme
        {
          plugin = resurrect;
          extraConfig = "set -g @resurrect-strategy-nvim 'session'";
        }
        {
          plugin = continuum;
          extraConfig = ''
            set -g @continuum-restore 'on'
            set -g @continuum-save-interval '60' # minutes
          '';
        }
      ];
      terminal = "screen-256color";
    };
  };
}