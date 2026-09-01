# home/dev/codex.nix -- OpenAI Codex CLI
#
# Provider config (~/.codex/config.toml: Azure work endpoint + the trust list
# codex appends at runtime) is hand-managed and stays out of nix and out of
# this public repo. Verified against the pinned HM codex module source
# (modules/programs/codex/default.nix): the config.toml home.file entry is
# guarded by `lib.mkIf (mergedSettings != { })`, and with settings, plugins,
# and marketplaces unset and enableMcpIntegration off (its default),
# mergedSettings == { } -- so enabling programs.codex never writes or takes
# ownership of ~/.codex/config.toml.
#
# programs.codex.context is NOT used for AGENTS.md: the module's
# mkTextOrPathEntry only treats literal nix paths as file sources
# (lib.isPath); an out-of-store symlink derivation would fall into the text
# branch and be written out as its store-path string. The symlink is declared
# via home.file instead -- same target location, stays out-of-store (spec §4:
# edits in the repo are live immediately).
#
# Skills: ~/.agents/skills is fanned out by modules/home/dev/claude.nix.
# Codex binary strings suggest it reads the vendor-neutral ~/.agents dir, but
# skill discovery there is not conclusively verified -- confirm live in
# Task 7. $CODEX_HOME/skills is left app-owned.

{
  lib,
  dotfilesDir,
  config,
  pkgs,
  ...
}:

with lib;
{
  config = {
    programs.codex = {
      enable = true;
      package = pkgs.codex;
      # Leave settings/context/plugins/marketplaces unset -- see header.
    };

    # Global context: same source of truth as every other harness.
    home.file.".codex/AGENTS.md".source =
      config.lib.file.mkOutOfStoreSymlink "${dotfilesDir}/agents/AGENTS.md";
  };
}
