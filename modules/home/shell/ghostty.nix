# modules/home/shell/ghostty.nix -- Ghostty terminal configuration

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.shell.ghostty;

  # On aarch64-linux VMs with virtio_gpu/virgl, OpenGL is limited to 4.0 but
  # Ghostty requires 4.3. Force software rendering (llvmpipe) which supports 4.6.
  # Also need __EGL_VENDOR_LIBRARY_FILENAMES so Nix's EGL finds system mesa.
  # On x86_64-linux, wrap with nixGL for GPU support.
  # On macOS, use Homebrew.
  wrappedGhostty = pkgs.symlinkJoin {
    name = "ghostty-wrapped";
    paths = [ pkgs.ghostty ];
    buildInputs = [ pkgs.makeWrapper ];
    postBuild = ''
      wrapProgram $out/bin/ghostty \
        --set LIBGL_ALWAYS_SOFTWARE 1 \
        --set __EGL_VENDOR_LIBRARY_FILENAMES /usr/share/glvnd/egl_vendor.d/50_mesa.json
    '';
  };

  ghosttyPkg = if pkgs.stdenv.isDarwin
    then null  # macOS uses Homebrew
    else if pkgs.stdenv.isAarch64
    then lib.hiPrio wrappedGhostty
    else lib.hiPrio (config.lib.nixGL.wrap pkgs.ghostty);  # x86_64: needs nixGL
in {
  options.modules.shell.ghostty = {
    enable = mkEnableOption "Ghostty terminal emulator";
  };

  config = mkIf cfg.enable {
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
