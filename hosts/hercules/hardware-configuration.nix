{ config, lib, pkgs, modulesPath, ... }:

{
  imports = [
    "${modulesPath}/installer/scan/not-detected.nix"
  ];

  boot = {
    initrd.availableKernelModules = [ "ata_piix" "mptspi" "uhci_hcd" "ehci_pci" "sd_mod" "sr_mod" ];
    initrd.kernelModules = [];
    extraModulePackages = [];
    kernelModules = [ ];
  };

  environment.systemPackages = with pkgs; [
    open-vm-tools
  ];

  virtualisation.vmware.guest.enable = true;

  # We expect to run the VM on hidpi machines.
  hardware.video.hidpi.enable = true;

  # Modules
  modules.hardware = {
    fs = {
      enable = false;
      ssd.enable = false;
    };
  };

  # CPU
  # nix.maxJobs = lib.mkDefault 16;
  # powerManagement.cpuFreqGovernor = "performance";
  # hardware.cpu.amd.updateMicrocode = true;

  # Displays
  # services.xserver = {
  #   # This must be done manually to ensure my screen spaces are arranged exactly
  #   # as I need them to be *and* the correct monitor is "primary". Using
  #   # xrandrHeads does not work.
  #   monitorSection = ''
  #     VendorName  "Unknown"
  #     ModelName   "DELL U2515H"
  #     HorizSync   30.0 - 113.0
  #     VertRefresh 56.0 - 86.0
  #     Option      "DPMS"
  #   '';
  #   screenSection = ''
  #     Option "metamodes" "HDMI-0: nvidia-auto-select +1920+0, DVI-I-1: nvidia-auto-select +0+180, DVI-D-0: nvidia-auto-select +4480+180"
  #     Option "SLI" "Off"
  #     Option "MultiGPU" "Off"
  #     Option "BaseMosaic" "off"
  #     Option "Stereo" "0"
  #     Option "nvidiaXineramaInfoOrder" "DFP-1"
  #   '';
  # };

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
