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
in {
  options.modules.dev.kb-engine = {
    enable = mkEnableOption "kb-engine local KB embedding + hybrid search";
  };

  config = mkIf cfg.enable {
    # uv is provided by the host's common packages (and modules.dev.python);
    # only the wrapper is added here to avoid duplicating uv on PATH.
    home.packages = [ kbEngine ];
  };
}
