# modules/home/dev/opencode.nix -- OpenCode AI coding agent

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.opencode;
in {
  options.modules.dev.opencode = {
    enable = mkEnableOption "OpenCode AI coding agent";
  };

  config = mkIf cfg.enable {
    home.packages = [
      pkgs.opencode
    ];
  };
}
