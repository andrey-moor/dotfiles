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

  # The two clipboards do not share text on their own here, so this bridge
  # carries it both ways. Measured 2026-10-07 on Hyprland 0.56.2. An X11
  # CLIPBOARD write, which is what the agent does on a host copy, was announced
  # as a Wayland selection while a Wayland window held focus. Hyprland gates
  # that on XWM's remembered X11 focus, which can be stale. The gate is in
  # src/xwayland/XWM.cpp in 0.56.2. Its refusals log as "denying access to write
  # to clipboard because no X client is in focus" and "Ignoring clipboard
  # access: xwayland not in focus". The data is not served without live X11
  # focus, so wl-paste often reads nothing from such an announcement. The X11 to
  # Wayland half is what makes a host copy pasteable, because wl-copy
  # republishes the text under an owner that can serve it. A Wayland copy is not
  # mirrored to X11 at all, so the Wayland to X11 half is needed too. Both
  # halves compare content before they write. Without that they answer each
  # other, because every write shows up as a fresh selection on the far side.
  # Unguarded, the bridge spun at about 400 cycles per second. The Wayland to
  # X11 half also skips empty data, so an unreadable mirrored selection never
  # clears the X11 clipboard. The cost: on this host any X11 client can read
  # text copied in a Wayland app. Copies a password manager marks sensitive
  # stay put.
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
      # agent reads it when the host asks. The handler writes only what X11 does
      # not already hold, and never writes nothing. Reading the offer is capped
      # at 2 s, so an offer that never closes its pipe cannot wedge this service.
      # The price is a truncated copy in that case. The shell path is absolute
      # because a service's PATH has no sh. CLIPBOARD_STATE belongs to that
      # inner shell, and a selection marked sensitive is dropped before the read.
      # shellcheck disable=SC2016
      wl-paste --type text --watch ${pkgs.runtimeShell} -c '
        [ "$CLIPBOARD_STATE" = data ] || exit 0
        d=$(mktemp -d -p "$XDG_RUNTIME_DIR")
        trap "rm -rf \"\$d\"" EXIT
        timeout 2 cat > "$d/in" || :
        [ -s "$d/in" ] || exit 0
        timeout 1 xclip -o -selection clipboard -t UTF8_STRING > "$d/x" 2>/dev/null || : > "$d/x"
        cmp -s "$d/in" "$d/x" && exit 0
        xclip -selection clipboard -t UTF8_STRING -i < "$d/in"
      ' &

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

  # Fusion's emulated HD Audio card has an imprecise DMA pointer, so PipeWire's
  # default timer-based scheduling keeps mispredicting when to write and the
  # stream breaks up every few seconds. Measured 2026-09-18 on a 30 s tone:
  # about 1.5 xruns per second on the sink, while WAIT and BUSY stayed near
  # 20 us against a 42 ms quantum, so the graph had all the headroom it needed
  # and the clock was the problem. Waking on the card's own period interrupt
  # instead takes that to zero xruns over the same tone. Headroom is already
  # 8192 by then, because PipeWire detects this card as a batch device.
  services.pipewire.wireplumber.extraConfig."50-vmware-alsa" = {
    "monitor.alsa.rules" = [
      {
        matches = [
          { "node.name" = "~alsa_output.*"; }
          { "node.name" = "~alsa_input.*"; }
        ];
        actions.update-props."api.alsa.disable-tsched" = true;
      }
    ];
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
