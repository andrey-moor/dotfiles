# home/dev/jj.nix -- Jujutsu (jj) version control

{ config, pkgs, ... }:

{
  programs.jujutsu = {
    enable = true;
    settings = {
      # The identity is set once, in home/profiles/andreym.nix.
      user = {
        name = config.modules.shell.git.userName;
        email = config.modules.shell.git.userEmail;
      };
      ui = {
        # Use delta for diffs if available
        diff.tool = [
          "delta"
          "--color-only"
        ];
        pager = "delta";
      };
    };
  };

  # Delta for better diffs
  home.packages = with pkgs; [
    delta
  ];
}
