{ pkgs, config, lib, ... }:
{
  imports = [
    ../home.nix
    ./hardware-configuration.nix
  ];

  virtualisation.vmware.guest.enable = true;

  users.users.andreym.hashedPassword = "$5$nw148GYjnRcBJihu$DHJVly9snAijKAKPhQKhgi/AUeHPXNpZWKey0WHp99B";

  ## Modules
  modules = {
    desktop = {
      i3.enable = true;
      browsers = {
        default = "brave";
        brave.enable = true;
      };
      rider.enable = true;
    };
    editors = {
      default = "nvim";
      vim.enable = false;
    };
    shell = {
      alacritty.enable = true;
      kitty.enable = false;
      fish.enable = true;
      rofi.enable = true;
      direnv.enable = true;
      git.enable    = true;
      gnupg.enable  = true;
      tmux.enable   = true;
    };
    services = {
      ssh.enable = true;
      docker.enable = true;
    };
  };


  ## Local config
  programs.ssh.startAgent = true;
  services.openssh.startWhenNeeded = true;

  networking.networkmanager.enable = true;
  networking.firewall.enable = false;
  # The global useDHCP flag is deprecated, therefore explicitly set to false
  # here. Per-interface useDHCP will be mandatory in the future, so this
  # generated config replicates the default behaviour.
  networking.useDHCP = false;


  ## Personal backups
  # Syncthing is a bit heavy handed for my needs, so rsync to my NAS instead.
  # systemd = {
  #   services.backups = {
  #     description = "Backup /usr/store to NAS";
  #     wants = [ "usr-drive.mount" ];
  #     path  = [ pkgs.rsync ];
  #     environment = {
  #       SRC_DIR  = "/usr/store";
  #       DEST_DIR = "/usr/drive";
  #     };
  #     script = ''
  #       rcp() {
  #         if [[ -d "$1" && -d "$2" ]]; then
  #           echo "---- BACKUPING UP $1 TO $2 ----"
  #           rsync -rlptPJ --chmod=go= --delete --delete-after \
  #               --exclude=lost+found/ \
  #               --exclude=@eaDir/ \
  #               --include=.git/ \
  #               --filter=':- .gitignore' \
  #               --filter=':- $XDG_CONFIG_HOME/git/ignore' \
  #               "$1" "$2"
  #         fi
  #       }
  #       rcp "$HOME/projects/" "$DEST_DIR/projects"
  #       rcp "$SRC_DIR/" "$DEST_DIR"
  #     '';
  #     serviceConfig = {
  #       Type = "oneshot";
  #       Nice = 19;
  #       IOSchedulingClass = "idle";
  #       User = config.user.name;
  #       Group = config.user.group;
  #     };
  #   };
  #   timers.backups = {
  #     wantedBy = [ "timers.target" ];
  #     partOf = [ "backups.service" ];
  #     timerConfig.OnCalendar = "*-*-* 00,12:00:00";
  #     timerConfig.Persistent = true;
  #   };
  # };
}
