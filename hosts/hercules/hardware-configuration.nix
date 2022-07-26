{ config, lib, pkgs, modulesPath, ... }:

{
  imports = [
    "${modulesPath}/installer/scan/not-detected.nix"
    #./modules/parallels-guest.nix
  ];

  #hardware.parallels = {
  #  enable = true;
  #  package = (config.boot.kernelPackages.callPackage ./modules/prl-tools.nix {});
  #};

  boot = {
    initrd.availableKernelModules = [ "ata_piix" "mptspi" "uhci_hcd" "ehci_pci" "sd_mod" "sr_mod" ];
    initrd.kernelModules = [];
    extraModulePackages = [];
    kernelModules = [ ];
  };

  environment.systemPackages = with pkgs; [
    open-vm-tools
  ];

  # virtualisation.vmware.guest.enable = true;
  #disabledModules = [ "virtualisation/parallels-guest.nix" ];

  # We expect to run the VM on hidpi machines.
  hardware.video.hidpi.enable = true;

  # Modules
  modules.hardware = {
    fs = {
      enable = false;
      ssd.enable = false;
    };
  };

  # Storage
  fileSystems = {
    "/" = {
      device = "/dev/disk/by-label/nixos";
      fsType = "ext4";
    };
    "/boot" = {
      device = "/dev/disk/by-label/boot";
      fsType = "vfat";
    };
    "/host" = {
      fsType = "fuse./run/current-system/sw/bin/vmhgfs-fuse";
      device = ".host:/";
      options = [
        "umask=22"
        "uid=1000"
        "gid=1000"
        "allow_other"
        "auto_unmount"
        "defaults"
      ];
    };
  };
  swapDevices = [];
}
