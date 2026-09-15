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

  # A resize must keep the scale the host's monitor line asks for.
  scale = elemAt (splitString "," config.modules.nixos.desktop.monitor) 3;

  # `hyprctl keyword` is rejected outright by the Lua config manager ("keyword
  # can't work with non-legacy parsers. Use eval." -- src/debug/HyprCtl.cpp in
  # v0.56.2); `hyprctl eval` re-runs hl.monitor(), which merges into the
  # existing rule for that output and schedules a monitor refresh. Lua takes
  # single-quoted strings, so nothing needs escaping through the shell.
  # Coupled to modules/nixos/desktop-hyprland.nix on purpose: the two have to
  # agree on the config format.
  setMonitorMode =
    if config.modules.nixos.desktop.configFormat == "lua" then
      "hyprctl eval \"hl.monitor({ output = '${cfg.connector}', mode = '\${want}@60', position = 'auto', scale = '${scale}' })\""
    else
      "hyprctl keyword monitor \"${cfg.connector},\${want}@60,auto,${scale}\"";
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

    # The defaults are the Parallels tuning explained in the follower script.
    resizePollInterval = mkOption {
      type = types.numbers.positive;
      default = 2;
      description = "Seconds between reads of the connector's preferred mode.";
    };

    resizeStablePolls = mkOption {
      type = types.ints.unsigned;
      default = 3;
      description = "Polls in a row that must repeat the preferred mode before the follower applies it.";
    };

    resizeHysteresis = mkOption {
      type = types.ints.unsigned;
      default = 16;
      description = "Pixels, in width or height, by which the preferred mode must differ from the last applied mode before the follower applies it.";
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
            # The card index differs per hypervisor: card1 on Parallels
            # (simpledrm claims card0 first), card0 on VMware (vmwgfx).
            conn_modes() {
              local f
              for f in /sys/class/drm/card*-${cfg.connector}/modes; do
                [ -r "$f" ] && { echo "$f"; return 0; }
              done
              return 1
            }
            # Pick the Hyprland instance whose socket answers (stale dirs of
            # previous sessions linger in $XDG_RUNTIME_DIR/hypr). The loop keeps
            # the answer until that instance stops answering.
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
            # act when the host's value has been stable for resizeStablePolls
            # polls and differs from what we last applied by more than
            # resizeHysteresis px.
            #
            # An idle poll starts no process. `sleep` is the loadable builtin
            # that ships with the bash running this script, and `read` reads the
            # mode. With external commands and a lookup on every ask, a 0.5 s
            # poll started about 10 processes a second, measured 2026-09-14.
            enable -f ${pkgs.runtimeShellPackage}/lib/bash/sleep sleep ||
              echo "no loadable sleep builtin: every poll starts a sleep process"
            conn=""; sig=""; last_seen=""; stable=0; applied=""; asked=0
            while sleep ${toString cfg.resizePollInterval}; do
              if [ -z "$conn" ]; then conn="$(conn_modes)" || continue; fi
              read -r want < "$conn" || continue
              [ -n "$want" ] || continue
              if [ "$want" = "$last_seen" ]; then stable=$((stable + 1)); else stable=0; last_seen="$want"; fi
              [ "$stable" -ge ${toString cfg.resizeStablePolls} ] || continue
              # Ask Hyprland as soon as a value counts as stable, then again at
              # most every 2 s, not on every poll. The repeat undoes a config
              # reload, which sends Hyprland back to its session-start mode.
              # `hyprctl reload` and nixos-rebuild switch both did on 2026-09-14.
              [ "$stable" -eq ${toString cfg.resizeStablePolls} ] || [ $((SECONDS - asked)) -ge 2 ] || continue
              asked=$SECONDS
              if [ -z "$sig" ]; then sig="$(live_sig)" || continue; fi
              export HYPRLAND_INSTANCE_SIGNATURE="$sig"
              # A gone instance makes hyprctl print an error that jq rejects.
              # That counts as no answer: look the instance up again.
              have="$(hyprctl monitors -j 2>/dev/null | jq -r --arg c "${cfg.connector}" '.[] | select(.name==$c) | "\(.width)x\(.height)"')" || have=""
              if [ -z "$have" ]; then sig=""; continue; fi
              [ "$want" != "$have" ] || continue
              if [ -n "$applied" ]; then
                aw=''${applied%x*}; ww=''${want%x*}; ah=''${applied#*x}; wh=''${want#*x}
                dw=$((aw - ww)); dh=$((ah - wh)); dw=''${dw#-}; dh=''${dh#-}
                [ "$dw" -gt ${toString cfg.resizeHysteresis} ] || [ "$dh" -gt ${toString cfg.resizeHysteresis} ] || continue
              fi
              echo "preferred $want != current $have (stable): requesting"
              ${setMonitorMode}
              applied="$want"
            done
          '';
          serviceConfig.Restart = "always";
        };
  };
}
