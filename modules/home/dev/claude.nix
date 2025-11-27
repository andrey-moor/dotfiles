# modules/home/dev/claude.nix -- Claude Code CLI

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.claude;
in {
  options.modules.dev.claude = {
    enable = mkEnableOption "Claude Code CLI";
  };

  config = mkIf cfg.enable {
    home.packages = [
      pkgs.main.claude-code  # Latest from nixpkgs main branch
    ];
  };
}
