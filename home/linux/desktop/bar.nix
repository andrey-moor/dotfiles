# home/linux/desktop/bar.nix -- waybar
#
# Workspaces, window title, clock, tray, pulseaudio, network, cpu, memory. No
# battery or backlight on a VM. Colours come from the theme as CSS variables,
# so a theme switch needs no CSS edit.
{
  config,
  lib,
  pkgs,
  ...
}:
let
  t = config.modules.desktop.theme.data;
  css = lib.concatStringsSep "\n" (lib.mapAttrsToList (k: v: "@define-color ${k} ${v};") t.colors);
in
{
  programs.waybar = {
    enable = true;
    systemd.enable = true;
    settings.main = {
      layer = "top";
      position = "top";
      height = 32;
      spacing = 8;
      modules-left = [
        "hyprland/workspaces"
        "hyprland/window"
      ];
      modules-center = [ "clock" ];
      modules-right = [
        "tray"
        "pulseaudio"
        "network"
        "cpu"
        "memory"
      ];
      "hyprland/workspaces" = {
        format = "{id}";
        on-click = "activate";
        persistent-workspaces."*" = 5;
      };
      "hyprland/window" = {
        max-length = 60;
        separate-outputs = true;
      };
      clock = {
        format = "{:%a %d %b  %H:%M}";
        tooltip-format = "{calendar}";
      };
      pulseaudio = {
        format = "{icon} {volume}%";
        format-muted = "󰝟";
        format-icons.default = [
          "󰕿"
          "󰖀"
          "󰕾"
        ];
        on-click = "pwvucontrol";
      };
      network = {
        format-ethernet = "󰈀 {ipaddr}";
        format-disconnected = "󰌙";
        tooltip-format = "{ifname} {ipaddr}/{cidr}";
      };
      cpu.format = "󰍛 {usage}%";
      memory.format = "󰘚 {percentage}%";
      tray.spacing = 8;
    };
    style = ''
      ${css}
      * { font-family: "JetBrainsMono Nerd Font"; font-size: 13px; min-height: 0; }
      window#waybar { background: alpha(@background, 0.92); color: @foreground; border-bottom: 2px solid @accent; }
      #workspaces button { padding: 0 8px; color: @muted; }
      #workspaces button.active { color: @accent; border-bottom: 2px solid @accent; }
      #clock, #pulseaudio, #network, #cpu, #memory, #tray, #window { padding: 0 10px; }
    '';
  };

  # The mixer the pulseaudio module opens on click.
  home.packages = [ pkgs.pwvucontrol ];
}
