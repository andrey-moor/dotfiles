# modules/nixos/himmelblau.nix -- Entra ID join + Intune enrollment
#
# Wraps upstream's `services.himmelblau` (flake input pinned at 4.0.0) with the
# five fixes the P2 spike had to apply by hand, so the enrollment ceremony is
# hand-fix-free.
#
# Tenant-bearing values (domain, tenant id, UPN) may never appear in a
# committed .nix file -- this repo is public -- and may not live in a
# gitignored file either: `github:andrey-moor/dotfiles#stargazer` (the
# reference used by the installer, by CI and by system.autoUpgrade) cannot see
# gitignored paths. They therefore live in an age-encrypted sops secret that IS
# committed, and are rendered at activation via `sops.templates` into the
# himmelblau drop-in and the user map. Nothing tenant-bearing enters the nix
# store or an eval.
#
# Deliberately NOT set:
#   settings.domain  -- it would render the domain into the world-readable
#                       [global] store file. Unnecessary: himmelblau's
#                       get_configured_domains() (src/common/src/config.rs)
#                       treats every INI section name other than [global] and
#                       [offline_breakglass] as a configured domain, so the
#                       encrypted `[<domain>]` drop-in section is the only
#                       declaration needed.
#   pam_allow_groups -- null means "every Entra user may authenticate"; an
#                       empty list is a populated allow-list with zero entries
#                       and locks everyone out.
#   hsm_type         -- the Nix build omits the `tpm` cargo feature
#                       (himmelblau-idm/himmelblau#1656); "tpm" kills the daemon.

{
  lib,
  config,
  pkgs,
  inputs,
  ...
}:

with lib;
let
  cfg = config.modules.nixos.himmelblau;
  hb = config.services.himmelblau;

  # Upstream's rendered [global] INI. We relocate it into the drop-in
  # directory instead of letting it be /etc/himmelblau/himmelblau.conf.
  globalConf = config.environment.etc."himmelblau/himmelblau.conf".source;

  # Seed for the writable main config. Non-empty on purpose: himmelblau treats
  # a zero-length config file as a *mask* that suppresses that layer.
  mainConfigSeed = pkgs.writeText "himmelblau.conf" ''
    # Intentionally left writable and (almost) empty.
    #
    # Declarative configuration lives in himmelblau.conf.d/ (see
    # modules/nixos/himmelblau.nix). This file exists so the daemon, PAM and
    # NSS all resolve the default config path and pick those drop-ins up, and
    # so anything that writes back to its config has somewhere to write.
  '';

  ph = name: config.sops.placeholder."stargazer-tenant/${name}";

  # 0444, not the sops default 0400: himmelblaud runs under DynamicUser, and
  # nss_himmelblau / pam_himmelblau read the same files from *every* process
  # that resolves a user. These are tenant identifiers, not credentials -- they
  # are encrypted to keep them out of a public git history, not off the host.
  tenantRenderMode = "0444";
