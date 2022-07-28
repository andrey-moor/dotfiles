{ config, options, pkgs, lib, ... }:

with lib;
with lib.my;
let cfg = config.modules.shell.neovim;
    configDir = "${config.dotfiles.modulesDir}/shell";
in {
  options.modules.shell.neovim = with types; {
    enable = mkBoolOpt false;
  };

  config = mkIf cfg.enable {

    home-manager.users.${config.user.name}.programs.neovim = {
      enable = true;
      # package = pkgs.neovim
      package = pkgs.neovim-nightly;

      extraConfig = builtins.readFile ./config/init.vim;

      viAlias = true;
      vimAlias = true;

      # extraPackages = with pkgs; [
      #   tree-sitter
      # ];

      plugins = with pkgs.vimPlugins; [
        telescope-nvim          # fuzzy finder
        vim-fish                # fish shell highlighting
        vim-fugitive            # git plugin
        vim-nix                 # nix support (highlighting, etc)
        vim-devicons
        onedark-nvim
        # nord-vim                # Nord theme
        dashboard-nvim          # dashboard
        bufferline-nvim


        coc-nvim
        coc-tsserver
        coc-prettier
        coc-eslint
        coc-lists
        auto-pairs
        nerdcommenter

        vim-gitgutter

        #lightline-vim
        vim-airline
        vim-airline-themes
        indentLine

        # nvim-lspconfig
        # nvim-cmp
        # cmp-nvim-lsp

        nerdtree                # tree explorer
        nerdtree-git-plugin     # shows files git status on the NerdTree

        completion-nvim
        (nvim-treesitter.withPlugins (
          plugins: pkgs.tree-sitter.allGrammars
        ))
        # nvim-treesitter-playground
        nvim-treesitter-textobjects
      ];
    };
  };
}
