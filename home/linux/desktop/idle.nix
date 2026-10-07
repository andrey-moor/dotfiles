# home/linux/desktop/idle.nix -- hypridle
#
# Lock at 10 min, screen off at 20 min (DPMS is best effort on vmwgfx), lock
# before sleep. 1Password is not locked on screen lock, on purpose: that
# caused SSH-agent re-auth churn on the previous machine.
{
  config,
  lib,
  ...
}:
{
  services.hypridle = {
    enable = true;
    settings = {
      general = {
        lock_cmd = "pidof hyprlock || ${lib.getExe config.programs.hyprlock.package}";
        before_sleep_cmd = "loginctl lock-session";
        after_sleep_cmd = "hyprctl dispatch dpms on";
      };
      # Repeatable hyprlang sections are lists in home-manager's schema.
      listener = [
        {
          timeout = 600;
          on-timeout = "loginctl lock-session";
        }
        {
          timeout = 1200;
          on-timeout = "hyprctl dispatch dpms off";
          on-resume = "hyprctl dispatch dpms on";
        }
      ];
    };
  };
}
