-- Keybinds. Omarchy's default/hypr/bindings.lua is not ported yet, so this
-- file carries only the four binds the module had before the split.
--
-- The programs come from the theme table, which the generated header defines,
-- so no binding names a command this module does not install.

hl.bind("SUPER + RETURN", hl.dsp.exec_cmd(theme.terminal), { description = "Terminal" })
hl.bind("SUPER + D", hl.dsp.exec_cmd(theme.launcher), { description = "Launcher" })
hl.bind("SUPER + Q", hl.dsp.window.close(), { description = "Close window" })
hl.bind("SUPER + SHIFT + E", hl.dsp.exit(), { description = "Exit Hyprland" })
