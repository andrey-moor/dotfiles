# Bazel build system tools

{
  lib,
  pkgs,
  ...
}:

with lib;
{
  config = {
    home.packages = with pkgs; [
      bazelisk # User-friendly Bazel launcher (auto-manages versions)
      bazel-buildtools # buildifier, buildozer, unused_deps
      bazel-watcher # ibazel for watch mode

      # Wrapper so `bazel` invokes bazelisk
      (writeShellScriptBin "bazel" ''exec bazelisk "$@"'')
    ];
  };
}
