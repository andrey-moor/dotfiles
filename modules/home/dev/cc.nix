# modules/home/dev/cc.nix -- C/C++ development tools (home-manager)

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.cc;
in {
  options.modules.dev.cc = {
    enable = mkEnableOption "C/C++ development tools";
  };

  config = mkIf cfg.enable {
    home.packages = with pkgs; [
      # Compilers and build tools
      gcc
      clang
      cmake
      gnumake
      ninja
      meson

      # Debugging and profiling
      gdb

      # Package managers
      pkg-config

      # Language servers and tools
      clang-tools  # clangd LSP, clang-format, etc.
      bear         # Build system integration
    ];
  };
}
