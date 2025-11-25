# modules/home/profiles/default.nix -- Profile management system

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.profiles;
in {
  options.modules.profiles = with types; {
    user = mkOption { type = nullOr str; default = null; };
  };

  # User profile is loaded based on modules.profiles.user setting
}
