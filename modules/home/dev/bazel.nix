# Bazel build system tools

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.bazel;
in {
  options.modules.dev.bazel = {
    enable = mkEnableOption "Bazel build system tools";
  };

  config = mkIf cfg.enable {
    home.packages = with pkgs; [
      bazelisk          # User-friendly Bazel launcher (auto-manages versions)
      bazel-buildtools  # buildifier, buildozer, unused_deps
      bazel-watcher     # ibazel for watch mode

      # Wrapper so `bazel` invokes bazelisk
      (writeShellScriptBin "bazel" ''exec bazelisk "$@"'')
    ];
  };
}
