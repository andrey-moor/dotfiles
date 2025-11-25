# Nushell Environment Config File

# Nix environment (Determinate Systems installer)
$env.NIX_SSL_CERT_FILE = '/nix/var/nix/profiles/default/etc/ssl/certs/ca-bundle.crt'

# GPG agent for SSH authentication (Yubikey)
$env.GPG_TTY = (tty)
$env.SSH_AUTH_SOCK = $"($env.HOME)/.gnupg/S.gpg-agent.ssh"

$env.PATH = ($env.PATH | split row (char esep)
    | prepend '/nix/var/nix/profiles/default/bin'
    | prepend '/run/current-system/sw/bin'
    | prepend $"/etc/profiles/per-user/($env.USER)/bin"
    | prepend $"($nu.home-path)/.nix-profile/bin"
    | prepend '/usr/local/bin/'
    | prepend '/opt/homebrew/bin'
    | prepend '/Applications/Parallels Desktop.app/Contents/MacOS/'
)

