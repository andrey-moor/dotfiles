# home/dev/python.nix -- Python development tools

{ lib, config, pkgs, ... }:

with lib;
{
  config = {
    home.packages = with pkgs; [
      (python3.withPackages (ps: with ps; [
        pip
        pytest
        pyyaml
      ]))
      uv  # Python package manager and runner (uvx)
    ];
  };
}
