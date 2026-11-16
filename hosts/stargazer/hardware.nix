# hosts/stargazer/hardware.nix -- generic aarch64 EFI virtual machine
#
# There is no hardware-configuration.nix here on purpose: the machine is a
# VMware Fusion VM whose devices are described by modules/nixos/vmware-guest.nix,
# and every filesystem comes from hosts/stargazer/disko.nix.

{ lib, ... }:

{
  # systemd-boot until Task 6; modules/nixos/secureboot.nix forces it off when
  # lanzaboote takes over the ESP.
  boot.loader.systemd-boot.enable = lib.mkDefault true;
  boot.loader.efi.canTouchEfiVariables = true;

  # The initrd is systemd-based, which the LUKS passphrase prompt needs. NixOS
  # 26.11 removed the scripted initrd, so there is no option to set any more.
}
