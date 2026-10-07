-- Translated from omarchy default/hypr/bindings/{tiling,applications,
-- clipboard,media,utilities}.lua, tag v4.0.4, MIT.
--
-- Omarchy's o.bind wrapper is not ported, so every line here is a plain
-- hl.bind(keys, dispatcher, { description = ... }) and a shell action is
-- wrapped in hl.dsp.exec_cmd by hand. Programs come from the theme table the
-- generated header defines, so no binding names the terminal or the launcher.
--
-- Checked against the pinned Hyprland 0.56.2 source, src/config/lua:
--   - hl.bind reads only these option names: description or desc, repeating,
--     locked, release, non_consuming, auto_consuming, transparent,
--     ignore_mods, dont_inhibit, long_press, submap_universal, click, drag,
--     device, allow_input_capture (bindings/LuaBindingsToplevel.cpp). There is
--     no `mouse` option: SKeybind.mouse is set only by the legacy .conf bindm.
--     The two mouse binds below need none, because hl.dsp.window.drag and the
--     no-argument hl.dsp.window.resize set releasePending on the live keybind
--     themselves (bindings/LuaBindingsDispatchers.cpp).
--   - Two binds on one key both fire. KeybindManager.cpp collects every match
--     into bindsHit and then runs them all, which is what Omarchy's doubled
--     ALT + TAB relies on.
--   - hl.dispatch, hl.timer, hl.get_active_window, hl.get_config and hl.config
--     all exist, so the clipboard trio and the zoom pair are kept as written.
--
-- Not bound, grouped by reason.
--
-- Omarchy helper scripts with no target in this configuration:
--   CTRL + ALT + DELETE close all windows, SUPER + CTRL + F tiled fullscreen,
--   SUPER + Home and SUPER + ALT + Home window width, SUPER + L workspace
--   layout toggle, SUPER + SLASH and SUPER + ALT + SLASH monitor scaling,
--   SUPER + BACKSPACE transparency, SUPER + SHIFT + BACKSPACE gaps,
--   SUPER + CTRL + BACKSPACE square aspect, SUPER + CTRL + I idle toggle,
--   SUPER + CTRL + N nightlight, SUPER + CTRL + PRINT screenshot OCR,
--   SUPER + CTRL + PERIOD transcode, SUPER + CTRL + S share, the three
--   SUPER + CTRL + R reminder binds, SUPER + CTRL + ALT + T, B and W
--   notification helpers, SUPER + SHIFT + CTRL + A agent, and the audio
--   output and source switches on SHIFT + XF86AudioMute, Pause and Play.
--
-- Omarchy menu and panel surfaces, which this phase has no counterpart for:
--   SUPER + SPACE root menu goes to the launcher instead, SUPER + ALT + SPACE
--   apps menu, SUPER + CTRL + C capture menu, SUPER + CTRL + O toggle menu,
--   SUPER + CTRL + H hardware menu, SUPER + SHIFT + code:201 root menu,
--   SUPER + ESCAPE system menu, SUPER + SHIFT + CTRL + SPACE theme menu,
--   SUPER + ALT + K and SUPER + CTRL + K keybinding menus, the panel letters
--   SUPER + CTRL + A, B, D, W, P, SUPER + CTRL + ALT + D, and the nine
--   SUPER + CTRL + code:N bar panels. SUPER + ESCAPE would need wlogout, so
--   hl.dsp.exit stays on SUPER + SHIFT + E as it was before this file grew.
--
-- Apps, TUIs and web apps not installed here:
--   SUPER + SHIFT + F and SUPER + ALT + SHIFT + F nautilus,
--   SUPER + ALT + RETURN tmux, SUPER + CTRL + RETURN herdr,
--   SUPER + SHIFT + M spotify, SUPER + SHIFT + ALT + M cliamp,
--   SUPER + SHIFT + G signal, SUPER + SHIFT + W omawrite,
--   SUPER + CTRL + T btop, and every web app bind: SUPER + SHIFT + A,
--   SUPER + SHIFT + ALT + A, SUPER + SHIFT + C, SUPER + SHIFT + E,
--   SUPER + SHIFT + ALT + E, SUPER + SHIFT + Y, SUPER + SHIFT + ALT + G,
--   SUPER + SHIFT + CTRL + G, SUPER + SHIFT + P, SUPER + SHIFT + S,
--   SUPER + SHIFT + X, SUPER + SHIFT + ALT + X.
--
-- Hardware this VM does not have:
--   the four XF86MonBrightness binds and their two ALT precise variants, the
--   three keyboard backlight binds, the three touchpad binds, XF86Eject,
--   XF86PowerOff, SUPER + CTRL + Delete and SUPER + CTRL + ALT + Delete for
--   the laptop panel, the two Lid Switch binds, and the two webcam overlay
--   resize binds on SUPER + ALT + code:34 and code:35.
--
-- Needs a command or a flag this phase did not define:
--   SUPER + SHIFT + ALT + B private browser window, ALT + XF86AudioRaiseVolume
--   and ALT + XF86AudioLowerVolume precise volume, SUPER + ALT + comma invoke
--   last notification, SUPER + SHIFT + ALT + comma notification history.
--
-- Dropped because its target does not exist:
--   the slurp selection-layer block on hl.on("layer.opened"). Both the event
--   and keybind:unbind() are in 0.56.2, but desktop-capture-region takes no
--   --take-window or --select-window flag, so there is nothing to bind. Its
--   "capture entire screen" entry is the one bind below that is not Omarchy's:
--   SHIFT + PRINT runs desktop-capture-screen, which would be unreachable.
--
-- Also dropped: default/hypr/bindings/voxtype.lua in full.
--
-- Moved from the four binds this file carried before. SUPER + Q is now
-- SUPER + W, which is where Omarchy closes a window. SUPER + D is gone,
-- because Omarchy opens the launcher with SUPER + SPACE.

