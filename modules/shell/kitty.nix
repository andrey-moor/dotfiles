{ config, options, pkgs, lib, ... }:

with lib;
with lib.my;
let cfg = config.modules.shell.kitty;
    configDir = config.dotfiles.configDir;
in {
  options.modules.shell.kitty = with types; {
    enable = mkBoolOpt false;
  };

  config = mkIf cfg.enable {

    home-manager.users.${config.user.name}.programs.kitty = {
      enable = true;
      extraConfig = builtins.readFile "${configDir}/kitty/kitty.conf";
    };

    # home-manager.users.${config.user.name}.programs.alacritty = {
    #   enable = true;

    #   settings = {
    #     env.TERM = "xterm-256color";

    #     key_bindings = [
    #       { key = "K"; mods = "Command"; chars = "ClearHistory"; }
    #       { key = "V"; mods = "Command"; action = "Paste"; }
    #       { key = "C"; mods = "Command"; action = "Copy"; }
    #       { key = "Key0"; mods = "Command"; action = "ResetFontSize"; }
    #       { key = "Equals"; mods = "Command"; action = "IncreaseFontSize"; }
    #       { key = "Subtract"; mods = "Command"; action = "DecreaseFontSize"; }
    #     ];
    #   };
    # };

    # home.configFile = {
    #   # Write it recursively so other modules can write files to it
    #   "kitty" = { source = "${configDir}/kitty"; recursive = true; };
    # };
  };
}