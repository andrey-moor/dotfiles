# home/shell/lazygit.nix -- Lazygit TUI configuration

{
  programs.lazygit = {
    enable = true;
    settings = {
      gui = {
        theme = {
          lightTheme = false;
        };
      };
    };
  };
}
