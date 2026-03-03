# modules/home/shell/git.nix -- Git configuration (home-manager)

{
  lib,
  config,
  pkgs,
  ...
}:

with lib;
let
  cfg = config.modules.shell.git;

  # GCM wrapper: sets env vars for device code flow + credential cache,
  # and redirects GIT_CONFIG_GLOBAL to a writable file so GCM can cache
  # Azure AD authority info (it runs `git config --global` internally).
  # The writable file includes the nix-managed config via [include].
  gcm-azure = pkgs.writeShellScript "git-credential-manager-azure" ''
    export GCM_CREDENTIAL_STORE=cache
    export GCM_MSAUTH_FLOW=auto
    export GCM_AZREPOS_CREDENTIALTYPE=oauth

    gcm_config="$HOME/.config/git/gcm-config"
    nix_config="$HOME/.config/git/config"
    if [ ! -f "$gcm_config" ]; then
      printf '[include]\n\tpath = %s\n' "$nix_config" > "$gcm_config"
    fi
    export GIT_CONFIG_GLOBAL="$gcm_config"

    exec ${pkgs.git-credential-manager}/bin/git-credential-manager "$@"
  '';
in
{
  options.modules.shell.git = {
    enable = mkEnableOption "Git configuration";
    userName = mkOption {
      type = types.str;
      default = "Andrey M";
    };
    userEmail = mkOption {
      type = types.str;
      default = "";
    };
    signingKey = mkOption {
      type = types.str;
      default = "";
      description = "GPG key ID or SSH public key for signing commits and tags";
    };
    signingFormat = mkOption {
      type = types.nullOr (types.enum [ "openpgp" "ssh" "x509" ]);
      default = null;
      description = "Signing format (openpgp for GPG, ssh for 1Password/SSH keys)";
    };
    signer = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Path to signing program (e.g. /opt/1Password/op-ssh-sign)";
    };
  };

  config = mkIf cfg.enable {
    programs.git = {
      enable = true;
      lfs.enable = true;

      signing = mkIf (cfg.signingKey != "") ({
        key = cfg.signingKey;
        signByDefault = true;
      } // optionalAttrs (cfg.signingFormat != null) {
        format = cfg.signingFormat;
      } // optionalAttrs (cfg.signer != null) {
        signer = cfg.signer;
      });

      settings = {
        user = {
          name = cfg.userName;
          email = cfg.userEmail;
        };
        init.defaultBranch = "main";
        pull.rebase = true;
        push.autoSetupRemote = true;
        core.autocrlf = "input";
        diff.algorithm = "histogram";
        merge.conflictStyle = "diff3";
        tag.gpgSign = cfg.signingKey != "";
        credential."https://dev.azure.com" = {
          useHttpPath = true;
          helper = toString gcm-azure;
        };
        alias = {
          st = "status";
          co = "checkout";
          br = "branch";
          ci = "commit";
          lg = "log --oneline --graph --decorate";
        };
      };
    };

    home.packages = with pkgs; [
      gh # GitHub CLI
      github-copilot-cli # GitHub Copilot extension for gh
      git-crypt # Transparent file encryption
    ];
  };
}
