# home/dev/jj.nix -- Jujutsu (jj) version control

{ pkgs, ... }:

{
  programs.jujutsu = {
    enable = true;
    settings = {
      user = {
        name = "Andrey Moor";
        email = "m@andreym.com";
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
