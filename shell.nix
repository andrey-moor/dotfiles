# Dev shell for working on this repo.
#
# `nix develop` (flake devShells) passes the flake's pkgs. direnv loads it
# through `use flake` in .envrc.
{ pkgs }:

pkgs.mkShellNoCC {
  packages = with pkgs; [
    just
    git
  ];
}
