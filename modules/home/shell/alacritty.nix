# modules/home/shell/alacritty.nix -- Alacritty terminal config
#
# Config only: the alacritty binary is installed outside nix (e.g. Omarchy on
# the Linux hosts). Whole-dir out-of-store symlink into the repo.

{ lib, config, ... }:

with lib;
let
  cfg = config.modules.shell.alacritty;
  dotfilesDir = config.modules.dotfilesDir;
in {
  options.modules.shell.alacritty = {
    enable = mkEnableOption "Alacritty terminal configuration";
  };

  config = mkIf cfg.enable {
    xdg.configFile."alacritty".source =
      config.lib.file.mkOutOfStoreSymlink "${dotfilesDir}/config/alacritty";
  };
}
