# P9b research — upstream Omarchy "Quattro" (v4.0.x), 2026-09-03

Web research by a subagent; companion to `2026-09-03-p9b-survey-omarchy-gap.md`.
Every claim carries its source URL in the agent's report; this is the distilled
version kept for the brainstorm/spec. "Quatro" as the owner remembered it is
**Quattro**.

## 1. Version and history

- Repo moved to `github.com/omacom/omarchy` (default branch `quattro`, MIT).
  v4.0.0 "The Quattro Release" 2026-08-14; current stable **v4.0.2**
  (2026-08-31), v4.0.1 2026-08-25 (both security fast-follows). ISO
  `omarchy-4.0.2.iso`.
- Timeline: 2.0 2025-08 · 3.0 2025-09 · 3.4 2026-02-26 (rocinante) · 3.8.4
  2026-07-21 · 4.0.0 2026-08-14.
- Since 3.4 (what rocinante has): 3.7 unified `omarchy` CLI, OCR, gaming
  installers; 3.8 reminders, weather, transcode, Foot as installable terminal,
  directory-style hooks; 3.8.3 tmux pane splits, Hyprland 0.55 compat.

## 2. Default stack in v4.0.2

- **Compositor**: Hyprland 0.56.2 on the stable mirror; config is **Lua**
  (`hl.config{}`, `o.bind`, `hl.unbind`). Session via **uwsm**. Defaults:
  dwindle, gaps 5/10, border 2, rounding 0, blur/shadow off, active border
  gradient `33ccff→00ff99 45deg` (`default/hypr/looknfeel.lua`).
- **Desktop shell = Quickshell 0.3.1**: one process `omarchy-shell` hosting
  bar, launcher/menu, notifications, OSD, clipboard, emoji picker, lock, idle,
  polkit agent, background, panels — all plugins under `shell/plugins/`
  (`omarchy.bar/.menu/.notifications/.osd/.clipboard/.emojis/.lock/.polkit/
  .background/.reminders/.agents/.image-picker`, panels audio/bluetooth/clock/
  network/monitor/power/weather/wifiqr/tailscale/…, services battery/idle/
  media/nightlight). Config `~/.config/omarchy/shell.json` (bar layout, idle:
  screensaver 150 s, lock 300 s).
- **Launcher/menu**: `Super+Space` unified Omarchy menu (apps + everything);
  `Super+Alt+Space` apps only. Menu tree `default/omarchy/omarchy-menu.jsonc`;
  user extensions `~/.config/omarchy/extensions/omarchy-menu.jsonc`.
- Notifications/OSD/clipboard/emoji all in-shell (`Super+Ctrl+V` history,
  `Super+Ctrl+E` emoji, `Super+Ctrl+,` DND). Lock/idle shell-owned
  (`Super+Ctrl+L`). Wallpaper shell background plugin; per-theme
  `backgrounds/`; `Super+Ctrl+Space` picker.
- **Capture**: grim+slurp + shell region picker, annotation in **Tensaku**,
  recording gpu-screen-recorder, OCR tesseract, QR zbar, hyprpicker.
  Night light hyprsunset (`Super+Ctrl+N`).
- **Terminal default = Foot**; Alacritty/Ghostty/Kitty installable. tmux
  (prefix `Ctrl+Space`) + **Herdr** (`Super+Ctrl+Return`).
- **Browser = Chromium** (themed, two bundled extensions); Chrome/Edge/Brave/
  Firefox/Zen installable. Nautilus, imv, mpv, Evince, nvim for text.
  Pinta, LibreOffice, Obsidian, OBS, Kdenlive, LocalSend, xournalpp.
- **First-party apps**: Omawrite (markdown, replaces Typora), Omacalc, Omacut,
  ttfx (screensaver), cliamp, tobi-try, dua-cli.
- Editor omarchy-nvim (LazyVim); shell tools bash + starship, zoxide, fzf,
  ripgrep, fd, eza, bat, tldr, btop, lazygit, lazydocker, fastfetch, mise.
- **Themes**: 22 shipped (tokyo-night default; catppuccin present), each =
  `colors.toml` (24 semantic colours) + backgrounds + icons.theme etc.;
  templates `default/themed/*.tpl` rendered to
  `~/.local/state/omarchy/current/theme/`.
