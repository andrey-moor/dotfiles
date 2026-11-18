# modules/nixos/secureboot.nix -- Secure Boot via lanzaboote
#
# Importing it enables it. A host without it boots plain systemd-boot. Here
# lanzaboote signs systemd-boot and the UKIs with the db key under pkiBundle.
# The key is not generated here. stargazer ships one shared db key pair
# (hosts/stargazer/common.nix, sops), and the firmware learns its certificate
# from the VM definition (`scripts/stargazer-vm secure-boot on`), which
# appends it to VMware's default db. PK and KEK stay VMware's.
#
# The bootloader installer runs BEFORE activation. So the first switch that
# introduces the key files must follow a `nixos-rebuild test`, and a fresh
# install needs the files placed under /mnt first (README §4.3b). Otherwise
# lzbt fails with "Failed to read public key" and nothing activates.
#
# Checking signatures: `sbverify --list <file>` prints the signer. Everything
# lanzaboote writes, the UKIs and EFI/systemd/systemd-*.efi, shows
# `CN=Database Key`. `sbctl verify` does not work here: it insists on
# keys/KEK/KEK.key, which the sops layout does not ship, and its Landlock
# sandbox cannot follow the key symlinks.
#
# The LUKS passphrase slot is never removed. Secure Boot serves compliance and
# is never a boot requirement. Parallels needed a shim chain instead. That mode
# was removed when stargazer moved to VMware Fusion in 2026-09, and
# docs/parallels-workarounds.md keeps its history.

{
  lib,
  pkgs,
  inputs,
  ...
}:

with lib;
{
  imports = [ inputs.lanzaboote.nixosModules.lanzaboote ];

  config = {
    # lanzaboote replaces systemd-boot. Both cannot own the ESP.
    boot.loader.systemd-boot.enable = mkForce false;
    boot.lanzaboote = {
      enable = true;
      # Where sbctl keeps the signing keys.
      pkiBundle = "/var/lib/sbctl";
    };

    environment.systemPackages = with pkgs; [
      sbctl
      mokutil
      # sbverify --list is the signature check (see the header).
      sbsigntool
    ];
  };
}
