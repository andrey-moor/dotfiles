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
  pkgs,
  ...
}:

with lib;
let
  cfg = config.modules.nixos.vmGuest;

  # `hyprctl keyword` is rejected outright by the Lua config manager ("keyword
  # can't work with non-legacy parsers. Use eval." -- src/debug/HyprCtl.cpp in
  # v0.56.2); `hyprctl eval` re-runs hl.monitor(), which merges into the
  # existing rule for that output and schedules a monitor refresh. Lua takes
  # single-quoted strings, so nothing needs escaping through the shell.
  # Coupled to modules/nixos/desktop-hyprland.nix on purpose: the two have to
  # agree on the config format.
  setMonitorMode =
    if config.modules.nixos.desktop.configFormat == "lua" then
      "hyprctl eval \"hl.monitor({ output = '${cfg.connector}', mode = '\${want}@60', position = 'auto', scale = '1' })\""
    else
      "hyprctl keyword monitor \"${cfg.connector},\${want}@60,auto,1\"";
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
          path = [
            pkgs.jq
            config.programs.hyprland.package
          ];
          script = ''
            conn=/sys/class/drm/card1-${cfg.connector}/modes
            # Pick the Hyprland instance whose socket answers (stale dirs of
            # previous sessions linger in $XDG_RUNTIME_DIR/hypr).
            live_sig() {
              local d
              for d in "$XDG_RUNTIME_DIR"/hypr/*/; do
                [ -S "$d.socket.sock" ] || continue
                if HYPRLAND_INSTANCE_SIGNATURE="$(basename "$d")" timeout 2 hyprctl version >/dev/null 2>&1; then
                  basename "$d"; return 0
                fi
              done
              return 1
            }
            # Debounce + hysteresis: Parallels reports a preferred mode 8 px
            # narrower after every mode we apply, so chasing each change is a
            # feedback loop (seen 2026-09-02: 1064 -> 1056 -> ... -> 1024). Only
            # act when the host's value has been stable for 3 polls and differs
            # from what we last applied by more than 16 px.
            last_seen=""; stable=0; applied=""
            while sleep 2; do
              [ -r "$conn" ] || continue
              want="$(head -n1 "$conn")"
              [ -n "$want" ] || continue
              if [ "$want" = "$last_seen" ]; then stable=$((stable + 1)); else stable=0; last_seen="$want"; fi
              [ "$stable" -ge 3 ] || continue
              sig="$(live_sig)" || continue
              export HYPRLAND_INSTANCE_SIGNATURE="$sig"
              have="$(hyprctl monitors -j 2>/dev/null | jq -r --arg c "${cfg.connector}" '.[] | select(.name==$c) | "\(.width)x\(.height)"')"
              [ -n "$have" ] && [ "$want" != "$have" ] || continue
              if [ -n "$applied" ]; then
                aw=''${applied%x*}; ww=''${want%x*}; ah=''${applied#*x}; wh=''${want#*x}
                dw=$((aw - ww)); dh=$((ah - wh)); dw=''${dw#-}; dh=''${dh#-}
                [ "$dw" -gt 16 ] || [ "$dh" -gt 16 ] || continue
              fi
              echo "preferred $want != current $have (stable): requesting"
              ${resizeCommand}
              applied="$want"
            done
          '';
          serviceConfig.Restart = "always";
        };
  };
}
