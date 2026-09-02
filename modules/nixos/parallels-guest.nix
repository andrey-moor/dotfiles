# modules/nixos/parallels-guest.nix -- Parallels Desktop specifics
#
# The generic virtio/virtio-gpu guest support (initrd modules, graphics, the
# resize follower) lives in ./vm-guest.nix; only what is true of Parallels and
# nothing else belongs here.
#
# Parallels Tools on aarch64 is userspace-only (no kernel modules are built by
# nixpkgs' prl-tools), drags in an unfree ~1 GB DMG fetch, and its clipboard
# helper spawns a ghost window Hyprland tiles, so it stays behind an opt-in
# option. Its clipboard (prlcp) does NOT work under Wayland/XWayland on aarch64
# (tested 2026-09-02: neither direction, not even on the X11 clipboard) --
# host<->guest clipboard has to come from a hypervisor-independent path (TBD).

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
  imports = [ ./vm-guest.nix ];

  options.modules.nixos.parallels = {
    guestTools = mkEnableOption "Parallels Tools (shared folders, dynamic resolution)";

    mtu = mkOption {
      type = types.int;
      default = 1400;
      description = "MTU for the primary NIC. Parallels' shared (NAT) network needs 1400 for Entra/Intune traffic to complete.";
    };
  };

  config = {
    hardware.parallels.enable = cfg.guestTools;

    # prlcc is the Parallels Tools control agent; harmless on Wayland, and the
    # only piece of the Tools stack worth autostarting in the session.
    modules.nixos.desktop.extraExecOnce = mkIf cfg.guestTools [ "prlcc" ];

    # MTU declaratively, on the link: the spike VM lost its DHCP lease after
    # the same value was set by hand with `ip link set mtu`. UseMTU is off by
    # default in networkd's DHCPv4 client, so the lease cannot undo this.
    networking.useDHCP = false;
    networking.useNetworkd = true;
    systemd.network.networks."10-primary" = {
      matchConfig.Name = "en*";
      networkConfig = {
        DHCP = "yes";
        # No router advertisements: the LAN advertises a v6 default route but
        # has no working v6 egress, and Entra publishes AAAA records. With the
        # RA route present the kernel sources v6 from the Tailscale ULA and
        # himmelblaud's connect() to login.microsoftonline.com just times out
        # (its ip_version=ipv4-only does not stop the AAAA attempt). Seen on
        # the first enrollment attempt, 2026-09-02.
        IPv6AcceptRA = false;
      };
      linkConfig.MTUBytes = toString cfg.mtu;
    };
  };
}
