# P9b: stargazer desktop layer, implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `nixosConfigurations.stargazer` from a minimal Hyprland that proves the platform into the desktop the owner uses every day. One home-manager module per desktop role, a theme that is data, and Omarchy 4's key map.

**Architecture:** The NixOS module `modules/nixos/desktop-hyprland.nix` keeps the compositor, greeter, PipeWire, portals, fonts and the session target, and renders `/etc/xdg/hypr/hyprland.lua` from checked-in Lua files plus a generated `theme.lua`. Every other desktop role is a plain home-manager module under `home/linux/desktop/`, bundled by `home/linux/desktop.nix`. `lib/theme.nix` turns a theme name into colours, mode and wallpapers from `themes/<name>/colors.toml`, Omarchy's palette format. The hypervisor layer `modules/nixos/vmware-guest.nix` is not touched.

**Tech Stack:** NixOS 26.11 (nixpkgs locked 2026-09-10), home-manager (locked 2026-10-05), catppuccin/nix (locked 2026-09-16), Hyprland 0.56.2 with the Lua config manager, waybar 0.15, vicinae 0.29, mako 1.11, hyprlock 0.9.6, hypridle 0.1.8, swayosd 0.3.2, awww 0.12.1, grim, slurp, satty 0.22, hyprpicker, wf-recorder, hyprpolkitagent 0.1.3, adw-gtk3, kvantum, catppuccin-cursors, Papirus.

**Spec:** `docs/superpowers/specs/2026-09-04-p9b-desktop-design.md` (revised 2026-10-06). Research inputs: `docs/superpowers/plans/2026-09-03-p9b-{survey-omarchy-gap,research-omarchy-quattro,vetting-composed-stack}.md`. Hypervisor facts: `docs/vmware-fusion-workarounds.md`.

## Global Constraints

- The repo is public. No tenant id, domain, UPN, device id or AADSTS payload in any committed file. Journal excerpts go to `spikes/intune/notes/`, which is gitignored.
- Every text a person reads follows the `plain-prose` skill: no em-dashes, no semicolons in prose, no sentence over 30 words.
- Conventional commits, one per task, with the trailers `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01KXGT9GVA7PmREkR6KhTkiu`. Commit and push only when the owner says so.
- Role modules are plain modules: no options, no `mkIf`, imports are the enabling. The only options this phase adds are `modules.desktop.theme.*` (home-manager) and `modules.nixos.desktop.theme.*` (NixOS). The spec's §3.1 rules apply verbatim.
- `modules/nixos/vmware-guest.nix` is not modified. The DMA-BUF patch, the clipboard bridge, the ALSA rule and the resize timing stay as they are.
- These P9c facts survive every task: greetd starts after himmelblaud, the `greeting` option exists and the drill banner works, sshd takes keys only with `KbdInteractiveAuthentication = false`, `andreym` has no local password, `login` has `unixAuth = false`, himmelblau debug is off.
- Every task ends with these checks passing: `just lint`, `nix eval --raw .#nixosConfigurations.stargazer.config.system.build.toplevel.drvPath`, the same for `stargazer-drill`, `nix eval --raw .#homeConfigurations.rocinante.activationPackage.drvPath`, and `nix eval --raw .#darwinConfigurations.behemoth.system.drvPath` unchanged from `/nix/store/pqqjhjky972si9yzxvhwm4wi8dchx60d-darwin-system-26.11.4cff07d.drv`.
- Hyprland stays at 0.56.2 for the whole phase. The version guard in `vmware-guest.nix` turns a bump into an evaluation error, which is the intended signal.
- SSH to stargazer always carries `-o BatchMode=yes -o PreferredAuthentications=publickey`, with `SSH_AUTH_SOCK` pointing at the 1Password agent socket and `ssh-add -l` checked first. A fallthrough to keyboard-interactive once produced 38 failed Entra credential checks.
- Never run `id`, `id -nG` or `groups` for `andreym` on the VM. They print Entra group names.
- Switching the VM: push first when the owner has said so, then `sudo nixos-rebuild switch --flake github:andrey-moor/dotfiles#stargazer --refresh`. Task 4 changes PAM. There, activate with `nixos-rebuild test` from the VM's clone first and keep an SSH session open. The owner tests at the console before `switch`. Never activate `stargazer-drill` on the real VM.
- The owner is at the console for anything that needs a login, a PIN or a visual check. Say exactly what to look for.

## Reference for implementers

**Hyprland 0.56.2 Lua API**, from the shipped `share/hypr/hyprland.lua` of the installed package. These exist: `hl.config({...})`, `hl.bind(keys, dispatcher, opts)`, `hl.dsp.*`, `hl.exec_cmd(cmd)`, `hl.on(event, fn)`, `hl.monitor({...})`, `hl.env(name, value)`, `hl.curve(name, {...})`, `hl.animation({...})`, `hl.window_rule({ name = ..., match = {...}, <rule> = ... })`, `hl.layer_rule({...})`, `hl.workspace_rule({...})`, `hl.permission`, `hl.device`, `hl.gesture`. Omarchy v4.0.4's `o.window(match, rules)` targets a newer `hl.window`, which 0.56.2 does not have. Translate every `o.window` into `hl.window_rule` with `match = { class = "..." }`. `hl.bind` options seen in Omarchy's files: `description`, `locked`, `repeating`, `mouse`. Key names: `SUPER`, `SHIFT`, `CTRL`, `ALT`, `RETURN`, `TAB`, `SPACE`, `ESCAPE`, `PRINT`, arrows `LEFT RIGHT UP DOWN`, `code:NN` for keycodes, `mouse:272`, `mouse_down`, lower-case `comma` for the comma key.

**Omarchy v4.0.4 files** (MIT licence, attribution required): `default/hypr/bindings/{tiling,applications,clipboard,media,utilities}.lua`, `default/hypr/{looknfeel,input,windows,envs}.lua`, `default/hypr/helpers.lua` (defines `o.bind`, which wraps `hl.bind` with `hl.dsp.exec_cmd` for string actions), `themes/<name>/colors.toml`. Themes shipped: catppuccin, catppuccin-latte, ethereal, everforest, flexoki-light, gruvbox, hackerman, kanagawa, last-horizon, lumon, lupine, matte-black, miasma, nord, osaka-jade, retro-82, ristretto, rose-pine, solitude, tokyo-night, vantablack, white. The 26 keys: `mode`, `accent`, `selection`, `muted`, `background`, `dark_background`, `darker_background`, `lighter_background`, `foreground`, `dark_foreground`, `light_foreground`, `bright_foreground`, `red yellow orange green cyan blue magenta brown`, `bright_red bright_yellow bright_green bright_cyan bright_blue bright_magenta`. Fetch with `gh api "repos/basecamp/omarchy/contents/<path>?ref=v4.0.4" --jq .content | base64 -d`. GitHub's API rate limit is shared across the session, so fetch each file once and keep it.

**home-manager options present in the pinned input:** `programs.waybar.{enable,package,settings,style,systemd.{enable,enableDebug,enableInspect,targets}}`, `services.mako.{enable,package,settings,extraConfig}`, `programs.hyprlock.{enable,package,settings,extraConfig,sourceFirst,importantPrefixes}`, `services.hypridle.{enable,package,settings,importantPrefixes,systemdTarget}`, `services.swayosd.{enable,package,topMargin,stylePath}`, `services.awww.{enable,package,extraArgs}`, `programs.satty.{enable,package,settings}`, `services.hyprpolkitagent.{enable,package}`, `services.cliphist.{enable,package,clipboardPackage,allowImages,extraOptions,systemdTargets}`, `services.wl-clip-persist.{enable,package,clipboardType,extraOptions,systemdTargets}`, `programs.vicinae.{enable,package,systemd.{enable,autoStart,target},useLayerShell,enableFirefoxIntegration,extensions,themes,settings}` (module path `programs/vicinae/default.nix`), `gtk.{enable,theme,iconTheme,cursorTheme,font,colorScheme,gtk3,gtk4}`, `qt.{enable,platformTheme.name,style.name}` (platform theme names `adwaita`, `qgnomeplatform`, style `kvantum`), `qt.kde.settings`, `xdg.mimeApps.{enable,defaultApplications,associations.added,associations.removed}`, `xdg.userDirs.{enable,createDirectories,pictures,...}`, `xdg.desktopEntries.<name>.{name,exec,icon,comment,categories,terminal,type,settings}`, `xdg.terminal-exec.{enable,package,settings}`, `xdg.portal.{enable,extraPortals,config,configPackages,xdgOpenUsePortal}`.

