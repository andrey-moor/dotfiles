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
use $"($NU_SCRIPTS)/aliases/git/git-aliases.nu" *

alias ll = ls -l
alias gsd = ^gsd  # override nu_scripts git alias (git svn dcommit)

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

# tmux: attach-or-create session (defaults to "main"; pass a name for ad-hoc sessions).
# Defaulting to "main" keeps a single canonical session so continuum/resurrect doesn't
# end up persisting multiple parallel sessions across server restarts.
def t [name?: string] {
  let session = if $name != null { $name } else { "main" }
  tmux new-session -A -s $session
}

# bonfire: context monitor for Claude sessions
alias bonfire = /mnt/psf/Home/Documents/Microsoft/monorepo-bonfire/bazel-bin/tools/cli/bonfire/bonfire/bonfire

alias tl = tmux list-sessions
alias ta = tmux new-session -A -s main
alias tkill = tmux kill-session -t

# tmux dev layout: editor + AI + terminal
def tml [ai?: string] {
  let current_dir = $env.PWD
  let in_tmux = ($env | get -o TMUX | is-not-empty)

  if not $in_tmux {
    # continuum auto-restore can recreate "main" as a hollow, shell-only session
    # (pane layout restored, but nvim/claude not). Only attach when the dev
    # layout is actually live; otherwise drop the stale session and rebuild.
    let pane_cmds = (do -i { tmux list-panes -t main -F '#{pane_current_command}' } | complete | get stdout)
    let has_layout = ($pane_cmds | lines | any {|cmd| $cmd == $env.EDITOR })
    if $has_layout {
      tmux attach-session -t main
    } else {
      # Drop any stale/restored "main"; retry once if continuum recreates it.
      do -i { tmux kill-session -t main }
      let created = (do -i { tmux new-session -d -s main -c $current_dir } | complete | get exit_code)
      if $created != 0 {
        do -i { tmux kill-session -t main }
        tmux new-session -d -s main -c $current_dir
      }
      let editor_pane = (tmux display-message -t main -p '#{pane_id}' | str trim)
      tmux split-window -t main -v -p 15 -c $current_dir
      tmux select-pane -t $editor_pane
      tmux split-window -t $editor_pane -h -p 30 -c $current_dir
      let ai_pane = (tmux display-message -t main -p '#{pane_id}' | str trim)
      if $ai != null {
        tmux send-keys -t $ai_pane $ai C-m
      }
      tmux send-keys -t $editor_pane $"($env.EDITOR) ." C-m
      tmux select-pane -t $editor_pane
      tmux attach-session -t main
    }
  } else {
    let editor_pane = (tmux display-message -p '#{pane_id}' | str trim)
    tmux split-window -v -p 15 -c $current_dir
    tmux select-pane -t $editor_pane
    tmux split-window -h -p 30 -c $current_dir
    let ai_pane = (tmux display-message -p '#{pane_id}' | str trim)
    if $ai != null {
      tmux send-keys -t $ai_pane $ai C-m
    }
    tmux send-keys -t $editor_pane $"($env.EDITOR) ." C-m
    tmux select-pane -t $editor_pane
  }
}

# dev layout with claude
def nic [] { tml "claude -c" }

# dev layout with opencode
def nioc [] { tml opencode }

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
