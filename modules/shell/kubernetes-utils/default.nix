{ config, options, lib, pkgs, ... }:

with lib;
with lib.my;
let cfg = config.modules.shell.kubernetes-utils;
in {
  options.modules.shell.kubernetes-utils = {
    enable = mkBoolOpt false;
  };

  config = mkIf cfg.enable {
    user.packages = with pkgs; [
      minikube
      kubectx
      kubectl
      helm
    ];
  };
}

