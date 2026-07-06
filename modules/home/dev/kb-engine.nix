# modules/home/dev/kb-engine.nix -- kb-engine local KB embedding + hybrid search

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.dev.kb-engine;

  # Wrapper: run the in-repo uv project with the [ml] (jina-v3 embeddings) and
  # [topics] (umap/hdbscan clustering) extras — both are needed for full function.
  kbEngine = pkgs.writeShellScriptBin "kb-engine" ''
    exec ${pkgs.uv}/bin/uv run --project ${config.modules.dotfilesDir}/kb-engine \
      --extra ml --extra topics kb-engine "$@"
  '';

  logDir = "${config.home.homeDirectory}/Library/Logs";

  # Weekly pipeline runner: run the deterministic pipeline against the vault,
  # then nudge with a notification reporting how many items need review. The
  # pipeline is LLM-free and mutates notes only for active topics (none yet),
  # so this is safe to run unattended.
  pipelineRunner = pkgs.writeShellScript "kb-engine-pipeline" ''
    set -euo pipefail
    out="$(${kbEngine}/bin/kb-engine --vault "${cfg.vaultPath}" pipeline --json)"
    echo "$out"
    # inbox backlog + proposals awaiting naming + unfiled notes = the review queue.
    n="$(printf '%s' "$out" | /usr/bin/python3 -c \
      'import json,sys; d=json.load(sys.stdin); print(d["inbox"]+d["proposals"]+d["unfiled"])' \
      2>/dev/null || echo "")"
    if [ -n "$n" ]; then
      msg="KB digest ready — $n to review"
    else
      msg="KB digest ready"
    fi
    /usr/bin/osascript -e "display notification \"$msg\" with title \"kb-engine\""
  '';

  # Nightly vault autosnapshot: stage everything, then commit only when the
  # index actually changed so quiet nights are no-ops. The vault git repo is
  # local-only — plain versioning/diffability atop iCloud + Time Machine.
  autocommitRunner = pkgs.writeShellScript "kb-vault-autocommit" ''
    set -euo pipefail
    cd "${cfg.vaultPath}"
    ${pkgs.git}/bin/git add -A
    ${pkgs.git}/bin/git diff --cached --quiet || ${pkgs.git}/bin/git commit -m "auto: $(date +%F)"
  '';
in {
  options.modules.dev.kb-engine = {
    enable = mkEnableOption "kb-engine local KB embedding + hybrid search";

    vaultPath = mkOption {
      type = types.str;
      default = "${config.home.homeDirectory}/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main";
      description = "Path to the Obsidian vault the scheduled pipeline maintains.";
    };

    schedule = {
      enable = mkEnableOption "weekly launchd agent that runs the kb-engine pipeline + nudges";

      calendar = mkOption {
        # A launchd StartCalendarInterval spec (Weekday/Hour/Minute, etc.).
        type = types.attrsOf types.int;
        default = { Weekday = 1; Hour = 9; Minute = 0; }; # Monday 09:00
        description = "launchd StartCalendarInterval for the weekly pipeline run.";
      };
    };
  };

  config = mkIf cfg.enable (mkMerge [
    {
      # uv is provided by the host's common packages (and modules.dev.python);
      # only the wrapper is added here to avoid duplicating uv on PATH.
      home.packages = [ kbEngine ];
    }
    (mkIf cfg.schedule.enable {
      launchd.agents.kb-engine-pipeline = {
        enable = true;
        config = {
          ProgramArguments = [ "${pipelineRunner}" ];
          StartCalendarInterval = cfg.schedule.calendar;
          StandardOutPath = "${logDir}/kb-engine-pipeline.log";
          StandardErrorPath = "${logDir}/kb-engine-pipeline.err";
        };
      };
      launchd.agents.kb-vault-autocommit = {
        enable = true;
        config = {
          ProgramArguments = [ "${autocommitRunner}" ];
          StartCalendarInterval = { Hour = 21; Minute = 30; };
          StandardOutPath = "${logDir}/kb-vault-autocommit.log";
          StandardErrorPath = "${logDir}/kb-vault-autocommit.err";
        };
      };
    })
  ]);
}
