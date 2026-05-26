# modules/home/dev/nix.nix -- Nix development tools (home-manager)

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.nix;
in {
  options.modules.dev.nix = {
    enable = mkEnableOption "Nix development tools";
  };

  config = mkIf cfg.enable {
    home.packages = with pkgs; [
      # Nix tools
      nixfmt             # Formatter (RFC-style; nixfmt-rfc-style is now an alias)
      nil                # LSP
      nix-prefetch-git   # Prefetch git repos
      nix-tree           # Dependency tree viewer
      nix-output-monitor # Pretty build output
      nix-diff           # Compare derivations
    ];
  };
}
