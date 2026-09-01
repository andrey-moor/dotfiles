# home/dev/cc.nix -- C/C++ development tools (home-manager)

{
  lib,
  config,
  pkgs,
  ...
}:

with lib;
{
  config = {
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
      clang-tools # clangd LSP, clang-format, etc.
      bear # Build system integration
    ];
  };
}
