# P9b survey — stargazer (NixOS VM) vs rocinante (Omarchy 3.4.0, frozen)

Read-only survey, 2026-09-03, by a subagent over the repo at HEAD and rocinante
live (Tailscale SSH). Input to the P9b brainstorm ("make stargazer the final
daily-driver config before P7"). The old Omarchy `Stargazer` VM was not
surveyed. Upstream Omarchy's current release is covered by a separate note.

**Caveat that changes the picture:** rocinante's `~/dotfiles` is at `f0ba223`
(2026-08-24) — 70 commits behind main, pre-P3..P6 (old `modules/home/` layout,
chezmoi still present). Its live home-manager generation is built from that old
tree, so the current `homeConfigurations.rocinante` has never been applied
there; `~/.config/{nvim,nushell,alacritty}` are chezmoi-era copies, and its nvim
is omarchy-nvim (LazyVim), not the repo's AstroNvim.

## A. What stargazer already has (repo)

System (`hosts/stargazer/default.nix`, `modules/nixos/*`):
- NixOS 26.11 pin, disko LUKS2+btrfs, lanzaboote+shim Secure Boot, sops via
  ssh-to-age, himmelblau Entra login, `/etc/os-release` = Ubuntu 24.04,
  `system.autoUpgrade` daily/persistent from the github ref (`base.nix:91`)
- `base.nix`: user `andreym` (wheel/video/input, passwordless sudo), sshd
  key-only, systemd-resolved + public DNS/DoT, tailscale, firewall default-deny
  with `tailscale0` trusted, flakes, TZ LA, `git vim curl`
- `vm-guest.nix` / `parallels-guest.nix`: virtio initrd, `virtio_gpu`,
  `hardware.graphics`, `virtio-gpu-resize` follower, networkd DHCP MTU 1400 /
  no RA, Parallels Tools on (`prlcc` autostart)
- `desktop-hyprland.nix`: `programs.hyprland` (0.56.2, **Lua** config rendered
  to `/etc/xdg/hypr/hyprland.lua`), greetd+tuigreet (`--remember`, no
  autologin), PipeWire alsa+pulse + rtkit, `hyprland-session.target` shim,
  fonts = `nerd-fonts.jetbrains-mono` only, systemPackages `alacritty waybar
  mako fuzzel wl-clipboard mesa-demos`; exec-once = waybar, mako (both
  unconfigured); 4 keybinds total (Super+Return alacritty, Super+D fuzzel,
  Super+Q close, Super+Shift+E exit); monitor pinned `Virtual-1,preferred,auto,1`
- Existing options: `modules.nixos.desktop.{configFormat,monitor,terminal,extraExecOnce}`

Home-manager (`home/core.nix`, `home/dev.nix`, `dev/python.nix`,
`linux/firefox.nix`, `linux/wayvnc.nix`):
- Base: coreutils findutils ripgrep fd jq yq-go tree htop curl wget unzip just;
  EDITOR=nvim; `xdg.enable`
- core: profile (git identity; **installs `pkgs.ghostty` on every Linux host**,
  `home/profiles/andreym.nix:18-20`), alacritty config symlink, atuin (+daemon),
  bat (catppuccin), direnv+nix-direnv, ghostty config (aarch64 branch wraps a
  nonexistent `/bin/ghostty`, `home/shell/ghostty.nix:23-47`, Arch-era), git+LFS+
  GCM azure wrapper, gpg+yubikey tools (pinentry-tty), lazygit, nushell+carapace+
  nu_scripts, 1Password CLI + SSH-agent routing + allowed_signers, openvpn, ssh,
  starship, tmux
- dev: bazelisk/buildtools, claude-code (+MCP), codex, go toolchain, jj+delta,
  kubernetes tooling, neovim AstroNvim (`extraPackages` has **xclip**, X11),
  nix tooling, opencode, rustup+cargo tools, terraform, vscode (catppuccin + 6
  extensions), python3+uv
- firefox (catppuccin mocha, uBlock/ClearURLs/Kagi/1Password/firefox-color),
  wayvnc (tailnet IP, no GPU, cursor overlay)

## B. What rocinante/Omarchy has that stargazer lacks

Legend: [G] generic, [H] host-specific (physical Framework Desktop: AMD Strix
Halo, MT7925 Wi-Fi, no battery, 5GbE). "NixOS eq." = obvious nixpkgs/HM
equivalent.

### B1. Desktop shell pieces

- **Launcher: walker 2.15 + elephant 2.20** (providers: desktopapplications,
  websearch, files, symbols, calc, clipboard, menus, runner, todo, unicode,
  bluetooth, providerlist). `~/.config/walker/config.toml` stock Omarchy
  (prefixes `/ . : = @ $`), `~/.config/elephant/*.toml` + `menus/*.lua`,
  `elephant.service` user unit, `~/.config/autostart/walker.desktop`
  (`walker --gapplication-service`). Stargazer: fuzzel, unconfigured. NixOS
  eq.: `pkgs.walker` (+ HM `programs.walker`), `pkgs.elephant` (verify
  provider packaging). [G]
- **Bar: waybar** `~/.config/waybar/config.jsonc` (stock 3.4.0) — modules:
  custom/omarchy (menu), workspaces 1-5 persistent, clock, custom/update,
  custom/voxtype, screenrecording/idle/notification-silencing indicators
  (scripts under `$OMARCHY_PATH/default/waybar/indicators/`), tray-expander,
  bluetooth, network, pulseaudio, cpu, battery; ~10 `on-click` handlers call
  `omarchy-*` scripts. `style.css` imports theme `waybar.css`, JetBrainsMono
  NF 12px, icon font `omarchy.ttf`. NixOS eq.: HM `programs.waybar`. [G;
  battery/bluetooth/wifi modules H]
- **Notifications: mako** config → theme `mako.ini` including
  `default/mako/core.ini`. Binds: Super+, dismiss / Super+Shift+, all /
  Super+Ctrl+, silence / Super+Alt+, invoke. NixOS eq.: HM `services.mako`. [G]
- **Lock / idle: hyprlock 0.9.3 + hypridle 0.1.7.** hyprlock stock (theme
  colours, background from `~/.config/omarchy/current/background`). hypridle
  **user-customised**: timeouts 600/601/1200 s vs stock 150/151/330;
  `lock_cmd = omarchy-lock-screen`, `before_sleep_cmd = loginctl
  lock-session`. `omarchy-lock-screen` **locally patched** (only dirty file in
  `~/.local/share/omarchy`) to stop `1password --lock` on screen lock
  (2026-05-10, SSH-agent re-auth churn). Screensaver = tte in a terminal.
  NixOS eq.: HM `programs.hyprlock`, `services.hypridle`. [G;
  kbd_backlight/brightnessctl listeners H]
- **Wallpaper:** `swaybg -i ~/.config/omarchy/current/background -m fill`
  (catppuccin `2-cat-waves-mocha.png`). [G]
- **Theming (Omarchy theme system):** `~/.config/omarchy/current/theme` =
  catppuccin; per-app theme files (alacritty, btop, chromium, ghostty,
  hyprland, hyprlock, icons = `Yaru-purple`, kitty, mako, neovim, obsidian,
  swayosd, vscode, walker, waybar); 17 themes; `omarchy-theme-set*`. GTK via
  gsettings: `Adwaita-dark`, icons `Yaru-purple`, `prefer-dark`, cursor 24; Qt
  via kvantum. Stargazer: nothing (catppuccin HM module imported in `homeBase`
  but only used for firefox). NixOS eq.: `catppuccin/nix` (already an input),
  HM `gtk`, `qt`, `dconf`. [G]
- **Screenshots / capture:** Print = grim+slurp → satty (copy + save
  `~/Pictures`); Super+Print `hyprpicker -a`; Alt+Print screenrecord
  (gpu-screen-recorder); `~/.config/hypr/xdph.conf` sets
  `hyprland-preview-share-picker`, `allow_token_by_default`. NixOS eq.:
  `pkgs.{grim,slurp,satty,hyprpicker,gpu-screen-recorder}`;
  `hyprland-preview-share-picker` — verify. [G; gpu-screen-recorder useless
  on virtio-gpu]
- **Clipboard:** wl-clipboard (have) + elephant clipboard history
  (`Super+Ctrl+V` → `walker -m clipboard`); universal Super+C/X/V →
  Ctrl+Insert / Ctrl+X / Shift+Insert (`default/hypr/bindings/clipboard.conf`).
  Host↔guest clipboard on stargazer stays TigerVNC/OSC52 by decision. [G]
- **OSD:** swayosd server autostart + client for volume/mic/brightness/
  playerctl; `~/.config/swayosd/{config.toml,style.css}`. NixOS eq.: HM
  `services.swayosd`. [G; brightness keys H]
- **Keybindings — the whole Omarchy set** (rocinante `hyprland.conf` sources
  `default/hypr/{autostart,bindings/media,bindings/clipboard,bindings/tiling-v2,
  bindings/utilities,envs,looknfeel,input,windows}.conf` + theme + user
  `{monitors,input,bindings,looknfeel,autostart}.conf`):
  - tiling-v2: Super+W close (stargazer uses Super+Q), Ctrl+Alt+Del close-all,
    Super+J/P/T/F/Ctrl+F/Alt+F, Super+O pop, arrows focus/swap, Super+1..0 &
    Shift/Shift+Alt move, Super+S scratchpad, Tab cycling, monitor moves,
    Alt+Tab, Super+-/= resize, mouse drag, groups (Super+G, Alt+arrows, Alt+1..5)
  - utilities: Super+Space walker, Super+Ctrl+E emoji, Super+Ctrl+C capture
    menu, Super+Alt+Space omarchy-menu, Super+Esc system menu, Super+K
    keybinding viewer, Super+Shift+Space toggle bar, Super+Ctrl+Space bg,
    Super+Shift+Ctrl+Space theme, Super+Backspace opacity, Super+Shift+Backspace
    gaps, notification binds, Super+Ctrl+I idle toggle, Super+Ctrl+N nightlight
    (hyprsunset), Print/Alt+Print/Super+Print, Super+Ctrl+S share,
    Super+Ctrl+A/B/W/T → wiremix/bluetui/impala/btop TUIs, Super+Ctrl+X
    voxtype (not installed), zoom, Super+Ctrl+L lock, Apple Display
    brightness (asdcontrol) [H]
  - **user `bindings.conf` (owner deltas):** Super+Return `xdg-terminal-exec
    --dir=$(omarchy-cmd-terminal-cwd)`, Super+Alt+Return tmux, Super+Shift+F
    nautilus, Super+Shift+B browser (+Alt private), Super+Shift+M spotify, N
    editor, D lazydocker, G signal, O obsidian (`-disable-gpu
    --enable-wayland-ime`), W typora, / 1password; web apps: Super+Shift+A
    ChatGPT, +Alt Grok, C HEY calendar, E HEY mail, Y YouTube, Alt+G WhatsApp,
    Ctrl+G Google Messages, P Google Photos, X X, Alt+X X post
  - **user `input.conf`:** `kb_options = compose:caps`, `repeat_rate 40`,
    `repeat_delay 600`, `numlock_by_default`, touchpad `scroll_factor 0.4`,
    per-terminal scroll_touchpad windowrules; `~/.XCompose` present [G]
  - **user `monitors.conf`:** `env = GDK_SCALE,2`, `monitor=,preferred,auto,auto`
    [H — VM pins Virtual-1 at scale 1]
  - `envs.conf` (Wayland env for GDK/QT/SDL/MOZ/Electron,
    `XDG_CURRENT_DESKTOP=Hyprland`, xwayland `force_zero_scaling`, cursor 24),
    `looknfeel.conf` (gaps 5/10, border 2, rounding 0, shadow, blur, animations,
    dwindle `pseudotile/preserve_split/force_split 2`, `cursor.hide_on_key_press`),
    `windows.conf` (opacity 0.97/0.9 via tag, per-app rules under
    `default/hypr/apps/*.conf`)
  - **Format gap:** rocinante = Hyprland 0.54.2 hyprlang `.conf` with
    `source =`; stargazer = 0.56.2 **Lua** (`.conf` only as revert path, gone
    in 0.57). Every line above must be translated or rendered. [G]
- **Session plumbing:** sddm autologin `Session=hyprland-uwsm`; **uwsm**
  (`uwsm-app --` everywhere, `~/.config/uwsm/{default,env}`:
  `TERMINAL=xdg-terminal-exec`, `EDITOR=nvim`, `OMARCHY_PATH` on PATH, mise
  activate); `xdg-terminal-exec` + `~/.config/xdg-terminals.list` (ghostty
  first); `polkit-gnome` agent autostart; fcitx5 autostart (only `keyboard-us`
  configured — unused); `systemctl --user import-environment` +
  `dbus-update-activation-environment --all`; `xdg-user-dirs`. Stargazer:
  greetd/tuigreet, no polkit agent, no uwsm, hand-rolled
  `hyprland-session.target`. NixOS eq.: `programs.hyprland.withUWSM`,
  `security.polkit` + `hyprpolkitagent`, `pkgs.xdg-terminal-exec`, HM
  `xdg.userDirs`. [G]
- **Omarchy menu + ~190 `omarchy-*` scripts** (`~/.local/share/omarchy/bin`):
  launch-or-focus(-webapp/-tui), launch-{browser,editor,webapp,audio,bluetooth,
  wifi,walker,screensaver}, cmd-{screenshot,screenrecord,share,terminal-cwd,
  audio-switch}, toggle-{idle,nightlight,waybar,notification-silencing,
  screensaver}, menu(-keybindings), lock-screen, hyprland-window-{pop,close-all},
  workspace-toggle-gaps, monitor-scaling-toggle, theme-*, font-*, tz-select,
  snapshot, restart-*, system-{logout,reboot,shutdown}. Spec §6: "the portable
  subset" packaged. [G except brightness/battery/hw-* H]
- **Web apps:** `omarchy-launch-webapp` = `<browser> --app=URL` (chromium
  fallback); `~/.local/share/applications/*.desktop`: Basecamp, ChatGPT,
  Discord, Figma, Fizzy, GitHub, Google Contacts/Maps/Messages/Photos, HEY,
  Tailscale (+Admin), WhatsApp, X, YouTube, Zoom. NixOS eq.: HM
  `xdg.desktopEntries`. [G]
- **mimeapps:** text/* → nvim, images → imv, pdf → evince, http/https/mailto →
  **microsoft-edge**, video → mpv, `inode/directory` → nautilus,
  `x-scheme-handler/claude-cli` → claude-code-url-handler. NixOS eq.: HM
  `xdg.mimeApps`. [G, browser choice open — D4]
- **Fonts:** JetBrainsMono NF (have), CaskaydiaMono NF, Noto (+CJK, emoji,
  extra), Font Awesome 7, iA Writer, Liberation, Adwaita Sans/Mono,
  `omarchy.ttf`; fontconfig strong-binds sans→Liberation Sans, serif→Liberation
  Serif, mono→JetBrainsMono NF. NixOS eq.: `fonts.packages`,
  `fonts.fontconfig.defaultFonts`. [G]

### B2. GUI apps (aarch64 availability noted)

- 1password-beta (GUI, tray, SSH agent socket `~/.1password/agent.sock` which
  `env.nu:88` already expects) — `pkgs._1password-gui` (aarch64 ok) [G]
- chromium (webapp engine) — `pkgs.chromium` [G]
- microsoft-edge (default browser) — nixpkgs Edge is x86_64-only; HM
  `home/linux/edge.nix` x86_64-only [x86]
- obsidian — `pkgs.obsidian` [G]; typora — x86_64-only [x86]
- signal-desktop — verify aarch64 [G]
- spotify — x86_64-only (web app or `spotify-player`) [x86]; steam [H]
- libreoffice-fresh, evince, gnome-calculator, gnome-disk-utility, seahorse,
  nautilus (+sushi, gvfs), imv, mpv, pinta, kdenlive, obs-studio, xournalpp,
  localsend, system-config-printer, kvantum — all in nixpkgs [G; obs H]
- lmstudio (HM `home/dev/lmstudio.nix`) — no aarch64-linux [x86]
- vscode, firefox, alacritty (have); ghostty 1.3.1 (GL 4.3 → rocinante only)
- TUIs: impala (iwd), bluetui, wiremix; pamixer, playerctl [wiremix G;
  impala/bluetui H]
- obsbot-camera-control, asdcontrol, microsoft-azure-vpn-client-bin [H / x86]

### B3. CLI / dev tooling not in the HM layer

- eza, zoxide, fzf, dust, btop (+theme), fastfetch, tldr, gum, plocate, inxi,
  whois, xmlstarlet, imagemagick, ffmpegthumbnailer, less, man-db,
  bash-completion, usbutils [G]
- gh, lazydocker, mise (+usage; `mise activate` in uwsm env), tobi-try,
  tzupdate, tree-sitter-cli, luarocks, ruby, clang/llvm, dotnet-runtime-9.0,
  python-{gobject,jinja,poetry-core}, postgresql-libs, mariadb-libs,
  libqalculate, libfido2 [G]
- **docker + buildx + compose** (`docker.service`, `docker` group, ~10 owner
  containers: code-indexer/qdrant/neo4j stacks). Repo has only unused podman
  `home/linux/containers.nix`. NixOS eq.: `virtualisation.docker.enable` [G]
- rocinante-only HM (`hosts/rocinante/default.nix:41-61`): azure-cli
  (+bastion, ssh ext), uv, nodejs, dnsutils, netcat-openbsd, grpcurl,
  shellcheck, mesa-demos, copilot, hunk [G]
- `~/.local/bin` hand-installed: kubeconform, oras, py-spy, python3.10, gsd-sdk,
  vhclientx86_64 (x86), microsoft-identity-broker-wrapper, claude [mostly G]
- Hand-made user units: `git-maintenance@{hourly,daily,weekly}.timer`. NixOS
  eq.: HM `programs.git.maintenance` [G]
- nvim on rocinante = omarchy-nvim/LazyVim; repo = AstroNvim (divergence, not
  a gap).
- neovim `extraPackages` uses `xclip` (`home/dev/neovim.nix:32`); Wayland
  wants `wl-clipboard`.

### B4. System services

- Audio: pipewire + wireplumber + alsa/pulse/jack — add `jack.enable` if wanted [G]
- Bluetooth: bluez, bluetui, waybar module — `hardware.bluetooth.enable` [H]
- Wi-Fi: iwd + impala, wifi-powersave rules, wireless-regdb —
  `networking.wireless.iwd` (spec §6 says NetworkManager) [H]
- Printing/mDNS: cups + cups-browsed/filters/pdf, avahi + nss-mdns [G-ish]
- Power: power-profiles-daemon, upower, brightnessctl, fwupd, amd-ucode,
  `omarchy-battery-monitor.timer` [H]
- Login: sddm autologin (`hyprland-uwsm`), plymouth (theme omarchy) [cosmetic]
- Snapshots/boot: snapper (root, home) + timers, limine + limine-snapper-sync,
  zram-generator — NixOS generations replace rollback; `zramSwap.enable` [G]
- Firewall: ufw + ufw-docker — NixOS firewall [replaced]
- Smartcard: pcscd.socket + ccid + opensc + `p11-kit-server.socket` —
  `services.pcscd` (check himmelblau FIDO) [G]
- Keyring: gnome-keyring daemon socket + seahorse + libsecret —
  `services.gnome.gnome-keyring` (himmelblau #981) [G]
- Identity: identity-device-broker, `intune-agent.timer`, HM
  `home/linux/intune.nix` + `rosetta.nix` — replaced by himmelblau [x86/Arch]
- Misc: kernel-modules-hook, linux-modules-cleanup, tzupdate, xdg-user-dirs,
  fast-shutdown, sudo tweaks, file-watchers sysctl [mostly Arch-specific;
  file-watchers sysctl G]

### B5. Omarchy-specific, NOT worth porting

- `omarchy-update*`, `omarchy-pkg-*`, `omarchy-install-*`, `omarchy-migrate`,
  `omarchy-reinstall*`, `omarchy-refresh-*`, `omarchy-keyring`, yay —
  pacman/yay mechanics; Nix generations replace them
- limine + limine-snapper-sync, `omarchy-snapshot` — generations do this
- ufw/ufw-docker, `omarchy-setup-dns`, tzupdate, kernel-modules-hook,
  `install/config/*.sh` sysctl/sudoers hacks — NixOS options
- sddm + theme, plymouth theme — greetd works with himmelblau; plymouth optional
- `omarchy-theme-set*` / 17 themes — only if theme switching is wanted (D3)
- fcitx5 — no IM in use
- voxtype, `omarchy-windows-vm`, hibernation, `hw-*`, keyboard-backlight
  scripts, Apple Display brightness — hardware not present
- intune-portal / identity-broker / azure-vpn + `home/linux/{intune,rosetta}.nix`
  — himmelblau path; Azure VPN client x86_64-only (open for P7)
- chezmoi remnants — retired in P5
- mise — overlaps direnv+nix-direnv; keep only if `mise-work` is used
- Edge/typora/spotify/steam/lmstudio on aarch64 — no packages; revisit on P7

## C. Explicit decisions on record

- Spec §6 (`docs/superpowers/specs/2026-07-23-environment-refactor-design.md:126-147`):
  Omarchy as tracked flake input (`inputs.omarchy`, non-flake, pinned master);
  base layer = hypr defaults via `source =`, waybar/walker/mako configs, themes,
  "portable subset of `omarchy-*` scripts packaged as a derivation"; override
  layer = our deltas loaded after; system layer never Omarchy's
  (`programs.hyprland.enable`, PipeWire, bluetooth + blueman, NetworkManager,
  greetd autologin after LUKS, nixos-hardware). Known risk "Hyprland 0.55+
  hyprlang→Lua migration" — now real: `source =` of Omarchy `.conf` cannot
  work under Lua.
- Spec §8 step 7 (`:192`): P7 = NixOS on rocinante's 2nd NVMe + Omarchy-input
  desktop + data migration checklist (~/dev rsync, browser profiles,
  atuin/shell history, GPG state, rice files).
- P9 plan `:12`: "Desktop scope = minimal declarative Hyprland. The §6 Omarchy
  tracked-input port is its OWN later phase built on this VM before P7."
- P9 plan `:105`: terminal on stargazer = Alacritty (Parallels GL 4.0 ceiling).
- P9 plan `:189-206`: clipboard not coupled to the hypervisor (wayvnc +
  TigerVNC, OSC 52, pbcopy/pbpaste shims).
- P9 plan `:18`: Rosetta, `intune.nix` on stargazer, nixGL, ufw dropped.
- `desktop-hyprland.nix:1-10`: "The Omarchy tracked-input port is its own
  later phase and will replace most of this".
- `hosts/rocinante/README.md:3-6`: rocinante Omarchy install is frozen (no
  `omarchy-update`), fallback of record for 30 days post-cutover.

## D. Open questions (surveyor's recommended default in bold)

1. Port mechanism under Lua-only Hyprland: vendor Omarchy as a flake input and
   translate `.conf` at build time, or hand-port bindings/looknfeel/windows to
   Lua once and use the Omarchy input only for scripts/themes/waybar/walker
   configs? **Hand-port to Lua; keep `inputs.omarchy` for scripts + waybar/
   walker/mako/swayosd/hyprlock configs + theme assets.**
2. Launcher: walker+elephant vs fuzzel. **walker+elephant.**
3. Theme: static Catppuccin Mocha via `catppuccin/nix` vs port runtime theme
   switching. **Static Catppuccin Mocha; Yaru-purple icons + Adwaita-dark GTK.**
4. Default browser on aarch64: **Firefox default handler; chromium for `--app`
   web apps; Edge/Azure-VPN rocinante-only until P7.**
5. GUI app set on the VM: **shared = 1password-gui, obsidian, signal,
   nautilus+evince+imv+mpv, localsend, libreoffice; spotify as web app;
   typora/lmstudio/steam/edge = rocinante-only imports.**
6. Terminal per host: **alacritty on stargazer, ghostty on rocinante-P7; delete
   the `/bin/ghostty`/nixGL branches; move ghostty out of the profile.**
7. Containers: **`virtualisation.docker.enable` on NixOS hosts; delete
   `containers.nix` (mention, not silent).**
8. Session/login stack: **greetd+tuigreet no autologin (Entra PAM needs an
   interactive login), `withUWSM = true`, `hyprpolkitagent`, gnome-keyring on
   (watch himmelblau #981), keep "don't lock 1Password on screen lock".**

Also: whether rocinante should be re-switched to current main now (70 commits
behind, chezmoi-era HM) — the frozen-host policy only covers
`omarchy-update`/pacman.
