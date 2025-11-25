$env.config.show_banner = false
$env.config.highlight_resolved_externals = true

$env.EDITOR = "nvim"
$env.VISUAL = "nvim"

# Ensure gpg-agent is running and TTY is updated
^gpgconf --launch gpg-agent
^gpg-connect-agent updatestartuptty /bye out> /dev/null

# Theme
source catppuccin_mocha.nu

# nu_scripts path (managed by nix)
const NU_SCRIPTS = $"($nu.home-path)/.local/share/nushell/nu_scripts"

# completions
source $"($NU_SCRIPTS)/custom-completions/docker/docker-completions.nu"
source $"($NU_SCRIPTS)/custom-completions/curl/curl-completions.nu"
source $"($NU_SCRIPTS)/custom-completions/ssh/ssh-completions.nu"
source $"($NU_SCRIPTS)/custom-completions/jj/jj-completions.nu"
source $"($NU_SCRIPTS)/custom-completions/just/just-completions.nu"
source $"($NU_SCRIPTS)/custom-completions/uv/uv-completions.nu"
source $"($NU_SCRIPTS)/custom-completions/nix/nix-completions.nu"
source $"($NU_SCRIPTS)/custom-completions/git/git-completions.nu"

# modules
use $"($NU_SCRIPTS)/modules/argx/"
use $"($NU_SCRIPTS)/modules/lg/"
use $"($NU_SCRIPTS)/modules/docker/"
use $"($NU_SCRIPTS)/modules/kubernetes/"

# Shell Aliases
use $"($NU_SCRIPTS)/aliases/bat/bat-aliases.nu" *
use $"($NU_SCRIPTS)/aliases/chezmoi/chezmoi-aliases.nu" *
use $"($NU_SCRIPTS)/aliases/docker/docker-aliases.nu" *
use $"($NU_SCRIPTS)/aliases/git/git-aliases.nu" *

alias ll = ls -l 

alias switch = just --justfile ~/Documents/dotfiles/justfile switch
alias update = just --justfile ~/Documents/dotfiles/justfile update; just --justfile ~/Documents/dotfiles/justfile switch

alias vim = nvim 
alias v = nvim 

alias k = kubectl
alias kgp = kubectl get pods -A
alias kgs = kubectl get svc -A
alias kctx = kubectx
alias kns = kubens

alias tl = tmux list-sessions
alias t = tmux
alias tnew = tmux new-session -s
alias tneww = tmux new-window
alias ta = tmux attach-session -t
alias tkill = tmux kill-session -t

# direnv
$env.config = {
  hooks: {
    pre_prompt: [{ ||
      if (which direnv | is-empty) {
        return
      }

      direnv export json | from json | default {} | load-env
      if 'ENV_CONVERSIONS' in $env and 'PATH' in $env.ENV_CONVERSIONS {
        $env.PATH = do $env.ENV_CONVERSIONS.PATH.from_string $env.PATH
      }
    }]
  }
}

mkdir ($nu.data-dir | path join "vendor/autoload")
starship init nu | save -f ($nu.data-dir | path join "vendor/autoload/starship.nu")
