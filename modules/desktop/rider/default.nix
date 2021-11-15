{ config, options, lib, pkgs, ... }:

with lib;
with lib.my;
let cfg = config.modules.desktop.rider;
in {
  options.modules.desktop.rider = {
    enable = mkBoolOpt false;
  };

  config = mkIf cfg.enable {

    user.packages = with pkgs; [
      dotnet-sdk
      jetbrains.rider
    ];
  };
}
