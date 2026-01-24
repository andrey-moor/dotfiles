# modules/home/linux/intune.nix -- Microsoft Intune Portal + Identity Brokers (x86_64)
#
# Minimal setup following https://github.com/recolic/microsoft-intune-archlinux
# with bubblewrap for per-process os-release spoofing.
#
# On native x86_64 Arch, system libraries at /usr/lib are used directly.
# Only OpenSSL 3.3.2 is overridden (system 3.6.0 has X509_REQ_set_version bug).
#
# MANUAL PREREQUISITES (see hosts/rocinante/README.md):
#   1. Device broker D-Bus policy + systemd service
#   2. GNOME keyring with password set as default
#   3. Remove/disable lsb_release

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.linux.intune;

  brokerPkg = pkgs.callPackage ../../../packages/microsoft-identity-broker { };
  intunePkg = pkgs.callPackage ../../../packages/intune-portal { };

  # OpenSSL 3.3.2 from Arch Linux archives
  # Fixes Code:1200 "credential is invalid" broker bug.
  # See: https://github.com/openssl/openssl/pull/23965
  opensslArch = pkgs.stdenv.mkDerivation {
    pname = "openssl-arch";
    version = "3.3.2";
    src = pkgs.fetchurl {
      url = "https://archive.archlinux.org/packages/o/openssl/openssl-3.3.2-1-x86_64.pkg.tar.zst";
      sha256 = "sha256-JcgIxjDmdu7umbRUUWKEwJthIddDR4gC0l9NMD2j9BM=";
    };
    nativeBuildInputs = [ pkgs.zstd ];
    unpackPhase = ''
      mkdir -p $out
      cd $out
      zstd -d < $src | tar xf -
    '';
    installPhase = ''
      mv $out/usr/lib $out/lib
      rm -rf $out/usr $out/.BUILDINFO $out/.MTREE $out/.PKGINFO
    '';
  };

  # Fake os-release for per-process spoofing via bubblewrap
  fakeOsRelease = pkgs.writeText "os-release-ubuntu" ''
    NAME="Ubuntu"
    VERSION="22.04.3 LTS (Jammy Jellyfish)"
    ID=ubuntu
    ID_LIKE=debian
    PRETTY_NAME="Ubuntu 22.04.3 LTS"
    VERSION_ID="22.04"
    VERSION_CODENAME=jammy
  '';

  # LD_LIBRARY_PATH: only what the system doesn't provide
  ldLibraryPath = builtins.concatStringsSep ":" [
    "${opensslArch}/lib"  # Override system OpenSSL 3.6.0
    "${intunePkg}/lib"    # Bundled libs (RPATH points to /opt/microsoft/...)
  ];

  # Wrap a command with bwrap to spoof os-release
  bwrapExec = cmd: ''
    exec ${pkgs.bubblewrap}/bin/bwrap \
      --ro-bind / / \
      --dev /dev \
      --proc /proc \
      --bind /tmp /tmp \
      --bind "$HOME" "$HOME" \
      --ro-bind /run/user /run/user \
      --ro-bind /run/dbus /run/dbus \
      --ro-bind ${fakeOsRelease} /usr/lib/os-release \
      --ro-bind ${fakeOsRelease} /etc/os-release \
      --setenv WEBKIT_DISABLE_DMABUF_RENDERER 1 \
      -- ${cmd}
  '';

  intuneWrapper = pkgs.writeShellScriptBin "intune-portal-wrapped" ''
    export LD_LIBRARY_PATH="${ldLibraryPath}:''${LD_LIBRARY_PATH:-}"
    ${optionalString cfg.debug ''
      echo "[DEBUG] intune-portal starting at $(date)" >&2
      echo "[DEBUG] LD_LIBRARY_PATH=$LD_LIBRARY_PATH" >&2
    ''}
    ${bwrapExec "${intunePkg}/bin/intune-portal \"$@\""}
  '';

  intuneAgentWrapper = pkgs.writeShellScriptBin "intune-agent-wrapped" ''
    export LD_LIBRARY_PATH="${ldLibraryPath}:''${LD_LIBRARY_PATH:-}"
    ${bwrapExec "${intunePkg}/bin/intune-agent \"$@\""}
  '';

  userBrokerWrapper = pkgs.writeShellScriptBin "microsoft-identity-broker-wrapped" ''
    export LD_LIBRARY_PATH="${ldLibraryPath}:''${LD_LIBRARY_PATH:-}"
    ${optionalString cfg.debug ''
      echo "[DEBUG] user-broker starting at $(date)" >&2
    ''}
    exec "${brokerPkg}/bin/microsoft-identity-broker" "$@"
  '';

  deviceBrokerWrapper = pkgs.writeShellScriptBin "microsoft-identity-device-broker-wrapped" ''
    export LD_LIBRARY_PATH="${ldLibraryPath}:''${LD_LIBRARY_PATH:-}"
    ${bwrapExec "${brokerPkg}/bin/microsoft-identity-device-broker \"$@\""}
  '';

  userBrokerDbusService = pkgs.writeTextFile {
    name = "com.microsoft.identity.broker1.service";
    destination = "/share/dbus-1/services/com.microsoft.identity.broker1.service";
    text = ''
      [D-BUS Service]
      Name=com.microsoft.identity.broker1
      Exec=${userBrokerWrapper}/bin/microsoft-identity-broker-wrapped
    '';
  };

  statusHelper = pkgs.writeShellScriptBin "intune-status" ''
    echo "=== INTUNE STATUS ==="
    echo ""
    echo "PROCESSES:"
    ps aux | grep -E "(intune|microsoft.*broker)" | grep -v grep || echo "  (none running)"
    echo ""
    echo "SERVICES:"
    systemctl status microsoft-identity-device-broker --no-pager 2>/dev/null | head -5 || echo "  Device broker: not found"
    systemctl --user status intune-agent.timer --no-pager 2>/dev/null | head -5 || echo "  Agent timer: not found"
    echo ""
    echo "VERSIONS:"
    echo "  intune-portal: ${intunePkg.version}"
    echo "  broker: ${brokerPkg.version}"
  '';

  logsHelper = pkgs.writeShellScriptBin "intune-logs" ''
    case "''${1:---all}" in
      --portal)  sudo journalctl -f -t intune-portal ;;
      --broker)  journalctl --user -f -t microsoft-identity-broker ;;
      --device)  sudo journalctl -u microsoft-identity-device-broker -f ;;
      --all|*)
        journalctl --user -f -t microsoft-identity-broker 2>/dev/null | sed 's/^/[broker] /' &
        sudo journalctl -u microsoft-identity-device-broker -f 2>/dev/null | sed 's/^/[device] /' &
        wait ;;
    esac
  '';

