{ config, options, pkgs, lib, ... }:

with lib;
with lib.my;
let cfg = config.modules.shell.alacritty;
    configDir = "${config.dotfiles.modulesDir}/shell/alacritty/config";
in {
  options.modules.shell.alacritty = with types; {
    enable = mkBoolOpt false;
  };

  config = mkIf cfg.enable {

    fonts.fonts = with pkgs; [
      jetbrains-mono
    ];

    home-manager.users.${config.user.name}.programs.alacritty = {
      enable = true;
      settings = {
        import = [
          "~/.config/alacritty/onedark.yml"
        ];
        background_opacity = 1.0;
        dynamic_title = true;
        font = {
          normal = {
            family = "JetBrains Mono";
            style = "Medium";
          };
          size = 20;
        };
        selection.save_to_clipboard = true;
        shell.program = "${pkgs.fish}/bin/fish";
        window = {
          decorations = "full";
          padding = {
            x = 5;
            y = 5;
          };
        };
        key_bindings = [
          { key = "C"; mods = "Command"; action = "Copy"; }
          { key = "V"; mods = "Command"; action = "Paste"; }
          { key = "K"; mods = "Command"; action = "ClearHistory"; }

          { key = "Equals"; mods = "Command"; action = "IncreaseFontSize"; }
          { key = "Plus"; mods = "Command"; action = "IncreaseFontSize"; }
          { key = "Minus"; mods = "Command"; action = "DecreaseFontSize"; }
          { key = "NumpadSubtract"; mods = "Command"; action = "DecreaseFontSize"; }
        ];
      };
    };

    home.configFile = {
      "alacritty" = { source = configDir; recursive = true; };
    };
  };
}
