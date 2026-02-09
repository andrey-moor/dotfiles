# modules/home/dev/claude.nix -- Claude Code CLI
# MCP server config lives in .mcp.json (project-scope, version controlled)

{ lib, config, pkgs, inputs, ... }:

with lib;
let cfg = config.modules.dev.claude;
in {
  options.modules.dev.claude = {
    enable = mkEnableOption "Claude Code CLI";
  };

  config = mkIf cfg.enable {
    home.packages = [
      inputs.claude-code-nix.packages.${pkgs.system}.default
    ];
  };
}