-- tiling.lua

hl.bind("SUPER + W", hl.dsp.window.close(), { description = "Close window" })

hl.bind("SUPER + J", hl.dsp.layout("togglesplit"), { description = "Toggle window split" })
hl.bind("SUPER + P", hl.dsp.window.pseudo(), { description = "Pseudo window" })
hl.bind("SUPER + T", hl.dsp.window.float({ action = "toggle" }), { description = "Toggle window floating/tiling" })
hl.bind("SUPER + F", hl.dsp.window.fullscreen({ mode = "fullscreen" }), { description = "Full screen" })
hl.bind("SUPER + ALT + F", hl.dsp.window.fullscreen({ mode = "maximized" }), { description = "Full width" })

-- Omarchy's pop is a helper script. Two dispatches in one Lua handler do the
-- same thing, and both halves toggle, so a second press puts the window back.
hl.bind("SUPER + O", function()
  hl.dispatch(hl.dsp.window.float({ action = "toggle" }))
  hl.dispatch(hl.dsp.window.pin())
end, { description = "Pop window out (float & pin)" })

hl.bind("SUPER + LEFT", hl.dsp.focus({ direction = "l" }), { description = "Focus on left window" })
hl.bind("SUPER + RIGHT", hl.dsp.focus({ direction = "r" }), { description = "Focus on right window" })
hl.bind("SUPER + UP", hl.dsp.focus({ direction = "u" }), { description = "Focus on above window" })
hl.bind("SUPER + DOWN", hl.dsp.focus({ direction = "d" }), { description = "Focus on below window" })

for workspace = 1, 10 do
  local key = "code:" .. tostring(workspace + 9)
  hl.bind("SUPER + " .. key, hl.dsp.focus({ workspace = tostring(workspace) }), {
    description = "Switch to workspace " .. workspace,
  })
  hl.bind("SUPER + SHIFT + " .. key, hl.dsp.window.move({ workspace = tostring(workspace) }), {
    description = "Move window to workspace " .. workspace,
  })
  hl.bind("SUPER + SHIFT + ALT + " .. key, hl.dsp.window.move({ workspace = tostring(workspace), follow = false }), {
    description = "Move window silently to workspace " .. workspace,
  })
end

hl.bind("SUPER + S", hl.dsp.workspace.toggle_special("scratchpad"), { description = "Toggle scratchpad" })
hl.bind("SUPER + ALT + S", hl.dsp.window.move({ workspace = "special:scratchpad", follow = false }), {
  description = "Move window to scratchpad",
})

hl.bind("SUPER + TAB", hl.dsp.focus({ workspace = "e+1" }), { description = "Next workspace" })
hl.bind("SUPER + SHIFT + TAB", hl.dsp.focus({ workspace = "e-1" }), { description = "Previous workspace" })
hl.bind("SUPER + CTRL + TAB", hl.dsp.focus({ workspace = "previous" }), { description = "Former workspace" })

