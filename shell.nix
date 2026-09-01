# Dev shell for working on this repo.
#
# `nix develop` (flake devShells) passes the flake's pkgs; a bare `nix-shell`
# falls back to the pinned tarball below.
{
  pkgs ? import (fetchTarball "https://github.com/NixOS/nixpkgs/tarball/nixos-25.05") {
    config = { };
    overlays = [ ];
  },
}:

pkgs.mkShellNoCC {
  packages = with pkgs; [
    just
    git
  ];
}
