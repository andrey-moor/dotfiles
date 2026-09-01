# home/dev/neovim.nix -- Neovim editor (package + out-of-store config)

{
  lib,
  dotfilesDir,
  config,
  pkgs,
  ...
}:

with lib;
{
  config = {
    programs.neovim = {
      enable = true;
      defaultEditor = true;
      viAlias = true;
      vimAlias = true;
      vimdiffAlias = true;

      # Support for various languages in plugins
      withNodeJs = true;
      withPython3 = true;
      withRuby = false; # AstroNvim doesn't use Ruby providers; new HM default

      # Extra packages available to neovim
      extraPackages = with pkgs; [
        # For telescope and other plugins
        ripgrep
        fd
        # For clipboard support
        xclip
      ];

      # NOTE: No extraConfig or plugins here!
      # Full AstroNvim configuration lives in <dotfiles>/config/nvim, deployed
      # below as an out-of-store symlink. Lazy.nvim manages plugins and writes
      # lazy-lock.json through the symlink straight into the repo.
    };

    # Whole-dir out-of-store symlink: edits in the repo are live immediately,
    # and nvim's own writes (lazy-lock.json) land in the working copy.
    xdg.configFile."nvim".source = config.lib.file.mkOutOfStoreSymlink "${dotfilesDir}/config/nvim";

    # Home Manager writes its own init.lua (provider host_prog setup) when
    # programs.neovim is enabled, which would conflict with the whole-dir
    # symlink above. Disable it so the repo's plain Lua config wins. Providers
    # are still discovered via PATH because withNodeJs/withPython3 put them
    # there.
    xdg.configFile."nvim/init.lua".enable = mkForce false;
  };
}
