# home/dev/opencode.nix -- OpenCode AI coding agent
#
# programs.opencode owns ~/.config/opencode (nothing hand-managed lives
# there), but no provider/model settings are declared here -- the repo-level
# opencode.json carries project config, and with `settings` unset the module
# writes no opencode.json (guarded by `mkIf (cfg.settings != { } || ...)`).
#
# Context and skills are wired via xdg.configFile instead of the module's
# `context`/`skills` options: the context path branch requires a literal nix
# path (lib.isPath -- an out-of-store symlink derivation would be written as
# its store-path string), and the skills path branch inspects the source
# directory at build time (breaks in the sandbox when the source is an
# out-of-store symlink into $HOME). Direct symlinks produce the identical
# layout the module would (`opencode/AGENTS.md`, `opencode/skills/<name>`).

{
  lib,
  dotfilesDir,
  config,
  pkgs,
  ...
}:

with lib;
let
  cfg = config.modules.dev.opencode;

  mkAgentsLink = subpath: config.lib.file.mkOutOfStoreSymlink "${dotfilesDir}/agents/${subpath}";

  skillNames = attrNames (
    filterAttrs (_: type: type == "directory") (builtins.readDir ../../agents/skills)
  );
in
{
  config = {
    programs.opencode = {
      enable = true;
      package = pkgs.main.opencode;
    };

    xdg.configFile = mkMerge (
      [
        { "opencode/AGENTS.md".source = mkAgentsLink "AGENTS.md"; }
      ]
      ++ map (name: {
        "opencode/skills/${name}".source = mkAgentsLink "skills/${name}";
      }) skillNames
    );
  };
}
