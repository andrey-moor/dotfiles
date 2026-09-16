# Stargazer -- aarch64 NixOS VM on VMware Fusion (nix-darwin's behemoth hosts it)
#
# Declarative from the ISO up: LUKS+btrfs via disko, integrated home-manager
# reusing the home/ bundles, Hyprland on vmwgfx, Entra join and Intune
# enrollment via himmelblau. Everything that does not depend on the hypervisor
# is in ./common.nix. This file is the Fusion layer. Install and ceremonies are
# in ./README.md, and docs/vmware-fusion-workarounds.md says why each Fusion
# piece exists.

{ ... }:

{
  imports = [
    ./common.nix
    ../../modules/nixos/vmware-guest.nix
  ];

  networking.hostName = "stargazer";

  # scripts/stargazer-vm sets gui.fitGuestUsingNativeDisplayResolution, so
  # Fusion gives the guest the Mac's full Retina pixel count. Scale 2 keeps
  # text at its usual size and makes it sharp. The resize follower reuses this
  # scale for every mode it applies.
  modules.nixos.desktop.monitor = "Virtual-1,preferred,auto,2";

  # Plain lanzaboote. The firmware trusts our db certificate once the VM
  # definition appends it to VMware's default db (`scripts/stargazer-vm
  # secure-boot on`, README §7). ./common.nix wires the signing key.
  modules.nixos.secureboot.enable = true;

  # SSH on Fusion's NAT network (vmnet8, reachable only from behemoth), in
  # addition to the tailnet. VMware's guest operations need a guest password,
  # which does not exist here, so this is how behemoth reaches a fresh install
  # before it joins the tailnet. Key-only as everywhere. The name follows the
  # vmxnet3 PCI slot Fusion assigns, which the .vmx keeps.
  networking.firewall.interfaces.enp2s0.allowedTCPPorts = [ 22 ];
}
