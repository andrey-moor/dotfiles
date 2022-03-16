# modules/themes/alucard/default.nix --- a regal dracula-inspired theme

{ options, config, lib, pkgs, ... }:

with lib;
with lib.my;
let cfg = config.modules.theme;
in {
  config = mkIf (cfg.active == "nord") (mkMerge [
    # Desktop-agnostic configuration
    {
      modules = {
        theme = {
          wallpaper = mkDefault ./config/wallpaper.png;
        };
      };
    }

    # Desktop (X11) theming
    (mkIf config.services.xserver.enable {
      fonts = {
        fonts = with pkgs; [
          fira-code
          fira-code-symbols
          jetbrains-mono
          siji
          font-awesome-ttf
          source-code-pro
          source-sans-pro
          source-serif-pro
        ];
        fontconfig.defaultFonts = {
          #sansSerif = ["Fira Sans"];
          #monospace = ["Fira Code"];
          monospace = [ "Source Code Pro" ];
          sansSerif = [ "Source Sans Pro" ];
          serif     = [ "Source Serif Pro" ];
        };
      };

      # Other dotfiles
      home.configFile = with config.modules; mkMerge [
        {
          # Sourced from sessionCommands in modules/themes/default.nix
          "xtheme/90-theme".source = ./config/Xresources;
        }
      ];
    })
  ]);
}
