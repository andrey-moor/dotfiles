# modules/home/dev/go.nix -- Go development environment

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.go;
in {
  options.modules.dev.go = {
    enable = mkEnableOption "Go development environment";
  };

  config = mkIf cfg.enable {
    programs.go = {
      enable = true;
      # GOPATH and GOBIN via env attribute
      env = {
        GOPATH = "$HOME/go";
        GOBIN = "$HOME/go/bin";
      };
    };

    home.packages = with pkgs; [
      gopls          # Go language server
      gotools        # goimports, etc.
      go-tools       # staticcheck
      delve          # Go debugger
    ];
  };
}
