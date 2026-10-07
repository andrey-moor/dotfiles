-- Translated from omarchy default/hypr/windows.lua, tag v4.0.4, MIT.
--
-- Omarchy's o.window helper does not exist in Hyprland 0.56.2, so each rule is
-- an hl.window_rule call with its match table spelled out. A rule name makes a
-- reload update the rule in place instead of registering a second one.
--
-- Dropped from the original: require("default.hypr.apps"), the per-app tweak
-- file. Nothing here opts out of the default opacity yet.

-- See https://wiki.hypr.land/Configuring/Basics/Window-Rules/
hl.window_rule({
  name = "suppress-maximize-events",
  match = { class = ".*" },
  suppress_event = "maximize",
})

-- Tag all windows for default opacity (apps can override with the
-- -default-opacity tag).
hl.window_rule({
  name = "tag-default-opacity",
  match = { class = ".*" },
  tag = "+default-opacity",
})

-- Fix some dragging issues with XWayland.
hl.window_rule({
  name = "fix-xwayland-drags",
  match = {
    class = "^$",
    title = "^$",
    xwayland = true,
    float = true,
    fullscreen = false,
    pin = false,
  },
  no_focus = true,
})

-- Apply default opacity after apps have had a chance to opt out.
hl.window_rule({
  name = "default-opacity",
  match = { tag = "default-opacity" },
  opacity = "0.985 0.96",
})
