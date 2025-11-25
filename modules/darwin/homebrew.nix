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
  };

  config = mkIf cfg.enable {
    # nix-homebrew configuration
    nix-homebrew = {
      enable = true;
      enableRosetta = true;
      user = config.user.name;
      # Migrate existing Homebrew installation
      autoMigrate = true;
      taps = {
        "homebrew/homebrew-core" = inputs.homebrew-core;
        "homebrew/homebrew-bundle" = inputs.homebrew-bundle;
        # Note: homebrew-cask is not managed here to avoid "Refusing to untap" errors
        # Homebrew includes cask support by default
      };
      mutableTaps = true;
    };

    # Homebrew packages
    homebrew = {
      enable = true;
      onActivation = {
        cleanup = "zap";
        autoUpdate = true;
        upgrade = true;
      };

      # GUI applications
      casks = cfg.casks;

      # CLI tools not in nixpkgs or better via Homebrew
      brews = cfg.brews;
    };
  };
}
