# modules/home/dev/python.nix -- Python development tools

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.python;
in {
  options.modules.dev.python = {
    enable = mkEnableOption "Python development tools";
  };

  config = mkIf cfg.enable {
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
