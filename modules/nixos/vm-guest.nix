# modules/nixos/vm-guest.nix -- hypervisor-agnostic virtio guest support
#
# Everything here holds for any virtio/virtio-gpu hypervisor (Parallels today,
# UTM/QEMU later): the initrd modules that bring the real DRM driver up before
# the compositor, the graphics stack, and the resize follower that keeps
# Hyprland's mode in step with the host window. Hypervisor-specific plumbing
# lives next door in parallels-guest.nix, which imports this file.

{
  lib,
  config,
  ...
}:

with lib;
let
  cfg = config.modules.nixos.vmGuest;
in
{
  options.modules.nixos.vmGuest = {
    connector = mkOption {
      type = types.str;
      default = "Virtual-1";
      description = "DRM connector virtio-gpu exposes. Same name under Parallels and QEMU.";
    };

    followResize = mkOption {
      type = types.bool;
      default = true;
      description = "Poll the connector's preferred mode and hand it to Hyprland, so the guest follows host window resizes.";
    };
  };

  config = {
    # Root device is SATA (Parallels offers ide/scsi/sata/nvme, no virtio disk);
    # networking and the GPU are virtio.
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

    # Dynamic resolution: on a host window resize the hypervisor updates the
    # virtio-gpu connector's preferred mode in sysfs but emits no hotplug event,
    # so Hyprland keeps its stale mode list. Poll the preferred mode and request
    # it. (Parallels' own prlcc cannot help on Wayland -- it uses xrandr.)
    systemd.user.services.virtio-gpu-resize =
      mkIf (cfg.followResize && config.programs.hyprland.enable)
        {
          description = "Follow the hypervisor window size (virtio-gpu preferred mode -> Hyprland)";
          partOf = [ "hyprland-session.target" ];
          wantedBy = [ "hyprland-session.target" ];
          after = [ "hyprland-session.target" ];
          path = [ config.programs.hyprland.package ];
          script = ''
            conn=/sys/class/drm/card1-${cfg.connector}/modes
            last=""
            while sleep 1; do
              [ -r "$conn" ] || continue
              want="$(head -n1 "$conn")"
              [ -n "$want" ] && [ "$want" != "$last" ] || continue
              sig="$(ls -t "$XDG_RUNTIME_DIR/hypr" 2>/dev/null | head -n1)"
              [ -n "$sig" ] || continue
              HYPRLAND_INSTANCE_SIGNATURE="$sig" hyprctl keyword monitor "${cfg.connector},''${want}@60,auto,1" >/dev/null && last="$want"
            done
          '';
          serviceConfig.Restart = "always";
        };
  };
}
