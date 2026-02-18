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
      prefix = "C-Space";
      keyMode = "vi";
      baseIndex = 1;
      historyLimit = 50000;
      escapeTime = 0;
      focusEvents = true;
      aggressiveResize = true;

      plugins = with pkgs.tmuxPlugins; [
        sensible
        vim-tmux-navigator
      ];

      extraConfig = ''
        # Default shell
        set -g default-command "${pkgs.nushell}/bin/nu"

        # Secondary prefix (keep C-b as fallback)
        set -g prefix2 C-b
        bind C-Space send-prefix

        # Terminal capabilities
        set -ag terminal-overrides ",*:RGB"

        # Reload config
        bind q source-file ~/.config/tmux/tmux.conf

        # Vi copy mode bindings
        bind -T copy-mode-vi v send -X begin-selection
        bind -T copy-mode-vi y send -X copy-selection-and-cancel

        # Pane controls
        bind h split-window -h -c "#{pane_current_path}"
        bind v split-window -v -c "#{pane_current_path}"
        bind -n C-M-PageUp split-window -h -c "#{pane_current_path}"
        bind -n C-M-PageDown split-window -v -c "#{pane_current_path}"
        bind -n C-M-Home split-window -h -c "#{pane_current_path}"
        bind -n C-M-End kill-pane

        bind -n C-M-Left select-pane -L
        bind -n C-M-Right select-pane -R
        bind -n C-M-Up select-pane -U
        bind -n C-M-Down select-pane -D

        bind -n C-M-S-Left resize-pane -L 5
        bind -n C-M-S-Down resize-pane -D 5
        bind -n C-M-S-Up resize-pane -U 5
        bind -n C-M-S-Right resize-pane -R 5

        # Window navigation
        bind r command-prompt -I "#W" "rename-window -- '%%'"
        bind c new-window -c "#{pane_current_path}"
        bind x kill-window
        bind -n C-S-Home new-window -c "#{pane_current_path}"
        bind -n C-S-End kill-window
        bind -n C-S-PageUp next-window
        bind -n C-S-PageDown previous-window
        bind -n M-1 select-window -t 1
        bind -n M-2 select-window -t 2
        bind -n M-3 select-window -t 3
        bind -n M-4 select-window -t 4
        bind -n M-5 select-window -t 5
        bind -n M-6 select-window -t 6
        bind -n M-7 select-window -t 7
        bind -n M-8 select-window -t 8
        bind -n M-9 select-window -t 9

        # Session controls
        bind R command-prompt -I "#S" "rename-session -- '%%'"
        bind C new-session
        bind X kill-session
        bind -n C-M-S-Home new-session -c "#{pane_current_path}"
        bind -n C-M-S-End kill-session
        bind -n C-M-S-PageUp switch-client -p
        bind -n C-M-S-PageDown switch-client -n

        # General
        set -g renumber-windows on
        set -g set-clipboard on
        set -g allow-passthrough on
        set -g detach-on-destroy off

        # Status bar
        set -g status-position top
        set -g status-interval 5
        set -g status-left-length 30
        set -g status-right-length 50
        set -g window-status-separator ""

        # Theme
        set -g status-style "bg=default,fg=default"
        set -g status-left "#[fg=black,bg=blue,bold] #S #[bg=default] "
        set -g status-right "#[fg=blue]#{?client_prefix,PREFIX ,}#[fg=brightblack]#h "
        set -g window-status-format "#[fg=brightblack] #I:#W "
        set -g window-status-current-format "#[fg=blue,bold] #I:#W "
        set -g pane-border-style "fg=brightblack"
        set -g pane-active-border-style "fg=blue"
        set -g message-style "bg=default,fg=blue"
        set -g message-command-style "bg=default,fg=blue"
        set -g mode-style "bg=blue,fg=black"
        setw -g clock-mode-colour blue
      '';
    };
  };
}