in {
  options.modules.linux.intune = {
    enable = mkEnableOption "Microsoft Intune Portal with identity brokers (x86_64)";

    debug = mkOption {
      type = types.bool;
      default = false;
      description = "Enable debug logging for Intune components";
    };
  };

  config = mkIf (cfg.enable && pkgs.stdenv.isLinux) {
    home.packages = [
      intunePkg
      brokerPkg
      pkgs.bubblewrap
      pkgs.gnome-keyring
      pkgs.libsecret
      opensslArch
      intuneWrapper
      intuneAgentWrapper
      userBrokerWrapper
      deviceBrokerWrapper
      userBrokerDbusService
      statusHelper
      logsHelper
    ];

    # D-Bus service for user broker auto-activation
    xdg.dataFile."dbus-1/services/com.microsoft.identity.broker1.service" = {
      source = "${userBrokerDbusService}/share/dbus-1/services/com.microsoft.identity.broker1.service";
    };

    # Systemd user service for intune-agent (compliance reporting)
    systemd.user.services.intune-agent = {
      Unit.Description = "Intune Agent - compliance reporting";
      Service = {
        Type = "oneshot";
        ExecStart = "${intuneAgentWrapper}/bin/intune-agent-wrapped";
      };
    };

    systemd.user.timers.intune-agent = {
      Unit.Description = "Intune Agent scheduler";
      Timer = {
        OnStartupSec = "5m";
        OnUnitActiveSec = "1h";
        RandomizedDelaySec = "10m";
      };
      Install.WantedBy = [ "timers.target" ];
    };
  };
}
