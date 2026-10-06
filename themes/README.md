# themes/

Theme data, read by `lib/theme.nix`. A theme is a directory name, so switching
the desktop palette is one word in `hosts/stargazer/default.nix` plus a rebuild.

## Source

The five palettes here are vendored from
[basecamp/omarchy](https://github.com/basecamp/omarchy) at tag `v4.0.4` (MIT).
`colors.toml` is Omarchy's own format, copied byte for byte, so an upstream
theme can be dropped in unchanged.

## Format

`themes/<name>/colors.toml` has 26 keys in total: `mode` plus 25 colours.
`mode` is `"dark"` or `"light"`. The 25 colour keys are:

```
accent selection muted
background dark_background darker_background lighter_background
foreground dark_foreground light_foreground bright_foreground
red yellow orange green cyan blue magenta brown
bright_red bright_yellow bright_green bright_cyan bright_blue bright_magenta
```

`lib/theme.nix` throws when any of the 25 is missing, so a half-written palette
fails at eval rather than at runtime.

`themes/<name>/backgrounds.json` is a list of `{ name, url, sha256 }`. The
wallpapers themselves are never committed. Nix fetches each one by hash at
build time, which keeps the repo small and the images reproducible.

Optional per-app fragments may sit in the same directory and are picked up when
present: `vscode.json`, `neovim.lua`, `obsidian.css`, `firefox.json`,
`icons.theme`. A missing fragment is `null`, which lets an app module keep its
own default.

## Adding a theme

Two files, no code change:

1. `themes/<name>/colors.toml` with the 26 keys above.
2. `themes/<name>/backgrounds.json` with a hash per wallpaper. Get each hash
   with `nix-prefetch-url <url>` and convert it with
   `nix hash convert --hash-algo sha256 --to sri <hex>`. An empty list is fine.

Then set `modules.nixos.desktop.theme.name = "<name>"` on the host and rebuild.
`just test-theme` checks the library against the vendored palettes.
