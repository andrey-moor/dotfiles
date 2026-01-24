# modules/home/shell/ssh.nix -- SSH client configuration

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.shell.ssh;
in {
  options.modules.shell.ssh = {
    enable = mkEnableOption "SSH client configuration";
  };

  config = mkIf cfg.enable {
    home.packages = with pkgs; [
      sshpass  # Non-interactive SSH password auth
    ];

    programs.ssh = {
      enable = true;

      # Disable default config (we set everything explicitly)
      enableDefaultConfig = false;

      # Include OrbStack SSH config for VM access (macOS only)
      includes = [ "~/.orbstack/ssh/config" ];

      matchBlocks = {
        # Global defaults
        "*" = {
          extraOptions = {
            AddKeysToAgent = "yes";
            ServerAliveInterval = "60";
            ServerAliveCountMax = "3";
          };
        };

        # Personal GitHub - uses GPG auth key via gpg-agent
        "github.com" = {
          hostname = "github.com";
          user = "git";
          # No IdentitiesOnly - allow agent to offer keys
        };

        # Microsoft/Work GitHub - uses FIDO2 resident key
        "github.com-microsoft" = {
          hostname = "github.com";
          user = "git";
          identityFile = "~/.ssh/id_ed25519_sk_rk_microsoft";
          identitiesOnly = true;
        };

        # Rocinante - Linux VM (Tailscale)
        "rocinante" = {
          hostname = "100.65.74.95";
          user = "andreym";
        };
      };
    };
  };
}
