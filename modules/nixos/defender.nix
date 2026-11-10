# modules/nixos/defender.nix -- Microsoft Defender for Endpoint (mdatp)
#
# Importing this module installs Defender and runs its daemon. Onboarding to an
# organisation happens only when the host sets
# modules.nixos.defender.onboardingFile, the tenant's mdatp_onboard.json as a
# decrypted secret path. Without it a fresh install stays unlicensed. Unsetting
# it later does not offboard: the copied file stays in /etc/opt.
#
# Microsoft supports arm64 Linux but not NixOS. This module rebuilds by hand
# what the Ubuntu deb's maintainer scripts do on install, and nothing more:
#   - the mdatp system user and group (preinst)
#   - /opt/microsoft/mdatp, as a writable overlay over the unpatched store copy
#   - the default definitions copied into /var/opt, and its crash dir (postinst)
#   - /var/log/microsoft/mdatp as 0775 root:mdatp (postinst)
#   - /usr/bin/mdatp pointing at sbin/wdavdaemonclient (postinst)
#   - mdatp.service, taken from the deb's conf/mdatp.service
# The binaries keep their Ubuntu interpreter, /lib/ld-linux-aarch64.so.1,
# which nix-ld provides here.
#
# Not done: mde_netfilter_v2 (network protection, inert until onboarded),
# SELinux labels, rsyslog and logrotate files, shell completions.

