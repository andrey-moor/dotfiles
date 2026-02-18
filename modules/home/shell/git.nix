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
      description = "GPG key ID for signing commits and tags";
    };
  };

  config = mkIf cfg.enable {
    programs.git = {
      enable = true;
      lfs.enable = true;

      signing = mkIf (cfg.signingKey != "") {
        key = cfg.signingKey;
        signByDefault = true;
      };

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
