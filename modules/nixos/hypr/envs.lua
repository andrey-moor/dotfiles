-- Translated from omarchy default/hypr/envs.lua, tag v4.0.4, MIT.
--
-- Dropped from the original: the gum_env and nvidia requires, OMARCHY_PATH,
-- the PATH rewrite and XCOMPOSEFILE. None of them apply on this host.
-- Cursor size comes from the theme table, which the generated header defines.

hl.env("XCURSOR_SIZE", tostring(theme.cursor_size))
hl.env("HYPRCURSOR_SIZE", tostring(theme.cursor_size))

-- Force all apps to use Wayland.
hl.env("GDK_BACKEND", "wayland,x11,*")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")
hl.env("QT_QPA_PLATFORMTHEME", "gtk3")
hl.env("MOZ_ENABLE_WAYLAND", "1")
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "wayland")
hl.env("OZONE_PLATFORM", "wayland")
hl.env("XDG_SESSION_TYPE", "wayland")

-- Allow better support for screen sharing (Google Meet, Discord and friends).
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_DESKTOP", "Hyprland")

hl.config({
  xwayland = {
    force_zero_scaling = true,
  },

  ecosystem = {
    no_update_news = true,
  },
})
