# home/dev/hunk.nix -- hunk: review-first terminal diff viewer

{
  pkgs,
  ...
}:

{
  home.packages = [
    (pkgs.callPackage ../../packages/hunk { })
  ];
}
