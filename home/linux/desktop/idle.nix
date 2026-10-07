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
let
  # `hyprctl dispatch X` evaluates `return hl.dispatch(X)` as Lua under
  # Hyprland 0.56's Lua config, so the old `dpms off` form is a syntax error.
  # hl.dsp.dpms takes its action from a table field; a bare string argument
  # falls through to toggle, so the table is the only form that forces a state.
  dpms = action: "hyprctl dispatch 'hl.dsp.dpms({ action = \"${action}\" })'";
in
{
  services.hypridle = {
    enable = true;
    settings = {
      general = {
        lock_cmd = "pidof hyprlock || ${lib.getExe config.programs.hyprlock.package}";
        before_sleep_cmd = "loginctl lock-session";
        after_sleep_cmd = dpms "on";
      };
      # Repeatable hyprlang sections are lists in home-manager's schema.
      listener = [
        {
          timeout = 600;
          on-timeout = "loginctl lock-session";
        }
        {
          timeout = 1200;
          on-timeout = dpms "off";
          on-resume = dpms "on";
        }
      ];
    };
  };
}
