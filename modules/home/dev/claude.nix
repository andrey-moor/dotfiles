# modules/home/dev/claude.nix -- Claude Code CLI
# MCP server config is managed by chezmoi (mutable config)

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.dev.claude;

  # Wrapper script that uses op run when 1Password is available
  claude-wrapper = pkgs.writeShellScriptBin "claude" ''
    if command -v op &>/dev/null && op account list &>/dev/null 2>&1; then
      exec op run -- ${pkgs.main.claude-code}/bin/claude "$@"
    else
      exec ${pkgs.main.claude-code}/bin/claude "$@"
    fi
  '';
in {
  options.modules.dev.claude = {
    enable = mkEnableOption "Claude Code CLI";
  };

  config = mkIf cfg.enable {
    home.packages = [
      claude-wrapper
      pkgs._1password-cli  # op CLI for secret injection
      pkgs.uv              # uvx for Python-based MCP servers
      pkgs.nodejs          # npx for Node-based MCP servers
    ];
  };
}
