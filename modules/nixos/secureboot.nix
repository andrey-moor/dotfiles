# modules/nixos/secureboot.nix -- opt-in Secure Boot via lanzaboote (P9 Task 6)
#
# Off by default so the host installs with plain systemd-boot. Turning it on is
# a two-step ceremony, documented in hosts/stargazer/README.md:
#
#   1. Build+switch with this module still OFF, then create the keys:
#        sudo nix run nixpkgs#sbctl -- create-keys   # sbctl is only installed once this module is on
#   2. Set `modules.nixos.secureboot.enable = true`, switch, then
#        sudo sbctl enroll-keys --microsoft      # 2023 CAs, not own-keys-only
#      and flip Parallels' EFI Secure Boot on (`prlctl set <vm>
#      --efi-secure-boot on`). Confirm `bootctl status` still reported `setup`
#      before enrolling -- if Parallels installed a vendor PK, stop.
#
# `--microsoft` matters for compliance, not just for boot: the tenant's custom
# compliance script looks for "Microsoft UEFI CA 2023" in `db` once Secure Boot
# is on. sbctl >= 0.17 bundles those certificates. The reader it uses,
# `mokutil`, is installed by modules/nixos/himmelblau.nix.
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
in
{
  imports = [ inputs.lanzaboote.nixosModules.lanzaboote ];

  options.modules.nixos.secureboot = {
    enable = mkEnableOption "lanzaboote-signed boot (Secure Boot with custom keys)";

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
    };

    environment.systemPackages = with pkgs; [
      sbctl
      mokutil
    ];
  };
}