- **Fonts**: JetBrainsMono Nerd Font, iA Writer, noto (+cjk, +emoji),
  font-awesome, `omarchy.ttf`; icons yaru.
- **Boot/login**: Limine + snapper, Plymouth theme, LUKS by default, btrfs,
  zram; SDDM (Wayland greeter) with **autologin only on encrypted installs**
  ("the LUKS prompt is the auth"). **Secure Boot must be off** (upstream).
- **Keyboard**: `kb_options = "compose:caps,shift:both_capslock_cancel"`,
  `repeat_rate 40 / repeat_delay 250`, numlock, touchpad clickfinger,
  `scroll_factor 0.4`; fcitx5 in every session.
- **Helpers**: 431 `omarchy-*` scripts exposed as `omarchy <group> <cmd>`.
  Distribution now = pacman packages at `/usr/share/omarchy` (`$OMARCHY_PATH`),
  ALPM guard forces `omarchy update`.
- **Web apps**: `omarchy-webapp-install <name> <url> <icon>` → `.desktop` with
  Chromium `--app=`; shipped HEY, Basecamp, ChatGPT, Grok, WhatsApp, Google
  Messages/Photos/Maps/Contacts, X, YouTube, Zoom, Discord, Figma, GitHub, Fizzy.
- **Docker**: docker + compose + buildx + ufw-docker; user NOT in docker
  group by default since 4.0.1 (opt-in).
- **Hotkeys** (v4): `Super+Space` menu · `Super+Alt+Space` apps · `Super+Esc`
  system · `Super+K` viewer · `Super+Ctrl+L` lock · `Super+Return` terminal ·
  `Super+Alt+Return` tmux · `Super+Ctrl+Return` Herdr · `Super+Shift+Return`
  browser · `Super+Shift+F/N/D/O/W/M` files/editor/lazydocker/Obsidian/
  Omawrite/Spotify · `Super+Shift+/` 1Password · `Super+Shift+Ctrl+A` agent ·
  `Super+Ctrl+Q` calc · `Super+Ctrl+T` btop · `Super+W` close · `Super+T`
  float · `Super+F` fullscreen · `Super+O` pop · `Super+L` dwindle↔scrolling ·
  `Super+P` pseudo · `Super+J` split · `Super+G` group · `Super+S` scratchpad ·
  `Super+1..9` (+Shift move, +Shift+Alt silent) · `Super+Tab` workspaces ·
  arrows focus/swap · `Super+-/=` resize · `Alt+Tab` cycle · `Super+C/X/V`
  universal clipboard · `Print`/`Alt+Print`/`Super+Print`/`Super+Ctrl+Print`
  capture/record/colour/OCR · panels `Super+Ctrl+A/B/W/D/P` · notifications
  `Super+,` family · `Super+Ctrl+Shift+Space` theme · `Super+Ctrl+Space` bg ·
  `Super+Shift+Space` bar · `Super+Ctrl+N` nightlight · `Super+Ctrl+I` stay
  awake · `Super+Ctrl+R` reminder. (3.x `Super+Alt+Space` = menu is gone.)

## 3. New / replaced / removed in Quattro

- Replaced by the Quickshell shell: Waybar, Walker+Elephant, Mako, SwayOSD,
  hyprlock, hypridle, swaybg, polkit-gnome.
- Alacritty/Ghostty → Foot default; Typora → Omawrite; GNOME Calculator →
  Omacalc; iwd/impala/bluetui → **NetworkManager** + shell panels.
- Hyprland `.conf` → Lua; `omarchy-upgrade-to-quattro` migrates installs.
- Git checkout → pacman packages; plugin system (`omarchy plugin …`,
  omarchyplugins.com); theme colours 8 → 24; coding-agent integration
  (agents bar widget, `a`/`c`/`cx`/`cy` aliases, Omarchy agent skill).
- System: pkexec/polkit instead of sudo prompts, apps in systemd scopes,
  deferred first-boot provisioning, factory-reset snapshot, LUKS re-key on
  first boot, DDC/CI brightness, clamshell mode.