**catppuccin/nix**: `catppuccin.enable`, `catppuccin.flavor` (latte, frappe, macchiato, mocha), `catppuccin.accent`, and per-module `catppuccin.<module>.enable`. HM modules present: alacritty, bat, cursors, firefox, foot, fuzzel, ghostty, gtk (icons only), hyprland (needs `wayland.windowManager.hyprland.enable`, which this repo does not use, so it is NOT used here), hyprlock, imv, kvantum, mako, mpv, nushell, starship, swaylock, tmux, vicinae, vscode, waybar (`catppuccin.waybar.mode` = `prependImport` or `createLink`). No neovim module. Neovim is themed by AstroNvim's `astrocommunity.colorscheme.catppuccin` in `config/nvim` and is left alone.

**NixOS facts:** `programs.hyprlock.enable` force-enables the system-level `services.hypridle` and sets `security.pam.services.hyprlock = { }`. This plan does NOT use `programs.hyprlock`. It sets the PAM service itself and uses home-manager's `services.hypridle`, so idle has one owner. `virtualisation.docker.rootless.{enable,setSocketVariable,daemon.settings,package,extraPackages}` exist. `xdg.portal.{extraPortals,config,configPackages,xdgOpenUsePortal}` exist. `fonts.fontconfig.defaultFonts.{monospace,sansSerif,serif,emoji}` exist. `programs.hyprland.{enable,xwayland.enable,withUWSM}` exist and `withUWSM` stays off (spec D9).

**Current state to build on:** `modules/nixos/desktop-hyprland.nix` (209 lines) renders a single Lua string with four binds and starts `waybar` and `mako` through `execOnce`. `hosts/stargazer/common.nix` imports `home/core.nix`, `home/dev.nix`, `home/dev/python.nix`, `home/linux/firefox.nix`, `home/linux/firefox-entra-sso.nix`, `home/linux/wayvnc.nix` for the user and sets `modules.linux.wayvnc`. `hosts/stargazer/default.nix` sets `modules.nixos.desktop.monitor = "Virtual-1,preferred,auto,2"`. `hosts/stargazer/drill.nix` imports `default.nix` and overrides the hostname, console auth and the greeting. `home/profiles/andreym.nix` line 19 installs `ghostty` on Linux. `home/shell/ghostty.nix` already picks `pkgs.ghostty` on aarch64. `home/linux/containers.nix` is imported by nothing. `home/dev/neovim.nix` line 32 lists `xclip`.

---

### Task 1: Theme data and the theme library

