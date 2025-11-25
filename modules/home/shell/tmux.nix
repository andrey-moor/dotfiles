# modules/home/shell/tmux.nix -- Tmux terminal multiplexer configuration

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.shell.tmux;
in {
  options.modules.shell.tmux = {
    enable = mkEnableOption "Tmux terminal multiplexer";
  };

  config = mkIf cfg.enable {
    programs.tmux = {
      enable = true;
      mouse = true;
      terminal = "tmux-256color";
      historyLimit = 10000;
      escapeTime = 0;

      plugins = with pkgs.tmuxPlugins; [
        sensible
        catppuccin
        cpu
        battery
      ];

      extraConfig = ''
        # Catppuccin theme configuration
        set -g @catppuccin_flavor "mocha"
        set -g @catppuccin_window_status_style "rounded"

        # Status line configuration
        set -g status-right-length 100
        set -g status-left-length 100
        set -g status-left ""
        set -g status-right "#{E:@catppuccin_status_application}"
        set -agF status-right "#{E:@catppuccin_status_cpu}"
        set -ag status-right "#{E:@catppuccin_status_session}"
        set -ag status-right "#{E:@catppuccin_status_uptime}"
        set -agF status-right "#{E:@catppuccin_status_battery}"
      '';
    };
  };
}
