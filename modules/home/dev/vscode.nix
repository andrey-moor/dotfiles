# modules/home/dev/vscode.nix -- Visual Studio Code with extensions

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.dev.vscode;
in {
  options.modules.dev.vscode = {
    enable = mkEnableOption "Visual Studio Code";
  };

  config = mkIf cfg.enable {
    programs.vscode = {
      enable = true;

      # Extensions managed by Nix
      # Find more at: https://search.nixos.org/packages?query=vscode-extensions
      extensions = with pkgs.vscode-extensions; [
        # Theme
        catppuccin.catppuccin-vsc
        catppuccin.catppuccin-vsc-icons

        # Language support examples (uncomment as needed)
        # golang.go
        # rust-lang.rust-analyzer
        # ms-python.python
        # jnoortheen.nix-ide
      ];

      # Settings managed by Nix
      userSettings = {
        # Catppuccin theme configuration
        "workbench.colorTheme" = "Catppuccin Mocha";
        "workbench.iconTheme" = "catppuccin-mocha";

        # Editor appearance
        "editor.fontFamily" = "'JetBrainsMono Nerd Font', monospace";
        "editor.fontSize" = 14;
        "editor.lineNumbers" = "relative";
        "editor.cursorBlinking" = "solid";
        "editor.cursorStyle" = "block";

        # Editor behavior
        "editor.formatOnSave" = true;
        "editor.tabSize" = 2;
        "editor.insertSpaces" = true;

        # Terminal
        "terminal.integrated.fontFamily" = "'JetBrainsMono Nerd Font'";

        # Disable telemetry
        "telemetry.telemetryLevel" = "off";
      };
    };
  };
}
