# modules/darwin/homebrew.nix -- Homebrew integration via nix-homebrew

{ lib, config, inputs, ... }:

with lib;
let cfg = config.modules.darwin.homebrew;
in {
  options.modules.darwin.homebrew = {
    enable = mkEnableOption "Homebrew package management";
    casks = mkOption {
      type = types.listOf types.str;
      default = [];
      description = "Homebrew casks to install";
    };
    brews = mkOption {
      type = types.listOf types.str;
      default = [];
      description = "Homebrew formulae to install";
    };
    masApps = mkOption {
      type = types.attrsOf types.int;
      default = {};
      description = "Mac App Store apps to install (name = id)";
      example = { "Screens 5" = 1663047912; };
    };
  };

  config = mkIf cfg.enable {
    # nix-homebrew configuration
    nix-homebrew = {
      enable = true;
      enableRosetta = false;
      user = config.user.name;
      # Migrate existing Homebrew installation
      autoMigrate = true;
      taps = {
        "homebrew/homebrew-core" = inputs.homebrew-core;
        "homebrew/homebrew-bundle" = inputs.homebrew-bundle;
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
        # Homebrew 6 made `brew bundle --cleanup` a dry-run that exits non-zero
        # unless cleanup is forced, which aborts activation. Force it through.
        extraFlags = [ "--force-cleanup" ];
      };

      # GUI applications
      casks = cfg.casks;

      # CLI tools not in nixpkgs or better via Homebrew
      brews = cfg.brews;

      # Mac App Store apps
      masApps = cfg.masApps;
    };
  };
}