- 4.0.1/4.0.2: docker group opt-in, agents auto-review instead of bypass,
  themes can't ship code, signed `[omarchy]` repo, SSH password auth off.

## 4. Canonical config paths (tag v4.0.2)

- `default/hypr/omarchy.lua` (entry), `default/hypr/bootstrap.lua`
  (`package.path` from `$OMARCHY_PATH`)
- `default/hypr/bindings/{applications,clipboard,media,tiling,utilities,voxtype}.lua`
- `default/hypr/{looknfeel,input,envs,windows,autostart,workspace-layouts,nvidia,toggles}.lua`,
  `default/hypr/apps/*.lua`, `default/hypr/toggles/*.lua`
- `config/hypr/{hyprland,bindings,monitors,input,looknfeel,autostart}.lua`
  (user templates seeded to `~/.config/hypr/`), `config/hypr/{hyprsunset,xdph}.conf`
- `config/omarchy/shell.json`, `default/themed/shell.toml.tpl`
- `shell/shell.qml`, `shell/plugins/<plugin>/{manifest.json,*.qml}`,
  `shell/README.md`, `docs/omarchy-shell.md`
- `themes/<name>/colors.toml` + assets; `default/themed/*.tpl`; `docs/theming.md`
- `default/omarchy/omarchy-menu.jsonc`, `default/omarchy/launcher.hides`
- `bin/omarchy-*` (431); `docs/file-layout.md`
- `install/omarchy-base.packages`, `install/omarchy-other.packages`,
  `install/config/*.sh`, `install/hardware/*`, `install/user/first-run/*`
- `default/{uwsm,sddm,plymouth,limine,snapper,systemd,fontconfig,
  xdg-terminal-exec,applications/mimeapps.list,bash/*,xcompose}`, `etc/**`
- `config/{foot,alacritty,ghostty,kitty,tmux,herdr,btop,starship.toml,lazygit,
  fastfetch,imv,git,opencode,chromium-flags.conf}`
- `migrations/*.sh` (96); `manual/*.md` (51 chapters)
- Companions: `omacom-io/omarchy-pkgs`, `omacom-io/omarchy-iso`,
  `omacom-io/{omawrite,omacalc,omacut,ttfx,herdr}`

## 5. Existing NixOS ports (GitHub, 2026-09-03)

- **olafkfreund/nixarchy** — 34★, active (pushed 2026-09-03). Vendors the 4.x
  tree as a derivation (`OMARCHY_PATH` → store path), replaces the 24
  pacman-touching scripts, pins quickshell 0.3.1, ISO + demo. Most complete
  Quattro port.
- **zicochaos/omarchy-nix** — 32★, pushed 2026-08-18. Same vendoring
  approach, NixOS + HM modules, `nix flake check` behavioural tests; claims
  desktop parity on Intel hardware; notes quickshell crashes under
  VirtualBox/QEMU software GPU.
- **atqamz/omanixy** — 17★, pushed 2026-09-03. "Omarchy owns presentation,
  NixOS owns the OS": packages only the Quickshell shell as an HM service
  (`programs.omanixy.*`), no `bin/` tree, no Hyprland config; supports
  `aarch64-linux`. Closest to "just the shell".
- **T00fy/omanix** — 88★, pushed 2026-08-14. Clean-room Nix reimplementation
  of the **3.x** stack (Waybar/Walker/Mako/hyprlock/hypridle, Ghostty). Not
  Quattro.
- **henrysipp/omarchy-nix** — 787★ but unmaintained since 2025-11.
- Others early/personal: detroyejr/omarchy-quickshell-nix, fandangos/
  nixos-omarchy-kde, jagenaujagenau/omarchy-nixos, Jylhis/marchyo,
  HighRankingBantam/toonix.
- **Caveat for stargazer**: both vendoring ports say quickshell needs a real
  or virtio GPU; nixarchy pins 0.3.1 because 0.3.0 "aborts on DPMS and leaves
  the compositor locked". Whether quickshell 0.3.1 renders under Parallels
  virtio-gpu is **unconfirmed**.

Unconfirmed: the exact Quickshell/Hyprland pins Omarchy tests against (the
stable mirror lags Arch by a month); Omarchy's edge mirror was unreachable.
