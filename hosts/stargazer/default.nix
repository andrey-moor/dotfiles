# Stargazer -- aarch64 NixOS VM on Parallels (nix-darwin's behemoth hosts it)
#
# Successor to the hand-installed Omarchy/Arch VM: declarative from the ISO up,
# LUKS+btrfs via disko, integrated home-manager reusing the home/ bundles,
# minimal Hyprland on virtio-gpu, Entra join + Intune enrollment via himmelblau.
# Everything hypervisor-neutral is in ./common.nix; this file is the Parallels
# layer (the Fusion trial is ../stargazer-fusion).

{ ... }:

{
  imports = [
    ./common.nix
    ../../modules/nixos/parallels-guest.nix
  ];

  networking.hostName = "stargazer";

  # Parallels Tools (userspace-only on aarch64): dynamic resolution,
  # clipboard, shared folders. Opt-in; watch for Hyprland irritation.
  modules.nixos.parallels.guestTools = true;

  # P9 Task 6: lanzaboote-signed boot, chained behind a Microsoft-signed shim.
  # Parallels' EDK II aa64 ignores a custom PK/KEK/db (enrolling ours halted the
  # VM with Secure Boot on), so the only path to the tenant's SecureBootEnabled
  # rule is shim -> our-key-signed systemd-boot -> our-key-signed UKIs, with the
  # db cert enrolled as a MOK. Ceremony: hosts/stargazer/README.md §7.
  modules.nixos.secureboot = {
    enable = true;
    shim.enable = true;
  };

  # Secure Boot signing key. One key pair for every stargazer instance, so the
  # db certificate is known before a VM exists and `stargazer-vm enroll-mok`
  # can run at creation time instead of after `sbctl create-keys` inside the
  # guest. Private half here (age-encrypted); public half and sbctl's owner
  # GUID are plain files in ./secureboot, placed by tmpfiles below. Only the
  # db key exists: in shim mode nothing is ever enrolled into PK/KEK.
  sops.secrets."sbctl-db-key" = {
    sopsFile = ../../secrets/stargazer-sbctl.yaml;
    key = "db.key";
    path = "/var/lib/sbctl/keys/db/db.key";
    mode = "0400";
  };

  systemd.tmpfiles.rules = [
    "d /var/lib/sbctl 0700 root root -"
    "d /var/lib/sbctl/keys 0700 root root -"
    "d /var/lib/sbctl/keys/db 0700 root root -"
    "L+ /var/lib/sbctl/keys/db/db.pem - - - - ${./secureboot/db.pem}"
    "L+ /var/lib/sbctl/GUID - - - - ${./secureboot/GUID}"
  ];

  # Tailnet address (node joined 2026-09-02).
  home-manager.users.andreym.modules.linux.wayvnc.address = "100.114.228.95";
}
