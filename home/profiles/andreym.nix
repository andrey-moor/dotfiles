# home/profiles/andreym.nix -- User-specific configuration for andreym
#
# Imported by home/core.nix: every host is this user's.

{ lib, config, pkgs, ... }:

with lib;
{
  config = {
    # User-specific packages (Linux only - macOS uses Homebrew for GUI apps)
    home.packages = with pkgs; optionals pkgs.stdenv.isLinux [
      ghostty  # Preferred terminal (on macOS, managed via Homebrew cask)
    ];

    # Git configuration for this user. SSH signing via 1Password on every
    # host (home/shell/onepassword.nix is in core).
    modules.shell.git = {
      userName = "Andrey Moor";
      userEmail = "m@andreym.com";
      signingFormat = "ssh";
      signingKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICdtwwW6A7j8vesJzYxp06VugC0Go+q1rBCbTXbCzSfs";
      signer = config.modules.shell.onepassword.signer;
    };

    # Per-org git identity + signing key (1Password SSH keys)
    programs.git.includes = [
      {
        condition = "gitdir:~/Documents/microsoft/";
        contents = {
          user.email = "amoor@microsoft.com";
          user.signingKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJIvYOLXV0u6EZgw96emCgaMBCYGQLkiW7lJKmYZTfc/";
          url."git@github.com-microsoft:".insteadOf = "git@github.com:";
        };
      }
      {
        condition = "gitdir:~/Documents/linkedin/";
        contents = {
          user.email = "amoor@linkedin.com";
          user.signingKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJtI2UYmOcRkM+PrENRzpRB+4Nzj1Xj8/7tsXfHelBhY";
          url."git@github.com-linkedin:".insteadOf = "git@github.com:";
        };
      }
    ];

    # Jujutsu VCS (inherits from git config or override here)
    # modules.dev.jj is already configured with same defaults
  };
}
