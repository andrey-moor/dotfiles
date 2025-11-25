# modules/home/shell/bat.nix -- Bat (better cat) configuration

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.shell.bat;
in {
  options.modules.shell.bat = {
    enable = mkEnableOption "Bat syntax highlighting";
  };

  config = mkIf cfg.enable {
    programs.bat = {
      enable = true;
      config = {
        theme = "Catppuccin Mocha";
        style = "numbers,changes,header";
      };
      themes = {
        "Catppuccin Mocha" = {
          src = pkgs.fetchFromGitHub {
            owner = "catppuccin";
            repo = "bat";
            rev = "6810349b28055dce54076712fc05fc68da4b8ec0";
            sha256 = "sha256-lJapSgRVENTrbmpVyn+UQabC9fpV1G1e+CdlJ090uvg=";
          };
          file = "themes/Catppuccin Mocha.tmTheme";
        };
      };
    };
  };
}
