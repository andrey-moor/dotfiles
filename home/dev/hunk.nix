# home/dev/hunk.nix -- hunk: review-first terminal diff viewer

{
  lib,
  pkgs,
  ...
}:

with lib;
{
  config = {
    home.packages = [
      (pkgs.callPackage ../../packages/hunk { })
    ];
  };
}
