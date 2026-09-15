# stargazer-fusion -- the stargazer configuration on VMware Fusion (Apple
# silicon), for the 2026-09 re-platform trial.
#
# Same machine as hosts/stargazer (everything in hosts/stargazer/common.nix),
# different hypervisor layer:
#   - modules/nixos/vmware-guest.nix instead of parallels-guest.nix
#   - NVMe boot disk (Fusion's default for Arm guests) instead of SATA
#   - Secure Boot mode A: plain lanzaboote, custom PK/KEK/db enrolled from the
#     guest -- the path Parallels' firmware refused. No shim, no MOK.
#   - its own hostname, so the trial joins the tailnet and Entra as a distinct
#     device next to the Parallels one
#
# Mode A needs sbctl's key layout under /var/lib/sbctl at install time (the
# bootloader step runs before activation, as with the Parallels host): the
# trial pre-places a throwaway PK/KEK/db set generated on behemoth under /mnt
# before `nixos-install`. If the trial becomes the migration, those keys move
# into sops like the Parallels db key did.

{ ... }:

{
  imports = [
    ../stargazer/common.nix
    ../../modules/nixos/vmware-guest.nix
  ];

  networking.hostName = "stargazer-fusion";

  disko.devices.disk.main.device = "/dev/nvme0n1";

  # scripts/stargazer-fusion-vm sets gui.fitGuestUsingNativeDisplayResolution,
  # so Fusion gives the guest the Mac's full Retina pixel count. Scale 2 keeps
  # text at its usual size and makes it sharp. The resize follower reuses this
  # scale for every mode it applies.
  modules.nixos.desktop.monitor = "Virtual-1,preferred,auto,2";

  modules.nixos.secureboot = {
    enable = true;
    shim.enable = false;
  };

  # SSH on Fusion's NAT network (vmnet8, reachable only from behemoth), in
  # addition to the tailnet. Parallels could run root commands through
  # `prlctl exec` before the host had joined Tailscale or Entra; VMware's
  # guest operations require a guest password, which does not exist here.
  # Key-only as everywhere. The name follows the vmxnet3 PCI slot Fusion
  # assigned at first power-on (persisted in the .vmx).
  networking.firewall.interfaces.enp2s0.allowedTCPPorts = [ 22 ];
}
