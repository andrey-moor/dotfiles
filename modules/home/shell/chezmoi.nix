# modules/home/shell/chezmoi.nix -- Chezmoi dotfile manager

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.shell.chezmoi;
  dotfilesDir = config.modules.dotfilesDir;
  tomlFormat = pkgs.formats.toml { };
in {
  options.modules.shell.chezmoi = {
    enable = mkEnableOption "Chezmoi dotfile manager";
  };

  config = mkIf cfg.enable {
    home.packages = [ pkgs.chezmoi ];

    # Write chezmoi config
    xdg.configFile."chezmoi/chezmoi.toml".source = tomlFormat.generate "chezmoi.toml" {
      sourceDir = "${dotfilesDir}/chezmoi";
    };

    # Export DOTFILES for use in shell configs
    home.sessionVariables = {
      DOTFILES = dotfilesDir;
    };
  };
}
