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
  # Every lock path runs this, never `loginctl lock-session`. logind points
  # session/auto at the user's Display session, and an SSH login that came
  # first takes that slot. The Lock signal for the seat then never arrives.
  #
  # systemd-run puts the locker in a transient unit of its own. Spawned
  # directly it would sit in hypridle.service's cgroup, so restarting hypridle
  # killed the live lock screen. No --unit name is passed on purpose, because a
  # unit of that name still awaiting collection would fail the next lock.
  lock = "pidof hyprlock || systemd-run --user --quiet --collect -- ${lib.getExe config.programs.hyprlock.package}";

  # `hyprctl dispatch X` evaluates `return hl.dispatch(X)` as Lua under
  # Hyprland 0.56's Lua config, so the old `dpms off` form is a syntax error.
  # hl.dsp.dpms takes its action from a table field. A bare string argument
  # falls through to toggle, so the table is the only form that forces a state.
  dpms = action: "hyprctl dispatch 'hl.dsp.dpms({ action = \"${action}\" })'";
in
{
  services.hypridle = {
    enable = true;
    settings = {
      general = {
        lock_cmd = lock;
        before_sleep_cmd = lock;
        after_sleep_cmd = dpms "on";
      };
      # Repeatable hyprlang sections are lists in home-manager's schema.
      listener = [
        {
          timeout = 600;
          on-timeout = lock;
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
