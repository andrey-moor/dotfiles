# modules/home/shell/ssh.nix -- SSH client configuration

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.shell.ssh;
  op = config.modules.shell.onepassword.enable;
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

    # Stable symlink for forwarded SSH agent (survives tmux reattach).
    # On each SSH login, ~/.ssh/rc re-links ~/.ssh/agent.sock to the new
    # ephemeral forwarded socket.  Shell init (env.nu) sets SSH_AUTH_SOCK
    # to the symlink, so even long-running tmux panes follow the update.
    home.file.".ssh/rc" = mkIf pkgs.stdenv.isLinux {
      text = ''
        #!/bin/bash
        if [ -n "$SSH_AUTH_SOCK" ] && [ "$SSH_AUTH_SOCK" != "$HOME/.ssh/agent.sock" ]; then
          ln -sf "$SSH_AUTH_SOCK" "$HOME/.ssh/agent.sock"
        fi
      '';
      executable = true;
    };

    programs.ssh = {
      enable = true;

      # Disable default config (we set everything explicitly)
      enableDefaultConfig = false;

      # Include OrbStack SSH config for VM access (macOS only)
      includes = [
        "~/.orbstack/ssh/config"
        "~/.ssh/extra_config"
      ];

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

        # Personal GitHub
        "github.com" = {
          hostname = "github.com";
          user = "git";
        } // optionalAttrs op {
          identityFile = "~/.ssh/1p_personal.pub";
          identitiesOnly = true;
        };

        # Microsoft/Work GitHub
        "github.com-microsoft" = {
          hostname = "github.com";
          user = "git";
          identitiesOnly = true;
          identityFile = if op
            then "~/.ssh/1p_microsoft.pub"
            else "~/.ssh/id_ed25519_sk_rk_microsoft_nano";
        };

        # LinkedIn/Work GitHub
        "github.com-linkedin" = {
          hostname = "github.com";
          user = "git";
          identitiesOnly = true;
          identityFile = if op
            then "~/.ssh/1p_linkedin.pub"
            else "~/.ssh/id_ed25519_sk_rk_linkedin";
        };

        # Rocinante - Linux workstation (Tailscale MagicDNS)
        "rocinante" = {
          user = "andreym";
        } // optionalAttrs op {
          forwardAgent = true;
        };

        # Stargazer - Linux VM (Parallels)
        "stargazer" = {
          user = "andreym";
        } // optionalAttrs op {
          forwardAgent = true;
        };
      };
    };
  };
}
