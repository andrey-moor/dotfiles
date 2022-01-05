{ options, config, lib, pkgs, ... }:

with lib;
with lib.my;
let cfg = config.modules.desktop.bspwm;
    #configDir = config.dotfiles.configDir;
    configDir = "${config.dotfiles.modulesDir}/desktop";
in {
  options.modules.desktop.bspwm = {
    enable = mkBoolOpt false;
  };

  config = mkIf cfg.enable {
    #modules.theme.onReload.bspwm = ''
    #  ${pkgs.bspwm}/bin/bspc wm -r
    #  source $XDG_CONFIG_HOME/bspwm/bspwmrc
    #'';

    environment.systemPackages = with pkgs; [
      lightdm
      (polybar.override {
        pulseSupport = false;
        nlSupport = false;
      })
    ];

    services = {
      picom.enable = false;
      #redshift.enable = true;
      xserver = {
        enable = true;
        displayManager = {
          defaultSession = "none+bspwm";
          lightdm.enable = true;
          lightdm.greeters.mini.enable = false;

          # AARCH64: For now, on Apple Silicon, we must manually set the
          # display resolution. This is a known issue with VMware Fusion.
          sessionCommands = ''
            ${pkgs.xlibs.xset}/bin/xset r rate 200 40
            ${pkgs.xorg.xrandr}/bin/xrandr -s '3840x2400'
          '';

        };
        #windowManager.bspwm.enable = true;
        windowManager = {
          bspwm.enable = true;
        };
      };
    };

    #systemd.user.services."dunst" = {
    #  enable = true;
    #  description = "";
    #  wantedBy = [ "default.target" ];
    #  serviceConfig.Restart = "always";
    #  serviceConfig.RestartSec = 2;
    #  serviceConfig.ExecStart = "${pkgs.dunst}/bin/dunst";
    #};
    
    # link recursively so other modules can link files in their folders
    home.configFile = {
      "sxhkd".source = "${configDir}/sxhkd/config";
      "bspwm/rc.d/polybar".source = ./config/polybar;
      "bspwm/rc.d/theme".source = ./config/bspwm_theme;
      "bspwm" = {
        source = "${configDir}/bspwm/config";
        recursive = true;
      };
      "polybar" = { source = ./polybar/config; recursive = true; };
    };
  };
}
