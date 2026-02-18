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
const NU_SCRIPTS = $"($nu.home-dir)/.local/share/nushell/nu_scripts"

# completions
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
use $"($NU_SCRIPTS)/modules/kubernetes/"

# Shell Aliases
use $"($NU_SCRIPTS)/aliases/bat/bat-aliases.nu" *
use $"($NU_SCRIPTS)/aliases/chezmoi/chezmoi-aliases.nu" *
use $"($NU_SCRIPTS)/aliases/git/git-aliases.nu" *

alias ll = ls -l 

def nix-switch [] { cd $env.DOTFILES; just switch }
def nix-update [] { cd $env.DOTFILES; just update; just switch }

alias vim = nvim
alias v = nvim
alias cc = claude
alias oc = opencode


alias k = kubectl
alias kgp = kubectl get pods -A
alias kgs = kubectl get svc -A
alias kctx = kubectx
alias kns = kubens

# tmux: smart create-or-attach session named after current directory
def t [name?: string] {
  let session = if $name != null { $name } else { $env.PWD | path basename }
  tmux new-session -A -s $session
}

# bonfire: context monitor for Claude sessions
alias bonfire = /mnt/psf/Home/Documents/Microsoft/monorepo-bonfire/bazel-bin/tools/cli/bonfire/bonfire/bonfire

alias tl = tmux list-sessions
alias ta = tmux attach-session
alias tkill = tmux kill-session -t

# External completer (carapace handles 800+ commands)
let carapace_completer = {|spans: list<string>|
    carapace $spans.0 nushell ...$spans | from json
}

$env.config.completions.external = {
    enable: true
    completer: $carapace_completer
}

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
atuin init nu | save -f ($nu.data-dir | path join "vendor/autoload/atuin.nu")
