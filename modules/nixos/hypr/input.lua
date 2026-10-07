-- Translated from omarchy default/hypr/input.lua, tag v4.0.4, MIT.
--
-- Dropped from the original: the /etc/vconsole.conf reader and the non-Latin
-- layout fallback it fed. This host pins one Latin layout, so there is nothing
-- to read and no second layout to prepend. The empty kb_variant, kb_model and
-- kb_rules the original set go with it, since they only restated the defaults.
--
-- Omarchy's o.window helper does not exist in Hyprland 0.56.2, so the two
-- scroll rules below are hl.window_rule calls. A rule name makes a reload
-- update the rule in place instead of registering a second one.

-- https://wiki.hypr.land/Configuring/Basics/Variables/#input
hl.config({
  input = {
    kb_layout = "us",
    -- CapsLock is the compose key, so Caps Lock itself lives on both Shifts.
    -- The _cancel variant releases it on the next lone Shift, so a misfire
    -- clears itself.
    kb_options = "compose:caps,shift:both_capslock_cancel",
    follow_mouse = 1,
    sensitivity = 0,

    repeat_rate = 40,
    repeat_delay = 250,
    numlock_by_default = true,

    touchpad = {
      natural_scroll = false,
      clickfinger_behavior = true,
      scroll_factor = 0.4,
    },
  },

  misc = {
    key_press_enables_dpms = true,
    mouse_move_enables_dpms = true,
  },
})

-- Scroll nicely in the terminal.
hl.window_rule({
  name = "terminal-scroll",
  match = { class = "(Alacritty|kitty|foot)" },
  scroll_touchpad = 1.5,
})

hl.window_rule({
  name = "ghostty-scroll",
  match = { class = "com.mitchellh.ghostty" },
  scroll_touchpad = 0.2,
})