hl.bind("SUPER + SHIFT + ALT + LEFT", hl.dsp.workspace.move({ monitor = "l" }), { description = "Move workspace to left monitor" })
hl.bind("SUPER + SHIFT + ALT + RIGHT", hl.dsp.workspace.move({ monitor = "r" }), { description = "Move workspace to right monitor" })
hl.bind("SUPER + SHIFT + ALT + UP", hl.dsp.workspace.move({ monitor = "u" }), { description = "Move workspace to up monitor" })
hl.bind("SUPER + SHIFT + ALT + DOWN", hl.dsp.workspace.move({ monitor = "d" }), { description = "Move workspace to down monitor" })

hl.bind("SUPER + SHIFT + LEFT", hl.dsp.window.swap({ direction = "l" }), { description = "Swap window to the left" })
hl.bind("SUPER + SHIFT + RIGHT", hl.dsp.window.swap({ direction = "r" }), { description = "Swap window to the right" })
hl.bind("SUPER + SHIFT + UP", hl.dsp.window.swap({ direction = "u" }), { description = "Swap window up" })
hl.bind("SUPER + SHIFT + DOWN", hl.dsp.window.swap({ direction = "d" }), { description = "Swap window down" })

hl.bind("ALT + TAB", hl.dsp.window.cycle_next(), { description = "Focus on next window" })
hl.bind("ALT + SHIFT + TAB", hl.dsp.window.cycle_next({ next = false }), { description = "Focus on previous window" })
hl.bind("ALT + TAB", hl.dsp.window.bring_to_top(), { description = "Reveal active window on top" })
hl.bind("ALT + SHIFT + TAB", hl.dsp.window.bring_to_top(), { description = "Reveal active window on top" })

hl.bind("CTRL + ALT + TAB", hl.dsp.focus({ monitor = "+1" }), { description = "Focus on next monitor" })
hl.bind("CTRL + ALT + SHIFT + TAB", hl.dsp.focus({ monitor = "-1" }), { description = "Focus on previous monitor" })

hl.bind("SUPER + code:20", hl.dsp.window.resize({ x = -100, y = 0, relative = true }), { description = "Expand window left" })
hl.bind("SUPER + code:21", hl.dsp.window.resize({ x = 100, y = 0, relative = true }), { description = "Shrink window left" })
hl.bind("SUPER + SHIFT + code:20", hl.dsp.window.resize({ x = 0, y = -100, relative = true }), { description = "Shrink window up" })
hl.bind("SUPER + SHIFT + code:21", hl.dsp.window.resize({ x = 0, y = 100, relative = true }), { description = "Expand window down" })

hl.bind("SUPER + ALT + code:20", hl.dsp.window.resize({ x = -25, y = 0, relative = true }), { description = "Expand window left a little" })
hl.bind("SUPER + ALT + code:21", hl.dsp.window.resize({ x = 25, y = 0, relative = true }), { description = "Shrink window left a little" })
hl.bind("SUPER + SHIFT + ALT + code:20", hl.dsp.window.resize({ x = 0, y = -25, relative = true }), { description = "Shrink window up a little" })
hl.bind("SUPER + SHIFT + ALT + code:21", hl.dsp.window.resize({ x = 0, y = 25, relative = true }), { description = "Expand window down a little" })

hl.bind("SUPER + CTRL + code:20", hl.dsp.window.resize({ x = -300, y = 0, relative = true }), { description = "Expand window left a lot" })
hl.bind("SUPER + CTRL + code:21", hl.dsp.window.resize({ x = 300, y = 0, relative = true }), { description = "Shrink window left a lot" })
hl.bind("SUPER + CTRL + SHIFT + code:20", hl.dsp.window.resize({ x = 0, y = -300, relative = true }), { description = "Shrink window up a lot" })
hl.bind("SUPER + CTRL + SHIFT + code:21", hl.dsp.window.resize({ x = 0, y = 300, relative = true }), { description = "Expand window down a lot" })

hl.bind("SUPER + mouse_down", hl.dsp.focus({ workspace = "e+1" }), { description = "Scroll active workspace forward" })
hl.bind("SUPER + mouse_up", hl.dsp.focus({ workspace = "e-1" }), { description = "Scroll active workspace backward" })

hl.bind("SUPER + mouse:272", hl.dsp.window.drag(), { description = "Move window" })
hl.bind("SUPER + mouse:273", hl.dsp.window.resize(), { description = "Resize window" })

hl.bind("SUPER + G", hl.dsp.group.toggle(), { description = "Toggle window grouping" })
hl.bind("SUPER + ALT + G", hl.dsp.window.move({ out_of_group = true }), { description = "Move active window out of group" })

