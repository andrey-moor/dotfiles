# modules/home/dev/codex.nix -- OpenAI Codex CLI

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.codex;
in {
  options.modules.dev.codex = {
    enable = mkEnableOption "OpenAI Codex CLI";
  };

  config = mkIf cfg.enable {
    home.packages = [
      # Wrapper that routes through LiteLLM proxy (GitHub Copilot backend)
      (pkgs.writeShellScriptBin "codex" ''
        export OPENAI_BASE_URL="http://127.0.0.1:4000"
        export OPENAI_API_KEY="sk-"
        exec ${pkgs.codex}/bin/codex -c web_search=disabled "$@"
      '')
    ];
  };
}
