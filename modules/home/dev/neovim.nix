# modules/home/dev/neovim.nix -- Neovim editor (package only, config via chezmoi)

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.neovim;
in {
  options.modules.dev.neovim = {
    enable = mkEnableOption "Neovim editor";
  };

  config = mkIf cfg.enable {
    programs.neovim = {
      enable = true;
      defaultEditor = true;
      viAlias = true;
      vimAlias = true;
      vimdiffAlias = true;

      # Support for various languages in plugins
      withNodeJs = true;
      withPython3 = true;

      # Extra packages available to neovim
      extraPackages = with pkgs; [
        # For telescope and other plugins
        ripgrep
        fd
        # For clipboard support
        xclip
      ];

      # NOTE: No extraConfig or plugins here!
      # Full AstroNvim configuration is managed by chezmoi at ~/.config/nvim/
      # This allows Lazy.nvim to manage plugins and write lazy-lock.json
    };
  };
}
