# modules/home/dev/jj.nix -- Jujutsu (jj) version control

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.jj;
in {
  options.modules.dev.jj = {
    enable = mkEnableOption "Jujutsu (jj) version control";
    userName = mkOption {
      type = types.str;
      default = "Andrey Moor";
      description = "User name for jj commits";
    };
    userEmail = mkOption {
      type = types.str;
      default = "m@andreym.com";
      description = "User email for jj commits";
    };
  };

  config = mkIf cfg.enable {
    programs.jujutsu = {
      enable = true;
      settings = {
        user = {
          name = cfg.userName;
          email = cfg.userEmail;
        };
        ui = {
          # Use delta for diffs if available
          diff.tool = [ "delta" "--color-only" ];
          pager = "delta";
        };
      };
    };

    # Delta for better diffs
    home.packages = with pkgs; [
      delta
    ];
  };
}
