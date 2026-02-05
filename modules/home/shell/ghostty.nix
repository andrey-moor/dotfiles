# modules/home/shell/ghostty.nix -- Ghostty terminal configuration

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.shell.ghostty;

  # On aarch64-linux VMs with virtio_gpu/virgl, OpenGL 4.3+ is required but
  # virtio only provides OpenGL 4.0. The Nix-built ghostty has EGL issues with
  # software rendering, so we use the system ghostty (/bin/ghostty) which works
  # with Mesa's LLVMpipe (LIBGL_ALWAYS_SOFTWARE=1).
  # See: https://github.com/ghostty-org/ghostty/issues/2025
  # On x86_64-linux, wrap with nixGL for GPU support.
  # On macOS, use Homebrew.
  #
  # Creates a wrapper that calls /bin/ghostty (system package) with software rendering.
  # Includes share/ from nix ghostty for bat syntax, dbus services, etc.
  # Requires ghostty to be installed via system package manager (e.g., pacman on Arch).
  systemGhosttyWrapper = pkgs.symlinkJoin {
    name = "ghostty-system-wrapper";
    paths = [
      (pkgs.writeShellScriptBin "ghostty" ''
        export LIBGL_ALWAYS_SOFTWARE=1
        exec /bin/ghostty "$@"
      '')
      # Include share/ from nix ghostty for bat syntax, terminfo, etc.
      pkgs.ghostty
    ];
    meta.mainProgram = "ghostty";
    postBuild = ''
      # Remove the nix ghostty binary, keep only our wrapper
      rm -f $out/bin/.ghostty-wrapped
      # Remove desktop files - we provide our own via xdg.desktopEntries
      rm -rf $out/share/applications
      rm -rf $out/share/dbus-1
    '';
  };

  ghosttyPkg = if pkgs.stdenv.isDarwin
    then null  # macOS uses Homebrew
    else if pkgs.stdenv.isAarch64
    then lib.hiPrio systemGhosttyWrapper  # Use system ghostty with software rendering
    else lib.hiPrio (config.lib.nixGL.wrap pkgs.ghostty);  # x86_64: needs nixGL
in {
  options.modules.shell.ghostty = {
    enable = mkEnableOption "Ghostty terminal emulator";
  };

  config = mkIf cfg.enable {
    # On aarch64-linux, override the desktop file to use our wrapper with software rendering
    # This fixes the Omarchy wrapper bug (escaped $is_apple_silicon variable)
    # Uses home.file to place in ~/.local/share/applications/ which has higher XDG priority
    home.file = mkIf (pkgs.stdenv.isLinux && pkgs.stdenv.isAarch64) {
      ".local/share/applications/com.mitchellh.ghostty.desktop" = {
        force = true;  # Override existing file
        text = ''
          [Desktop Entry]
          Version=1.0
          Name=Ghostty
          Type=Application
          Comment=A terminal emulator
          TryExec=${systemGhosttyWrapper}/bin/ghostty
          Exec=${systemGhosttyWrapper}/bin/ghostty %U
          Icon=com.mitchellh.ghostty
          Categories=System;TerminalEmulator;
          Keywords=terminal;tty;pty;
          StartupNotify=true
          StartupWMClass=com.mitchellh.ghostty
          Terminal=false
          X-TerminalArgExec=-e
          X-TerminalArgDir=--working-directory=
        '';
      };
    };

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
