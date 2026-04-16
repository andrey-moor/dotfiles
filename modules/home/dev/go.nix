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
        GOPATH = "${config.home.homeDirectory}/go";
        GOBIN = "${config.home.homeDirectory}/go/bin";
      };
    };

    home.packages = with pkgs; [
      gopls                 # Go language server
      (lib.hiPrio gotools)  # goimports, etc. — hiPrio resolves modernize collision with gopls 0.21+
      go-tools              # staticcheck
      delve                 # Go debugger
    ];
  };
}
