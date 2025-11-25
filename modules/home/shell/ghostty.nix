# modules/home/shell/ghostty.nix -- Ghostty terminal configuration

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.shell.ghostty;
in {
  options.modules.shell.ghostty = {
    enable = mkEnableOption "Ghostty terminal emulator";
  };

  config = mkIf cfg.enable {
    # On macOS, ghostty is installed via Homebrew cask
    # This module only provides config, the package comes from brew
    programs.ghostty = {
      enable = true;
      # Don't install package on Darwin - brew handles it
      package = if pkgs.stdenv.isDarwin then null else pkgs.ghostty;
      enableBashIntegration = false;
      enableZshIntegration = false;
      enableFishIntegration = false;
      settings = {
        theme = "catppuccin-mocha";
        font-family = "JetBrainsMono Nerd Font";
        font-size = 14;
        cursor-style = "block";
        cursor-style-blink = false;
        mouse-hide-while-typing = true;
        copy-on-select = true;
        confirm-close-surface = false;
        window-padding-x = 4;
        window-padding-y = 4;
      };
      themes = {
        catppuccin-mocha = {
          palette = [
            "0=#45475a"
            "1=#f38ba8"
            "2=#a6e3a1"
            "3=#f9e2af"
            "4=#89b4fa"
            "5=#f5c2e7"
            "6=#94e2d5"
            "7=#a6adc8"
            "8=#585b70"
            "9=#f38ba8"
            "10=#a6e3a1"
            "11=#f9e2af"
            "12=#89b4fa"
            "13=#f5c2e7"
            "14=#94e2d5"
            "15=#bac2de"
          ];
          background = "1e1e2e";
          foreground = "cdd6f4";
          cursor-color = "f5e0dc";
          cursor-text = "11111b";
          selection-background = "353749";
          selection-foreground = "cdd6f4";
        };
      };
    };
  };
}
