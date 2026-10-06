# Pure checks for lib/theme.nix. Run with `just test-theme`.
{ pkgs }:
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
  (check "backgrounds are store paths" (
    builtins.all (p: pkgs.lib.hasPrefix "/nix/store/" (toString p)) cat.backgrounds
  ))
  (check "tokyo-night differs" (tn.colors.accent != cat.colors.accent))
  (check "unknown theme throws" ((builtins.tryEval (theme "no-such-theme")).success == false))
]
