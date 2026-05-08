# modules/home/dev/hunk.nix -- hunk: review-first terminal diff viewer

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.hunk;
in {
  options.modules.dev.hunk = {
    enable = mkEnableOption "hunk -- review-first terminal diff viewer";
  };

  config = mkIf cfg.enable {
    home.packages = [
      (pkgs.callPackage ../../../packages/hunk { })
    ];
  };
}
