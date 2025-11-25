# modules/home/shell/default.nix -- Shell configuration base

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.shell;
in {
  options.modules.shell = with types; {
    default = mkOption { type = nullOr str; default = null; };
  };

  # Default shell handling is done in home-manager via programs.<shell>.enable
  # The actual shell switching is handled by the system (Darwin) or manually (Linux)
}
