{ options, config, lib, pkgs, ... }:

with lib;
with lib.my;
let cfg = config.modules.desktop.i3;
    configDir = config.dotfiles.configDir;
in {
  options.modules.desktop.i3 = {
    enable = mkBoolOpt false;
  };

  config = mkIf cfg.enable {
    services.xserver = {
      enable = true;
      layout = "us";
      dpi = 250;

      desktopManager = {
        xterm.enable = false;
        wallpaper.mode = "scale";
      };

      displayManager = {
        defaultSession = "none+i3";
        lightdm.enable = true;

        # AARCH64: For now, on Apple Silicon, we must manually set the
        # display resolution. This is a known issue with VMware Fusion.
        sessionCommands = ''
          ${pkgs.xorg.xset}/bin/xset r rate 200 40
          ${pkgs.xorg.xrandr}/bin/xrandr -s '3840x2400'
        '';
      };

      # i3: realpath(/etc/i3/config): No such file or directory
      windowManager.i3 = {
        enable = true;
        # configFile = path "$XDG_CONFIG_HOME/i3/config";
        extraPackages = with pkgs; [
          # rofi #application launcher most people use
          i3status # gives you the default i3 status bar
          # i3blocks #if you are planning on using i3blocks over i3status
        ];
      };
    };

    #fonts = {
    #    fonts = with pkgs; [
    #      (nerdfonts.override { fonts = [ "FiraCode" "JetBrainsMono" ]; })
    #    ];
    #    fontconfig.defaultFonts = {
    #      sansSerif = ["Fira Sans"];
    #      monospace = ["JetBrains Mono"];
    #    };
    #  };

    # link recursively so other modules can link files in their folders
    #home.configFile = {
    #  "i3" = {
    #    source = "${configDir}/i3";
    #    recursive = true;
    #  };
    #};
  };
}
