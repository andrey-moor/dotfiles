{ config, lib, ... }:
{
  imports = [
    ../home.nix
    ./hardware-configuration.nix
    ./modules/vmware-guest.nix
  ];

  virtualisation.vmware.guest.enable = true;

  # Disable the default module and import our override. We have
  # customizations to make this work on aarch64.
  disabledModules = [ "virtualisation/vmware-guest.nix" ];

  ## Modules
  modules = {
    theme.active = "nord";
    desktop = {
      bspwm.enable = true;
      i3.enable = false;
      browsers = {
        default = "brave";
        brave.enable = true;
      };
      rider.enable = false;
    };
    editors = {
      default = "nvim";
      vim.enable = false;
    };
    shell = {
      alacritty.enable = true;
      kitty.enable = true;
      fish.enable = true;
      rofi.enable = true;
      direnv.enable = true;
      git.enable    = true;
      gnupg.enable  = true;
      tmux.enable   = true;
      neovim.enable   = true;
    };
    services = {
      ssh.enable = true;
      docker.enable = true;
    };
  };
  
  ## Local config
  # programs.ssh.startAgent = true;
  services.openssh.startWhenNeeded = true;

  #services.gpg-agent = {
  #  enable = true;
  #  pinentryFlavor = "tty";

  #  # cache the keys forever so we don't get asked for a password
  #  defaultCacheTtl = 31536000;
  #  maxCacheTtl = 31536000;
  #};

  services.pcscd.enable = true;



  networking.networkmanager.enable = true;
  networking.firewall.enable = false;
  # The global useDHCP flag is deprecated, therefore explicitly set to false
  # here. Per-interface useDHCP will be mandatory in the future, so this
  # generated config replicates the default behaviour.
  # M1
  networking.useDHCP = false;
  #networking.interfaces.ens160.useDHCP = true;
}
