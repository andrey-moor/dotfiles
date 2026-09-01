# home/shell/alacritty.nix -- Alacritty terminal config
#
# Config only: the alacritty binary is installed outside nix (e.g. Omarchy on
# the Linux hosts). Whole-dir out-of-store symlink into the repo.

{ lib, dotfilesDir, config, ... }:

with lib;
{
  config = {
    xdg.configFile."alacritty".source =
      config.lib.file.mkOutOfStoreSymlink "${dotfilesDir}/config/alacritty";
  };
}
