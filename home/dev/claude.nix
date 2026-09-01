# home/dev/claude.nix -- Claude Code CLI + agent-stack wiring
#
# Authored content (AGENTS.md, skills, commands) lives in <dotfiles>/agents/
# and is fanned out as out-of-store symlinks: edits in the repo are live
# immediately, no rebuild needed. settings.json is a shared read/write file:
# a declared subset is merged in at activation time, everything else in it
# (model, permissions, tui, autoMode, ...) is app-owned and never touched.
#
# LANDMINE: never set `programs.claude-code.settings` or `.marketplaces`, and
# never declare a disabled MCP server — any of the three makes home-manager
# replace ~/.claude/settings.json with a READ-ONLY store symlink (write
# condition in the HM module: settings != {} || marketplaces != {} ||
# disabledMcpServerNames != []).

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
  cfg = config.modules.dev.claude;

  # Out-of-store symlink into the live repo working copy (spec §4).
  mkAgentsLink = subpath: config.lib.file.mkOutOfStoreSymlink "${dotfilesDir}/agents/${subpath}";

  # Names are enumerated from the flake's store copy of agents/; the symlink
  # targets point at the working tree via dotfilesDir.
  skillNames = attrNames (
    filterAttrs (_: type: type == "directory") (builtins.readDir ../../agents/skills)
  );
  commandNames = attrNames (builtins.readDir ../../agents/commands);

  # Declared subset of ~/.claude/settings.json, merged at activation time.
  declaredSettings = {
    alwaysThinkingEnabled = true;
    effortLevel = "high";
    env = {
      # Force full path: bare "bash" propagates to SHELL=bash in subprocess
      # envs, which breaks OpenSSH 10.2 Match exec clauses that resolve $SHELL
      # via execvp (no PATH lookup). /usr/bin/bash exists on macOS + Linux.
      CLAUDE_CODE_SHELL = "/usr/bin/bash";
    };
    # Authoritative plugin set — ad-hoc installs revert on switch.
    # ralph-loop@local is intentionally unmanaged (not listed here).
    enabledPlugins = {
      "superpowers@claude-plugins-official" = true;
      "frontend-design@claude-plugins-official" = true;
      "code-review@claude-plugins-official" = true;
      "skill-creator@claude-plugins-official" = true;
      "context7@claude-plugins-official" = true;
      "document-skills@anthropic-agent-skills" = true;
      "example-skills@anthropic-agent-skills" = true;
      "agent-browser@agent-browser" = true;
    };
    extraKnownMarketplaces = {
      claude-plugins-official.source = {
        source = "github";
        repo = "anthropics/claude-plugins-official";
      };
      anthropic-agent-skills.source = {
        source = "github";
        repo = "anthropics/skills";
      };
      agent-browser.source = {
        source = "github";
        repo = "vercel-labs/agent-browser";
      };
    };
  };

  declaredSettingsFile = pkgs.writeText "claude-declared-settings.json" (
    builtins.toJSON declaredSettings
  );

  # Merge semantics (ports the retired chezmoi modify_settings.json):
  #   - alwaysThinkingEnabled, effortLevel: overwrite
  #   - env: key-level additive (existing keys kept, CLAUDE_CODE_SHELL enforced)
  #   - enabledPlugins, extraKnownMarketplaces: authoritative replace
  #   - all other keys: preserved verbatim
  settingsMergeScript = pkgs.writeShellScript "claude-settings-merge" ''
    set -euo pipefail

    settings="$1"
    declared="$2"

    mkdir -p "$(dirname "$settings")"
    [ -e "$settings" ] || printf '{}\n' > "$settings"

    tmp="$(mktemp "$settings.XXXXXX")"
    trap 'rm -f "$tmp"' EXIT

    ${pkgs.jq}/bin/jq --slurpfile declared "$declared" '
      $declared[0] as $decl
      | . + {
          alwaysThinkingEnabled: $decl.alwaysThinkingEnabled,
          effortLevel: $decl.effortLevel,
          env: ((.env // {}) + $decl.env),
          enabledPlugins: $decl.enabledPlugins,
          extraKnownMarketplaces: $decl.extraKnownMarketplaces
        }
    ' "$settings" > "$tmp"

    mv "$tmp" "$settings"
  '';
in
{
  options.modules.dev.claude = {
    obsidianVault = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Path to an Obsidian vault; when set, adds the obsidian MCP server.";
    };
  };

  config = {
    programs.claude-code = {
      enable = true;
      package = inputs.claude-code-nix.packages.${pkgs.system}.default;
      # ~/.claude/CLAUDE.md is a thin importer; content lives in the repo.
      context = "@~/.agents/AGENTS.md\n";
      # Pull programs.mcp.servers in via HM's synthesized `hm` personal
      # plugin (carries an .mcp.json); tools appear as
      # mcp__plugin_hm_<server>__*. Stale user-scope duplicates in
      # ~/.claude.json are removed by scripts/agent-stack-cleanup.sh (Task 6).
      enableMcpIntegration = true;
    };

    # Declarative MCP servers. Never set `enabled = false` on any of these:
    # a disabled server lands in disabledMcpServerNames, which flips
    # settings.json to a read-only store symlink (see LANDMINE above).
    programs.mcp = {
      enable = true;
      servers = {
        kagi = {
          command = "op";
          args = [
            "run"
            "--"
            "uvx"
            "--python"
            "3.13"
            "kagimcp"
          ];
          # op:// reference resolved by `op run` at launch — not a secret.
          env.KAGI_API_KEY = "op://Private/Kagi/api_key";
        };
        fetch = {
          command = "uvx";
          args = [ "mcp-server-fetch" ];
        };
      }
      // optionalAttrs (cfg.obsidianVault != null) {
        obsidian = {
          command = "npx";
          args = [
            "-y"
            "@bitbonsai/mcpvault@latest"
            cfg.obsidianVault
          ];
        };
      };
    };

    home.file = mkMerge (
      [
        { ".agents/AGENTS.md".source = mkAgentsLink "AGENTS.md"; }
      ]
      # Skills fan out to both Claude Code and the vendor-neutral ~/.agents dir
      # (read by codex/copilot, wired in later tasks).
      ++ map (name: {
        ".claude/skills/${name}".source = mkAgentsLink "skills/${name}";
        ".agents/skills/${name}".source = mkAgentsLink "skills/${name}";
      }) skillNames
      ++ map (name: {
        ".claude/commands/${name}".source = mkAgentsLink "commands/${name}";
      }) commandNames
    );

    home.activation.claudeSettingsMerge = hm.dag.entryAfter [ "writeBoundary" ] ''
      run ${settingsMergeScript} \
        ${escapeShellArg "${config.home.homeDirectory}/.claude/settings.json"} \
        ${declaredSettingsFile}
    '';
  };
}
