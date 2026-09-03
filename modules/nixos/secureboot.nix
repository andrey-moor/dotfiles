# modules/nixos/secureboot.nix -- opt-in Secure Boot via lanzaboote (P9 Task 6)
#
# Off by default so the host installs with plain systemd-boot. Two modes:
#
#   A. custom keys (`enable`)             -- our PK/KEK/db in the firmware
#   B. shim + MOK (`enable` + `shim.enable`) -- for firmware that only trusts
#      Microsoft's CAs and ignores a custom PK/KEK/db. This is Parallels.
#
# Why B exists: on 2026-09-02 mode A was done by the book on stargazer
# (`sbctl create-keys` -> lanzaboote -> `sbctl enroll-keys --microsoft` ->
# `prlctl set --efi-secure-boot on`) and the VM *halted within seconds of
# power-on*, no loader reached; with the flag back off the signed systemd-boot
# hung at its menu. Parallels' EDK II aa64 does not honour custom keys.
# NEVER enroll PK/KEK/db into this firmware -- that is what froze the loader.
#
# Mode B chain: Microsoft-signed shim (Debian, aarch64) -> lanzaboote's signed
# systemd-boot, renamed to `grubaa64.efi` (shim's compiled-in second-stage name)
# -> lanzaboote's signed UKIs. shim verifies the second stage and the UKIs
# against its own MOK database, which the firmware never sees, so our db cert is
# enrolled once as a MOK instead of into PK/KEK/db.
#
# MokManager cannot do that enrollment on Parallels: its "press any key" screen
# never gets a timer tick or a keypress (Secure Boot on or off), so a
# `mokutil --import` request either hangs the boot or, with the countdown
# working, times out and is discarded. MokList is written offline instead:
# NVRAM.dat is a plain EDK II variable store and virt-fw-vars adds the cert to
# it (`scripts/stargazer-vm enroll-mok`). The same freeze hits systemd-boot
# once Secure Boot is enforcing, hence `settings.timeout = "menu-disabled"`.
#
# Ceremony for mode B (details and checks in hosts/stargazer/README.md §7):
#
#   1. Signing keys: stargazer does not `sbctl create-keys`; the host module
#      places one shared db key pair under /var/lib/sbctl (private half from
#      sops, public half + GUID from hosts/stargazer/secureboot/). Because the
#      bootloader installer runs BEFORE activation, the very first switch that
#      introduces those files must be preceded by `nixos-rebuild test` (or, on
#      a fresh install, the files pre-placed under /mnt) -- otherwise lzbt fails
#      with "Failed to read public key" and nothing is activated.
#      Switch with `enable`+`shim.enable` and Secure Boot still OFF, reboot; the
#      full chain must boot unsigned first.
#   2. Stop the VM and run `scripts/stargazer-vm enroll-mok` (defaults to the
#      repo certificate).
#   3. Delete any leftover "Linux Boot Manager" NVRAM entry (`efibootmgr -B`):
#      it points straight at EFI/systemd/systemd-bootaa64.efi, signed by our
#      key, which the firmware will refuse. The firmware must fall through to
#      the removable path EFI/BOOT/BOOTAA64.EFI, which is shim.
#   4. `prlctl set <vm> --efi-secure-boot on` (VM stopped), boot, then check
#      `bootctl status`, `mokutil --sb-state`, `mokutil --db | grep 'UEFI CA 2023'`
#      (that CA is Parallels' own db, which is what the tenant script reads) and
#      `aad-tool compliance-check`.
#
# Checking signatures: `sbverify --list <file>` (sbsigntool, installed in mode
# B) prints the signer. Everything lanzaboote owns -- the UKIs,
# EFI/systemd/systemd-*.efi and EFI/BOOT/grubaa64.efi -- shows `CN=Database
# Key`; EFI/BOOT/BOOTAA64.EFI and mmaa64.efi show Microsoft's CAs. `sbctl
# verify` is not usable here: it insists on keys/KEK/KEK.key, which the sops
# layout deliberately does not ship, and its Landlock sandbox cannot follow the
# symlinks anyway.
#
# The LUKS passphrase slot is never removed: Secure Boot is convenience plus
# compliance, never a boot requirement.

{
  lib,
  config,
  pkgs,
  inputs,
  ...
}:

