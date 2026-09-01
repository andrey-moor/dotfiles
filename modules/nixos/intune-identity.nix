# modules/nixos/intune-identity.nix -- what this host reports as its distro
#
# OWNER DECISION, 2026-09-01 -- a deliberate reversal of spec §8 step 8.
#
# Intune's "Allowed Distributions" compliance rule is evaluated CLIENT-SIDE by
# himmelblau, from /etc/os-release's ID and VERSION_ID, and himmelblau exposes
# no override for it (verified in himmelblau 4.0.0 and libhimmelblau,
# 2026-09-01; the vendor's own alternative is a tenant-side Custom Compliance
# policy, which is not ours to add). The tenant allows rhel and ubuntu only, so
# an honest ID=nixos is permanently NonCompliant and the device cannot reach
# the "fully compliant" bar the phase is for. We therefore report Ubuntu 24.04
# to the things that read /etc/os-release, and nothing else.
#
# Scope of the lie is deliberately narrow: `system.nixos.{distroId,distroName,
# release}` stay honest, because they also feed boot-entry labels, bootspec,
# the networking.hostName default, the system.stateVersion default and
# `nixos-version`. /etc/lsb-release stays honest too (himmelblau reads
# /etc/os-release only). Nothing in nixpkgs' NixOS modules, home-manager or the
# Nix tooling this repo uses reads /etc/os-release.

{
  lib,
  config,
  ...
}:

with lib;
let
  cfg = config.modules.nixos.intune-identity;
in
{
  options.modules.nixos.intune-identity = {
    distroId = mkOption {
      type = types.str;
      default = "ubuntu";
      description = "os-release ID. Must match one of the tenant's Allowed Distributions.";
    };

    idLike = mkOption {
      type = types.str;
      default = "debian";
      description = "os-release ID_LIKE.";
    };

    versionId = mkOption {
      type = types.str;
      default = "24.04";
      description = "os-release VERSION_ID. himmelblau normalises this to semver, so 24.04 -> 24.4.0 clears both of the tenant's minimums.";
    };

    version = mkOption {
      type = types.str;
      default = "24.04.3 LTS (Noble Numbat)";
      description = "os-release VERSION.";
    };

    versionCodename = mkOption {
      type = types.str;
      default = "noble";
      description = "os-release VERSION_CODENAME.";
    };

    name = mkOption {
      type = types.str;
      default = "Ubuntu";
      description = "os-release NAME.";
    };

    prettyName = mkOption {
      type = types.str;
      default = "Ubuntu 24.04.3 LTS";
      description = "os-release PRETTY_NAME.";
    };
  };

  config = {
    environment.etc."os-release".text = mkForce ''
      NAME="${cfg.name}"
      ID=${cfg.distroId}
      ID_LIKE=${cfg.idLike}
      PRETTY_NAME="${cfg.prettyName}"
      VERSION="${cfg.version}"
      VERSION_ID="${cfg.versionId}"
      VERSION_CODENAME=${cfg.versionCodename}
    '';
  };
}
