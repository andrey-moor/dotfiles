# Nushell Environment Config File

# Load home-manager session variables (cross-platform)
let hm_vars_path = if ($"/etc/profiles/per-user/($env.USER)/etc/profile.d/hm-session-vars.sh" | path exists) {
    $"/etc/profiles/per-user/($env.USER)/etc/profile.d/hm-session-vars.sh"
} else if ($"($env.HOME)/.nix-profile/etc/profile.d/hm-session-vars.sh" | path exists) {
    $"($env.HOME)/.nix-profile/etc/profile.d/hm-session-vars.sh"
} else {
    null
}

if $hm_vars_path != null {
    # List of automatic nushell env vars that cannot be set manually
    let excluded_vars = ['PWD', 'OLDPWD', 'CMD_DURATION_MS', 'LAST_EXIT_CODE', 'NU_VERSION', 'FILE_PWD', 'CURRENT_FILE']

    let hm_vars = (bash -c $'source ($hm_vars_path) && env'
        | lines
        | where {|line| ($line | str contains '=')}
        | each {|line|
            let parts = ($line | split row '=')
            if ($parts | length) >= 2 {
                {name: ($parts | first), value: ($parts | skip 1 | str join '=')}
            } else {
                null
            }
        }
        | where {|x| $x != null}
        | where {|x| $x.name not-in $excluded_vars})
    for var in $hm_vars {
        load-env {($var.name): ($var.value)}
    }
}

# Nix environment (Determinate Systems installer)
$env.NIX_SSL_CERT_FILE = '/nix/var/nix/profiles/default/etc/ssl/certs/ca-bundle.crt'

$env.PATH = ($env.PATH | split row (char esep)
    | prepend '/nix/var/nix/profiles/default/bin'
    | prepend '/run/current-system/sw/bin'
    | prepend $"/etc/profiles/per-user/($env.USER)/bin"
    | prepend $"($nu.home-dir)/.nix-profile/bin"
    | prepend '/usr/local/bin/'
    | prepend '/opt/homebrew/bin'
    | prepend '/Applications/Parallels Desktop.app/Contents/MacOS/'
    | prepend $"($env.HOME)/.cargo/bin"
    | prepend $"($env.HOME)/.local/bin"
)

# GPG/SSH agent setup
$env.GPG_TTY = (do -i { tty } | default "")

# SSH agent priority:
# 1. Forwarded agent (SSH session) — don't override SSH_AUTH_SOCK
# 2. 1Password agent socket (macOS or Linux)
# 3. gpg-agent (YubiKey fallback)
let is_ssh = ($env | get -i SSH_CLIENT | default "" | is-not-empty)
let has_agent = ($env | get -i SSH_AUTH_SOCK | default "" | is-not-empty)

if not ($is_ssh and $has_agent) {
    let op_mac = $"($nu.home-dir)/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"
    let op_linux = $"($nu.home-dir)/.1password/agent.sock"
    if ($op_mac | path exists) {
        $env.SSH_AUTH_SOCK = $op_mac
    } else if ($op_linux | path exists) {
        $env.SSH_AUTH_SOCK = $op_linux
    } else {
        $env.SSH_AUTH_SOCK = (do -i { gpgconf --list-dirs agent-ssh-socket | str trim } | default "")
    }
}