hl.bind("SUPER + ALT + LEFT", hl.dsp.window.move({ into_group = "l" }), { description = "Move window to group on left" })
hl.bind("SUPER + ALT + RIGHT", hl.dsp.window.move({ into_group = "r" }), { description = "Move window to group on right" })
hl.bind("SUPER + ALT + UP", hl.dsp.window.move({ into_group = "u" }), { description = "Move window to group on top" })
hl.bind("SUPER + ALT + DOWN", hl.dsp.window.move({ into_group = "d" }), { description = "Move window to group on bottom" })

hl.bind("SUPER + ALT + TAB", hl.dsp.group.next(), { description = "Next window in group" })
hl.bind("SUPER + ALT + SHIFT + TAB", hl.dsp.group.prev(), { description = "Previous window in group" })

hl.bind("SUPER + CTRL + LEFT", hl.dsp.group.prev(), { description = "Move grouped window focus left" })
hl.bind("SUPER + CTRL + RIGHT", hl.dsp.group.next(), { description = "Move grouped window focus right" })

hl.bind("SUPER + ALT + mouse_down", hl.dsp.group.next(), { description = "Next window in group" })
hl.bind("SUPER + ALT + mouse_up", hl.dsp.group.prev(), { description = "Previous window in group" })

for index = 1, 5 do
  hl.bind("SUPER + ALT + code:" .. tostring(index + 9), hl.dsp.group.active({ index = index }), {
    description = "Switch to group window " .. index,
  })
end

-- applications.lua

hl.bind("SUPER + RETURN", hl.dsp.exec_cmd(theme.terminal), { description = "Terminal" })
hl.bind("SUPER + SHIFT + RETURN", hl.dsp.exec_cmd("firefox"), { description = "Browser" })
hl.bind("SUPER + SHIFT + B", hl.dsp.exec_cmd("firefox"), { description = "Browser" })
hl.bind("SUPER + SHIFT + N", hl.dsp.exec_cmd(theme.terminal .. " -e nvim"), { description = "Editor" })
hl.bind("SUPER + SHIFT + D", hl.dsp.exec_cmd(theme.terminal .. " -e lazydocker"), { description = "Docker" })
hl.bind("SUPER + SHIFT + O", hl.dsp.exec_cmd("obsidian"), { description = "Obsidian" })
hl.bind("SUPER + SHIFT + SLASH", hl.dsp.exec_cmd("1password"), { description = "Passwords" })

-- clipboard.lua

-- Send with explicit mods to the focused surface by omitting the window target,
-- so universal clipboard shortcuts reach both normal windows and focused
-- layer-shell surfaces. A virtual keyboard (wtype) won't do: the physically
-- held SUPER merges into the injected chord at the seat.
-- The down/up split works around Hyprland send_shortcut sometimes leaving
-- synthetic key state stuck/repeating.
-- https://github.com/hyprwm/Hyprland/discussions/14099
local function send_shortcut_once(mods, key)
  return function()
    hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = key, state = "down" }))

    hl.timer(function()
      hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = key, state = "up" }))
    end, { timeout = 50, type = "oneshot" })
  end
end

-- Omarchy reads a "terminal" window tag that default/hypr/apps/terminals.lua
-- sets, and windows.lua did not port that file. So the class list moves here
-- and the predicate stays inside this file. Both terminals this host installs
-- paste with SHIFT + Insert and copy with CTRL + Insert.
local terminal_classes = {
  ["Alacritty"] = true,
  ["com.mitchellh.ghostty"] = true,
}

local function active_window_is_terminal()
  local window = hl.get_active_window()
  if not window then
    return false
  end

  return terminal_classes[window.class] == true
end

local function universal_clipboard_shortcut(default_mods, default_key, terminal_mods, terminal_key)
  return function()
    if active_window_is_terminal() then
      send_shortcut_once(terminal_mods, terminal_key)()
    else
      send_shortcut_once(default_mods, default_key)()
    end
  end
end

hl.bind("SUPER + C", universal_clipboard_shortcut("CTRL", "C", "CTRL", "Insert"), { description = "Universal copy" })
hl.bind("SUPER + V", universal_clipboard_shortcut("CTRL", "V", "SHIFT", "Insert"), { description = "Universal paste" })
hl.bind("SUPER + X", send_shortcut_once("CTRL", "X"), { description = "Universal cut" })

-- The clipboard history and the emoji grid are launcher commands, so take the
-- binary off theme.launcher rather than naming it. The ids are the launcher's
-- own provider:entrypoint pair, which `vicinae cmd ls` prints.
local launcher_bin = theme.launcher:match("^%S+")