{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.modules.nixos.defender;
  mdatp = pkgs.callPackage ../../packages/mdatp { };

  # `mdatp` on PATH for interactive shells. NixOS keeps /usr/bin out of PATH.
  # A plain symlink, so the process still runs as sbin/wdavdaemonclient.
  mdatpCli = pkgs.runCommand "mdatp-cli" { } ''
    mkdir -p $out/bin
    ln -s /opt/microsoft/mdatp/sbin/wdavdaemonclient $out/bin/mdatp
  '';
in
{
  options.modules.nixos.defender.onboardingFile = lib.mkOption {
    type = lib.types.nullOr lib.types.str;
    default = null;
    description = ''
      Runtime path of the tenant's mdatp_onboard.json, normally a sops secret.
      A string, not a path, so the secret never enters the Nix store. When
      set, it is copied to /etc/opt/microsoft/mdatp/mdatp_onboard.json before
      the daemon starts, which is the file the official onboarding script
      writes.
    '';
  };

  config = {
    # preinst runs `useradd --system --no-create-home --user-group mdatp`.
    users.users.mdatp = {
      isSystemUser = true;
      group = "mdatp";
    };
    users.groups.mdatp = { };

    # nix-ld puts a real loader at /lib/ld-linux-aarch64.so.1, so the binaries
    # run unpatched and /proc/<pid>/exe stays the Microsoft file.
    programs.nix-ld = {
      enable = true;
      # Only what the deb expects from the distro, by NEEDED entries: glibc
      # (nix-ld adds it), libacl, libcap, libelf, libgcc_s, libsqlite3,
      # libsystemd and libz. mkForce drops nix-ld's default set. That set
      # carries openssl and curl. When the `mdatp` CLI runs without its own
      # LD_LIBRARY_PATH, from a shell or from the compliance check, nix-ld's
      # libraries come before RUNPATH and would shadow the copies Defender
      # bundles in lib/. The daemon unit sets LD_LIBRARY_PATH and is safe.
      # Side effects for the whole host: every foreign glibc binary now runs
      # through nix-ld with only these libraries, and no other module can add
      # to the list.
      libraries = lib.mkForce [
        pkgs.acl
        pkgs.libcap
        pkgs.elfutils
        pkgs.sqlite
        pkgs.stdenv.cc.cc.lib
        pkgs.systemd
        pkgs.zlib
      ];
    };

    environment.systemPackages = [ mdatpCli ];

    # The tenant's Intune discovery script runs inside himmelblaud-tasks and
    # finds Defender with `command -v mdatp`. That unit's PATH holds only its
    # own store paths, so without this every Defender field reports false.
    systemd.services.himmelblaud-tasks.path = [ mdatpCli ];

    systemd.tmpfiles.rules = [
      "d /opt/microsoft 0755 root root -"
      "d /etc/opt/microsoft 0755 root root -"
      "d /etc/opt/microsoft/mdatp 0755 root root -"
      "d /var/opt/microsoft 0755 root root -"
      "d /var/opt/microsoft/mdatp 0755 root root -"
      # postinst's SetCrashReportPath. The daemon logs an error without it.
      "d /var/opt/microsoft/mdatp/crash 0755 root root -"
      "d /var/log/microsoft 0755 root root -"
      # postinst's SetAndVerifyLogDirPermissions demands exactly this.
      "d /var/log/microsoft/mdatp 0775 root mdatp -"
      # postinst's ConfigureTools makes the same link. The compliance check
      # calls `mdatp health` through it.
      "L+ /usr/bin/mdatp - - - - /opt/microsoft/mdatp/sbin/wdavdaemonclient"
    ];

    # Mounts /opt/microsoft/mdatp before the daemon starts. A symlink into the
    # store fails: the daemon checks that its install directory is writable,
    # and the store is read-only. An overlay keeps the store copy as the lower
    # layer and takes writes in /var/lib/mdatp-overlay. Paths under
    # /opt/microsoft/mdatp then match the deb's unit file exactly.
    systemd.services.mdatp-prepare = {
      description = "Microsoft Defender install directory";
      wantedBy = [ "multi-user.target" ];
      path = [
        pkgs.coreutils
        pkgs.util-linux
      ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
      };
      script = ''
        set -euo pipefail
        lower=${mdatp}
        target=/opt/microsoft/mdatp
        state=/var/lib/mdatp-overlay
        defs=/var/opt/microsoft/mdatp/definitions.noindex/00000000-0000-0000-0000-000000000000

        # Lazy, because a running `mdatp health` or a shell inside the
        # directory would make a plain umount fail and leave the old mount.
        if mountpoint -q "$target"; then
          umount --lazy "$target"
        fi

        # A new package version starts from a clean upper layer, the way a deb
        # upgrade replaces the files. Stale copied-up files would hide the new
        # ones. postinst's DefaultDefinitionsDatabase likewise recreates the
        # fallback definitions on every install.
        if [ "$(cat "$state/lower" 2>/dev/null || true)" != "$lower" ]; then
          rm -rf "$state/upper" "$state/work" "$defs"
          mkdir -p "$defs"
          for f in "$lower"/definitions/*; do
            install -m 0444 "$f" "$defs/"
          done
        fi

        install -d -m 0700 "$state"
        mkdir -p "$state/upper" "$state/work" "$target"
        mount -t overlay overlay \
          -o "lowerdir=$lower,upperdir=$state/upper,workdir=$state/work" \
          "$target"
        echo "$lower" > "$state/lower"

        # postinst's CreateOrUpdateStateFile. The machine GUID is the device's
        # identity in the Defender portal, and the daemon does not set it. It is
        # the VM's DMI product UUID, lower case, the way the deb derives it, so
        # it stays the same across rebuilds of this host. Written once, while
        # the daemon is stopped, and never changed afterwards: a new GUID would
        # register a second device. The field is read with Defender's own JSON
        # tool, as postinst does, so a reformatted file cannot fool the check.
        statefile=/var/opt/microsoft/mdatp/wdavstate
        helper="$target/sbin/install_helper"
        current=""
        if [ -e "$statefile" ]; then
          current=$("$helper" get-json --file "$statefile" --field machineGuid 2>/dev/null || true)
        fi
        if [ -z "$current" ] || [ "$current" = "null" ]; then
          # No random fallback: that would mint a new device on every install.
          uuid=$(tr '[:upper:]' '[:lower:]' < /sys/class/dmi/id/product_uuid 2>/dev/null || true)
          if ! [[ "$uuid" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] \
            || [ "$uuid" = "00000000-0000-0000-0000-000000000000" ]; then
            echo "mdatp-prepare: no valid DMI product UUID, refusing to set a machine GUID" >&2
            exit 1
          fi
          "$helper" set-json --file "$statefile" --field machineGuid --type string --value "$uuid"
          "$helper" set-json --file "$statefile" --field machineUuidType --type string --value Dmid
          "$helper" set-json --file "$statefile" --field platformDmidecodeUuid --type string --value "$uuid"
          "$helper" set-json --file "$statefile" --field releaseRing --type string --value Production
          "$helper" set-json --file "$statefile" --field validateId --type bool --value true
        fi
        # postinst's RestoreAllFilePermission leaves the state file like this.
        if [ -e "$statefile" ]; then
          chown root:mdatp "$statefile"
          chmod 0600 "$statefile"
        fi
      ''
      + lib.optionalString (cfg.onboardingFile != null) ''

        # Onboarding. The official script copies the tenant's file to this path
        # and the daemon picks it up. A regular root-only copy, not a symlink
        # into /run/secrets, because that is what the daemon expects to find.
        install -m 0600 -o root -g root ${lib.escapeShellArg cfg.onboardingFile} \
          /etc/opt/microsoft/mdatp/mdatp_onboard.json
      '';
      preStop = ''
        if mountpoint -q /opt/microsoft/mdatp; then
          umount --lazy /opt/microsoft/mdatp
        fi
      '';
    };

    # The deb's conf/mdatp.service, field for field.
    systemd.services.mdatp = {
      description = "Microsoft Defender";
      after = [
        "network.target"
        "mdatp-prepare.service"
      ];
      requires = [ "mdatp-prepare.service" ];
      wantedBy = [ "multi-user.target" ];
      # Any change to mdatp-prepare, a package bump or an edit to its script,
      # makes a switch restart it, and Requires= stops this unit with it.
      # Triggering on the prepare unit itself makes the switch start the
      # daemon again in every such case.
      restartTriggers = [ config.systemd.units."mdatp-prepare.service".unit ];
      # Default dependencies stay on, so the unit Conflicts= with shutdown.target
      # and the daemon stops before the final shutdown phase.
      startLimitIntervalSec = 120;
      startLimitBurst = 3;
      # The daemon shells out to lscpu for its device inventory. NixOS gives
      # units a minimal PATH without util-linux.
      path = [ pkgs.util-linux ];
      environment = {
        LD_LIBRARY_PATH = "/opt/microsoft/mdatp/lib/";
        LD_PRELOAD = "";
        LD_AUDIT = "";
        MALLOC_ARENA_MAX = "2";
        ENABLE_CRASHPAD = "1";
      };
      serviceConfig = {
        Type = "simple";
        WorkingDirectory = "/opt/microsoft/mdatp/sbin";
        ExecStart = "/opt/microsoft/mdatp/sbin/wdavdaemon";
        NotifyAccess = "main";
        LimitNOFILE = 65536;
        Restart = "always";
        RestartSec = 5;
        Delegate = "yes";
      };
    };

    # The tenant's discovery script fails the updates check when definitions
    # are more than 1440 minutes old. The daemon's own schedule once went 14
    # hours without an update while a manual one worked at once, so a timer
    # asks for one every 6 hours. Persistent catches up after a suspend.
    systemd.services.mdatp-definitions-update = {
      description = "Update Microsoft Defender definitions";
      after = [ "mdatp.service" ];
      requisite = [ "mdatp.service" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${mdatpCli}/bin/mdatp definitions update";
        TimeoutStartSec = "10min";
      };
    };
    systemd.timers.mdatp-definitions-update = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "00/6:00";
        RandomizedDelaySec = "10min";
        Persistent = true;
      };
    };
  };
}
