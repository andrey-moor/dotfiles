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

# GPG agent for SSH authentication (Yubikey)
$env.GPG_TTY = (do -i { tty } | default "")
$env.SSH_AUTH_SOCK = (gpgconf --list-dirs agent-ssh-socket | str trim)

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