**Files:**
- Create: `themes/README.md`, `themes/catppuccin/colors.toml`, `themes/catppuccin/backgrounds.json`, `themes/tokyo-night/colors.toml`, `themes/tokyo-night/backgrounds.json`, `themes/gruvbox/colors.toml`, `themes/gruvbox/backgrounds.json`, `themes/nord/colors.toml`, `themes/nord/backgrounds.json`, `themes/rose-pine/colors.toml`, `themes/rose-pine/backgrounds.json`
- Create: `lib/theme.nix`
- Create: `modules/nixos/desktop-theme.nix` (the NixOS option) and `home/linux/theme.nix` (the home-manager option)
- Modify: `hosts/stargazer/common.nix` (import both, set the name, forward it)
- Test: `tests/theme.nix` (a pure `nix eval` test, run by `just lint`'s neighbour `just test-theme` added to the `justfile`)

**Interfaces:**
- Produces: `lib/theme.nix` = `{ pkgs }: name: { inherit name; colors = <attrset of the 25 colour keys>; mode = "dark" | "light"; backgrounds = [ <store paths> ]; fragments = { vscode = <path or null>; neovim = ...; obsidian = ...; firefox = ...; icons = ...; }; }`.
- Produces: NixOS option `modules.nixos.desktop.theme.name` (string, default `"catppuccin"`) and `modules.nixos.desktop.theme.cursorSize` (int, default derived: 24 at scale 1, 32 at scale 2 from the monitor line). The NixOS module forwards both to every user's `modules.desktop.theme.*`.
- Produces: HM options `modules.desktop.theme.{name,cursorSize,wallpaperDir}`, and a read-only `modules.desktop.theme.data` holding the `lib/theme.nix` result, which every role module reads. `catppuccin.enable`, `catppuccin.flavor` and `catppuccin.accent` are set from the name: `catppuccin` → mocha, `catppuccin-latte` → latte, anything else → `catppuccin.enable = false`.

- [ ] **Step 1: Fetch the five palettes from Omarchy v4.0.4 and vendor them**

For each of `catppuccin tokyo-night gruvbox nord rose-pine`:

```bash
mkdir -p themes/$t
gh api "repos/basecamp/omarchy/contents/themes/$t/colors.toml?ref=v4.0.4" --jq .content | base64 -d > themes/$t/colors.toml
gh api "repos/basecamp/omarchy/contents/themes/$t/backgrounds?ref=v4.0.4" --jq '.[] | "\(.name) \(.download_url)"'
```

Write `themes/$t/backgrounds.json` as a list of `{ "name": "...", "url": "...", "sha256": "..." }`, the hash from `nix-prefetch-url <url>` converted with `nix hash convert --hash-algo sha256 --to sri`. Do not vendor the images. Write `themes/README.md`: the format, the source (basecamp/omarchy, MIT, tag v4.0.4), how to add a theme (two files), and that wallpapers are fetched by hash and never committed.

- [ ] **Step 2: Write the failing eval test**

`tests/theme.nix`:

```nix
# Pure checks for lib/theme.nix. Run with `just test-theme`.
{ pkgs ? import <nixpkgs> { } }:
let
  theme = import ../lib/theme.nix { inherit pkgs; };
  cat = theme "catppuccin";
  tn = theme "tokyo-night";
  check = name: cond: if cond then "ok ${name}" else throw "FAIL ${name}";
in
builtins.concatStringsSep "\n" [
  (check "catppuccin accent" (cat.colors.accent == "#89b4fa"))
  (check "catppuccin mode" (cat.mode == "dark"))
  (check "25 colour keys" (builtins.length (builtins.attrNames cat.colors) == 25))
  (check "backgrounds are store paths" (builtins.all (p: pkgs.lib.hasPrefix "/nix/store/" (toString p)) cat.backgrounds))
  (check "tokyo-night differs" (tn.colors.accent != cat.colors.accent))
  (check "unknown theme throws" ((builtins.tryEval (theme "no-such-theme")).success == false))
]
```

Add to `justfile`:

```make
# Pure theme-library checks (no build)
test-theme:
    nix eval --raw --impure --expr 'import ./tests/theme.nix { pkgs = import <nixpkgs> {}; }'
```

- [ ] **Step 3: Run it to see it fail**

Run: `just test-theme`
Expected: error, `lib/theme.nix` does not exist.

- [ ] **Step 4: Write `lib/theme.nix`**

```nix
# lib/theme.nix -- theme name -> { name, colors, mode, backgrounds, fragments }
#
# Pure. Reads themes/<name>/colors.toml (Omarchy's palette, see
# themes/README.md) and themes/<name>/backgrounds.json (wallpapers fetched by
# hash, never committed). Fragments are optional per-app files in the same
# directory, null when absent, so an app module can fall back to its default.
{ pkgs }:
name:
let
  dir = ../themes + "/${name}";
  colorsFile = dir + "/colors.toml";
  exists = builtins.pathExists colorsFile;
  raw = builtins.fromTOML (builtins.readFile colorsFile);
  colors = builtins.removeAttrs raw [ "mode" ];
  keys = [
    "accent" "selection" "muted"
    "background" "dark_background" "darker_background" "lighter_background"
    "foreground" "dark_foreground" "light_foreground" "bright_foreground"
    "red" "yellow" "orange" "green" "cyan" "blue" "magenta" "brown"
    "bright_red" "bright_yellow" "bright_green" "bright_cyan" "bright_blue" "bright_magenta"
  ];
  missing = builtins.filter (k: !(colors ? ${k})) keys;
  backgroundsJson = dir + "/backgrounds.json";
  backgrounds =
    if builtins.pathExists backgroundsJson then
      map (b: pkgs.fetchurl { inherit (b) url sha256; name = b.name; }) (builtins.fromJSON (builtins.readFile backgroundsJson))
    else
      [ ];
  fragment = file: if builtins.pathExists (dir + "/${file}") then dir + "/${file}" else null;
in
if !exists then
  throw "lib/theme.nix: no theme named ${name} (themes/${name}/colors.toml is missing)"
else if missing != [ ] then
  throw "lib/theme.nix: themes/${name}/colors.toml lacks ${builtins.concatStringsSep ", " missing}"
else
  {
    inherit name colors backgrounds;
    mode = raw.mode or "dark";
    fragments = {
      vscode = fragment "vscode.json";
      neovim = fragment "neovim.lua";
      obsidian = fragment "obsidian.css";
      firefox = fragment "firefox.json";
      icons = fragment "icons.theme";
    };
  }
```

The `keys` list has 25 entries, which is what Omarchy ships after `mode`. Record in `themes/README.md` that the file has 26 keys in total: `mode` plus 25 colours.

- [ ] **Step 5: Run the test to see it pass**

Run: `just test-theme`
Expected: six `ok` lines.

- [ ] **Step 6: Write the two option modules**

`modules/nixos/desktop-theme.nix`:

```nix
# modules/nixos/desktop-theme.nix -- the host picks a theme by name
#
# The name travels to every home-manager user as modules.desktop.theme.name,
# so the compositor (rendered by desktop-hyprland.nix) and the user's role
# modules read one palette. lib/theme.nix does the lookup.
{ lib, config, pkgs, ... }:
with lib;
let
  cfg = config.modules.nixos.desktop.theme;
  scale = toInt (elemAt (splitString "," config.modules.nixos.desktop.monitor) 3);
in
{
  options.modules.nixos.desktop.theme = {
    name = mkOption {
      type = types.str;
      default = "catppuccin";
      description = "Directory name under themes/. Switching is this one word and a rebuild.";
    };
    cursorSize = mkOption {
      type = types.int;
      default = if scale >= 2 then 32 else 24;
      description = "Cursor size in pixels. Follows the monitor scale because Fusion hands the guest Retina pixels.";
    };
  };
  config = {
    home-manager.sharedModules = [
      { modules.desktop.theme = { inherit (cfg) name cursorSize; }; }
    ];
  };
}
```

`home/linux/theme.nix`:

```nix
# home/linux/theme.nix -- home-manager side of the theme
#
# Role modules read modules.desktop.theme.data. catppuccin/nix modules are
# enabled only for the two catppuccin themes, with the flavor from the name.
{ lib, config, pkgs, ... }:
with lib;
let
  cfg = config.modules.desktop.theme;
  theme = import ../../lib/theme.nix { inherit pkgs; };
  isCatppuccin = hasPrefix "catppuccin" cfg.name;
in
{
  options.modules.desktop.theme = {
    name = mkOption { type = types.str; default = "catppuccin"; description = "Theme directory under themes/."; };
    cursorSize = mkOption { type = types.int; default = 24; description = "Cursor size in pixels."; };
    wallpaperDir = mkOption {
      type = types.nullOr types.path;
      default = null;
      description = "Directory of wallpapers to cycle. Null means the theme's own backgrounds.";
    };
    data = mkOption {
      type = types.attrs;
      readOnly = true;
      default = theme cfg.name;
      description = "The lib/theme.nix result for the chosen name.";
    };
  };
  config = {
    catppuccin.enable = isCatppuccin;
    catppuccin.flavor = if cfg.name == "catppuccin-latte" then "latte" else "mocha";
    catppuccin.accent = "blue";
    home.pointerCursor = {
      gtk.enable = true;
      size = cfg.cursorSize;
      package = pkgs.catppuccin-cursors.mochaDark;
      name = "catppuccin-mocha-dark-cursors";
    };
  };
}
```

`pkgs.catppuccin-cursors.mochaDark` and the name must be checked against the pinned package: `nix eval --raw .#nixosConfigurations.stargazer.pkgs.catppuccin-cursors.mochaDark.name`. If the attribute differs, use what exists and record it in the report.

- [ ] **Step 7: Wire the host**

In `hosts/stargazer/common.nix`, add `../../modules/nixos/desktop-theme.nix` to `imports` and `../../home/linux/theme.nix` to `home-manager.users.andreym.imports`. In `hosts/stargazer/default.nix` add after the monitor line:

```nix
  # One word picks the palette for the compositor and every role module.
  modules.nixos.desktop.theme.name = "catppuccin";
```

- [ ] **Step 8: Verify**

```bash
just fmt && just lint && just test-theme
nix eval --json .#nixosConfigurations.stargazer.config.home-manager.users.andreym.modules.desktop.theme.data.colors.accent   # "#89b4fa"
nix eval --json .#nixosConfigurations.stargazer.config.home-manager.users.andreym.modules.desktop.theme.cursorSize           # 32
nix eval --json .#nixosConfigurations.stargazer.config.home-manager.users.andreym.catppuccin.flavor                          # "mocha"
nix eval --raw .#nixosConfigurations.stargazer-drill.config.system.build.toplevel.drvPath
nix eval --raw .#homeConfigurations.rocinante.activationPackage.drvPath
nix eval --raw .#darwinConfigurations.behemoth.system.drvPath   # unchanged
```

- [ ] **Step 9: Commit**

```bash
git add themes lib/theme.nix tests/theme.nix justfile modules/nixos/desktop-theme.nix home/linux/theme.nix hosts/stargazer
git commit -m 'feat(desktop): theme as data, five Omarchy palettes and lib/theme.nix'
```

---

### Task 2: Hyprland Lua split and the generated theme.lua

**Files:**
- Create: `modules/nixos/hypr/bindings.lua`, `modules/nixos/hypr/input.lua`, `modules/nixos/hypr/looknfeel.lua`, `modules/nixos/hypr/windows.lua`, `modules/nixos/hypr/envs.lua`
- Modify: `modules/nixos/desktop-hyprland.nix`
- Test: `nix build .#nixosConfigurations.stargazer.config.environment.etc."xdg/hypr/hyprland.lua".source` and `luac -p` on the result, then a live `hyprctl reload` check on the VM.

**Interfaces:**
- Consumes: `config.modules.nixos.desktop.theme.name` (Task 1) through `lib/theme.nix`.
- Produces: `/etc/xdg/hypr/hyprland.lua` = generated header (monitor, cursor, exec-once, `theme` table) + the five checked-in files concatenated in the order `envs, input, looknfeel, windows, bindings`. A Lua global table `theme` with fields `colors.<key>` (strings like `"#89b4fa"`), `mode`, `cursor_size`, `terminal`, `launcher`, `scale`, so the Lua files never hard-code a colour or a program. A helper `rgba(hex, alpha)` returning Hyprland's `"rgba(RRGGBBAA)"` form.
- Produces: `modules.nixos.desktop.launcher` option (string, default `"fuzzel"`) so the binding target can change in Task 3 without editing Lua.

- [ ] **Step 1: Write the four non-binding Lua files from Omarchy v4.0.4, adapted to 0.56.2**

`envs.lua`: the `hl.env` lines for `XCURSOR_SIZE` and `HYPRCURSOR_SIZE` from `theme.cursor_size`, `GDK_BACKEND`, `QT_QPA_PLATFORM`, `QT_QPA_PLATFORMTHEME = "gtk3"`, `MOZ_ENABLE_WAYLAND`, `ELECTRON_OZONE_PLATFORM_HINT`, `OZONE_PLATFORM`, `XDG_SESSION_TYPE`, `XDG_CURRENT_DESKTOP`, `XDG_SESSION_DESKTOP`, and `hl.config({ xwayland = { force_zero_scaling = true }, ecosystem = { no_update_news = true } })`. Drop `OMARCHY_PATH`, the PATH surgery, `XCOMPOSEFILE` and the nvidia require.

`input.lua`: `hl.config({ input = { kb_layout = "us", kb_options = "compose:caps,shift:both_capslock_cancel", follow_mouse = 1, sensitivity = 0, repeat_rate = 40, repeat_delay = 250, numlock_by_default = true, touchpad = { natural_scroll = false, clickfinger_behavior = true, scroll_factor = 0.4 } }, misc = { key_press_enables_dpms = true, mouse_move_enables_dpms = true } })`. Drop the vconsole reader and the non-Latin layout logic. Translate the two `o.window` scroll rules to `hl.window_rule({ name = "terminal-scroll", match = { class = "(Alacritty|kitty|foot)" }, scroll_touchpad = 1.5 })` and the ghostty one with `0.2`.

`looknfeel.lua`: Omarchy's file with the two colour locals replaced by `theme`:

```lua
local active_border = { colors = { rgba(theme.colors.accent, "ee"), rgba(theme.colors.bright_cyan, "ee") }, angle = 45 }
local inactive_border = rgba(theme.colors.muted, "aa")
```

Keep gaps 5/10, border 2, rounding 0, shadow and blur off, the dwindle, scrolling, master, misc, cursor and binds blocks, all five `hl.curve` lines and all 17 `hl.animation` lines verbatim. The groupbar `text_color` values become `rgba(theme.colors.foreground, "ff")` and `rgba(theme.colors.foreground, "90")`.

`windows.lua`: translate each `o.window` to `hl.window_rule`. `suppress_event = "maximize"` for class `.*`, the default-opacity tag, the XWayland drag fix with `match = { class = "^$", title = "^$", xwayland = true, float = true, fullscreen = false, pin = false }` and `no_focus = true`, and the final `opacity = "0.985 0.96"` rule for `match = { tag = "default-opacity" }`. Drop `require("default.hypr.apps")`.

`bindings.lua`: for this task only the four existing binds, written with `theme.terminal` and `theme.launcher`:

```lua
hl.bind("SUPER + RETURN", hl.dsp.exec_cmd(theme.terminal), { description = "Terminal" })
hl.bind("SUPER + D", hl.dsp.exec_cmd(theme.launcher), { description = "Launcher" })
hl.bind("SUPER + Q", hl.dsp.window.close(), { description = "Close window" })
hl.bind("SUPER + SHIFT + E", hl.dsp.exit(), { description = "Exit Hyprland" })
```

Task 8 replaces this file with Omarchy's map.

- [ ] **Step 2: Rewrite the renderer in `desktop-hyprland.nix`**

Replace `luaConfig` with a header plus `builtins.readFile` of the five files in order. The header:

```nix
  themeData = (import ../../lib/theme.nix { inherit pkgs; }) config.modules.nixos.desktop.theme.name;
  luaTable = attrs: "{ " + concatStringsSep ", " (mapAttrsToList (k: v: "${k} = ${luaStr v}") attrs) + " }";
  luaHeader = ''
    -- Generated by modules/nixos/desktop-hyprland.nix from themes/${themeData.name}.
    -- Copy to ~/.config/hypr/hyprland.lua to take it over.
    theme = {
        name = ${luaStr themeData.name},
        mode = ${luaStr themeData.mode},
        cursor_size = ${toString config.modules.nixos.desktop.theme.cursorSize},
        scale = ${luaStr (elemAt monitorFields 3)},
        terminal = ${luaStr cfg.terminal},
        launcher = ${luaStr cfg.launcher},
        colors = ${luaTable themeData.colors},
    }
    function rgba(hex, alpha) return "rgba(" .. hex:sub(2) .. alpha .. ")" end

    hl.monitor({ output = ${luaStr (elemAt monitorFields 0)}, mode = ${luaStr (elemAt monitorFields 1)}, position = ${luaStr (elemAt monitorFields 2)}, scale = ${luaStr (elemAt monitorFields 3)} })
    hl.config({ cursor = { no_hardware_cursors = true } })
    hl.on("hyprland.start", function()
    ${concatMapStringsSep "\n" (c: "    hl.exec_cmd(${luaStr c})") execOnce}
    end)
  '';
  luaConfig = luaHeader + concatMapStringsSep "\n" (f: "\n-- ${f}\n" + builtins.readFile ./hypr/${f}) [ "envs.lua" "input.lua" "looknfeel.lua" "windows.lua" "bindings.lua" ];
```

Add the option `launcher = mkOption { type = types.str; default = "fuzzel"; description = "Command the launcher keybind runs."; }`. Import `./desktop-theme.nix` from this module so the theme option always exists where the compositor is. Keep `execOnce` with the dbus line, `waybar` and `mako` for now (Task 3 removes them). Delete `confConfig` and the `configFormat` option: the revert path to hyprlang is gone in 0.57 and the Lua config has been in production since September. Record the deletion in the commit body. Keep the module's comment block, trimmed to what still applies.

- [ ] **Step 3: Syntax-check the rendered file without a compositor**

```bash
f=$(nix build --no-link --print-out-paths .#nixosConfigurations.stargazer.config.environment.etc."xdg/hypr/hyprland.lua".source)
nix run nixpkgs#lua5_4 -- -e "local f=assert(loadfile('$f')) print('parses')" 2>&1 | tail -1
```

Hyprland's Lua is 5.4-compatible for parsing. Globals like `hl` are undefined at parse time, so only `loadfile` is run, never the chunk. Expected: `parses`.

- [ ] **Step 4: Live check on the VM**

Push when the owner says so, then on the VM: `sudo nixos-rebuild switch --flake github:andrey-moor/dotfiles#stargazer --refresh`, then `hyprctl reload` and `hyprctl getoption general:border_size` (expect 2) and `hyprctl getoption general:gaps_out` (expect 10). The owner confirms at the console: borders show the accent gradient, the four binds work, and the display size came back within 2 seconds of the reload (the follower).

- [ ] **Step 5: Verify and commit**

Run the Global Constraints checks. Commit: `refactor(desktop): hyprland config from checked-in lua files and a generated theme table`.

---

### Task 3: Desktop bundle, bar, notifications, launcher, and the ghostty trial

**Files:**
- Create: `home/linux/desktop.nix`, `home/linux/desktop/bar.nix`, `home/linux/desktop/notifications.nix`, `home/linux/desktop/launcher.nix`
- Modify: `modules/nixos/desktop-hyprland.nix` (drop waybar, mako, fuzzel packages and the two exec-once lines, set `launcher` default to `"vicinae toggle"`), `hosts/stargazer/common.nix` (import `home/linux/desktop.nix`), `hosts/stargazer/default.nix` (terminal decision after the trial)

**Interfaces:**
- Consumes: `config.modules.desktop.theme.data` from Task 1.
- Produces: user services `waybar.service`, `mako.service`, `vicinae.service`, all `PartOf`/`WantedBy` `graphical-session.target` through home-manager's defaults. The launcher command is `vicinae toggle`. fuzzel stays installed as the fallback, bound to nothing.

- [ ] **Step 1: `home/linux/desktop.nix`**

```nix
# home/linux/desktop.nix -- the desktop roles, one module each (spec section 3.1)
{ imports = [ ./desktop/bar.nix ./desktop/notifications.nix ./desktop/launcher.nix ]; }
```

Later tasks append to this list.

- [ ] **Step 2: `bar.nix`**

```nix
# home/linux/desktop/bar.nix -- waybar
#
# Workspaces, window title, clock, tray, pulseaudio, network, cpu, memory. No
# battery or backlight on a VM. Colours come from the theme as CSS variables,
# so a theme switch needs no CSS edit. For the catppuccin themes catppuccin/nix
# prepends its palette import as well, which defines the same names.
{ config, lib, pkgs, ... }:
let
  t = config.modules.desktop.theme.data;
  css = lib.concatStringsSep "\n" (lib.mapAttrsToList (k: v: "@define-color ${k} ${v};") t.colors);
in
{
  programs.waybar = {
    enable = true;
    systemd.enable = true;
    settings.main = {
      layer = "top"; position = "top"; height = 32; spacing = 8;
      modules-left = [ "hyprland/workspaces" "hyprland/window" ];
      modules-center = [ "clock" ];
      modules-right = [ "tray" "pulseaudio" "network" "cpu" "memory" ];
      "hyprland/workspaces" = { format = "{id}"; on-click = "activate"; persistent-workspaces."*" = 5; };
      "hyprland/window" = { max-length = 60; separate-outputs = true; };
      clock = { format = "{:%a %d %b  %H:%M}"; tooltip-format = "{calendar}"; };
      pulseaudio = { format = "{icon} {volume}%"; format-muted = "󰝟"; format-icons.default = [ "󰕿" "󰖀" "󰕾" ]; on-click = "pwvucontrol"; };
      network = { format-ethernet = "󰈀 {ipaddr}"; format-disconnected = "󰌙"; tooltip-format = "{ifname} {ipaddr}/{cidr}"; };
      cpu.format = "󰍛 {usage}%";
      memory.format = "󰘚 {percentage}%";
      tray.spacing = 8;
    };
    style = ''
      ${css}
      * { font-family: "JetBrainsMono Nerd Font"; font-size: 13px; min-height: 0; }
      window#waybar { background: alpha(@background, 0.92); color: @foreground; border-bottom: 2px solid @accent; }
      #workspaces button { padding: 0 8px; color: @muted; }
      #workspaces button.active { color: @accent; border-bottom: 2px solid @accent; }
      #clock, #pulseaudio, #network, #cpu, #memory, #tray, #window { padding: 0 10px; }
    '';
  };
  catppuccin.waybar.mode = "createLink";
  home.packages = [ pkgs.pwvucontrol ];
}
```

`catppuccin.waybar.mode = "createLink"` keeps catppuccin's CSS out of the way: our `@define-color` lines define every name the bar uses, and the link is simply unused. Check `pkgs.pwvucontrol` exists for aarch64 with `nix eval --raw .#nixosConfigurations.stargazer.pkgs.pwvucontrol.version`. If not, use `pavucontrol`.

- [ ] **Step 3: `notifications.nix`**

```nix
# home/linux/desktop/notifications.nix -- mako
{ config, ... }:
let t = config.modules.desktop.theme.data; in
{
  services.mako = {
    enable = true;
    settings = {
      default-timeout = 5000;
      anchor = "top-right";
      font = "JetBrainsMono Nerd Font 11";
      background-color = t.colors.background;
      text-color = t.colors.foreground;
      border-color = t.colors.accent;
      border-size = 2;
      border-radius = 0;
      "urgency=high" = { border-color = t.colors.red; default-timeout = 0; };
    };
  };
}
```

With `catppuccin.mako.enable` defaulting on for catppuccin themes, catppuccin/nix sets the same keys. Set `catppuccin.mako.enable = false;` in this module so the theme pipeline is the single source, and say so in a comment.

- [ ] **Step 4: `launcher.nix`**

```nix
# home/linux/desktop/launcher.nix -- vicinae, with fuzzel kept as the fallback
#
# vicinae brings clipboard history, emoji and a calculator, so no separate
# clipboard manager is needed unless its history proves insufficient (spec
# section 2). It is Qt6 and the first Qt6 client on vmwgfx behind the DMA-BUF
# patch, so this module is the one to check first when a login shows a blank
# launcher. fuzzel stays installed and unbound as the zero-dependency fallback.
{ config, pkgs, ... }:
let t = config.modules.desktop.theme.data; in
{
  programs.vicinae = {
    enable = true;
    systemd.enable = true;
    useLayerShell = true;
    settings = {
      font.size = 11;
      theme.name = if config.catppuccin.enable then "catppuccin-${config.catppuccin.flavor}" else "vicinae-dark";
      window.rounding = 0;
    };
  };
  home.packages = [ pkgs.fuzzel ];
}
```

Check the vicinae `settings` schema against `programs/vicinae/default.nix` in the pinned home-manager and the `themes` option: if catppuccin/nix's `catppuccin.vicinae` module provides the theme, prefer it and drop `theme.name`. Record which path was taken.

- [ ] **Step 5: Remove the NixOS-side duplicates**

In `desktop-hyprland.nix`: remove `waybar`, `mako`, `fuzzel` from `environment.systemPackages`, remove `"waybar"` and `"mako"` from `execOnce`, set the `launcher` default to `"vicinae toggle"`. Keep `alacritty`, `wl-clipboard`, `mesa-demos`.

- [ ] **Step 6: The ghostty trial (spec D7)**

ghostty is already installed on aarch64 by `home/shell/ghostty.nix`. On the VM after the switch, the owner runs `ghostty` from the launcher and reports: text renders, resize works, no GL error in `journalctl --user -t ghostty`. If clean, set `modules.nixos.desktop.terminal = "ghostty"` in `hosts/stargazer/default.nix` with a comment dated to the trial. If not, leave alacritty and record the failure in `docs/vmware-fusion-workarounds.md` as a new row.

- [ ] **Step 7: Verify, switch, commit**

Global Constraints checks. After the switch on the VM: `systemctl --user is-active waybar mako vicinae` all `active`, `hyprctl clients -j | jq -r '.[].class'` shows nothing unexpected, owner confirms bar, notification (`notify-send test`) and launcher at the console. Commit: `feat(desktop): bar, notifications and launcher as role modules`.

---

### Task 4: Lock, idle, polkit, and the PAM stacks

**Files:**
- Create: `home/linux/desktop/lock.nix`, `home/linux/desktop/idle.nix`, `home/linux/desktop/polkit.nix`
- Modify: `modules/nixos/himmelblau.nix` (pamServices and unixAuth for the lockers), `modules/nixos/desktop-hyprland.nix` (`security.polkit.enable`, PAM services for hyprlock and swaylock), `home/linux/desktop.nix`

**Interfaces:**
- Consumes: theme data.
- Produces: `hyprlock` as the locker, `swaylock` installed as the fallback, `hypridle.service` (home-manager's), `hyprpolkitagent.service`. PAM services `hyprlock` and `swaylock` exist, carry `pam_himmelblau` and no `pam_unix` auth line.

- [ ] **Step 1: PAM in the NixOS modules**

In `desktop-hyprland.nix`:

```nix
    security.polkit.enable = true;
    # Lockers get their own PAM services. programs.hyprlock would do this too,
    # but it also force-enables the system hypridle unit, and idle has one
    # owner here, home-manager's services.hypridle.
    security.pam.services.hyprlock = { };
    security.pam.services.swaylock = { };
```

In `modules/nixos/himmelblau.nix`, next to the existing `security.pam.services.login.unixAuth = false;`:

```nix
    # The lockers answer with the Hello PIN through pam_himmelblau, like login.
    # With no local password a pam_unix prompt there could never succeed, so
    # it goes too, and a wrong PIN re-prompts instead of showing a dead field.
    services.himmelblau.pamServices = [ "hyprlock" "swaylock" ];
    security.pam.services.hyprlock.unixAuth = false;
    security.pam.services.swaylock.unixAuth = false;
```

Check how upstream's module merges `pamServices`: if it replaces the default list `[ "passwd" "login" "systemd-user" ]` rather than appending, write the full list. Verify by evaluation: `nix eval --raw .#nixosConfigurations.stargazer.config.security.pam.services.hyprlock.text | grep -E '^auth'` shows the himmelblau line and no `pam_unix`, and the same for `login` is unchanged.

- [ ] **Step 2: `lock.nix`**

```nix
# home/linux/desktop/lock.nix -- hyprlock, swaylock as the fallback
#
# ext-session-lock: the compositor keeps the screen locked if the locker dies.
# PAM: modules/nixos/himmelblau.nix gives hyprlock and swaylock the Hello PIN
# path and nothing else. The single input field takes the PIN.
{ config, pkgs, ... }:
let t = config.modules.desktop.theme.data; in
{
  programs.hyprlock = {
    enable = true;
    settings = {
      general = { hide_cursor = true; ignore_empty_input = true; };
      background = [ { path = "screenshot"; blur_passes = 2; color = t.colors.background; } ];
      input-field = [ {
        size = "320, 48"; outline_thickness = 2; rounding = 0;
        outer_color = t.colors.accent; inner_color = t.colors.background; font_color = t.colors.foreground;
        placeholder_text = "<i>Hello PIN</i>"; fail_text = "<i>Wrong PIN</i>";
        position = "0, -40"; halign = "center"; valign = "center";
      } ];
      label = [ {
        text = "$TIME"; color = t.colors.foreground; font_size = 48; font_family = "JetBrainsMono Nerd Font";
        position = "0, 120"; halign = "center"; valign = "center";
      } ];
    };
  };
  catppuccin.hyprlock.enable = false;
  home.packages = [ pkgs.swaylock ];
}
```

- [ ] **Step 3: `idle.nix`**

```nix
# home/linux/desktop/idle.nix -- hypridle
#
# Lock at 10 min, screen off at 20 min (DPMS is best effort on vmwgfx), lock
# before sleep. 1Password is not locked on screen lock, on purpose: that
# caused SSH-agent re-auth churn on the previous machine.
{ config, pkgs, lib, ... }:
{
  services.hypridle = {
    enable = true;
    settings = {
      general = {
        lock_cmd = "pidof hyprlock || ${lib.getExe config.programs.hyprlock.package}";
        before_sleep_cmd = "loginctl lock-session";
        after_sleep_cmd = "hyprctl dispatch dpms on";
      };
      listener = [
        { timeout = 600; on-timeout = "loginctl lock-session"; }
        { timeout = 1200; on-timeout = "hyprctl dispatch dpms off"; on-resume = "hyprctl dispatch dpms on"; }
      ];
    };
  };
}
```

- [ ] **Step 4: `polkit.nix`**

```nix
# home/linux/desktop/polkit.nix -- hyprpolkitagent, the session's auth agent
{ ... }: { services.hyprpolkitagent.enable = true; }
```

- [ ] **Step 5: Test on the VM with `nixos-rebuild test` first, owner at the console**

From the VM's clone with the task's changes applied and `git add`ed: `sudo nixos-rebuild test --flake ~/dotfiles#stargazer`. Keep an SSH session open. Then the owner, at the console, in this order and reporting each result:

1. `Super+Ctrl+L` is not bound yet. Run `loginctl lock-session` from a terminal. hyprlock appears with the PIN field.
2. Type a wrong PIN. It must show `Wrong PIN` and re-prompt. No `Password:` field anywhere.
3. Type the Hello PIN. The session unlocks.
4. `systemctl suspend` from a terminal, then resume from Fusion. The lock screen must be there and the PIN must unlock it. Suspend of a Fusion guest may be unsupported. If `systemctl suspend` returns an error, record that in `docs/vmware-fusion-workarounds.md` and test the lock-before-sleep path by `loginctl lock-session` only.
5. Leave the machine idle 10 minutes, or set the timeout to 30 seconds for the test and back. It locks by itself.
6. `pkexec true` from a terminal shows the hyprpolkitagent dialog, and the Hello PIN satisfies it. If `pkexec` asks for a password instead, polkit's own PAM service needs the same treatment: add `"polkit-1"` to `pamServices` and `security.pam.services.polkit-1.unixAuth = false`, re-test.

Over SSH during the test: `journalctl -b -u himmelblaud --since -10min | grep -ciE 'unix_user_online_auth_step|offline_auth_step'` grows with each unlock, and `grep -c AADSTS` stays at 0.

Only after all six pass: push with the owner's go and `switch`.

- [ ] **Step 6: Verify and commit**

Global Constraints checks. Commit: `feat(desktop): hyprlock, hypridle and hyprpolkitagent, lockers unlock with the Hello PIN`.

---

### Task 5: Wallpaper, capture, clipboard and OSD

**Files:**
- Create: `home/linux/desktop/wallpaper.nix`, `home/linux/desktop/capture.nix`, `home/linux/desktop/clipboard.nix`, `home/linux/desktop/osd.nix`, `home/linux/desktop/scripts/capture-region.sh`, `home/linux/desktop/scripts/wallpaper-next.sh`
- Modify: `home/linux/desktop.nix`

**Interfaces:**
- Produces: commands the key map (Task 8) calls: `desktop-capture-region`, `desktop-capture-screen`, `desktop-capture-record`, `desktop-wallpaper-next`, `swayosd-client --output-volume raise|lower|mute-toggle`, `vicinae toggle` and vicinae's clipboard view.

- [ ] **Step 1: `wallpaper.nix`**

```nix
# home/linux/desktop/wallpaper.nix -- awww (swww's maintained successor)
#
# The wallpaper set is the theme's backgrounds, fetched by hash (lib/theme.nix).
# `desktop-wallpaper-next` cycles through them at runtime over awww's IPC. No
# theme daemon and no writes to ~/.config: the current index lives in
# $XDG_RUNTIME_DIR and resets at login.
{ config, pkgs, lib, ... }:
let
  cfg = config.modules.desktop.theme;
  dir = if cfg.wallpaperDir != null then cfg.wallpaperDir else pkgs.linkFarm "wallpapers-${cfg.data.name}" (map (p: { name = baseNameOf p; path = p; }) cfg.data.backgrounds);
  next = pkgs.writeShellApplication {
    name = "desktop-wallpaper-next";
    runtimeInputs = [ pkgs.awww pkgs.coreutils pkgs.findutils ];
    text = builtins.replaceStrings [ "@DIR@" ] [ "${dir}" ] (builtins.readFile ./scripts/wallpaper-next.sh);
  };
in
{
  services.awww.enable = true;
  home.packages = [ next ];
  systemd.user.services.desktop-wallpaper = {
    Unit = { Description = "Set the theme's first wallpaper"; After = [ "awww.service" ]; PartOf = [ "graphical-session.target" ]; };
    Service = { Type = "oneshot"; ExecStart = "${lib.getExe next} --first"; };
    Install.WantedBy = [ "graphical-session.target" ];
  };
}
```

`scripts/wallpaper-next.sh`:

```bash
# Cycle the wallpapers in @DIR@ over awww's IPC. --first sets the first one.
set -euo pipefail
state="${XDG_RUNTIME_DIR:-/tmp}/desktop-wallpaper.idx"
mapfile -t files < <(find @DIR@ -maxdepth 1 -type f,l | sort)
[ "${#files[@]}" -gt 0 ] || exit 0
idx=0
if [ "${1:-}" != "--first" ] && [ -f "$state" ]; then idx=$(( ($(cat "$state") + 1) % ${#files[@]} )); fi
echo "$idx" > "$state"
for _ in 1 2 3 4 5 6 7 8 9 10; do awww query >/dev/null 2>&1 && break; sleep 0.5; done
awww img --transition-type fade --transition-duration 1 "${files[$idx]}"
```

Check the awww daemon's unit name in `services/awww.nix` and the exact `awww img` flags in `awww --help` on the VM. Adjust if they differ.

- [ ] **Step 2: `capture.nix` and `scripts/capture-region.sh`**

```nix
# home/linux/desktop/capture.nix -- screenshots, colour picker, screen recording
#
# grim + slurp select, satty annotates and copies, hyprpicker picks a colour,
# wf-recorder records with CPU encoding because vmwgfx has no video encoder.
{ config, pkgs, ... }:
let
  t = config.modules.desktop.theme.data;
  tool = name: text: pkgs.writeShellApplication { inherit name text; runtimeInputs = with pkgs; [ grim slurp satty wl-clipboard wf-recorder libnotify coreutils procps ]; };
in
{
  programs.satty = {
    enable = true;
    settings.general = { fullscreen = true; early-exit = true; copy-command = "wl-copy"; save-after-copy = true; output-filename = "~/Pictures/Screenshots/%Y-%m-%d_%H-%M-%S.png"; };
  };
  home.packages = [
    pkgs.hyprpicker
    (tool "desktop-capture-region" (builtins.readFile ./scripts/capture-region.sh))
    (tool "desktop-capture-screen" ''grim - | satty --filename -'')
    (tool "desktop-capture-record" ''
      if pkill -INT -x wf-recorder; then notify-send "Recording saved" "~/Videos"; exit 0; fi
      mkdir -p ~/Videos; region="$(slurp)" || exit 0
      notify-send "Recording" "Alt+Print stops it"
      exec wf-recorder -g "$region" -f ~/Videos/"$(date +%Y-%m-%d_%H-%M-%S)".mp4
    '')
  ];
  xdg.userDirs = { enable = true; createDirectories = true; };
}
```

`scripts/capture-region.sh`:

```bash
# Select a region or a window, then annotate in satty.
set -euo pipefail
region="$(slurp -d)" || exit 0
grim -g "$region" - | satty --filename -
```

- [ ] **Step 3: `clipboard.nix`**

```nix
# home/linux/desktop/clipboard.nix -- clipboard history
#
# vicinae keeps the history (spec section 2). cliphist is not installed unless
# that proves insufficient; this module exists so the role has a home. The
# Fusion bridge (modules/nixos/vmware-guest.nix) also watches the clipboard and
# skips CLIPBOARD_STATE=sensitive, which is the rule any history tool here must
# keep.
{ pkgs, ... }: { home.packages = [ pkgs.wl-clipboard ]; }
```

- [ ] **Step 4: `osd.nix`**

```nix
# home/linux/desktop/osd.nix -- swayosd, client only
#
# No libinput backend: it needs a privileged unit, and a VM has no backlight or
# caps-lock LED worth showing. Volume and mute come from the key map calling
# swayosd-client.
{ config, pkgs, ... }:
let t = config.modules.desktop.theme.data; in
{
  services.swayosd = {
    enable = true;
    topMargin = 0.9;
    stylePath = pkgs.writeText "swayosd.css" ''
      window { background: alpha(${t.colors.background}, 0.9); border: 2px solid ${t.colors.accent}; border-radius: 0; }
      label, image { color: ${t.colors.foreground}; }
      progressbar progress { background: ${t.colors.accent}; }
    '';
  };
}
```

`stylePath` expects a path. Confirm the option type in the pinned `services/swayosd.nix` and adapt.

- [ ] **Step 5: Verify, switch, commit**

Global Constraints checks. On the VM after the switch: `systemctl --user is-active awww desktop-wallpaper swayosd` (unit names from the modules), `desktop-wallpaper-next` changes the wallpaper, `desktop-capture-region` produces a file under `~/Pictures/Screenshots`, `swayosd-client --output-volume raise` shows the OSD and audio still plays cleanly (acceptance 8). Owner confirms by eye. Commit: `feat(desktop): wallpaper, capture, clipboard and OSD roles`.

---

### Task 6: Apps, MIME, web apps, fonts, GTK and Qt

**Files:**
- Create: `home/linux/desktop/apps.nix`, `home/linux/desktop/webapps.nix`, `home/linux/desktop/look.nix`
- Modify: `modules/nixos/desktop-hyprland.nix` (fonts and portals), `home/linux/desktop.nix`

**Interfaces:**
- Produces: `mkWebApp` as a function in `webapps.nix` (`{ name, url, icon }` → `xdg.desktopEntries` entry running `chromium --app=<url> --class=<name>`), an empty initial list. MIME defaults. `xdg-terminal-exec` resolving to the host's terminal.

- [ ] **Step 1: `apps.nix`**

```nix
# home/linux/desktop/apps.nix -- the GUI set and MIME defaults (spec D6, section 6)
{ config, pkgs, ... }:
{
  home.packages = with pkgs; [ _1password-gui obsidian papers imv mpv qalculate-gtk ];
  programs.imv.enable = true;
  programs.mpv.enable = true;
  xdg.mimeApps = {
    enable = true;
    defaultApplications = {
      "text/plain" = "nvim.desktop";
      "image/png" = "imv.desktop"; "image/jpeg" = "imv.desktop"; "image/webp" = "imv.desktop";
      "video/mp4" = "mpv.desktop"; "video/x-matroska" = "mpv.desktop"; "audio/mpeg" = "mpv.desktop";
      "application/pdf" = "org.gnome.Papers.desktop";
      "x-scheme-handler/http" = "firefox.desktop"; "x-scheme-handler/https" = "firefox.desktop"; "x-scheme-handler/mailto" = "firefox.desktop";
    };
  };
  xdg.terminal-exec = {
    enable = true;
    settings.default = [ "${config.modules.desktop.terminalDesktopEntry}" ];
  };
  systemd.user.services."1password" = {
    Unit = { Description = "1Password, silent start"; PartOf = [ "graphical-session.target" ]; After = [ "graphical-session.target" ]; };
    Service = { ExecStart = "${pkgs._1password-gui}/bin/1password --silent"; Restart = "on-failure"; };
    Install.WantedBy = [ "graphical-session.target" ];
  };
}
```

Verify the desktop-entry ids (`nvim.desktop`, `imv.desktop`, `mpv.desktop`, `org.gnome.Papers.desktop`, `firefox.desktop`) by listing `share/applications` of each built package. Add `terminalDesktopEntry` as a small option in `home/linux/theme.nix` (default `"Alacritty.desktop"`, the host sets `"com.mitchellh.ghostty.desktop"` if Task 3 chose ghostty). `x-scheme-handler/claude-cli` is added only after checking which package ships its handler desktop file. If none does, leave it out and note it.

- [ ] **Step 2: `webapps.nix`**

```nix
# home/linux/desktop/webapps.nix -- web apps as desktop entries (spec section 6)
#
# chromium is installed for `--app=` only. The list starts empty and grows when
# the owner misses one. `--class` lets window rules target the app.
{ pkgs, lib, ... }:
let
  mkWebApp = { name, url, icon }: {
    inherit name icon;
    exec = "${pkgs.chromium}/bin/chromium --app=${url} --class=${name}";
    terminal = false;
    type = "Application";
    categories = [ "Network" ];
  };
  webApps = { };
in
{
  home.packages = [ pkgs.chromium ];
  xdg.desktopEntries = lib.mapAttrs (_: mkWebApp) webApps;
}
```

- [ ] **Step 3: `look.nix` (GTK, Qt, icons, cursor)**

```nix
# home/linux/desktop/look.nix -- GTK and Qt look, icons, cursor
{ config, pkgs, ... }:
let dark = config.modules.desktop.theme.data.mode == "dark"; in
{
  gtk = {
    enable = true;
    theme = { name = if dark then "adw-gtk3-dark" else "adw-gtk3"; package = pkgs.adw-gtk3; };
    iconTheme = { name = if dark then "Papirus-Dark" else "Papirus"; package = pkgs.papirus-icon-theme; };
    colorScheme = if dark then "dark" else "light";
  };
  qt = { enable = true; platformTheme.name = "adwaita"; style.name = "kvantum"; };
  catppuccin.kvantum.enable = config.catppuccin.enable;
}
```

Check `gtk.colorScheme` exists in the pinned home-manager (the options list shows it) and that `qt.style.name = "kvantum"` with `catppuccin.kvantum` evaluates without an assertion.

- [ ] **Step 4: Fonts and portals in the NixOS module**

```nix
    fonts.packages = with pkgs; [ nerd-fonts.jetbrains-mono noto-fonts noto-fonts-cjk-sans noto-fonts-color-emoji font-awesome ];
    fonts.fontconfig.defaultFonts = {
      monospace = [ "JetBrainsMono Nerd Font" ];
      sansSerif = [ "Noto Sans" ];
      serif = [ "Noto Serif" ];
      emoji = [ "Noto Color Emoji" ];
    };
    xdg.portal = {
      enable = true;
      extraPortals = [ pkgs.xdg-desktop-portal-gtk ];
      config.hyprland.default = [ "hyprland" "gtk" ];
    };
```

`programs.hyprland.enable` already adds `xdg-desktop-portal-hyprland`. Verify no duplicate portal package by evaluating `xdg.portal.extraPortals`.

- [ ] **Step 5: Verify, switch, commit**

On the VM: `xdg-mime query default application/pdf` → `org.gnome.Papers.desktop`, `xdg-terminal-exec` opens the host's terminal, `gsettings get org.gnome.desktop.interface gtk-theme` → `adw-gtk3-dark`, `fc-match monospace` → JetBrainsMono Nerd Font, 1Password starts silently and its SSH agent socket works for `ssh -T git@github.com` from the VM. Commit: `feat(desktop): apps, MIME defaults, web app helper, fonts and GTK/Qt look`.

---

### Task 7: Rootless Docker

**Files:**
- Create: `modules/nixos/containers.nix`
- Modify: `hosts/stargazer/common.nix` (import), `home/linux/desktop/apps.nix` (lazydocker)

**Interfaces:**
- Produces: `modules.nixos.containers.rootful` (bool, default false). Rootless Docker by default with `DOCKER_HOST` set, `lazydocker` installed.

- [ ] **Step 1: The module**

```nix
# modules/nixos/containers.nix -- Docker, rootless unless a host flips it
#
# The docker group is root-equivalent, so rootless is the default (spec D5).
# A compose stack that needs the rootful daemon sets rootful = true.
{ lib, config, ... }:
with lib;
let cfg = config.modules.nixos.containers; in
{
  options.modules.nixos.containers.rootful = mkOption {
    type = types.bool; default = false;
    description = "Run the rootful daemon and put andreym in the docker group instead of rootless Docker.";
  };
  config = {
    virtualisation.docker.rootless = mkIf (!cfg.rootful) { enable = true; setSocketVariable = true; };
    virtualisation.docker.enable = cfg.rootful;
    users.users.andreym.extraGroups = mkIf cfg.rootful [ "docker" ];
    users.users.andreym.autoSubUidGidRange = true;
  };
}
```

- [ ] **Step 2: Test on the VM**

After the switch: `docker info --format '{{.SecurityOptions}}'` contains `rootless`, `docker run --rm hello-world` prints the greeting, then the owner's compose stacks from the spec (code-indexer, qdrant, neo4j) with `docker compose up -d` in each project directory, cloned onto the VM for the test. Any stack that fails under rootless gets its failure recorded and the host flips `rootful = true` as the spec allows, with the reason in the commit body.

- [ ] **Step 3: Verify and commit**

Commit: `feat(stargazer): rootless docker with a per-host rootful switch`.

---

### Task 8: The Omarchy 4 key map

**Files:**
- Modify: `modules/nixos/hypr/bindings.lua` (replace the four binds)
- Modify: `modules/nixos/desktop-hyprland.nix` only if a new helper is needed

**Interfaces:**
- Consumes: every command Tasks 3 to 7 produced.

- [ ] **Step 1: Translate Omarchy v4.0.4's bindings, verbatim where the target exists**

Write `bindings.lua` as `hl.bind(keys, dispatcher, { description = ... })` lines in the same order as Omarchy's files. Rules:

- Tiling (`tiling.lua`): everything that is a pure `hl.dsp.*` dispatcher is kept verbatim, including the `for workspace = 1, 10` loop, groups, resize with `code:20`/`code:21`, mouse binds with `{ mouse = true }`, `ALT + TAB` cycling. Omarchy helper scripts (`omarchy-hyprland-window-close-all`, `-pop`, `-width`, `-workspace-layout-toggle`, `-monitor-scaling`) have no target here: `SUPER + O` pop becomes `hl.dsp.window.float({ action = "toggle" })` followed by `hl.dsp.window.pin()` if the API allows a sequence, otherwise it is dropped. The others are dropped and listed in the file header as not bound.
- Applications: `SUPER + RETURN` → `theme.terminal`, `SUPER + SHIFT + RETURN` and `SUPER + SHIFT + B` → `firefox`, `SUPER + SHIFT + N` → `theme.terminal .. " -e nvim"`, `SUPER + SHIFT + O` → `obsidian`, `SUPER + SHIFT + SLASH` → `1password`, `SUPER + SHIFT + D` → `theme.terminal .. " -e lazydocker"`. Spotify, Signal, Omawrite, HEY, the Google web apps and X are not bound.
- Clipboard: the three `send_shortcut_once`/`universal_clipboard_shortcut` functions from `clipboard.lua` are copied verbatim, since they use only `hl.dispatch`, `hl.dsp.send_key_state`, `hl.timer` and `hl.get_active_window`. Verify each of those exists in 0.56.2 by grepping `src/config/lua/bindings/*.cpp` of the pinned Hyprland source (`nix build .#nixosConfigurations.stargazer.pkgs.hyprland.src`). If `hl.get_active_window` or `hl.timer` is missing, bind `SUPER + C/X/V` to plain `send_key_state` without the terminal special case and say so. `SUPER + CTRL + V` → `vicinae toggle` with the clipboard view, the exact subcommand from `vicinae --help`.
- Media: `XF86AudioRaiseVolume/LowerVolume/Mute` → `swayosd-client --output-volume raise/lower/mute-toggle`, `XF86AudioMicMute` → `swayosd-client --input-volume mute-toggle`, play/pause/next/prev → `playerctl` (add `pkgs.playerctl` to `osd.nix`). Brightness, keyboard backlight and touchpad binds are dropped.
- Utilities: `SUPER + SPACE` → `vicinae toggle`, `SUPER + CTRL + E` → vicinae's emoji view, `SUPER + ESCAPE` → a `wlogout`-free system menu is out of scope, so bind `hl.dsp.exit()` behind `SUPER + SHIFT + E` as today, `SUPER + K` → `theme.terminal .. " -e sh -c 'hyprctl binds | less'"`, `SUPER + CTRL + Q` → `qalculate-gtk`, `SUPER + SHIFT + SPACE` → `pkill -SIGUSR1 waybar` (waybar's toggle), `SUPER + CTRL + SPACE` → `desktop-wallpaper-next`, `SUPER + comma` → `makoctl dismiss`, `SUPER + SHIFT + comma` → `makoctl dismiss -a`, `SUPER + CTRL + comma` → `makoctl mode -t do-not-disturb` (add the mode to mako's settings), `PRINT` → `desktop-capture-region`, `SUPER + PRINT` → `pkill hyprpicker || hyprpicker -a`, `ALT + PRINT` → `desktop-capture-record`, `SUPER + CTRL + L` → `loginctl lock-session`, `SUPER + CTRL + Z` and `SUPER + CTRL + ALT + Z` zoom verbatim (they use `hl.get_config` and `hl.config`, check `hl.get_config` exists). The selection-layer binds block is kept verbatim if `hl.on("layer.opened")` exists in 0.56.2, otherwise dropped. Everything that calls `omarchy-menu`, `omarchy-shell` or a panel is not bound.
- The file header lists every Omarchy bind that is not bound and why, so the next person does not hunt for it.

- [ ] **Step 2: Parse check and live check**

The `luac`-style parse from Task 2 Step 3. On the VM after the switch, the owner walks the map: workspaces 1 to 5, move a window, float, fullscreen, group, resize, the clipboard trio in a terminal and in Firefox, Print, Super+Print, Alt+Print start and stop, Super+Space, Super+Ctrl+V, Super+Ctrl+L, Super+Ctrl+Space, volume keys with the OSD. `hyprctl binds | wc -l` is the count to put in the report.

- [ ] **Step 3: Commit**

Commit: `feat(desktop): omarchy 4 key map in lua, where the component exists`.

---

### Task 9: Cleanups from spec section 3.2

**Files:**
- Modify: `home/profiles/andreym.nix` (remove the `ghostty` line and the `optionals` block if it becomes empty), `home/shell/ghostty.nix` (keep, it already does the right thing per platform, but move its import from `home/core.nix` to `home/linux.nix` and `hosts/behemoth` as the spec says, or record a ruling to leave it), `home/dev/neovim.nix` (`xclip` → `wl-clipboard` on Linux, keep `xclip` out of macOS too since `pbcopy` is used there), `home/core.nix`
- Delete: `home/linux/containers.nix`

- [ ] **Step 1: Apply, with one ruling**

`home/shell/ghostty.nix` is imported by `home/core.nix` for every host and already selects the right package per platform. The spec wants it host-specific. Ruling to take: keep it in `core.nix`, because behemoth uses it with the Homebrew cask and the aarch64 branch is now correct for Fusion, and delete only the dead `ghostty` line in `andreym.nix`. Record the ruling in the ledger and the commit body. `home/linux/containers.nix` is imported by nothing: delete it. `xclip` → `wl-clipboard` in `neovim.nix`, Linux only, with a comment that macOS uses `pbcopy`.

- [ ] **Step 2: Verify**

Global Constraints checks, plus `nix eval --raw .#darwinConfigurations.behemoth.system.drvPath` may now differ because `andreym.nix` changed. Build behemoth (`just build`) and confirm it still has ghostty's config. The owner runs `just switch` on behemoth when convenient.

- [ ] **Step 3: Commit**

Commit: `chore(home): drop the dead ghostty line, unused containers.nix, and xclip on Wayland`.

---

### Task 10: Theme switch proof, acceptance, drill, and documents

**Files:**
- Modify: `hosts/stargazer/README.md` (a §5 note on the desktop roles and the two commands users need), `docs/superpowers/specs/2026-09-04-p9b-desktop-design.md` (status line), `docs/vmware-fusion-workarounds.md` (rows found during the phase), `CLAUDE.md` (module list and the theme option table), project memory

- [ ] **Step 1: Theme switch**

Set `modules.nixos.desktop.theme.name = "tokyo-night"` on the VM's clone, `sudo nixos-rebuild test`, `hyprctl reload`. Owner confirms borders, bar, mako and lock screen all changed colour and the wallpaper changed. Then back to `catppuccin` with `switch`. Record the time a theme switch takes.

- [ ] **Step 2: Acceptance list (spec section 7)**

Run every item and record the result in the ledger:

- greeter to themed desktop
- the key map
- Firefox SSO and WebAuthn, with the YubiKey connected from the Fusion menu first
- 1Password GUI and agent
- Obsidian
- VS Code
- terminal with the toolchain
- Docker compose stacks
- theme switch with two themes
- `aad-tool compliance-check` from the graphical session after a full power cycle and a PIN login, with no manual reauth
- audio clean and clipboard to the Mac both ways

- [ ] **Step 3: Fire drill as `#stargazer-drill`**

README §8 as written, with the real VM suspended first. New criteria provable over SSH: `systemctl --user list-unit-files | grep -E 'waybar|mako|vicinae|hypridle|hyprpolkitagent|awww|swayosd'` all enabled, `/etc/xdg/hypr/hyprland.lua` mentions the theme name, `/etc/pam.d/hyprlock` has the himmelblau line and no `pam_unix` auth line, `systemctl show greetd -p After` lists `himmelblaud.service`, and the greeter banner is in greetd's config. Record the drill's duration in §8.

- [ ] **Step 4: Documents and memory**

README §5 gains a short paragraph: the desktop roles live in `home/linux/desktop/`, `Super+K` shows the binds, `modules.nixos.desktop.theme.name` picks the theme. `CLAUDE.md`'s module table gains `modules.nixos.desktop.theme` and `modules.desktop.theme` and `modules.nixos.containers`. The spec's status line becomes "implemented 2026-xx-xx". Project memory records the phase, the rulings, and anything that bit.

- [ ] **Step 5: Commit**

Commit: `docs: stargazer desktop layer complete`. Push with the owner's go.

---

## Self-review notes

Spec coverage: §2 decisions D1 to D10 map to Tasks 2, 3 (D7 trial), 4 (D9 session), 6 (D4 browser, D6 apps), 7 (D5 Docker), 8 (D8 key map). §3.1 layout is Tasks 1 to 6. §3.2 cleanups are Task 9. §4 theme pipeline is Tasks 1 and 2, with the catppuccin modules gated in `home/linux/theme.nix`. §5 is Task 4. §6 is Task 6. §7 acceptance and rollout order are Task 10 and the task order. §8 risks: vicinae on vmwgfx (Task 3 Step 4 comment and the fuzzel fallback), ghostty (Task 3 Step 6), the ALSA rule (Task 5 Step 5 check), the DMA-BUF guard (Global Constraints), hyprlock PAM (Task 4 Step 5), waybar IPC (Task 3 Step 7), compose under rootless (Task 7 Step 2).

Type consistency: `modules.desktop.theme.data.colors.<key>` is a string in every consumer. `theme.terminal` and `theme.launcher` in Lua come from `cfg.terminal` and `cfg.launcher`. `modules.desktop.terminalDesktopEntry` is introduced in Task 6 and must be added to `home/linux/theme.nix` there, not assumed earlier.

Known gaps the executor must settle, each already marked in its task: the `catppuccin-cursors` attribute name, vicinae's settings schema, `swayosd` `stylePath` type, awww's unit name and flags, the desktop-entry ids, whether `pamServices` appends or replaces, whether suspend works on a Fusion guest, and which 0.56.2 Lua functions the clipboard helpers need.
