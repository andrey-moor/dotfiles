{ config, lib, ... }:
{
  imports = [
    ../home.nix
    ./hardware-configuration.nix
    ./modules/user.nix
    ./modules/vmware-guest.nix
  ];

  virtualisation.vmware.guest.enable = true;

  # Disable the default module and import our override. We have
  # customizations to make this work on aarch64.
  disabledModules = [ "virtualisation/vmware-guest.nix" ];

  boot.kernelPatches = [
    # https://github.com/NixOS/nixpkgs/pull/140587
    # This will be unnecessary in a bit.
    {
      name = "efi-initrd-support";
      patch = null;
      extraConfig = ''
        EFI_GENERIC_STUB_INITRD_CMDLINE_LOADER y
      '';
    }

    # I don't know why this is necessary. This worked WITHOUT this
    # at one point, and then suddenly started requiring it. I need to
    # figure this out.
    {
      name = "fix-kernel-build";
      patch = null;
      extraConfig = ''
        DRM_SIMPLEDRM n
      '';
    }
  ];

  ## Modules
  modules = {
    desktop = {
      i3.enable = true;
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
      kitty.enable = false;
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
  programs.ssh.startAgent = true;
  services.openssh.startWhenNeeded = true;

  networking.networkmanager.enable = true;
  networking.firewall.enable = false;
  # The global useDHCP flag is deprecated, therefore explicitly set to false
  # here. Per-interface useDHCP will be mandatory in the future, so this
  # generated config replicates the default behaviour.
  networking.useDHCP = false;
}
