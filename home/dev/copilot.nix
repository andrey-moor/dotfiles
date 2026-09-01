# home/dev/copilot.nix -- GitHub Copilot CLI (terminal coding agent)
#
# Bleeding-edge via scarisey/copilot-cli-flake (auto-bumped weekly) with an
# inline overrideAttrs that pins ahead of scarisey when upstream npm is newer.
#
# To bump to the latest npm release:
#   just bump-copilot
#
# That recipe queries the npm registry, prefetches the tarball hash, and
# rewrites copilot-pin.json. When scarisey catches up to >= the pinned
# version, the override silently becomes a no-op (guarded by equality).
#
# Global instructions come from the shared agents/AGENTS.md source of truth
# via programs.github-copilot-cli.context, which writes only
# ~/.copilot/copilot-instructions.md. Verified against the pinned HM module
# source (modules/programs/github-copilot-cli.nix): config.json is guarded by
# `mkIf (cfg.settings != { })` and mcp-config.json by its merged-servers
# check (enableMcpIntegration defaults to false; MCP for copilot is
# deferred), and the module never manages ~/.copilot/settings.json -- so the
# app-owned ~/.copilot state stays untouched. The context option accepts
# derivations (isPathLike), so the out-of-store symlink passes through as a
# file source.
#
# Skills: the vendor-neutral ~/.agents/skills fan-out (claude.nix) covers
# copilot; nothing is declared here.
#
# The superpowers plugin is installed imperatively, once:
#   copilot plugin install obra/superpowers
# (the old chezmoi run_onchange installer is retired). That
# installer also filtered a spurious nix-openssl "Cannot open directory
# .../etc/ssl/certs" stderr warning; no wrapper is added here -- if the
# warning still reproduces under the current package, handle it in Task 7.

{
  lib,
  dotfilesDir,
  config,
  pkgs,
  inputs,
  ...
}:

with lib;
let
  pin = builtins.fromJSON (builtins.readFile ./copilot-pin.json);
  base = inputs.copilot-cli-flake.packages.${pkgs.system}.default;
  copilot =
    if builtins.compareVersions base.version pin.version >= 0 then
      base
    else
      base.overrideAttrs (_old: {
        inherit (pin) version;
        src = pkgs.fetchurl {
          url = "https://registry.npmjs.org/@github/copilot/-/copilot-${pin.version}.tgz";
          sha256 = pin.hash;
        };
      });
in
{
  config = {
    programs.github-copilot-cli = {
      enable = true;
      package = copilot;
      context = config.lib.file.mkOutOfStoreSymlink "${dotfilesDir}/agents/AGENTS.md";
    };
  };
}
