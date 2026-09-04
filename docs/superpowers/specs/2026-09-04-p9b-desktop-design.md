# P9b — stargazer as the daily-driver desktop (design)

Date: 2026-09-04. Status: approved in brainstorm, awaiting owner review of this
document. Predecessors: P9 (stargazer NixOS VM, installed + Entra/Intune
enrolled + Secure Boot on + compliant, fire drill passed 2026-09-03). Successor:
P7 (the same configuration on rocinante's physical hardware).

Inputs, all in `docs/superpowers/plans/`:
`2026-09-03-p9b-survey-omarchy-gap.md` (repo vs rocinante's Omarchy 3.4),
`2026-09-03-p9b-research-omarchy-quattro.md` (upstream Omarchy 4.0.x),
`2026-09-03-p9b-vetting-composed-stack.md` (per-component verification against
the pinned nixpkgs, aarch64 cache, home-manager and catppuccin inputs).

## 1. Goal

Turn `nixosConfigurations.stargazer` from "minimal Hyprland that proves the
platform" into the configuration the owner uses every day, so that the flake is
final before it goes onto physical hardware. Everything in `home/core.nix` and
`home/dev.nix` (Claude Code, Codex, OpenCode, Copilot, Kubernetes/Go/Rust/
Python toolchains, Neovim, tmux, nushell, git, jj, 1Password CLI) is unchanged;
this phase adds the desktop layer around it.

Owner priorities, in order: no lock-in to any single upstream (Omarchy,
omanixy, or another port); security; pick the best-maintained component per
role; keep the repo lean — add apps when they are missed, not in advance.

## 2. Decisions

| # | Decision | Why (short) |
|---|----------|-------------|
| D1 | **Composed stack**, not Omarchy 4's Quickshell shell | Community reports on Quattro are about breakage for customised installs and the project taking over more of the machine; 4.0.1/4.0.2 were security fast-follows; the composed pieces are mature with home-manager modules. A spike proved the Quickshell shell *runs* on stargazer (virtio-gpu, aarch64), so it remains a per-role swap later, not a redesign. |
| D2 | **Role contract**: one home-manager module per desktop role | Swapping a component (or adopting a Quickshell plugin for one role) is one import. |
| D3 | **Theme = data**: `modules.desktop.theme.name`, palette files in Omarchy's `colors.toml` format, rendered at build time | hlissner's "active theme" ergonomics without per-theme code; Omarchy's theme catalogue reusable as data; switching is one word + rebuild. Start with catppuccin, tokyo-night, gruvbox, nord, rose-pine. |
| D4 | **Firefox is the default browser everywhere**; Chromium only as the web-app engine; Edge only as an explicit x86_64 host import | Validated on stargazer 2026-09-03: Entra device SSO via the linux-entra-sso extension + himmelblau's broker (`acquireTokenSilently success`), WebAuthn with the YubiKey once attached as a USB device. |
| D5 | **Rootless Docker** by default, per-host switch to rootful + `docker` group | `docker` group is root-equivalent; rootless keeps container escapes at user level. Must be proven on the owner's compose stacks. |
| D6 | **GUI set**: Firefox, VS Code, Alacritty, 1Password GUI, Obsidian, papers, imv, mpv, qalculate. Web-app launcher mechanism, list empty. | What the repo already has plus what the owner's config already implies. Omarchy's default catalogue is not adopted. |
| D7 | **Terminal**: alacritty on the VM, ghostty on the x86_64 desktop; foot not introduced | Alacritty is configured, themed, works on virgl; ghostty needs GL 4.3 (Parallels caps at 4.0). |
| D8 | **Key map**: Omarchy 4's, verbatim where the component exists; shell-panel binds dropped | One reference (the Omarchy manual) for muscle memory; kept in Lua files, not Nix strings. |
| D9 | **Session**: keep greetd + tuigreet and the hand-rolled `hyprland-session.target`; uwsm deferred to P7 | Entra PAM needs an interactive login; uwsm would replace the greeter command, the session glue and D-Bus implementation, unverified with the Lua config. |
| D10 | **rocinante stays frozen** (OS and home-manager) until P7 | Its clone is 70 commits behind; re-switching would change the daily driver's nvim/shell weeks before the OS is replaced anyway. |

### Components (from the vetting; every one present in the aarch64 cache of the pinned nixpkgs)

| Role | Pick | Fallback | Note |
|------|------|----------|------|
| bar | waybar 0.15 (HM `programs.waybar`, catppuccin module) | ironbar | Hyprland IPC compat with 0.56 verified in step 2 |
| launcher | vicinae (HM `programs.vicinae`, catppuccin module; clipboard, emoji, calc built in; Hyprland ships `vicinae-hotkey-v1`) | walker+elephant, fuzzel | Qt6 on virgl: Quickshell (Qt6/QML) already rendered fine on this VM |
| notifications | mako 1.11 (HM `services.mako`, catppuccin) | swaync | |
| lock | hyprlock 0.9.6 (HM `programs.hyprlock`, catppuccin) | swaylock | PAM: see §5 |
| idle | hypridle 0.1.8 (HM `services.hypridle`) | swayidle | DPMS best-effort on virtio-gpu |
| OSD | swayosd 0.3.1, client only (HM `services.swayosd`) | wob | libinput backend has no NixOS wiring; not needed in a VM |
| wallpaper | awww 0.12 (HM `services.awww`; swww's maintained successor) | hyprpaper | runtime cycling via IPC |
| screenshots | grim + slurp + satty (HM `programs.satty`), hyprpicker | hyprshot (FlareXes fork) | flameshot excluded: broken on the Hyprland portal |
| recording | wf-recorder (CPU encode) on the VM; gpu-screen-recorder on the desktop | — | virtio-gpu has no video encoder |
| clipboard | vicinae's history; cliphist + wl-clip-persist only if insufficient | clipse | history is plaintext on disk (§5) |
| polkit agent | hyprpolkitagent 0.1.3 (HM `services.hyprpolkitagent`) | soteria | |
| night light | none on the VM; hyprsunset on the desktop | wlsunset | |
| files/viewers | papers, imv, mpv, qalculate; no file manager until missed | nautilus/thunar | |
| GTK/Qt/cursor/icons | adw-gtk3 + `gtk.enable`, kvantum + `qt.enable`, catppuccin-cursors, Papirus | | catppuccin/nix's `gtk` module now sets icons only |
| fonts | JetBrainsMono Nerd Font, Noto (+CJK, colour emoji), Font Awesome | | ~370 MB, cached |
| portals | xdg-desktop-portal-hyprland + xdg-desktop-portal-gtk | | keep xdph and Hyprland from one nixpkgs generation |

## 3. Architecture

### 3.1 Module layout

```
home/linux/desktop.nix              # bundle: { imports = [ ./desktop/*.nix ]; }
home/linux/desktop/
  bar.nix launcher.nix notifications.nix osd.nix lock.nix idle.nix
  polkit.nix wallpaper.nix capture.nix clipboard.nix apps.nix webapps.nix
home/linux/theme.nix                # HM side of the theme option (§4)
modules/nixos/desktop-hyprland.nix  # compositor + system side (existing, reshaped)
modules/nixos/hypr/
  bindings.lua input.lua looknfeel.lua windows.lua   # checked-in Lua, rendered with theme values
lib/theme.nix                       # pure: theme name -> { colors, mode, backgrounds, fragments }
themes/<name>/                      # colors.toml, backgrounds/, optional per-app fragments
```

Rules:
- Each role module is a plain module (no options, no `mkIf`), imports = enabled,
  exactly like the rest of `home/`. Host-specific values that differ between
  hosts (theme name, terminal, wallpaper directory) are options on the small
  shared `modules.desktop.*` set; everything else is fixed.
- A role module owns its systemd user service, config rendering, keybind
  *targets* (the commands the key map calls) and its theme consumption. It
  never reads another role's config.
- `desktop-hyprland.nix` keeps: `programs.hyprland`, greetd/tuigreet, PipeWire,
  `hyprland-session.target` and the exec-once handoff, the Lua renderer, xdg
  portals, fonts, GTK/Qt platform packages, the `virtio-gpu-resize` follower
  interaction. It loses waybar/mako/fuzzel and the ad-hoc four keybinds.
- The Hyprland configuration is rendered to `/etc/xdg/hypr/hyprland.lua` as
  today, but composed from the checked-in Lua files plus a generated
  `theme.lua` (colours, cursor size, monitor) so keybinds and rules are edited
  as Lua, not as Nix strings.
- Host wiring: `hosts/stargazer/default.nix` imports `home/linux/desktop.nix`
  for the user, sets `modules.nixos.desktop.theme.name` (propagated to the HM
  option), and keeps the NixOS module as now. P7's host does the same with a
  different terminal and the x86_64-only imports.

### 3.2 Cleanups included

- `pkgs.ghostty` leaves `home/profiles/andreym.nix`; ghostty (package and
  config) becomes `home/linux/ghostty.nix`, imported only by hosts whose GPU
  supports it. The aarch64 `/bin/ghostty` + `LIBGL_ALWAYS_SOFTWARE` branch in
  `home/shell/ghostty.nix` is deleted (Arch-era).
- `home/linux/containers.nix` (unused podman units) is deleted.
- `home/dev/neovim.nix` `extraPackages`: `xclip` → `wl-clipboard`.

## 4. Theme pipeline

- `themes/<name>/colors.toml`: Omarchy's 24-key semantic palette (`mode`,
  `accent`, `selection`, `muted`, `background` + dark/darker/lighter,
  `foreground`, eight base colours and their bright variants) copied from
  upstream with attribution. `themes/<name>/backgrounds/` holds the wallpapers.
- Optional per-app fragments in the same directory, picked up by the app
  module when present, otherwise the app keeps its previous setting:
  `vscode.json` (settings merged; the theme extension named there is added to
  the VS Code extension list), `neovim.lua` (colorscheme), `obsidian.css`
  (installed as a vault CSS snippet and selected), `firefox.json`
  (firefox-color values), `icons.theme` (icon theme name). The spec's
  companion table (in the plan) lists which themes ship which fragments.
- `lib/theme.nix`: `name -> { colors; mode; backgrounds; fragments; }` using
  `builtins.fromTOML`; no side effects.
- Options: `modules.nixos.desktop.theme.name` (NixOS) and
  `modules.desktop.theme.name` (HM), the host sets the first and forwards it
  to the second. Extra knobs: `cursorSize`, `wallpaperDir` (defaults to the
  theme's backgrounds).
- Rendering at build time: waybar CSS, mako, hyprlock, swayosd, vicinae theme,
  Hyprland borders/gradients/shadows, GTK (`adw-gtk3` vs `adw-gtk3-dark` from
  `mode`), kvantum, cursor theme, wallpaper symlink. catppuccin/nix modules
  (alacritty, bat, starship, waybar, mako, hyprlock, firefox, vscode, nvim,
  imv, mpv, kvantum, cursors, hyprland) are enabled only when the theme is
  catppuccin, with the flavor derived from the theme; other themes use the
  generic rendering plus fragments.
- Runtime behaviour: wallpaper cycling only (awww IPC, `Super+Ctrl+Space`
  rebound to "next background"). No theme daemon, no runtime writes to
  `~/.config`.

## 5. Session, lock, security

- Login: greetd + tuigreet (`--remember`, no autologin). Hyprland start and the
  `hyprland-session.target` handoff unchanged. All role services are user units
  `PartOf`/`WantedBy` `graphical-session.target`.
- Lock: hyprlock via `ext-session-lock` (compositor keeps the lock if the
  locker dies). PAM: `"hyprlock"` (and `"swaylock"`) added to
  `services.himmelblau.pamServices` so `pam_himmelblau` answers with the Hello
  PIN through the locker's single field; no local password path exists and
  none is added. Tested: lock/unlock, lock → suspend → resume → unlock,
  idle-triggered lock. swaylock stays installed as the fallback locker.
- Idle: hypridle; lock at 10 min, screen off at 20 min (best-effort on
  virtio-gpu), `before_sleep_cmd = loginctl lock-session`. 1Password is not
  locked on screen lock (the SSH-agent re-auth churn that the rocinante patch
  avoided).
- Polkit: `security.polkit.enable`, hyprpolkitagent as the session agent.
- Sudo: unchanged (`wheelNeedsPassword = false`, the himmelblau FIDO
  workaround). Follow-up F1.
- Docker: `virtualisation.docker.rootless = { enable = true; setSocketVariable = true; }`,
  user gets `autoSubUidGidRange`; `lazydocker` installed. Host option
  `modules.nixos.containers.rootful = true` flips to rootful + group. Verified
  against the owner's code-indexer/qdrant/neo4j compose files before the phase
  closes.
- Clipboard history: plaintext on disk (cliphist bbolt / clipse JSON; vicinae
  unverified). Documented; retention capped; cliphist dropped if vicinae's
  history suffices.
- Browser identity (done, to be committed): `home/linux/firefox-entra-sso.nix`
  puts himmelblau's `sso` native host on the Firefox package override
  (home-manager's `programs.firefox.nativeMessagingHosts` is silently dropped
  by its re-wrap) and pins the linux-entra-sso extension via
  `ExtensionSettings` (`force_installed`, exact xpi, `updates_disabled`),
  bumped together with the himmelblau pin. `services.udev.packages =
  [ libfido2 ]` for WebAuthn hidraw access.

## 6. Apps, MIME, web apps

- `apps.nix`: 1Password GUI (`--silent` autostart, SSH agent socket as the
  shell already expects), Obsidian, papers, imv, mpv, qalculate.
- `xdg.mimeApps`: text → nvim (terminal), images → imv, video/audio → mpv, PDF
  → papers, http/https/mailto → Firefox, `x-scheme-handler/claude-cli` →
  Claude Code's handler. `xdg.userDirs.enable` for `~/Pictures` etc.
- `webapps.nix`: helper `mkWebApp { name; url; icon; }` → `xdg.desktopEntries`
  running `chromium --app=<url> --class=<name>` so window rules can target it.
  Chromium installed for this purpose only. Initial list: empty.
- App chords kept from Omarchy 4 only where the app exists: `Super+Return`
  terminal, `Super+Shift+Return` browser, `Super+Shift+N` editor,
  `Super+Shift+O` Obsidian, `Super+Shift+/` 1Password, `Super+Shift+D`
  lazydocker. Other letters stay unbound.
- Terminal: alacritty; `xdg-terminal-exec` with a per-host terminals list so
  "open in terminal" resolves to the host's terminal.

## 7. Verification and rollout

Acceptance (all on stargazer, then re-proven by the drill):
1. Greeter → Hyprland with bar, launcher, notifications, OSD, wallpaper, all
   themed; lock and idle work with the Hello PIN, including after suspend.
2. Omarchy 4 key map works end to end (workspaces, tiling, clipboard,
   screenshots, lock, launcher, app chords).
3. Firefox Entra SSO and YubiKey WebAuthn (done); 1Password GUI + agent;
   Obsidian; VS Code; terminal with the full CLI toolchain.
4. Rootless Docker runs the owner's compose stacks.
5. Theme switch = one line + rebuild, verified with two themes.
6. `aad-tool compliance-check` still passes.
7. Fire drill (README §8, with desktop criteria that need no login: services
   active, theme rendered, PAM stacks present) passes from the pushed flake.

Rollout order (each step its own commit, switched on the VM, VM usable
throughout): theme pipeline → bar + launcher + notifications → lock + idle +
polkit (PAM tested immediately) → wallpaper + capture + clipboard + OSD →
apps + MIME + web apps → Docker → key map switch (last; changes muscle memory
all at once) → cleanups (§3.2) → drill.

CI: `just lint`, `nix flake check`, `build-stargazer`; every role module must
evaluate for `aarch64-linux` and `x86_64-linux`.

## 8. Risks and responses

| Risk | Response |
|------|----------|
| hyprlock PAM: unlock impossible or lockout after resume (himmelblau #1206, #1509 history) | test in step 3 before relying on it; swaylock fallback; LUKS passphrase and SSH path never removed, so the VM is always recoverable |
| vicinae misrenders on virgl | walker+elephant or fuzzel behind the same role |
| `hypr*` libraries drift if a nixpkgs bump moves Hyprland alone | check on every `just update`; all come from one nixpkgs generation |
| waybar `hyprland/workspaces` vs Hyprland 0.56 IPC | verified in step 2; ironbar fallback |
| a compose stack needs rootful Docker | host switch to rootful + group, documented |
| Parallels vmnet wedge recurs | runbook §10; out of this phase |
| Omarchy Lua defaults referenced by the key map call `omarchy-*` helpers | the key map is ours; targets are our role modules' commands, no Omarchy scripts at runtime |

## 9. Out of scope (recorded, not forgotten)

Quattro Quickshell shell (per-role swap later); uwsm (P7); sudo hardening (F1);
Edge, Typora/Omawrite, Spotify, LM Studio, Steam (x86_64, P7); rocinante
changes (P7); runtime theme switching; printing, Bluetooth, Wi-Fi tooling
(physical host, P7); Intune scripts-policy execution (`/etc/cron.d`, open from
P9).

Follow-ups: F1 sudo prompt via PIN/password once himmelblau's sudo behaviour
is configurable; F2 evaluate the Quattro shell per role once it has a release
history; F3 web-app list once the owner misses one.
