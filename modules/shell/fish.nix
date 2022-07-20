{ config, options, pkgs, lib, ... }:

with lib;
with lib.my;
let cfg = config.modules.shell.fish;
    configDir = config.dotfiles.configDir;

    fzfConfig = ''
      set -x FZF_DEFAULT_OPTS "--preview='bat {} --color=always'" \n
      set -x SKIM_DEFAULT_COMMAND "rg --files || fd || find ."
    '';

    fenv = {
      name = "foreign-env";
      src = pkgs.fishPlugins.foreign-env.src;
    };

    fzf-fish = {
      name = "fzf.fish";
      src = pkgs.fishPlugins.fzf-fish.src;
    };

    fishConfig = fzfConfig;
in {
  options.modules.shell.fish = with types; {
    enable = mkBoolOpt false;
  };

  config = mkIf cfg.enable {

    user.packages = with pkgs; [
      oh-my-fish
      any-nix-shell       # fish support for nix shell
      fzf                 # fuzzy finder that powers this plugin
      fd                  # faster and more colorful alternative to find
      bat                 # smarter cat with syntax highlighting
    ];

    home-manager.users.${config.user.name}.programs = {
      starship = {
        enable = true;
        enableFishIntegration = true;
        # Configuration written to ~/.config/starship.toml
        settings = {
          # add_newline = false;

          # character = {
          #   success_symbol = "[➜](bold green)";
          #   error_symbol = "[➜](bold red)";
          # };

          # package.disabled = true;
        };
      };

      fish = {
        enable = true;

        plugins = [
          fenv
          fzf-fish
          # pure
        ];

        interactiveShellInit = ''
          eval (direnv hook fish)
          any-nix-shell fish --info-right | source
        '';

        shellAliases = {
          g = "git";
          ga = "git add";
          gc = "git commit";
          gco = "git checkout";
          gcp = "git cherry-pick";
          gdiff = "git diff";
          gl = "git prettylog";
          gp = "git push";
          gs = "git status";
          gt = "git tag";

          l    = "ls -a";
          ".." = "cd ..";
          clr = "clear";

          pbcopy = "xclip";
          pbpaste = "xclip -o";
        };

        functions = {
          mkd = {
            description = "Make a directory tree and enter it";
            body = "mkdir -p $argv[1]; and cd $argv[1]";
          };
        };

        shellInit = fishConfig;
      };
    };
  };
}