in
{
  options.modules.nixos.himmelblau = {
    enable = mkEnableOption "himmelblau Entra ID join and Intune enrollment";

    tenantSecretFile = mkOption {
      type = types.path;
      default = ../../secrets/stargazer-tenant.yaml;
      description = ''
        sops file holding the tenant facts. Must define the keys `domain`
        (the Entra tenant's primary domain -- the domain half of the sign-in
        UPN), `tenant_id` (the tenant GUID, pinned per-domain so discovery
        cannot wander) and `upn` (the identity local user `andreym`
        authenticates as).
      '';
    };
  };

  config = mkIf cfg.enable {
    sops.secrets =
      genAttrs
        [
          "stargazer-tenant/domain"
          "stargazer-tenant/tenant_id"
          "stargazer-tenant/upn"
        ]
        (name: {
          sopsFile = cfg.tenantSecretFile;
          key = removePrefix "stargazer-tenant/" name;
        });

    # The `[<domain>]` section header is itself a placeholder: sops-nix
    # substitutes anywhere in the rendered bytes, not just on value positions.
    sops.templates."himmelblau-tenant.conf" = {
      content = ''
        [${ph "domain"}]
        tenant_id = ${ph "tenant_id"}
      '';
      mode = tenantRenderMode;
      restartUnits = [ "himmelblaud.service" ];
    };

    # Identity: local uid-1000 `andreym` authenticates against Entra. All four
    # PAM entry points consult this map before cn_name_mapping.
    sops.templates."himmelblau-user-map" = {
      content = "andreym:${ph "upn"}\n";
      mode = tenantRenderMode;
      restartUnits = [ "himmelblaud.service" ];
    };

    services.himmelblau = {
      enable = true;
      # Compliance evaluation is only visible in the daemon journal, and the
      # enrollment ceremony (Task 5) is read from there.
      debugFlag = true;
      settings = {
        debug = true;
        apply_policy = true;
        join_type = "join";
        # Passwordless FIDO (YubiKey) is the first factor at the local console.
        enable_hello = true;
        enable_experimental_mfa = true;
        enable_experimental_passwordless_fido = true;
        enable_passwordless_security_key = true;
        enable_sfa_fallback = false;
        enable_kerberos_cache = true;
        ip_version = "ipv4-only";
        # Upstream's default is /bin/bash, which does not exist on NixOS.
        shell = "/run/current-system/sw/bin/bash";
        user_map_file = config.sops.templates."himmelblau-user-map".path;
      };
    };

    environment.systemPackages = [
      inputs.himmelblau.packages.${pkgs.stdenv.hostPlatform.system}.aad-tool
      # The tenant's custom-compliance discovery script reads the Secure Boot
      # `db` through `mokutil --db` before falling back to efivars, and NixOS
      # ships none of its fallbacks. systemd services get
      # /run/current-system/sw/bin on PATH, so this is enough for the script.
      pkgs.mokutil
    ];

    # FIX 1 (mutable config). Upstream hard-codes
    # `ExecStart = himmelblaud --config <store path>` and symlinks the same
    # store path at /etc/himmelblau/himmelblau.conf. Both have to go: the
    # daemon expects a writable main config, and the per-domain tenant section
    # has no representation in `services.himmelblau.settings` (the generated
    # option set is closed, with no freeform escape).
    #
    # himmelblau 4.0.0 merges /etc/himmelblau/himmelblau.conf with every *.conf
    # in /etc/himmelblau/himmelblau.conf.d/ -- but only when invoked with
    # exactly the default config path (src/common/src/config.rs,
    # load_config_hierarchy). Hence: writable main file, declarative drop-ins.
    environment.etc."himmelblau/himmelblau.conf".enable = mkForce false;
    environment.etc."himmelblau/himmelblau.conf.d/00-global.conf".source = globalConf;
    # A symlink to the activation-rendered secret, not a store file.
    # collect_drop_ins() follows symlinks and silently skips a dangling one, so
    # a host that cannot yet decrypt (no `&stargazer` recipient in .sops.yaml)
    # simply comes up domain-less instead of failing to build or boot.
    environment.etc."himmelblau/himmelblau.conf.d/10-tenant.conf".source =
      config.sops.templates."himmelblau-tenant.conf".path;

    systemd.services.himmelblaud.serviceConfig.ExecStart = mkForce (
      "${hb.daemonPackage}/bin/himmelblaud --config /etc/himmelblau/himmelblau.conf"
      + optionalString hb.debugFlag " -d"
    );

    # FIX 2 (Kerberos). himmelblaud-tasks already has /etc/krb5.conf.d in its
    # ReadWritePaths but nothing creates it, so every login logged
    # `Path "/etc/krb5.conf.d/" does not exist` followed by a Kerberos failure.
    security.krb5 = {
      enable = true;
      settings.includedir = [ "/etc/krb5.conf.d/" ];
    };

    systemd.tmpfiles.rules = [
      "d /etc/krb5.conf.d 0755 root root -"
      "d /etc/himmelblau 0755 root root -"
      "C /etc/himmelblau/himmelblau.conf 0644 root root - ${mainConfigSeed}"
    ];

    # FIX 3 (226/NAMESPACE). himmelblaud-tasks mounts /run/himmelblaud, which
    # only exists once himmelblaud has created its RuntimeDirectory. Upstream
    # has BindsTo + a ConditionPathExists but no ordering, so the first boot
    # always fails the unit once before the restart succeeds.
    systemd.services.himmelblaud-tasks.after = [ "himmelblaud.service" ];
  };
}
