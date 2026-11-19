# home/dev/codex-gateway.nix -- Codex profiles that go through the LLM gateway
#
# The gateway is Bifrost on behemoth (config/containers). Each profile below is
# a file ~/.codex/<name>.config.toml, used as `codex --profile <name>`. A
# profile carries its own provider definition, so ~/.codex/config.toml stays
# hand-written and untouched: the ChatGPT plan login and the direct Azure
# provider live there, and Codex keeps writing its trust entries to it.
#
#   codex                         the default in config.toml
#   codex --profile local         open-weight model on this Mac (LM Studio)
#   codex --profile openrouter    hosted open-weight models
#   codex --profile claude        Claude, personal Anthropic API key
#   codex --profile claude-work   Claude, work Anthropic API key
#   codex --profile openai-api    OpenAI API key, not the ChatGPT plan
#
# `-m provider/model` picks another model for one run. The names are the
# gateway's: `curl -H "Authorization: Bearer $KEY" localhost:8080/v1/models`.
# Switching provider needs a new session. `/model` inside a session only
# changes the model.
#
# Verified with codex 0.160 and 0.167 on 2026-11-16: a read-only profile file
# with its own [model_providers.*] table works, and the key command below is
# run instead of reading an environment variable.

{
  config,
  lib,
  pkgs,
  ...
}:

let
  envFile = "${config.home.homeDirectory}/.config/behemoth-containers/gateway.env";

  # Codex knows its own models only. For any other name it warns "Model
  # metadata not found" and guesses the context size. This file tells it about
  # the gateway models: each entry is a copy of one model Codex ships, under
  # the gateway's name. Bifrost cannot serve such a list itself. A profile
  # that sets `model_catalog_json` sees only these models in `/model`.
  catalogBase = "gpt-5.5";
  catalogModels = [
    {
      slug = "lmstudio/qwen/qwen3.8-27b";
      display_name = "Qwen3.8 27B (local)";
      context_window = 65536;
    }
    {
      slug = "openrouter/moonshotai/kimi-k3.1-pro";
      display_name = "Kimi K3.1 Pro (OpenRouter)";
      context_window = 1048576;
    }
  ];
  # `support_verbosity` must be off: LM Studio rejects the field it adds.
  catalog =
    pkgs.runCommand "codex-gateway-catalog.json"
      {
        nativeBuildInputs = [
          config.programs.codex.package
          pkgs.jq
        ];
        models = builtins.toJSON catalogModels;
      }
      ''
        export HOME="$TMPDIR" CODEX_HOME="$TMPDIR/codex"
        mkdir -p "$CODEX_HOME"
        codex debug models --bundled > bundled.json
        jq --argjson models "$models" --arg base ${catalogBase} '
          (.models | map(select(.slug == $base)) | first) as $b
          | if $b == null then error("Codex no longer ships " + $base) else . end
          | { models: ($models | map($b + . + {
              description: "through the gateway",
              default_reasoning_level: null,
              supported_reasoning_levels: [],
              support_verbosity: false,
              default_verbosity: null,
              upgrade: null,
              priority: 0
            })) }
        ' bundled.json > "$out"
      '';

  # Shared by every profile. Top-level keys must come before the first table.
  provider = ''

    # Codex otherwise hands every environment variable named *KEY* or *TOKEN*
    # to each command the model runs.
    [shell_environment_policy]
    ignore_default_excludes = false

    [model_providers.bifrost]
    name = "Bifrost gateway"
    base_url = "http://127.0.0.1:8080/openai/v1"
    wire_api = "responses"
    requires_openai_auth = false
    # Bifrost translates for providers without OpenAI's WebSocket protocol.
    supports_websockets = false
    # A local model can take minutes to read a long prompt.
    stream_idle_timeout_ms = 900000

    # The gateway key is read from the file `just gateway-secrets` renders. It
    # never sits in the shell environment. 0 = fetch again only after a 401.
    [model_providers.bifrost.auth]
    command = "/usr/bin/sed"
    args = ["-n", "s/^BIFROST_VIRTUAL_KEY=//p", "${envFile}"]
    refresh_interval_ms = 0
  '';

  profile =
    {
      model,
      extra ? "",
    }:
    ''
      model_provider = "bifrost"
      model = "${model}"
      # Hosted web search is an OpenAI tool. Other backends reject it.
      web_search = "disabled"
    ''
    + extra
    + provider;

  profiles = {
    # Qwen3.8-27B loaded by LM Studio. Codex compacts at the window in the
    # catalog. LM Studio must load the model with at least as much context.
    local = profile {
      model = "lmstudio/qwen/qwen3.8-27b";
      extra = ''
        model_catalog_json = "${catalog}"
      '';
    };
    openrouter = profile {
      model = "openrouter/moonshotai/kimi-k3.1-pro";
      extra = ''
        model_catalog_json = "${catalog}"
      '';
    };
    claude = profile { model = "anthropic-personal/claude-opus-5-5"; };
    claude-work = profile { model = "anthropic-work/claude-opus-5-5"; };
    openai-api = profile { model = "openai/gpt-6.1-sol"; };
  };
in
{
  home.file = lib.mapAttrs' (
    name: text: lib.nameValuePair ".codex/${name}.config.toml" { inherit text; }
  ) profiles;
}
