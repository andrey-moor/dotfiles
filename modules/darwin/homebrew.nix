# modules/darwin/homebrew.nix -- Homebrew integration via nix-homebrew

{
  lib,
  config,
  inputs,
  ...
}:

with lib;
let
  cfg = config.modules.darwin.homebrew;

  # Every declared cask and formula must exist in the pinned taps. Upstream
  # renames them (tigervnc-viewer, google-cloud-sdk) and moves formulae to casks
  # (azure-cli, vercel-cli). Without this check such a change builds fine,
  # passes CI, and fails only when `just switch` reaches `brew bundle`. With
  # it, the weekly lock PR goes red instead.
  taps = {
    cask = {
      src = inputs.homebrew-cask;
      # Casks/<first letter>/<name>.rb, fonts under Casks/font/font-<letter>/
      file =
        name:
        if hasPrefix "font-" name then
          "Casks/font/font-${substring 5 1 name}/${name}.rb"
        else
          "Casks/${substring 0 1 name}/${name}.rb";
      renames = "cask_renames.json";
    };
    formula = {
      src = inputs.homebrew-core;
      # Formula/<first letter>/<name>.rb, lib* under Formula/lib/
      file =
        name:
        if hasPrefix "lib" name then
          "Formula/lib/${name}.rb"
        else
          "Formula/${substring 0 1 name}/${name}.rb";
      renames = "formula_renames.json";
    };
  };

  pinned =
    kind: name:
    let
      tap = taps.${kind};
      read = file: builtins.fromJSON (builtins.readFile "${tap.src}/${file}");
      renames = read tap.renames;
      moves = read "tap_migrations.json";
    in
    {
      # A name with a slash comes from another tap and is not checked.
      assertion =
        hasInfix "/" name
        || builtins.pathExists "${tap.src}/${tap.file name}"
        || (kind == "formula" && builtins.pathExists "${tap.src}/Aliases/${name}");
      message =
        "Homebrew ${kind} `${name}` is not in the pinned tap."
        + optionalString (renames ? ${name}) " Upstream renamed it to `${renames.${name}}`."
        + optionalString (moves ? ${name}) " Upstream moved it to `${moves.${name}}`.";
    };
in
{
  options.modules.darwin.homebrew = {
    casks = mkOption {
      type = types.listOf types.str;
      default = [ ];
      description = "Homebrew casks to install";
    };
    brews = mkOption {
      type = types.listOf types.str;
      default = [ ];
      description = "Homebrew formulae to install";
    };
    masApps = mkOption {
      type = types.attrsOf types.int;
      default = { };
      description = "Mac App Store apps to install (name = id)";
      example = {
        "Screens 5" = 1663047912;
      };
    };
  };

  config = {
    assertions =
      map (c: pinned "cask" c.name) config.homebrew.casks
      ++ map (b: pinned "formula" b.name) config.homebrew.brews;

    # nix-homebrew configuration
    nix-homebrew = {
      enable = true;
      enableRosetta = false;
      user = config.system.primaryUser;
      # Migrate existing Homebrew installation
      autoMigrate = true;
      # No homebrew-bundle tap: `brew bundle` has been part of Homebrew itself
      # since 2025 and the old tap now holds only a README.
      taps = {
        "homebrew/homebrew-core" = inputs.homebrew-core;
        # With nix-homebrew pinning homebrew-core, HOMEBREW_NO_INSTALL_FROM_API is
        # set, so casks MUST also come from a pinned tap — without this line they
        # silently resolve from a stale local API cache (bit us 2026-08-31: months-old
        # cask definitions with dead download URLs). Cask versions now track the
        # flake input; `nix flake update homebrew-cask` to bump.
        "homebrew/homebrew-cask" = inputs.homebrew-cask;
      };
      mutableTaps = true;
    };

    # Homebrew packages
    homebrew = {
      enable = true;
      # Brewfile must declare the nix-managed taps, or bundle cleanup untaps
      # them and uninstalls every cask that came from them (2026-08-31 incident).
      taps = builtins.attrNames config.nix-homebrew.taps;
      onActivation = {
        cleanup = "zap";
        # Taps are flake-pinned (above); letting brew self-update during activation
        # fights the pinning — on 2026-08-31 it cloned 1.1G of homebrew-core mid-switch
        # and crashed brew 6.0.18. Upgrades arrive by bumping the flake inputs.
        autoUpdate = false;
        upgrade = true;
        # Homebrew 6 made `brew bundle --cleanup` a dry-run unless it is forced.
        # nix-darwin passes --force-cleanup itself for "zap".
      };

      # GUI applications
      inherit (cfg) casks;

      # CLI tools not in nixpkgs or better via Homebrew
      inherit (cfg) brews;

      # Mac App Store apps
      inherit (cfg) masApps;
    };
  };
}
