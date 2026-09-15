# home/shell/ghostty.nix -- Ghostty terminal configuration

{
  lib,
  config,
  pkgs,
  ...
}:

with lib;
let
  # macOS: Homebrew cask. x86_64-linux (rocinante, not NixOS): nixGL for the
  # host GPU. aarch64-linux (NixOS VMs): the Nix build as-is; it needs OpenGL
  # 4.3 from the guest GPU, which VMware Fusion provides (SVGA3D) and Parallels
  # does not (virgl caps at 4.0 there, so that host uses Alacritty).
  ghosttyPkg =
    if pkgs.stdenv.isDarwin then
      null
    else if pkgs.stdenv.isAarch64 then
      pkgs.ghostty
    else
      lib.hiPrio (config.lib.nixGL.wrap pkgs.ghostty);
in
{
  config = {
    # Ensure ghostty terminfo is found by tmux/ncurses (e.g. when SSH-ing in)
    home.sessionVariables.TERMINFO_DIRS = "$HOME/.nix-profile/share/terminfo:/usr/share/terminfo";

    # On macOS, ghostty is installed via Homebrew cask
    # On Linux, wrap with nixGL for GPU acceleration
    programs.ghostty = {
      enable = true;
      package = ghosttyPkg;
      enableBashIntegration = false;
      enableZshIntegration = false;
      enableFishIntegration = false;
      settings = {
        command = "${pkgs.nushell}/bin/nu";
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
        keybind = [
          "global:ctrl+grave_accent=toggle_quick_terminal"
          "super+c=copy_to_clipboard"
          "super+v=paste_from_clipboard"
          "super+shift+c=copy_to_clipboard"
          "super+shift+v=paste_from_clipboard"
          "super+k=clear_screen"
          "super+t=new_tab"
          "super+shift+left_bracket=previous_tab"
          "super+shift+right_bracket=next_tab"
          "super+d=new_split:right"
          "super+shift+d=new_split:down"
          "super+right_bracket=goto_split:next"
          "super+left_bracket=goto_split:previous"
          "shift+enter=text:\\n"
        ];
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