hl.bind("SUPER + CTRL + V", hl.dsp.exec_cmd(launcher_bin .. " cmd launch clipboard:history"), {
  description = "Clipboard manager",
})

-- media.lua

hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("swayosd-client --output-volume raise"), {
  description = "Volume up",
  locked = true,
  repeating = true,
})
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("swayosd-client --output-volume lower"), {
  description = "Volume down",
  locked = true,
  repeating = true,
})
hl.bind("XF86AudioMute", hl.dsp.exec_cmd("swayosd-client --output-volume mute-toggle"), {
  description = "Mute",
  locked = true,
})
hl.bind("XF86AudioMicMute", hl.dsp.exec_cmd("swayosd-client --input-volume mute-toggle"), {
  description = "Mute microphone",
  locked = true,
})

hl.bind("XF86AudioNext", hl.dsp.exec_cmd("playerctl next"), { description = "Next track", locked = true })
hl.bind("ALT + XF86AudioPlay", hl.dsp.exec_cmd("playerctl next"), { description = "Next track", locked = true })
hl.bind("XF86AudioPause", hl.dsp.exec_cmd("playerctl play-pause"), { description = "Pause", locked = true })
hl.bind("XF86AudioPlay", hl.dsp.exec_cmd("playerctl play-pause"), { description = "Play", locked = true })
hl.bind("XF86AudioPrev", hl.dsp.exec_cmd("playerctl previous"), { description = "Previous track", locked = true })
hl.bind("ALT + SHIFT + XF86AudioPlay", hl.dsp.exec_cmd("playerctl previous"), {
  description = "Previous track",
  locked = true,
})

-- utilities.lua

hl.bind("SUPER + SPACE", hl.dsp.exec_cmd(theme.launcher), { description = "Launcher" })
hl.bind("SUPER + CTRL + E", hl.dsp.exec_cmd(launcher_bin .. " cmd launch core:search-emojis"), {
  description = "Emojis",
})
hl.bind("SUPER + SHIFT + E", hl.dsp.exit(), { description = "Exit Hyprland" })
hl.bind("SUPER + K", hl.dsp.exec_cmd(theme.terminal .. " -e sh -c 'hyprctl binds | less'"), {
  description = "Keybindings",
})
hl.bind("SUPER + CTRL + Q", hl.dsp.exec_cmd("qalculate-gtk"), { description = "Calculator" })
hl.bind("XF86Calculator", hl.dsp.exec_cmd("qalculate-gtk"), { description = "Calculator" })

hl.bind("SUPER + SHIFT + SPACE", hl.dsp.exec_cmd("pkill -SIGUSR1 waybar"), { description = "Toggle top bar" })
hl.bind("SUPER + CTRL + SPACE", hl.dsp.exec_cmd("desktop-wallpaper-next"), { description = "Background switcher" })

-- xkbcommon names the comma keysym "comma"; the upper-case "COMMA" does not match.
hl.bind("SUPER + comma", hl.dsp.exec_cmd("makoctl dismiss"), { description = "Dismiss last notification" })
hl.bind("SUPER + SHIFT + comma", hl.dsp.exec_cmd("makoctl dismiss -a"), { description = "Dismiss all notifications" })
hl.bind("SUPER + CTRL + comma", hl.dsp.exec_cmd("makoctl mode -t do-not-disturb"), {
  description = "Toggle silencing notifications",
})

hl.bind("PRINT", hl.dsp.exec_cmd("desktop-capture-region"), { description = "Screenshot" })
hl.bind("SHIFT + PRINT", hl.dsp.exec_cmd("desktop-capture-screen"), { description = "Capture entire screen" })
hl.bind("ALT + PRINT", hl.dsp.exec_cmd("desktop-capture-record"), { description = "Screenrecording" })
hl.bind("SUPER + PRINT", hl.dsp.exec_cmd("pkill hyprpicker || hyprpicker -a"), { description = "Color picker" })

hl.bind("SUPER + CTRL + Z", function()
  local zoom = hl.get_config("cursor.zoom_factor") or 1
  hl.config({ cursor = { zoom_factor = zoom + 1 } })
end, { description = "Zoom in" })

hl.bind("SUPER + CTRL + ALT + Z", function()
  hl.config({ cursor = { zoom_factor = 1 } })
end, { description = "Reset zoom" })

hl.bind("SUPER + CTRL + L", hl.dsp.exec_cmd("loginctl lock-session"), { description = "Lock system" })
