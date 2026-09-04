# P9b vetting — composed Hyprland stack components (2026-09-03)

Read-only verification by a subagent against the pinned nixpkgs, home-manager and catppuccin inputs (aarch64-linux, cache.nixos.org checks) plus upstream metadata. Input to the P9b spec. Corrections applied after review are noted inline as **[review]**.

## Composed Hyprland desktop — candidate verification (read-only, 2026-09-03)

Baseline facts: pinned nixpkgs `044bfe75…` (26.11-pre) = Hyprland **0.56.2**, hyprland-protocols 0.7.0, hyprutils 0.14.1, hyprlang 0.6.8, hyprgraphics 0.5.1, xdph 1.4.1. HM input = release 26.11 pre; catppuccin input `35d78c2`. **Every candidate below evaluated as `aarch64-linux` and is present on cache.nixos.org (`nix path-info` exit 0)** — "cached ✓" is therefore implied in all rows. Hyprland v0.56.2 still builds these protocols (`CMakeLists.txt` @v0.56.2): wlr-gamma-control, wlr-output-power-management, wlr-data-control + ext-data-control, ext-session-lock, ext-idle-notify, hyprland-ctm-control, hyprland-lock-notify, wlr-screencopy + ext-image-copy-capture (https://raw.githubusercontent.com/hyprwm/Hyprland/v0.56.2/CMakeLists.txt).

Legend: HM = home-manager module in pinned input; CAT = `catppuccin.<x>` HM module in pinned input; "hypr-lib" = links hyprlang/hyprutils/hyprgraphics (library ABI coupling, rebuilt by nixpkgs together — not compositor-version coupling); "hypr-proto" = uses a hyprland-protocols extension (must exist in the running compositor).

### 1. Bar
| candidate | upstream | nixpkgs | HM | CAT | Hyprland-coupled | VM caveats | verdict |
|---|---|---|---|---|---|---|---|
| waybar | 0.15.0 (2026-02-06), pushed 2026-08-27, 11.9k★ https://github.com/Alexays/Waybar | 0.15.0 | `programs.waybar` (settings, style, systemd.enable/targets) | ✓ `catppuccin.waybar` (mode prependImport/createLink, accent) | hyprland/workspaces module uses Hyprland IPC socket (not protocol) — 0.56 IPC compat unverified | GTK3 layer-shell, CPU fine | **pick** |
| ironbar | pushed 2026-09-01, 1.4k★ https://github.com/JakeStanger/ironbar | 0.19.0 | none | none | Hyprland IPC | — | alt only |
| ags | 2.3.0 in nixpkgs | 2.3.0 | none | none | — | Astal/GJS stack, heavier | no |
| quickshell | pushed 2026-08-29, 2.95k★ https://github.com/quickshell-mirror/quickshell | 0.3.0 | `programs.quickshell` | none | — | Qt6/QML, GPU-rendered scenegraph on virgl (untested) | note: Omarchy 4.0.0 (2026-08-14) replaced waybar+walker+mako+swayosd+hyprlock+hypridle+swaybg+polkit-gnome with one Quickshell shell (https://github.com/basecamp/omarchy/releases/tag/v4.0.0) |

**Rec:** waybar — HM+catppuccin+largest community; the Quickshell consolidation is Omarchy's direction, not a composed-desktop fit.

### 2. Launcher
| candidate | upstream | nixpkgs | HM | CAT | coupled | VM | verdict |
|---|---|---|---|---|---|---|---|
| walker + elephant | walker v2.17.0 (2026-07-16), pushed 2026-07-23, 3.0k★ https://github.com/abenz1267/walker; elephant v2.22.0 (2026-07-16), 453★ https://github.com/abenz1267/elephant | walker 2.17.0, elephant 2.22.0 — **match upstream latest** | `services.walker` (settings, theme{name,style,layout}, enableElephantIntegration, systemd.enable → `walker --gapplication-service`, Requires elephant.service) + `services.elephant` (settings, user service) | none | none (GTK4 layer-shell) | providers built as Go plugins from `internal/providers/*` (all enabled by default) incl. clipboard; Omarchy dropped walker in 4.0.0 | **pick**, flag freshness risk |
| fuzzel | 1.15.0 (2026-09-02) https://codeberg.org/dnkl/fuzzel | 1.14.1 (one behind) | `programs.fuzzel` | ✓ | none | pure Wayland, tiny | fallback (already in repo) |
| rofi 2.0 | wayland merged upstream; `rofi-wayland` attr gone | 2.0.0 | `programs.rofi` | ✓ | none | — | alt |
| anyrun | pushed **2024-07-29**, 880★ https://github.com/Kirottu/anyrun | 26.6.1 (fork/reroll — unverified) | `programs.anyrun` | none | — | stale upstream | no |
| vicinae | v0.28.1 (2026-09-03), pushed 2026-09-04, 9.3k★ https://github.com/vicinaehq/vicinae | 0.27.1 | `programs.vicinae` | ✓ | Hyprland ships `vicinae-hotkey-v1` protocol (0.56 CMake) | Qt6; built-in clipboard+emoji+calc | strong alt |

Clipboard/emoji: walker → elephant providers; vicinae → built-in; fuzzel/rofi → cliphist + external emoji picker (no built-in).
**Rec:** walker+elephant (nixpkgs is at upstream latest today; both have HM services) — keep fuzzel installed as the zero-dep fallback; re-evaluate vicinae if walker upstream stalls (Omarchy, its main driver, abandoned it in 4.0).

### 3. Notifications
| candidate | upstream | nixpkgs | HM | CAT | VM | verdict |
|---|---|---|---|---|---|---|
| mako | pushed 2026-06-30, 3.2k★ https://github.com/emersion/mako | 1.11.0 | `services.mako` (settings, extraConfig) | ✓ | layer-shell, tiny | **pick** |
| swaync | pushed 2026-06-25, 2.6k★ https://github.com/ErikReider/SwayNotificationCenter | 0.12.6 | `services.swaync` | ✓ | GTK4 center | alt if a control-centre is wanted |
| dunst | pushed 2026-08-11, 5.6k★ https://github.com/dunst-project/dunst | 1.13.2 | `services.dunst` | ✓ | X11+Wayland | no |

**Rec:** mako.

### 4. Lock screen (CRITICAL)
| candidate | upstream | nixpkgs | HM | CAT | coupled | PAM | verdict |
|---|---|---|---|---|---|---|---|
| hyprlock | v0.9.6 (2026-07-18), pushed 2026-08-11, 1.6k★ https://github.com/hyprwm/hyprlock | 0.9.6 | `programs.hyprlock` (settings, extraConfig) | ✓ | hypr-lib only (hyprlang/hyprutils/hyprgraphics; **no** hyprland-protocols dep in package.nix); ext-session-lock-v1; GLES | upstream `pam/hyprlock` = `auth include login` (https://raw.githubusercontent.com/hyprwm/hyprlock/main/pam/hyprlock). NixOS `programs.hyprlock` sets `security.pam.services.hyprlock = { }` **and force-enables `services.hypridle`** | **pick (with PAM fix below)** |
| swaylock | pushed 2026-07-09, 1.2k★ https://github.com/swaywm/swaylock | 1.8.6 (effects 1.7.0.0) | `programs.swaylock` (settings) | ✓ | none; ext-session-lock | upstream `auth include login`; NixOS `wayland-session.nix` sets `pam.services.swaylock = {}` when `programs.hyprland.enable` (already true here) | fallback |
| gtklock | pushed 2026-02-04, 497★ https://github.com/jovanlanik/gtklock | 4.0.0 | none | none | none | NixOS `programs.gtklock` → `pam.services.gtklock = {}` | no |

PAM facts (from pinned sources, not vibes):
- NixOS renders each `security.pam.services.<x> = {}` as a **standalone stack** (`unixAuth` default true → pam_unix); it does NOT `include login`. So the upstream "include login" is irrelevant on NixOS.
- himmelblau 4.0.0 module adds `pam_himmelblau` (`auth sufficient`, order unix-10) **only** to `pamServices` default `[passwd login systemd-user]` + sudo/doas/sshd (`nix/modules/himmelblau.nix` L113-198). Our repo does not extend that list → **hyprlock/swaylock/gtklock stacks get pam_unix only → with no local password, unlock is impossible** until `services.himmelblau.pamServices = [ … "hyprlock" ]` is added.
- pam_himmelblau conversation: single `prompt_echo_off` PIN prompt when Hello is enrolled (`src/pam/src/pam/mod.rs`); FIDO/MFA branches also exist (L696-846) — hyprlock's one-field UI can service a PIN prompt, not a FIDO touch/device-code dialog. Configurable `hello_pin_prompt` (man himmelblau.conf 5).
- himmelblau issue search (12 hits, none titled hyprlock/swaylock): resume-from-suspend lockouts #1206 (closed 2026-03-04), #1509 (closed 2026-07-07, "PIN prompt disappears after resume, service restart needed"), Hello re-enrol PAM_USER_UNKNOWN #1674 (2026-09-02) — https://github.com/himmelblau-idm/himmelblau/issues. No documented lock-screen PAM snippet in the 4.0.0 tree (grep of man/ docs-xml/ empty).
- Fail-safe: all three use ext-session-lock-v1 (Hyprland 0.56 supports it) — the compositor keeps the screen locked if the locker crashes; Hyprland also has `hyprland-lock-notify-v1`. Fingerprint: n/a in VM.

**Rec:** hyprlock, but gate on: add `"hyprlock"` to `services.himmelblau.pamServices`, keep `sudo` exclusion as-is, and test an offline PIN unlock + resume-from-suspend before relying on it; keep swaylock as the tested fallback (its PAM service already exists via `programs.hyprland`).

### 5. Idle
| candidate | upstream | nixpkgs | HM | coupled | VM | verdict |
|---|---|---|---|---|---|---|
| hypridle | v0.1.8 (2026-07-26), pushed 2026-08-11, 695★ https://github.com/hyprwm/hypridle | 0.1.8 | `services.hypridle` (settings, systemdTarget); NixOS `services.hypridle` (user unit WantedBy graphical-session.target, PATH gets hyprland+hyprlock) | **hypr-proto** (hyprland-protocols in package.nix) + hypr-lib | `hyprctl dispatch dpms off` on virtio-gpu: Hyprland ships wlr-output-power-management; whether virtio honours DPMS is unverified | **pick** |
| swayidle | pushed 2026-08-27, 755★ https://github.com/swaywm/swayidle | 1.9.0 | `services.swayidle` | none; ext-idle-notify | logind lock-session via `-w` | fallback |

**Rec:** hypridle (NixOS's hyprlock module enables it anyway); treat DPMS as best-effort in the VM.

### 6. OSD
| candidate | upstream | nixpkgs | HM | VM | verdict |
|---|---|---|---|---|---|
| swayosd | v0.3.2 (2026-06-22), 1.3k★ https://github.com/ErikReider/SwayOSD | 0.3.1 | `services.swayosd` (topMargin, stylePath); **no NixOS module** for the libinput backend (needs a system unit + dbus — nixpkgs patches systemd paths) | no backlight in VM → only volume/caps OSD | **pick**, server-side backend optional |
| avizo | 1.3-unstable-2024-11-03 | — | `services.avizo` | — | stale |
| wob | 0.16 | — | `services.wob` | — | bar-only |

**Rec:** swayosd (client only; skip the privileged libinput backend in the VM).

### 7. Wallpaper
| candidate | upstream | nixpkgs | HM | coupled | verdict |
|---|---|---|---|---|---|
| awww (ex-swww) | codeberg LGFae/awww, updated 2026-09-01, 424★ https://codeberg.org/LGFae/awww; nixpkgs alias `swww → awww` added 2026-03-22 | 0.12.1 | `services.awww` (extraArgs) | none; IPC `awww img` = theme-driven switching | **pick** |
| hyprpaper | v0.8.4 (2026-04-29) https://github.com/hyprwm/hyprpaper | 0.8.4 | `services.hyprpaper` | hypr-lib + hyprtoolkit + hyprwire | alt |
| swaybg | — | 1.2.2 | none | none; restart to switch | minimal fallback |

**Rec:** awww (maintained rename of swww, HM module, runtime switching).

### 8. Screenshots / picker / recording
| candidate | upstream | nixpkgs | HM | coupled | verdict |
|---|---|---|---|---|---|
| grim+slurp+satty | satty pushed 2026-09-02, 2.4k★ https://github.com/gabm/Satty | 1.5.0 / 1.5.0 / 0.22.0 | `programs.satty` (settings) | none (wlr-screencopy / ext-image-copy-capture both present in 0.56) | **pick** |
| hyprshot | GitHub API 404 for Gustash/Hyprshot — unverified | 1.3.0 | `programs.hyprshot` | wraps grim/slurp + `hyprland` (hyprctl) | alt |
| wayshot / flameshot | — | 1.6.0 / 14.0.0 | flameshot: `services.flameshot` | flameshot wayland via portal — unverified | no |
| hyprpicker | — | 0.4.7 | none | hypr-lib (hyprutils) | **pick** |
| gpu-screen-recorder | hosted git.dec05eba.com (GitHub 404) | 6.0.1 (NixOS `programs.gpu-screen-recorder`) | — | needs VAAPI/NVENC; virtio-gpu has no encoder → unverified/likely no | desktop only |
| wf-recorder / wl-screenrec | — | 0.6.0 / 0.3.2 | none | ffmpeg CPU encode | **wf-recorder for VM** |

### 9. Clipboard
| candidate | upstream | nixpkgs | HM | CAT | verdict |
|---|---|---|---|---|---|
| cliphist + wl-clipboard (+wl-clip-persist) | pushed 2026-06-08, 1.5k★ https://github.com/sentriz/cliphist | 0.7.0 / 2.3.0 / 0.5.0 | `services.cliphist` (allowImages, extraOptions, systemdTargets default `wayland.systemd.target`), `services.wl-clip-persist` | none | **pick** (text+image; plaintext DB on disk ~/.cache) |
| elephant clipboard provider | in elephant 2.22.0 | — | via `services.elephant` | — | use only if walker chosen and single-store wanted |
| clipse | pushed 2026-06-09, 1.0k★ https://github.com/savedra1/clipse | 1.2.1 | `services.clipse` | ✓ | TUI-only |

### 10. Polkit agent
| candidate | upstream | nixpkgs | HM | coupled | verdict |
|---|---|---|---|---|---|
| hyprpolkitagent | pushed 2026-09-03, 226★ https://github.com/hyprwm/hyprpolkitagent | 0.1.3 | `services.hyprpolkitagent` (unit PartOf/WantedBy `wayland.systemd.target`) | hyprutils + hyprland-qt-support + Qt6 | **pick** |
| polkit-gnome | 0.105 (2011-era; GNOME archive — unverified) | 0.105 | `services.polkit-gnome` | none | fallback |
| soteria | pushed 2026-07-21, 163★ https://github.com/imvaskel/soteria | 0.3.2 | none | GTK4 | alt |
| lxqt / mate | — | 2.4.0 / 1.28.1 | none | — | no |

### 11. Session manager
| candidate | facts | verdict |
|---|---|---|
| uwsm | pushed 2026-08-31, 1.15k★ https://github.com/Vladimir-csp/uwsm (releases/latest 404 → tag unverified); nixpkgs 0.26.7. `programs.hyprland.withUWSM` **exists** in pinned nixpkgs → `programs.uwsm.enable`, which needs `waylandCompositors.<n>` and writes a `hyprland-uwsm.desktop` running `uwsm start -F -- <bin>`; note it switches `services.dbus.implementation` to dbus-broker by default. **No HM uwsm module.** | conditional |
| plain exec-once (current) | `modules/nixos/desktop-hyprland.nix` L50-58, L152-160: exec-once does `dbus-update-activation-environment … && systemctl --user start hyprland-session.target`; own `hyprland-session.target` BindsTo graphical-session.target. HM's `wayland.windowManager.hyprland.systemd` does the identical thing (`lib.nix` L23,L110-111) and HM services default to `wayland.systemd.target` = graphical-session.target → all HM `services.*` above already start under the current design. | **keep for now** |

**Rec:** stay on the hand-rolled target for the VM; uwsm only when moving to the x86_64 desktop (would replace the greetd `--cmd start-hyprland` with `uwsm start hyprland-uwsm.desktop` and remove the exec-once target line — interaction with the Lua config unverified).

### 12. Night light
| candidate | nixpkgs | HM | coupled | VM | verdict |
|---|---|---|---|---|---|
| hyprsunset | v0.4.0 (2026-07-13) https://github.com/hyprwm/hyprsunset; 0.4.0 | `services.hyprsunset` (settings; `transitions` deprecated) | **hypr-proto** (hyprland-ctm-control-v1) | DRM CTM on virtio connector — unverified | desktop |
| wlsunset | 0.4.0 | `services.wlsunset` | wlr-gamma-control (still in 0.56) | gamma on virtio-gpu unverified | **VM pick** |
| gammastep | 2.0.11 | `services.gammastep` | wlr-gamma-control | — | alt |

**Rec:** skip in the VM (no benefit through a Parallels window); wlsunset if wanted; hyprsunset on the desktop.

### 13. Terminal
| candidate | upstream | nixpkgs | HM | CAT | GL | verdict |
|---|---|---|---|---|---|---|
| alacritty | v0.17.0 (2026-04-06) https://github.com/alacritty/alacritty | 0.17.0 | `programs.alacritty` (repo uses out-of-store config) | ✓ | GL 3.3 — works on virgl (repo note) | current |
| foot | 1.28.0 (2026-09-02) https://codeberg.org/dnkl/foot | 1.27.0 | `programs.foot` | ✓ | none (pixman/CPU, Wayland-only) | **VM pick**; Omarchy default since v3.8.0 (https://github.com/basecamp/omarchy/releases) |
| ghostty | releases/latest 404 (unverified) | 1.3.1 | `programs.ghostty` | ✓ | GL 4.3 per repo note + https://github.com/ghostty-org/ghostty/issues/2025 (docs page fetched had no GL statement) | **desktop pick** |
| kitty | — | 0.48.2 | `programs.kitty` | ✓ | GL 3.3 | alt |

### 14. Files / viewers
| role | pick | alt | nixpkgs | HM/CAT |
|---|---|---|---|---|
| file manager | nautilus 50.2.2 (Omarchy's choice; GNOME deps, works on wlroots — unverified weight) | thunar 4.20.9, pcmanfm-qt 2.4.1 | all cached | none |
| images | imv 5.0.1 | — | | `programs.imv` + CAT ✓ |
| video | mpv 0.41.0 | — | | `programs.mpv` + CAT ✓ |
| PDF | **papers 50.2** (`pkgs.papers`, evince successor) | evince 48.4 | | none |
| calc | qalculate-gtk 5.12.0 | gnome-calculator 50.0, qalculate-qt | | none |

### 15. Theming glue (catppuccin input coverage)
Present HM modules (`modules/home-manager/`): alacritty, foot, ghostty, kitty, waybar, mako, swaync, dunst, fuzzel, rofi, tofi, vicinae, hyprland (Lua theme file!), hyprlock, swaylock, hyprtoolkit, cursors, gtk, kvantum, qt5ct, imv, mpv, clipse, wlogout, wleave, firefox, chrome, nushell, starship, tmux, bat, fzf, lazygit, neovim, zathura, … (full list in the input). **Absent:** walker, elephant, hypridle, swayosd, awww, satty, hyprpolkitagent, papers, nautilus.
- GTK: `catppuccin.gtk` now only sets **icons** (Papirus + catppuccin-papirus-folders) — no GTK theme option in the module; `pkgs.catppuccin-gtk` 1.0.3 still exists but upstream deprecation status unverified. Use `gtk.enable` + adw-gtk3 6.5 (cached) for GTK3, libadwaita ignores themes.
- Qt: `catppuccin.kvantum` (asserts `qt.style.name = "kvantum"`) or `catppuccin.qt5ct` (asserts `qt.platformTheme.name = "qtct"`); kvantum plugin 1.1.8 / qt6ct 0.11 cached.
- Cursors: `catppuccin.cursors` + `catppuccin.hyprland` exports `HYPRCURSOR_THEME`; catppuccin-cursors 2.0.0.
- Icons: papirus-icon-theme 20260801, yaru-theme 25.10.3 (both cached).

### 16. Fonts (all cached; nar sizes from cache)
`nerd-fonts.jetbrains-mono` 3.5.0 — 239.5 MB; `noto-fonts` 2026.08.01 — 51.5 MB; `noto-fonts-cjk-sans` 2.004 — 64.6 MB; `noto-fonts-color-emoji` 2.051 — 10.7 MB (`noto-fonts-emoji` attr gone); `font-awesome` 7.2.0 — 0.7 MB; `ia-writer-duospace` (2018 snapshot) 0.3 MB; `ia-writer-quattro` (2023 snapshot) 0.8 MB.

### 17. Web apps
chromium 152.0.7977.64 — `hydraPlatforms` includes aarch64-linux; wrapper **and** `chromium-unwrapped` cached (closure 1.84 GB). firefox 154.0.1 cached (1.49 GB), `programs.firefox` HM already used (`home/linux/firefox.nix`). Omarchy launches web apps as `setsid uwsm-app -- <browser> --app=URL` and matches windows by class `chrome-<host>__-Default` (https://raw.githubusercontent.com/basecamp/omarchy/master/default/hypr/apps/browser.conf) → that app_id pattern works under Wayland; `--class` behaviour unverified. HM `xdg.desktopEntries` for launchers.

### 18. Docker
`users.users.andreym` is a real local uid-1000 user (`modules/nixos/base.nix`) mapped to Entra via `user_map_file`, so `extraGroups = [ "docker" ]` applies normally. Pinned nixpkgs `virtualisation/docker.nix` has **no** `rootless` option (grep = 0) **[review: wrong — it lives in `virtualisation/docker-rootless.nix`; `virtualisation.docker.rootless.enable` evaluates on stargazer; rootless Docker is available]** → rootless is `virtualisation.docker.rootless`-less here; choose rootful docker or rootless podman (repo already has podman-based `home/linux/containers.nix`). lazydocker v0.25.2 (2026-04-19) https://github.com/jesseduffield/lazydocker; nixpkgs 0.25.2, HM `programs.lazydocker`.

## One-line recommendations
1. Bar: **waybar** (HM+CAT, 11.9k★, Hyprland IPC). 2. Launcher: **walker+elephant** (nixpkgs == upstream latest, HM services), fuzzel kept as fallback. 3. Notifications: **mako**. 4. Lock: **hyprlock** + `services.himmelblau.pamServices += "hyprlock"`, swaylock as fallback. 5. Idle: **hypridle**. 6. OSD: **swayosd** (client only). 7. Wallpaper: **awww**. 8. Shots: **grim+slurp+satty**, **hyprpicker**, **wf-recorder** (VM) / gpu-screen-recorder (desktop). 9. Clipboard: **cliphist + wl-clip-persist**. 10. Polkit: **hyprpolkitagent**. 11. Session: **keep hand-rolled target**; uwsm on the desktop. 12. Night light: **none in VM**, hyprsunset on desktop. 13. Terminal: **foot** (VM), **ghostty** (desktop), alacritty stays. 14. **nautilus, imv, mpv, papers, qalculate-gtk**. 15. catppuccin/nix + adw-gtk3 + kvantum + catppuccin-cursors + Papirus. 16. fonts as listed (~370 MB). 17. chromium `--app=` via `xdg.desktopEntries`, firefox default. 18. rootful docker + lazydocker (or stay on podman).

## Risks / open questions
1. **Lock screen unlock is broken by default**: NixOS builds `pam.services.hyprlock` with pam_unix only; himmelblau only wires `passwd/login/systemd-user/sudo/sshd`. Needs `pamServices` extension + real test (PIN prompt via single-field UI; MFA/FIDO branch cannot be serviced by hyprlock).
2. himmelblau resume-from-suspend lockouts (#1206, #1509) — lock+suspend path must be fire-drilled; `himmelblau-keepwarm` timer may mask it.
3. NixOS `programs.hyprlock` force-enables `services.hypridle` (system-level user unit) — collides with HM `services.hypridle` if both are set; choose one layer.
4. walker/elephant freshness: nixpkgs matches upstream today (both 2026-07-16), but Omarchy — walker's main driver — dropped it in 4.0.0; watch cadence; walker↔elephant version pairing rule unverified.
5. Hyprland-coupled binaries: hypridle, hyprsunset (hyprland-protocols), hyprpolkitagent/hyprpicker/hyprlock/hyprpaper (hypr-libs); `system.autoUpgrade` from the lockfile rebuilds them together, but a nixpkgs bump that moves Hyprland alone can break them — pin-check on each `just update`.
6. uwsm: `withUWSM` exists but would replace the greetd command, the `hyprland-session.target` glue and flip dbus to dbus-broker; behaviour with the Lua config unverified — do not mix with the current exec-once target.
7. DPMS/gamma/CTM on virtio-gpu (hypridle dpms, wlsunset, hyprsunset) — all unverified in the VM.
8. Quickshell/Qt6 components (hyprpolkitagent, vicinae) on virgl — rendering untested.
9. waybar `hyprland/workspaces` vs 0.56 IPC changes — unverified.
10. Unverified upstream facts: ghostty GL 4.3 (repo note + issue #2025 only), Hyprshot repo location, uwsm latest tag, polkit-gnome archive status, catppuccin-gtk upstream deprecation, docker rootless (absent in this nixpkgs snapshot — confirm intent).

## Addenda (roles 6–10, from the agent's late helper)

- **6. OSD** — swayosd's caps-lock/brightness backend (`swayosd-libinput-backend`) has no NixOS/HM wiring (home-manager #6347 open); `services.swayosd` exposes only enable/package/stylePath/topMargin. Volume/mute OSD via `swayosd-client` from keybinds works without the backend. wob (0.16, active) is the zero-privilege alternative; avizo fork-fragmented. → swayosd client-only in the VM.
- **7. Wallpaper** — LGFae/swww archived 2025-10-31; canonical successor codeberg.org/LGFae/awww (v0.12.1 2026-04-25, CPU rendering, IPC `awww img` + transitions). hyprpaper pulls hyprtoolkit/hyprwire/hyprlang/hyprutils. → awww.
- **8. Screenshots/recording** — grim now at gitlab.freedesktop.org/emersion/grim; satty at Satty-org/Satty (v0.22.0 2026-08-03). Gustash/hyprshot stale since 2024-07; active fork FlareXes/hyprshot. **flameshot broken with xdg-desktop-portal-hyprland** (flameshot #4543) — excluded. gpu-screen-recorder is hardware-encode only → unusable on virtio-gpu; wl-screenrec VAAPI-oriented; **wf-recorder** (ffmpeg/libx264 CPU) for the VM. Keep xdph and Hyprland from the same nixpkgs generation (already true).
- **9. Clipboard** — cliphist v0.7.0: bbolt DB at `$XDG_CACHE_HOME/cliphist/db`, mode 0600, **plaintext**; clipse likewise; elephant's clipboard storage unverified. All wrap `wl-paste --watch`. → cliphist + wl-clip-persist; note secrets land on disk unencrypted.
- **10. Polkit** — hyprpolkitagent v0.1.3 built on hyprtoolkit (nixpkgs adds hyprland-qt-support + polkit-qt-1), hypr-lib coupled. polkit-gnome upstream abandoned (mirror archived 2026-06-19). soteria v0.3.3 (GTK4, single maintainer, no HM module) is the lowest-coupling alternative. → hyprpolkitagent (has the HM service), soteria if the hypr-lib coupling is unwanted.
- Risks addendum: (11) swayosd caps-lock backend needs a hand-rolled privileged unit; (12) flameshot excluded.
