# hosts/stargazer/hardware.nix -- generic aarch64 EFI virtual machine
#
# There is no hardware-configuration.nix here on purpose: the machine is a
# Parallels VM whose devices are fully described by modules/nixos/parallels-guest.nix,
# and every filesystem comes from hosts/stargazer/disko.nix.

{ lib, ... }:

{
  # systemd-boot until Task 6; modules/nixos/secureboot.nix forces it off when
  # lanzaboote takes over the ESP.
  boot.loader.systemd-boot.enable = lib.mkDefault true;
  boot.loader.efi.canTouchEfiVariables = true;

  # systemd in the initrd: needed for the LUKS passphrase prompt to behave, and
  # a prerequisite for anything TPM-shaped later.
  boot.initrd.systemd.enable = true;
}
