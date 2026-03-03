# modules/home/profiles/andreym.nix -- User-specific configuration for andreym

{ lib, config, pkgs, ... }:

with lib;
{
  config = mkIf (config.modules.profiles.user == "andreym") {
    # User-specific packages (Linux only - macOS uses Homebrew for GUI apps)
    home.packages = with pkgs; optionals pkgs.stdenv.isLinux [
      ghostty  # Preferred terminal (on macOS, managed via Homebrew cask)
    ];

    # Git configuration for this user
    modules.shell.git = {
      userName = "Andrey Moor";
      userEmail = "m@andreym.com";
    } // (if config.modules.shell.onepassword.enable then {
      # SSH signing via 1Password (Linux hosts without YubiKey)
      signingFormat = "ssh";
      signingKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICdtwwW6A7j8vesJzYxp06VugC0Go+q1rBCbTXbCzSfs";
      signer = config.modules.shell.onepassword.signer;
    } else {
      # GPG signing via YubiKey (macOS)
      signingKey = "622041A533BA5D69";
    });

    # Per-org git identity + signing key (1Password SSH keys)
    programs.git.includes = mkIf config.modules.shell.onepassword.enable [
      {
        condition = "gitdir:~/Documents/microsoft/";
        contents = {
          user.email = "amoor@microsoft.com";
          user.signingKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJIvYOLXV0u6EZgw96emCgaMBCYGQLkiW7lJKmYZTfc/";
          core.sshCommand = "ssh -i ~/.ssh/1p_microsoft.pub -o IdentitiesOnly=yes";
        };
      }
      {
        condition = "gitdir:~/Documents/linkedin/";
        contents = {
          user.email = "amoor@linkedin.com";
          user.signingKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJtI2UYmOcRkM+PrENRzpRB+4Nzj1Xj8/7tsXfHelBhY";
          core.sshCommand = "ssh -i ~/.ssh/1p_linkedin.pub -o IdentitiesOnly=yes";
        };
      }
    ];

    # Jujutsu VCS (inherits from git config or override here)
    # modules.dev.jj is already configured with same defaults
  };
}
