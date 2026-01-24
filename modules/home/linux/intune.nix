# modules/home/linux/intune.nix -- Microsoft Intune configuration layer (x86_64)
#
# Provides OpenSSL 3.3.2 override, LD_LIBRARY_PATH wrappers, user-level D-Bus
# service, systemd timer, and system setup helpers.
#
# Binaries come from AUR: intune-portal-bin, microsoft-identity-broker-bin
# os-release is spoofed system-wide (no bubblewrap needed).
#
# Run `intune-setup` after first `home-manager switch` to install system configs.

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.linux.intune;

  # OpenSSL 3.3.2 from Arch Linux archives
  # Fixes Code:1200 "credential is invalid" broker bug in OpenSSL 3.4+
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

  ldLibraryPath = "${opensslArch}/lib";

  # Fake Ubuntu os-release for system-wide spoofing
  fakeOsRelease = pkgs.writeText "os-release-ubuntu" ''
    NAME="Ubuntu"
    VERSION="22.04.3 LTS (Jammy Jellyfish)"
    ID=ubuntu
    ID_LIKE=debian
    PRETTY_NAME="Ubuntu 22.04.3 LTS"
    VERSION_ID="22.04"
    VERSION_CODENAME=jammy
  '';

  # --- Wrapper scripts ---

  intunePortalWrapper = pkgs.writeShellScriptBin "intune-portal" ''
    export LD_LIBRARY_PATH="${ldLibraryPath}:''${LD_LIBRARY_PATH:-}"
    export WEBKIT_DISABLE_DMABUF_RENDERER=1
    export LIBGL_ALWAYS_SOFTWARE=1
    exec /opt/microsoft/intune/bin/intune-portal "$@"
  '';

  intuneAgentWrapper = pkgs.writeShellScriptBin "intune-agent-wrapped" ''
    export LD_LIBRARY_PATH="${ldLibraryPath}:''${LD_LIBRARY_PATH:-}"
    exec /opt/microsoft/intune/bin/intune-agent "$@"
  '';

  userBrokerWrapper = pkgs.writeShellScriptBin "microsoft-identity-broker-wrapped" ''
    export LD_LIBRARY_PATH="${ldLibraryPath}:''${LD_LIBRARY_PATH:-}"
    export WEBKIT_DISABLE_DMABUF_RENDERER=1
    export LIBGL_ALWAYS_SOFTWARE=1
    exec /usr/bin/microsoft-identity-broker "$@"
  '';

  deviceBrokerWrapper = pkgs.writeShellScriptBin "microsoft-identity-device-broker-wrapped" ''
    export LD_LIBRARY_PATH="${ldLibraryPath}:''${LD_LIBRARY_PATH:-}"
    exec /usr/bin/microsoft-identity-device-broker "$@"
  '';

  # --- System config files (installed by intune-setup) ---

  deviceBrokerOverride = pkgs.writeText "device-broker-override.conf" ''
    [Service]
    ExecStart=
    ExecStart=${deviceBrokerWrapper}/bin/microsoft-identity-device-broker-wrapped
    Environment=HOME=${config.home.homeDirectory}
  '';

  pcscdOverride = pkgs.writeText "pcscd-override.conf" ''
    [Service]
    User=
    PrivateUsers=
    ProtectSystem=
    ProtectHome=
    CapabilityBoundingSet=
    ExecStart=
    ExecStart=/usr/bin/pcscd --foreground --auto-exit --disable-polkit
  '';

  # --- Helper scripts ---

  setupHelper = pkgs.writeShellScriptBin "intune-setup" ''
    set -euo pipefail
    echo "=== Intune System Setup ==="
    echo ""

    echo "[1/4] Spoofing os-release..."
    sudo cp ${fakeOsRelease} /etc/os-release
    sudo cp ${fakeOsRelease} /usr/lib/os-release
    echo "  -> /etc/os-release and /usr/lib/os-release set to Ubuntu 22.04"

    echo "[2/4] Configuring device broker..."
    sudo mkdir -p /etc/systemd/system/microsoft-identity-device-broker.service.d
    sudo cp ${deviceBrokerOverride} /etc/systemd/system/microsoft-identity-device-broker.service.d/override.conf
    echo "  -> Device broker override installed"

    echo "[3/4] Configuring pcscd (YubiKey access)..."
    sudo mkdir -p /etc/systemd/system/pcscd.service.d
    sudo cp ${pcscdOverride} /etc/systemd/system/pcscd.service.d/override.conf
    echo "  -> pcscd override installed"

    echo "[4/4] Registering YubiKey PKCS#11 module..."
    echo 'module: /usr/lib/libykcs11.so' | sudo tee /usr/share/p11-kit/modules/ykcs11.module > /dev/null
    echo "  -> ykcs11 p11-kit module registered"

    echo ""
    echo "Reloading systemd..."
    sudo systemctl daemon-reload
    sudo systemctl enable --now pcscd.socket
    sudo systemctl restart microsoft-identity-device-broker 2>/dev/null || true
    echo ""
    echo "Done! System configs installed."
    echo ""
    echo "Remaining manual steps:"
    echo "  1. Remove lsb_release: sudo mv /usr/bin/lsb_release /usr/bin/lsb_release.bak 2>/dev/null || true"
    echo "  2. Set up GNOME keyring with password-protected 'login' collection"
    echo "  3. Enroll: intune-portal"
  '';

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
    echo "SMART CARD:"
    systemctl is-active pcscd.socket 2>/dev/null && echo "  pcscd: active" || echo "  pcscd: inactive"
    p11tool --list-tokens 2>/dev/null | grep -i yubi | head -1 || echo "  YubiKey: not detected"
    echo ""
    echo "OS-RELEASE:"
    grep PRETTY_NAME /etc/os-release 2>/dev/null || echo "  (not set)"
  '';

  logsHelper = pkgs.writeShellScriptBin "intune-logs" ''
    case "''${1:---all}" in
      --broker)  journalctl --user -f -t microsoft-identity-broker ;;
      --device)  sudo journalctl -u microsoft-identity-device-broker -f ;;
      --agent)   journalctl --user -f -u intune-agent ;;
      --all|*)
        echo "Usage: intune-logs [--broker|--device|--agent|--all]"
        echo ""
        journalctl --user -f -t microsoft-identity-broker 2>/dev/null | sed 's/^/[broker] /' &
        sudo journalctl -u microsoft-identity-device-broker -f 2>/dev/null | sed 's/^/[device] /' &
        wait ;;
    esac
  '';

in {
  options.modules.linux.intune = {
    enable = mkEnableOption "Microsoft Intune configuration layer (x86_64, AUR binaries)";
  };

  config = mkIf (cfg.enable && pkgs.stdenv.isLinux) {
    home.packages = [
      opensslArch
      intunePortalWrapper
      intuneAgentWrapper
      userBrokerWrapper
      deviceBrokerWrapper
      setupHelper
      statusHelper
      logsHelper
    ];

    # User broker D-Bus service (auto-activated on demand)
    xdg.dataFile."dbus-1/services/com.microsoft.identity.broker1.service".text = ''
      [D-BUS Service]
      Name=com.microsoft.identity.broker1
      Exec=${userBrokerWrapper}/bin/microsoft-identity-broker-wrapped
    '';

    # Intune-agent systemd user service (compliance reporting)
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
