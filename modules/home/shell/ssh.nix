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
    ] ++ optionals stdenv.isLinux [
      lxqt.lxqt-openssh-askpass
    ];

    home.sessionVariables = mkIf pkgs.stdenv.isLinux {
      SSH_ASKPASS = "${pkgs.lxqt.lxqt-openssh-askpass}/bin/lxqt-openssh-askpass";
      SSH_ASKPASS_REQUIRE = "prefer";
    };

    home.file.".ssh/sockets/.keep".text = "";

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
            ControlMaster = "auto";
            ControlPath = "~/.ssh/sockets/%r@%n-%p";
            ControlPersist = "600";
          };
        };

        # Personal GitHub - uses GPG auth key via gpg-agent
        "github.com" = {
          hostname = "github.com";
          user = "git";
          # No IdentitiesOnly - allow agent to offer keys
        };

        # Microsoft/Work GitHub - uses FIDO2 resident key on YubiKey Nano
        "github.com-microsoft" = {
          hostname = "github.com";
          user = "git";
          identityFile = "~/.ssh/id_ed25519_sk_rk_microsoft_nano";
          identitiesOnly = true;
        };

        # LinkedIn/Work GitHub - uses FIDO2 resident key on YubiKey
        "github.com-linkedin" = {
          hostname = "github.com";
          user = "git";
          identityFile = "~/.ssh/id_ed25519_sk_rk_linkedin";
          identitiesOnly = true;
        };

        # Rocinante - Linux VM (Tailscale MagicDNS)
        "rocinante" = {
          user = "andreym";
        };
      };
    };
  };
}
