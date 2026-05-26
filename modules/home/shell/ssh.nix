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

      # `programs.ssh.settings` replaces the deprecated `matchBlocks`. Keys
      # without `Host `/`Match ` prefix become `Host <key>`; we use the
      # `header` field to render literal `Match …` blocks while keeping
      # short attribute names for DAG ordering. `IdentityAgent` is first-
      # match-wins in ssh_config(5), so the 1P/forwarded Match blocks must
      # render BEFORE the `github.com*` Host blocks — enforced via
      # `lib.hm.dag.entryBefore`.
      settings = {
        # Global defaults
        "*" = {
          AddKeysToAgent = "yes";
          ServerAliveInterval = "60";
          ServerAliveCountMax = "3";
          ControlMaster = "auto";
          ControlPath = "~/.ssh/sockets/%r@%n-%p";
          ControlPersist = "600";
        };

        # Linux + 1P only: route GitHub auth to the LOCAL 1Password SSH agent
        # when it's responsive, with the forwarded SSH_AUTH_SOCK as fallback.
        # Effect:
        #   * Local 1P unlocked → no behemoth round-trip, no Touch-ID prompt.
        #   * Local 1P locked / agent down + behemoth SSH agent reachable →
        #     falls through to forwarded agent (current pre-2026-05-07 behavior).
        #   * Both unavailable → auth fails (expected; unlock something).
        "00-github-local-1p" = mkIf (op && pkgs.stdenv.isLinux) (
          lib.hm.dag.entryBefore [ "github.com" "github.com-microsoft" "github.com-linkedin" ] {
            header = ''Match host github.com,github.com-microsoft,github.com-linkedin exec "test -S ~/.1password/agent.sock && timeout 1 env SSH_AUTH_SOCK=~/.1password/agent.sock ssh-add -l >/dev/null 2>&1"'';
            IdentityAgent = "~/.1password/agent.sock";
          }
        );

        "01-github-forwarded-fallback" = mkIf (op && pkgs.stdenv.isLinux) (
          lib.hm.dag.entryBefore [ "github.com" "github.com-microsoft" "github.com-linkedin" ] {
            header = ''Match host github.com,github.com-microsoft,github.com-linkedin exec "test -n \"$SSH_AUTH_SOCK\" && timeout 1 ssh-add -l >/dev/null 2>&1"'';
            IdentityAgent = "$SSH_AUTH_SOCK";
          }
        );

        # Personal GitHub
        "github.com" = {
          HostName = "github.com";
          User = "git";
        } // optionalAttrs op {
          IdentityFile = "~/.ssh/1p_personal.pub";
          IdentitiesOnly = "yes";
        };

        # Microsoft/Work GitHub
        "github.com-microsoft" = {
          HostName = "github.com";
          User = "git";
          IdentitiesOnly = "yes";
          IdentityFile = if op
            then "~/.ssh/1p_microsoft.pub"
            else "~/.ssh/id_ed25519_sk_rk_microsoft_nano";
        };

        # LinkedIn/Work GitHub
        "github.com-linkedin" = {
          HostName = "github.com";
          User = "git";
          IdentitiesOnly = "yes";
          IdentityFile = if op
            then "~/.ssh/1p_linkedin.pub"
            else "~/.ssh/id_ed25519_sk_rk_linkedin";
        };

        # Rocinante - Linux workstation (Tailscale MagicDNS)
        "rocinante" = {
          User = "andreym";
        } // optionalAttrs op {
          ForwardAgent = "yes";
        };

        # Stargazer - Linux VM (Parallels)
        "stargazer" = {
          User = "andreym";
        } // optionalAttrs op {
          ForwardAgent = "yes";
        };
      };
    };
  };
}
