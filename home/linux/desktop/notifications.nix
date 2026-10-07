# home/linux/desktop/notifications.nix -- mako
#
# The theme pipeline is the single source for mako's colours, so no
# catppuccin option is set here.
{
  config,
  lib,
  ...
}:
let
  t = config.modules.desktop.theme.data;
  mako = config.services.mako.package;
in
{
  services.mako = {
    enable = true;
    settings = {
      default-timeout = 5000;
      anchor = "top-right";
      font = "JetBrainsMono Nerd Font 11";
      background-color = t.colors.background;
      text-color = t.colors.foreground;
      border-color = t.colors.accent;
      border-size = 2;
      border-radius = 0;
      # Nested attrsets become `[section]` blocks in mako's config.
      "urgency=high" = {
        border-color = t.colors.red;
        default-timeout = 0;
      };
      # The mode the key map toggles with `makoctl mode -t do-not-disturb`.
      "mode=do-not-disturb" = {
        invisible = 1;
      };
    };
  };

  # home-manager's mako module installs the dbus service file but no unit, so
  # mako would start on the first notification and outlive the compositor.
  # Declaring the unit puts it under the session like waybar and vicinae.
  systemd.user.services.mako = {
    Unit = {
      Description = "Mako notification daemon";
      Documentation = [ "man:mako(5)" ];
      After = [ "graphical-session.target" ];
      PartOf = [ "graphical-session.target" ];
    };
    Service = {
      # Same shape as home-manager's dunst and swaync units. A `simple` unit
      # would go active before mako owns the name, and the dbus service file
      # the module installs could spawn a rival mako in that window.
      Type = "dbus";
      BusName = "org.freedesktop.Notifications";
      ExecStart = lib.getExe mako;
      ExecReload = "${lib.getExe' mako "makoctl"} reload";
      Restart = "on-failure";
      RestartSec = 5;
    };
    Install.WantedBy = [ "graphical-session.target" ];
  };
}
