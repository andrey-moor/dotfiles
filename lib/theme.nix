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
    "accent"
    "selection"
    "muted"
    "background"
    "dark_background"
    "darker_background"
    "lighter_background"
    "foreground"
    "dark_foreground"
    "light_foreground"
    "bright_foreground"
    "red"
    "yellow"
    "orange"
    "green"
    "cyan"
    "blue"
    "magenta"
    "brown"
    "bright_red"
    "bright_yellow"
    "bright_green"
    "bright_cyan"
    "bright_blue"
    "bright_magenta"
  ];
  missing = builtins.filter (k: !(colors ? ${k})) keys;
  backgroundsJson = dir + "/backgrounds.json";
  backgrounds =
    if builtins.pathExists backgroundsJson then
      map (b: pkgs.fetchurl { inherit (b) name url sha256; }) (
        builtins.fromJSON (builtins.readFile backgroundsJson)
      )
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