with lib;
let
  cfg = config.modules.nixos.secureboot;

  esp = config.boot.loader.efi.efiSysMountPoint;
  shim = pkgs.callPackage ../../packages/shim-signed-debian { };
  wrapperPath = makeBinPath [
    pkgs.coreutils
    pkgs.diffutils
  ];
  # What lanzaboote's own module sets as the default `boot.lanzaboote.package`
  # (there is no `pkgs.lzbt`; the flake wires it in per-system).
  lzbt = inputs.lanzaboote.packages.${pkgs.stdenv.hostPlatform.system}.lzbt;

  # lanzaboote calls `${lib.getExe cfg.package} … install … <esp> <toplevel>`
  # from its installHook, so wrapping the package is the one seam it offers
  # (`installCommand` is readOnly). After a successful install the ESP is
  # rearranged into the shim chain; lanzaboote overwrites BOOTAA64.EFI with
  # systemd-boot on every install (it cannot read a version out of shim, and
  # shim never verifies as ours), so this runs on every switch and is a no-op
  # only for the parts that already match.
  #
  # fbaa64.efi is deliberately absent: shim launches the fallback instead of the
  # second stage whenever it was loaded from \EFI\BOOT\BOOT*.EFI *and*
  # \EFI\BOOT\fbaa64.efi exists. Without a BOOT.CSV to rebuild Boot#### entries
  # from, that fallback just resets the machine -- a boot loop.
  lzbtShim = pkgs.writeShellScriptBin "lzbt" ''
    set -euo pipefail
    export PATH=${wrapperPath}:$PATH

    ${getExe lzbt} "$@"

    for arg in "$@"; do
      if [ "$arg" = "install" ]; then
        mode=install
      fi
    done
    [ "''${mode:-}" = "install" ] || exit 0

    boot=${escapeShellArg esp}/EFI/BOOT
    sdboot=${escapeShellArg esp}/EFI/systemd/systemd-bootaa64.efi

    if [ ! -f "$sdboot" ]; then
      echo "lzbt-shim: $sdboot missing, refusing to install the shim chain" >&2
      exit 1
    fi

    place() {
      if cmp -s "$1" "$2"; then
        echo "lzbt-shim: $2 already current"
        return 0
      fi
      echo "lzbt-shim: installing $2"
      cp --no-preserve=mode "$1" "$2.tmp"
      mv "$2.tmp" "$2"
    }

    # Second stage first: a half-applied chain must still be a bootable one.
    place "$sdboot" "$boot/grubaa64.efi"
    place ${shim}/shimaa64.efi "$boot/BOOTAA64.EFI"
    place ${shim}/mmaa64.efi "$boot/mmaa64.efi"
    sync "$boot"
  '';
in
{
  imports = [ inputs.lanzaboote.nixosModules.lanzaboote ];

  options.modules.nixos.secureboot = {
    enable = mkEnableOption "lanzaboote-signed boot (Secure Boot with custom keys)";

    shim.enable = mkEnableOption ''
      chain-loading through a Microsoft-signed shim, with our key enrolled as a
      MOK, for firmware that only trusts Microsoft's CAs and ignores a custom
      PK/KEK/db (Parallels). aarch64 only; requires `enable`
    '';

    pkiBundle = mkOption {
      type = types.str;
      default = "/var/lib/sbctl";
      description = "Where sbctl keeps the signing keys.";
    };
  };

  config = mkIf cfg.enable {
    # lanzaboote replaces systemd-boot; both cannot own the ESP.
    boot.loader.systemd-boot.enable = mkForce false;
    boot.lanzaboote = {
      enable = true;
      inherit (cfg) pkiBundle;
      package = mkIf cfg.shim.enable lzbtShim;
      # With Secure Boot enforcing, Parallels' firmware stops delivering timer
      # and key events to EFI applications: systemd-boot's countdown never
      # ticks and its menu ignores the keyboard (MokManager freezes the same
      # way). `menu-disabled` starts the default entry without waiting on any
      # event, so the menu is simply never offered on this host.
      settings.timeout = mkIf cfg.shim.enable "menu-disabled";
    };

    environment.systemPackages =
      with pkgs;
      [
        sbctl
        mokutil
      ]
      # openssl: PEM -> DER when a cert has to be handed to mokutil.
      # sbsigntool: `sbverify --list` is the signature check in shim mode.
      ++ optionals cfg.shim.enable [
        openssl
        sbsigntool
      ];
  };
}
