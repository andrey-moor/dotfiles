# modules/nixos/vmware-guest.nix -- VMware Fusion (Apple silicon) guest specifics
#
# Imports the hypervisor-agnostic vm-guest.nix and adds what Fusion needs.
# stargazer's hypervisor layer since 2026-09. docs/vmware-fusion-workarounds.md
# records why each piece exists.
#
# What matters on Fusion:
#   - Graphics: vmwgfx (SVGA3D, OpenGL 4.3). The DRM
#     connector is still "Virtual-1". On window resize Fusion sends
#     `Resolution_Set` to open-vm-tools, which updates the connector's
#     preferred mode, but Hyprland does not switch to it on its own (tested
#     2026-09-14). The virtio-gpu-resize follower from vm-guest.nix does that
#     job here too, so it stays on (its default).
#   - NIC: vmxnet3 (or e1000e), DHCP on a normal LAN/NAT lease.
#   - Disk: NVMe (hosts/stargazer/disko.nix).
#   - Tools: open-vm-tools (shared folders via vmhgfs-fuse, time sync,
#     resolution, copy/paste). The copy/paste agent speaks X11, so it runs
#     against XWayland (see `headless` below).

{
  config,
  lib,
  pkgs,
  ...
}:

{
  imports = [ ./vm-guest.nix ];

  # Without this patch Hyprland rejects every GPU client buffer on vmwgfx
  # (alacritty, hardware-rendered ghostty, GTK4 GL apps), while shared-memory
  # clients such as waybar and mako still work. Provenance and review notes are
  # in the patch header. The version check turns a nixpkgs Hyprland bump into
  # an evaluation error, not a silently failing patch or an unpatched session.
  programs.hyprland.package =
    lib.throwIfNot (pkgs.hyprland.version == "0.56.2")
      "modules/nixos/vmware-guest.nix: the vmwgfx DMA-BUF patch targets Hyprland 0.56.2, but nixpkgs now has ${pkgs.hyprland.version}. Check Hyprland discussion #12966 for an upstream fix, then update or drop the patch."
      (
        pkgs.hyprland.overrideAttrs (old: {
          patches = (old.patches or [ ]) ++ [ ./patches/hyprland-0.56.2-vmwgfx-dmabuf.patch ];
        })
      );

  # Fusion reports each window size once and exactly. Measured 2026-09-14:
  # one apply per resize and no drift after a mode change. The Parallels
  # debounce only adds delay here, about 8 s per resize. These values follow a
  # resize in about 1 s.
  modules.nixos.vmGuest = {
    resizePollInterval = 0.5;
    resizeStablePolls = 1;
    resizeHysteresis = 0;
  };

  virtualisation.vmware.guest.enable = true;
  # The module's `headless` default is `!services.xserver.enable`, which is
  # always true under Hyprland, and headless drops vmware-user: the
  # copy/paste agent. It speaks X11, so it runs against XWayland, and the
  # clipboard bridge below carries its text to Wayland clients.
  virtualisation.vmware.guest.headless = false;
  # The module starts that agent from an X display manager's session commands,
  # which greetd never runs, so the Hyprland session starts it instead.
  modules.nixos.desktop.extraExecOnce = [ "${config.security.wrapperDir}/vmware-user-suid-wrapper" ];

  # Hyprland lets an X11 client reach the Wayland clipboard only while an X11
  # window has focus (src/xwayland/XWM.cpp in 0.56.2: "denying access to write
  # to clipboard because no X client is in focus", "Ignoring clipboard access:
  # xwayland not in focus"). The agent has no window, so copies in both
  # directions stopped at XWayland (seen 2026-09-15). This bridge copies text
  # between the X11 CLIPBOARD and the Wayland clipboard itself. X11 clients can
  # read each other's selections, and wl-clipboard's data-control protocol
  # needs no focus. The cost: on this host any X11 client can read text copied
  # in a Wayland app. Copies a password manager marks sensitive stay put.
  systemd.user.services.vmware-clipboard-bridge = {
    description = "Copy text between the VMware agent's X11 clipboard and the Wayland clipboard";
    partOf = [ "hyprland-session.target" ];
    wantedBy = [ "hyprland-session.target" ];
    after = [ "hyprland-session.target" ];
    path = with pkgs; [
      wl-clipboard
      xclip
      clipnotify
      diffutils
    ];
    script = ''
      t=$(mktemp -d -p "$XDG_RUNTIME_DIR")
      trap 'rm -rf "$t"' EXIT

      # Wayland to X11: each text copy becomes the X11 CLIPBOARD, where the
      # agent reads it when the host asks. The shell path is absolute because a
      # service's PATH has no sh. CLIPBOARD_STATE belongs to that inner shell.
      # shellcheck disable=SC2016
      wl-paste --type text --watch ${pkgs.runtimeShell} -c '[ "$CLIPBOARD_STATE" = data ] || exit 0; exec xclip -selection clipboard -t UTF8_STRING' &

      # X11 to Wayland: copy the agent's text in unless Wayland already has it.
      # The read fails while Hyprland owns the X11 CLIPBOARD, which it does
      # for a moment after every Wayland copy.
      while clipnotify; do
        timeout 2 xclip -o -selection clipboard -t UTF8_STRING > "$t/x" 2>/dev/null || continue
        [ -s "$t/x" ] || continue
        timeout 2 wl-paste -n --type text > "$t/w" 2>/dev/null || : > "$t/w"
        cmp -s "$t/x" "$t/w" && continue
        wl-copy --type text/plain < "$t/x"
      done &

      # Either half ending ends the service, and systemd restarts both.
      wait -n
    '';
    serviceConfig = {
      Restart = "always";
      RestartSec = 2;
    };
  };

  # vmwgfx in the initrd so the LUKS prompt renders on the SVGA device without
  # a mode switch after the root is mounted.
  boot.initrd.kernelModules = [ "vmwgfx" ];

  # No router advertisements (himmelblau's short connect timeout vs a v6
  # default route with no egress) and our own resolvers, not the lease's.
  networking.useDHCP = false;
  networking.useNetworkd = true;
  systemd.network.networks."10-primary" = {
    matchConfig.Name = "en*";
    networkConfig = {
      DHCP = "yes";
      IPv6AcceptRA = false;
    };
    dhcpV4Config.UseDNS = false;
  };
}
