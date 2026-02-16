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

      # Use the new profiles API (home-manager 24.11+)
      profiles.default = {
        # Extensions managed by Nix
        # Find more at: https://search.nixos.org/packages?query=vscode-extensions
        extensions = with pkgs.vscode-extensions; [
          # Theme
          catppuccin.catppuccin-vsc
          catppuccin.catppuccin-vsc-icons

          # Containers
          ms-vscode-remote.remote-containers
          ms-azuretools.vscode-docker

          # Languages
          ms-python.python
          hashicorp.terraform
        ] ++ optionals pkgs.stdenv.isLinux [
          ms-vscode.cpptools  # gdb dependency broken on macOS
        ] ++ [
          # Kubernetes
          ms-kubernetes-tools.vscode-kubernetes-tools
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
  };
}
