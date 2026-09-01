# modules/nixos/parallels-guest.nix -- Parallels Desktop guest plumbing
#
# virtio + virtio-gpu only. Parallels Tools on aarch64 is userspace-only (no
# kernel modules are built by nixpkgs' prl-tools), drags in an unfree ~1 GB DMG
# fetch, and its clipboard helper spawns a ghost window Hyprland tiles, so it
# stays behind an opt-in option.

{
  lib,
  config,
  ...
}:

with lib;
let
  cfg = config.modules.nixos.parallels;
in
{
  options.modules.nixos.parallels = {
    guestTools = mkEnableOption "Parallels Tools (shared folders, clipboard, dynamic resolution)";

    mtu = mkOption {
      type = types.int;
      default = 1400;
      description = "MTU for the primary NIC. Parallels' shared (NAT) network needs 1400 for Entra/Intune traffic to complete.";
    };
  };

  config = {
    hardware.parallels.enable = cfg.guestTools;

    # Parallels offers ide/scsi/sata/nvme disks (no virtio disk), so the root
    # device is SATA; networking and the GPU are virtio.
    boot.initrd.availableKernelModules = [
      "ahci"
      "sd_mod"
      "sr_mod"
      "usbhid"
      "xhci_pci"
      "virtio_pci"
      "virtio_net"
      "virtio_scsi"
    ];
    # Load the real DRM driver in the initrd so it takes the framebuffer over
    # from simpledrm before the compositor enumerates /dev/dri.
    boot.initrd.kernelModules = [ "virtio_gpu" ];

    # No boot.kernelParams: virtio-gpu needs none, and the WLR_*/nomodeset
    # incantations copied around for VMware/QEMU guests are inert on
    # aquamarine-era Hyprland (see the P9 research notes, §2).

    hardware.graphics.enable = true;

    # MTU declaratively, on the link: the spike VM lost its DHCP lease after
    # the same value was set by hand with `ip link set mtu`. UseMTU is off by
    # default in networkd's DHCPv4 client, so the lease cannot undo this.
    networking.useDHCP = false;
    networking.useNetworkd = true;
    systemd.network.networks."10-primary" = {
      matchConfig.Name = "en*";
      networkConfig.DHCP = "yes";
      linkConfig.MTUBytes = toString cfg.mtu;
    };
  };
}
