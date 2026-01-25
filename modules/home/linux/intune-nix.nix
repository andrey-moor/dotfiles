# modules/home/linux/intune-nix.nix -- Microsoft Intune Portal + Identity Brokers (x86_64, Nix libs)
#
# Full Nix-managed solution for Microsoft Intune on x86_64-linux.
# Unlike intune.nix (which uses AUR binaries + Arch system libs), this module
# provides ALL libraries from Nix store to avoid ABI incompatibilities.
#
# ARCHITECTURE:
#   +------------------+     D-Bus      +----------------------+
#   |  intune-portal   | ------------> |  user broker (SSO)   |
#   |  (Nix + wrapper) |               |  (Nix + wrapper)     |
#   +------------------+               +----------------------+
#           |                                    |
#           | D-Bus                              | D-Bus
#           v                                    v
#   +------------------+               +----------------------+
#   |  device broker   |               |    gnome-keyring     |
#   |  (Nix, system)   |               |    (credentials)     |
#   +------------------+               +----------------------+
#
# COMPONENTS:
#   1. intune-portal (Nix): Main enrollment GUI
#   2. microsoft-identity-broker (Nix): User SSO authentication
#   3. microsoft-identity-device-broker (Nix): Device attestation (system service)
#
# WHY NIX LIBRARIES:
#   The AUR intune-portal binary was built against Ubuntu libraries. When running
#   on Arch with different GLib/GTK/WebKitGTK versions, ABI mismatches cause crashes.
#   By providing ALL libraries from Nix store, we ensure compatibility.
#
# MANUAL PREREQUISITES:
#   1. Fake Ubuntu os-release: sudo tee /etc/os-release << 'EOF'
#      NAME="Ubuntu"
#      VERSION="22.04.3 LTS (Jammy Jellyfish)"
#      ID=ubuntu
#      PRETTY_NAME="Ubuntu 22.04.3 LTS"
#      VERSION_ID="22.04"
#      EOF
#   2. Install AUR packages: yay -S intune-portal-bin microsoft-identity-broker-bin
#
# DEBUGGING:
#   - Set modules.linux.intune-nix.debug = true for verbose logging
#   - Run: intune-logs (tails all service logs)
#   - Logs: /tmp/intune-portal.log, journalctl --user, journalctl -u microsoft-identity-device-broker
#
# See: https://github.com/recolic/microsoft-intune-archlinux

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.linux.intune-nix;

  #############################################################################
  # PACKAGE SOURCES
  #############################################################################

  # Microsoft Identity Broker package (x86_64 binaries from Microsoft .deb)
  brokerPkg = pkgs.callPackage ../../../packages/microsoft-identity-broker { };

  # Microsoft Intune Portal package (x86_64 binaries from Microsoft .deb)
  intunePkg = pkgs.callPackage ../../../packages/intune-portal { };

  # Custom curl without HTTP/3 support to avoid ngtcp2's OPENSSL_3.5.0 requirement
  curlNoHttp3 = pkgs.curl.override { http3Support = false; };

  #############################################################################
  # OPENSSL 3.3.2 (fixes Code:1200 error in broker)
  #############################################################################

  # OpenSSL 3.3.2 from Arch Linux archives
  # Required because broker links against OpenSSL and newer versions have
  # X509_REQ_set_version bug causing Code:1200 "credential is invalid"
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

  # OpenSC 0.25.1 from Arch Linux archives
  # Required because Nix OpenSC 0.26.1 requires OPENSSL_3.4.0 symbols,
  # but we use Arch OpenSSL 3.3.2 (which only has up to OPENSSL_3.0.0).
  openscArch = pkgs.stdenv.mkDerivation {
    pname = "opensc-arch";
    version = "0.25.1";
    src = pkgs.fetchurl {
      url = "https://archive.archlinux.org/packages/o/opensc/opensc-0.25.1-1-x86_64.pkg.tar.zst";
      sha256 = "0qvfh0wbcbh02nram42fgip055msmdffhg310rsi3d843xa5pdy6";
    };
    nativeBuildInputs = [ pkgs.zstd ];
    unpackPhase = ''
      mkdir -p $out
      cd $out
      zstd -d < $src | tar xf -
    '';
    installPhase = ''
      mv $out/usr/* $out/
      rm -rf $out/usr $out/.BUILDINFO $out/.MTREE $out/.PKGINFO $out/etc
    '';
  };

  #############################################################################
  # SHARED ENVIRONMENT SETUP
  #############################################################################

  # Library paths for all wrappers
  libPaths = {
    glvnd = "${pkgs.libglvnd}/lib";
    mesa = "${pkgs.mesa}";
    wayland = "${pkgs.wayland}/lib";
    gio = "${pkgs.glib-networking}/lib/gio/modules";
    gnutls = "${pkgs.gnutls.out}/lib";
    nettle = "${pkgs.nettle}/lib";
    libtasn1 = "${pkgs.libtasn1}/lib";
    libidn2 = "${pkgs.libidn2}/lib";
    opensc = "${openscArch}";
    libp11 = "${pkgs.libp11}";
    pcsclite = "${pkgs.pcsclite.lib}";
    p11kit = "${pkgs.p11-kit.out}";
    libfido2 = "${pkgs.libfido2}";
    # System libraries needed by broker
    dbus = "${pkgs.dbus.lib}/lib";
    glib = "${pkgs.glib.out}/lib";
    systemd = "${pkgs.systemdLibs}/lib";
    util-linux = "${pkgs.util-linux.lib}/lib";
    curl = "${curlNoHttp3.out}/lib";
    zlib = "${pkgs.zlib.out}/lib";
    libssh2 = "${pkgs.libssh2.out}/lib";
    nghttp2 = "${pkgs.nghttp2.lib}/lib";
    brotli = "${pkgs.brotli.lib}/lib";
    icu = "${pkgs.icu.out}/lib";
    libstdcxx = "${pkgs.stdenv.cc.cc.lib}/lib";
    zstd = "${pkgs.zstd.out}/lib";
    # X11 and GUI libraries
    xorg-libX11 = "${pkgs.xorg.libX11.out}/lib";
    xorg-libXext = "${pkgs.xorg.libXext.out}/lib";
    xorg-libXrender = "${pkgs.xorg.libXrender.out}/lib";
    xorg-libXi = "${pkgs.xorg.libXi.out}/lib";
    xorg-libXcursor = "${pkgs.xorg.libXcursor.out}/lib";
    xorg-libXrandr = "${pkgs.xorg.libXrandr.out}/lib";
    xorg-libXfixes = "${pkgs.xorg.libXfixes.out}/lib";
    xorg-libXcomposite = "${pkgs.xorg.libXcomposite.out}/lib";
    xorg-libXdamage = "${pkgs.xorg.libXdamage.out}/lib";
    xorg-libxcb = "${pkgs.xorg.libxcb.out}/lib";
    libxkbcommon = "${pkgs.libxkbcommon.out}/lib";
    fontconfig = "${pkgs.fontconfig.lib}/lib";
    freetype = "${pkgs.freetype.out}/lib";
    expat = "${pkgs.expat.out}/lib";
    cairo = "${pkgs.cairo.out}/lib";
    pango = "${pkgs.pango.out}/lib";
    gdk-pixbuf = "${pkgs.gdk-pixbuf.out}/lib";
    gtk3 = "${pkgs.gtk3.out}/lib";
    atk = "${pkgs.atk.out}/lib";
    at-spi2-atk = "${pkgs.at-spi2-atk.out}/lib";
    at-spi2-core = "${pkgs.at-spi2-core.out}/lib";
    harfbuzz = "${pkgs.harfbuzz.out}/lib";
    pcre2 = "${pkgs.pcre2.out}/lib";
    webkitgtk = "${pkgs.webkitgtk_4_1.out}/lib";
    libsoup = "${pkgs.libsoup_3.out}/lib";
    libsecret = "${pkgs.libsecret.out}/lib";
    sqlite = "${pkgs.sqlite.out}/lib";
    libpsl = "${pkgs.libpsl.out}/lib";
    libidn = "${pkgs.libidn.out}/lib";
    libpng = "${pkgs.libpng.out}/lib";
    libjpeg = "${pkgs.libjpeg.out}/lib";
    libwebp = "${pkgs.libwebp.out}/lib";
    lcms2 = "${pkgs.lcms2.out}/lib";
    gstreamer = "${pkgs.gst_all_1.gstreamer.out}/lib";
    gst-plugins-base = "${pkgs.gst_all_1.gst-plugins-base.out}/lib";
    libxml2 = "${pkgs.libxml2.out}/lib";
    libxslt = "${pkgs.libxslt.out}/lib";
    enchant = "${pkgs.enchant.out}/lib";
    libnotify = "${pkgs.libnotify.out}/lib";
    # Arch OpenSSL 3.3.2 - fixes Code:1200 error in broker
    opensslArch = "${opensslArch}/lib";
  };

  # Environment variables for Mesa software rendering
  mesaEnvVars = ''
    export LIBGL_ALWAYS_SOFTWARE=1
    export GALLIUM_DRIVER=llvmpipe
    export MESA_LOADER_DRIVER_OVERRIDE=llvmpipe
    export __EGL_VENDOR_LIBRARY_DIRS="${libPaths.mesa}/share/glvnd/egl_vendor.d"
    export LIBGL_DRIVERS_PATH="${libPaths.mesa}/lib/dri"
  '';

  # Environment variables for WebKitGTK
  webkitEnvVars = ''
    export WEBKIT_DISABLE_DMABUF_RENDERER=1
    export GDK_BACKEND=x11
  '';

  # Environment variables for TLS/SSL
  tlsEnvVars = ''
    export GIO_MODULE_DIR="${libPaths.gio}"
    export SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt"
    export SSL_CERT_DIR="/etc/ssl/certs"
  '';

  # Environment variables for PKCS#11 / YubiKey support
  pkcs11EnvVars = ''
    export HOME="''${HOME:-/home/$(whoami)}"
    export XDG_CONFIG_HOME="''${XDG_CONFIG_HOME:-$HOME/.config}"
    export PCSCLITE_CSOCK_NAME="/run/pcscd/pcscd.comm"
    export P11_KIT_MODULE_PATH="${libPaths.opensc}/lib/pkcs11:${libPaths.p11kit}/lib/pkcs11"
  '';

  # Debug environment variables (when cfg.debug is true)
  debugEnvVars = optionalString cfg.debug ''
    export G_MESSAGES_DEBUG=all
    export WEBKIT_DEBUG=all
    export LIBGL_DEBUG=verbose
    export INTUNE_LOG_LEVEL=debug
    export MSAL_LOG_LEVEL=Trace
    export P11_KIT_DEBUG=all
    export GNUTLS_DEBUG_LEVEL=9
    echo "[DEBUG] Starting at $(date)" >&2
    echo "[DEBUG] HOME=$HOME" >&2
    echo "[DEBUG] XDG_CONFIG_HOME=$XDG_CONFIG_HOME" >&2
    echo "[DEBUG] LD_LIBRARY_PATH=$LD_LIBRARY_PATH" >&2
  '';

  #############################################################################
  # FULL LD_LIBRARY_PATH (all Nix libs)
  #############################################################################

  fullLdLibraryPath = "${libPaths.opensslArch}:${libPaths.glvnd}:${libPaths.mesa}/lib:${libPaths.webkitgtk}:${libPaths.libsoup}:${libPaths.libsecret}:${libPaths.gtk3}:${libPaths.gdk-pixbuf}:${libPaths.cairo}:${libPaths.pango}:${libPaths.harfbuzz}:${libPaths.fontconfig}:${libPaths.freetype}:${libPaths.atk}:${libPaths.at-spi2-atk}:${libPaths.at-spi2-core}:${libPaths.xorg-libX11}:${libPaths.xorg-libXext}:${libPaths.xorg-libXrender}:${libPaths.xorg-libXi}:${libPaths.xorg-libXcursor}:${libPaths.xorg-libXrandr}:${libPaths.xorg-libXfixes}:${libPaths.xorg-libXcomposite}:${libPaths.xorg-libXdamage}:${libPaths.xorg-libxcb}:${libPaths.libxkbcommon}:${libPaths.dbus}:${libPaths.glib}:${libPaths.systemd}:${libPaths.util-linux}:${libPaths.curl}:${libPaths.zlib}:${libPaths.libssh2}:${libPaths.nghttp2}:${libPaths.brotli}:${libPaths.icu}:${libPaths.libstdcxx}:${libPaths.zstd}:${libPaths.expat}:${libPaths.pcre2}:${libPaths.sqlite}:${libPaths.libpsl}:${libPaths.libidn}:${libPaths.libpng}:${libPaths.libjpeg}:${libPaths.libwebp}:${libPaths.lcms2}:${libPaths.gstreamer}:${libPaths.gst-plugins-base}:${libPaths.libxml2}:${libPaths.libxslt}:${libPaths.enchant}:${libPaths.libnotify}:${libPaths.wayland}:${libPaths.gnutls}:${libPaths.nettle}:${libPaths.libtasn1}:${libPaths.libidn2}:${libPaths.libfido2}/lib:${libPaths.opensc}/lib:${libPaths.libp11}/lib:${libPaths.pcsclite}/lib:${libPaths.p11kit}/lib";

  #############################################################################
  # INTUNE-PORTAL WRAPPER
  #############################################################################

  intunePackage = intunePkg;

  opensslConf = pkgs.writeText "openssl-pkcs11.cnf" ''
    openssl_conf = openssl_init
    [openssl_init]
    engines = engine_section
    [engine_section]
    pkcs11 = pkcs11_section
    [pkcs11_section]
    engine_id = pkcs11
    MODULE_PATH = ${openscArch}/lib/pkcs11/opensc-pkcs11.so
    init = 0
  '';

  intuneWrapper = pkgs.writeShellScriptBin "intune-portal" ''
    #!/usr/bin/env bash
    # intune-portal wrapper: Runs intune-portal with full Nix library paths

    export LD_LIBRARY_PATH="${fullLdLibraryPath}:''${LD_LIBRARY_PATH:-}"

    ${mesaEnvVars}
    ${webkitEnvVars}
    ${tlsEnvVars}
    ${pkcs11EnvVars}

    export OPENSSL_CONF="${opensslConf}"
    export OPENSSL_ENGINES="${pkgs.libp11}/lib/engines-3"
    export GNUTLS_CPUID_OVERRIDE=0x1
    export GNUTLS_FORCE_FIPS_MODE=0

    ${debugEnvVars}

    ${optionalString cfg.debug ''
      echo "[DEBUG] Launching intune-portal..." >&2
      exec ${intunePackage}/bin/intune-portal "$@" 2>&1 | tee -a /tmp/intune-portal.log
    ''}
    ${optionalString (!cfg.debug) ''
      exec ${intunePackage}/bin/intune-portal "$@"
    ''}
  '';

  #############################################################################
  # INTUNE-AGENT WRAPPER
  #############################################################################

  intuneAgentWrapper = pkgs.writeShellScriptBin "intune-agent" ''
    #!/usr/bin/env bash
    # intune-agent wrapper: Runs intune-agent with full Nix library paths

    export LD_LIBRARY_PATH="${fullLdLibraryPath}:''${LD_LIBRARY_PATH:-}"

    ${tlsEnvVars}

    ${optionalString cfg.debug ''
      echo "[DEBUG] intune-agent starting at $(date)" >&2
    ''}

    exec ${intunePackage}/bin/intune-agent "$@"
  '';

  #############################################################################
  # USER BROKER WRAPPER
  #############################################################################

  userBrokerWrapper = pkgs.writeShellScriptBin "microsoft-identity-broker" ''
    #!/usr/bin/env bash
    # microsoft-identity-broker wrapper: Nix-managed wrapper for broker

    export LD_LIBRARY_PATH="${fullLdLibraryPath}:''${LD_LIBRARY_PATH:-}"

    ${mesaEnvVars}
    ${webkitEnvVars}
    ${tlsEnvVars}
    ${pkcs11EnvVars}

    export OPENSSL_CONF="${opensslConf}"
    export OPENSSL_ENGINES="${pkgs.libp11}/lib/engines-3"

    ${debugEnvVars}

    ${optionalString cfg.debug ''
      echo "[DEBUG] Launching user broker (${brokerPkg.version})..." >&2
    ''}

    exec "${brokerPkg}/bin/microsoft-identity-broker" "$@"
  '';

  userBrokerDbusService = pkgs.writeTextFile {
    name = "com.microsoft.identity.broker1.service";
    destination = "/share/dbus-1/services/com.microsoft.identity.broker1.service";
    text = ''
      [D-BUS Service]
      Name=com.microsoft.identity.broker1
      Exec=${userBrokerWrapper}/bin/microsoft-identity-broker
    '';
  };

  #############################################################################
  # DEVICE BROKER WRAPPER
  #############################################################################

  deviceBrokerWrapper = pkgs.writeShellScriptBin "microsoft-identity-device-broker" ''
    #!/usr/bin/env bash
    # microsoft-identity-device-broker wrapper: Nix-managed wrapper for device broker
    #
    # NOTE: Device broker runs as a SYSTEM service. To use this wrapper:
    # 1. sudo systemctl edit microsoft-identity-device-broker.service
    # 2. Add: [Service]
    #         ExecStart=
    #         ExecStart=<nix-store-path>/bin/microsoft-identity-device-broker
    # 3. sudo systemctl daemon-reload && sudo systemctl restart microsoft-identity-device-broker

    export LD_LIBRARY_PATH="${fullLdLibraryPath}:''${LD_LIBRARY_PATH:-}"

    ${debugEnvVars}

    exec "${brokerPkg}/bin/microsoft-identity-device-broker" "$@"
  '';

  #############################################################################
  # HELPER SCRIPTS
  #############################################################################

  logsHelper = pkgs.writeShellScriptBin "intune-logs" ''
    #!/usr/bin/env bash
    case "''${1:---all}" in
      --portal)
        echo "=== intune-portal logs ==="
        tail -f /tmp/intune-portal.log 2>/dev/null || echo "No portal log (run with debug=true)"
        ;;
      --broker)
        echo "=== user broker logs (journald) ==="
        journalctl --user -f -t microsoft-identity-broker
        ;;
      --device)
        echo "=== device broker logs (journald) ==="
        sudo journalctl -u microsoft-identity-device-broker -f
        ;;
      --all|*)
        echo "=== Tailing all Intune logs (Ctrl+C to stop) ==="
        (
          tail -F /tmp/intune-portal.log 2>/dev/null | sed 's/^/[portal] /' &
          journalctl --user -f -t microsoft-identity-broker 2>/dev/null | sed 's/^/[broker] /' &
          sudo journalctl -u microsoft-identity-device-broker -f 2>/dev/null | sed 's/^/[device] /' &
          wait
        )
        ;;
    esac
  '';

  statusHelper = pkgs.writeShellScriptBin "intune-status" ''
    #!/usr/bin/env bash
    echo "=== INTUNE COMPONENT STATUS ==="
    echo ""

    echo "PROCESSES:"
    ps aux | grep -E "(intune|microsoft.*broker)" | grep -v grep || echo "  (none running)"
    echo ""

    echo "SERVICES:"
    echo "  Device broker (system):"
    systemctl status microsoft-identity-device-broker --no-pager 2>/dev/null | head -5 || echo "    Not found"
    echo ""
    echo "  Intune agent timer (user):"
    systemctl --user status intune-agent.timer --no-pager 2>/dev/null | head -5 || echo "    Not found"
    echo ""

    echo "D-BUS SERVICES:"
    if [[ -f ~/.local/share/dbus-1/services/com.microsoft.identity.broker1.service ]]; then
      echo "  User broker: ~/.local/share/dbus-1/services/com.microsoft.identity.broker1.service (Nix-managed)"
    else
      echo "  User broker: /usr/share/dbus-1/services/com.microsoft.identity.broker1.service (system)"
    fi
    echo ""

    echo "VERSIONS:"
    echo "  intune-portal: ${intunePackage.version}"
    echo "  broker: ${brokerPkg.version}"
    echo ""

    echo "SMART CARD:"
    systemctl is-active pcscd.socket 2>/dev/null && echo "  pcscd: active" || echo "  pcscd: inactive"
    p11tool --list-tokens 2>/dev/null | grep -i yubi | head -1 || echo "  YubiKey: not detected"
    echo ""

    echo "OS-RELEASE:"
    grep PRETTY_NAME /etc/os-release 2>/dev/null || echo "  (not set)"
  '';

  setupHelper = pkgs.writeShellScriptBin "intune-setup" ''
    set -euo pipefail
    echo "=== Intune System Setup (Nix libs) ==="
    echo ""

    echo "[1/4] Spoofing os-release..."
    cat << 'OSEOF' | sudo tee /etc/os-release > /dev/null
NAME="Ubuntu"
VERSION="22.04.3 LTS (Jammy Jellyfish)"
ID=ubuntu
ID_LIKE=debian
PRETTY_NAME="Ubuntu 22.04.3 LTS"
VERSION_ID="22.04"
VERSION_CODENAME=jammy
OSEOF
    sudo cp /etc/os-release /usr/lib/os-release
    echo "  -> os-release set to Ubuntu 22.04"

    echo "[2/4] Configuring pcscd (YubiKey access)..."
    sudo mkdir -p /etc/systemd/system/pcscd.service.d
    cat << 'PCSCDEOF' | sudo tee /etc/systemd/system/pcscd.service.d/override.conf > /dev/null
[Service]
ExecStart=
ExecStart=/usr/bin/pcscd --foreground --auto-exit
PCSCDEOF
    echo "  -> pcscd override installed"

    echo "[3/4] Enabling pcscd..."
    sudo systemctl daemon-reload
    sudo systemctl enable --now pcscd.socket
    echo "  -> pcscd.socket enabled"

    echo "[4/4] Setting up p11-kit module..."
    sudo mkdir -p /etc/pkcs11/modules
    echo "module: ${openscArch}/lib/pkcs11/opensc-pkcs11.so" | sudo tee /etc/pkcs11/modules/opensc.module > /dev/null
    echo "  -> OpenSC p11-kit module registered"

    echo ""
    echo "Done! System configs installed."
    echo ""
    echo "Next steps:"
    echo "  1. Set up GNOME keyring with password-protected 'login' collection"
    echo "  2. Enable intune-agent timer: systemctl --user enable --now intune-agent.timer"
    echo "  3. Enroll: intune-portal"
  '';

in {
  options.modules.linux.intune-nix = {
    enable = mkEnableOption "Microsoft Intune with full Nix library chain (x86_64)";

    debug = mkOption {
      type = types.bool;
      default = false;
      description = "Enable debug logging for all Intune components";
    };
  };

  config = mkIf (cfg.enable && pkgs.stdenv.isLinux && pkgs.stdenv.hostPlatform.isx86_64) {
    home.packages = [
      # NOTE: We don't add intunePackage or brokerPkg directly to avoid conflicts
      # with the wrapper scripts that also provide intune-portal, intune-agent, etc.
      # The wrappers exec the underlying binaries with proper LD_LIBRARY_PATH.

      # Keyring support
      pkgs.gnome-keyring
      pkgs.seahorse
      pkgs.libsecret

      # YubiKey/smart card tools
      pkgs.yubikey-manager
      pkgs.pcsc-tools

      # Helper scripts
      logsHelper
      statusHelper
      setupHelper

      # NSS tools for browser smart card setup
      pkgs.nss.tools

      # Wrappers
      intuneWrapper
      intuneAgentWrapper
      userBrokerWrapper
      deviceBrokerWrapper

      # D-Bus service override
      userBrokerDbusService

      # Required libraries
      pkgs.libglvnd
      pkgs.wayland
      pkgs.mesa
      pkgs.glib-networking
      pkgs.gnutls
      pkgs.nettle
      pkgs.libtasn1
      pkgs.libidn2
      openscArch
      pkgs.libp11
      pkgs.pcsclite.lib
      pkgs.p11-kit
      pkgs.p11-kit.bin
      pkgs.libfido2
      pkgs.dbus.lib
      pkgs.glib.out
      pkgs.systemdLibs
      pkgs.util-linux.lib
      curlNoHttp3.out
      pkgs.zlib.out
      pkgs.libssh2.out
      pkgs.nghttp2.lib
      pkgs.brotli.lib
      pkgs.icu.out
      pkgs.stdenv.cc.cc.lib
      pkgs.zstd.out
      pkgs.expat.out
      pkgs.pcre2.out
      pkgs.xorg.libX11.out
      pkgs.xorg.libXext.out
      pkgs.xorg.libXrender.out
      pkgs.xorg.libXi.out
      pkgs.xorg.libXcursor.out
      pkgs.xorg.libXrandr.out
      pkgs.xorg.libXfixes.out
      pkgs.xorg.libXcomposite.out
      pkgs.xorg.libXdamage.out
      pkgs.xorg.libxcb.out
      pkgs.libxkbcommon.out
      pkgs.fontconfig.lib
      pkgs.freetype.out
      pkgs.cairo.out
      pkgs.pango.out
      pkgs.gdk-pixbuf.out
      pkgs.gtk3.out
      pkgs.atk.out
      pkgs.at-spi2-atk.out
      pkgs.at-spi2-core.out
      pkgs.harfbuzz.out
      pkgs.webkitgtk_4_1.out
      pkgs.libsoup_3.out
      pkgs.sqlite.out
      pkgs.libpsl.out
      pkgs.libidn.out
      pkgs.libpng.out
      pkgs.libjpeg.out
      pkgs.libwebp.out
      pkgs.lcms2.out
      pkgs.gst_all_1.gstreamer.out
      pkgs.gst_all_1.gst-plugins-base.out
      pkgs.libxml2.out
      pkgs.libxslt.out
      pkgs.enchant.out
      pkgs.libnotify.out
      opensslArch
    ];

    # Install D-Bus service file to user's local share
    xdg.dataFile."dbus-1/services/com.microsoft.identity.broker1.service" = {
      source = "${userBrokerDbusService}/share/dbus-1/services/com.microsoft.identity.broker1.service";
    };

    # Install PKCS#11 module config for p11-kit
    xdg.configFile."pkcs11/modules/opensc.module".text = ''
module: ${openscArch}/lib/pkcs11/opensc-pkcs11.so
critical: no
trust-policy: no
'';

    # Systemd user service for intune-agent
    systemd.user.services.intune-agent = {
      Unit = {
        Description = "Intune Agent - compliance reporting";
      };
      Service = {
        Type = "oneshot";
        ExecStart = "${intuneAgentWrapper}/bin/intune-agent";
        StateDirectory = "intune";
        Slice = "background.slice";
      };
    };

    systemd.user.timers.intune-agent = {
      Unit = {
        Description = "Intune Agent scheduler";
        PartOf = [ "graphical-session.target" ];
        After = [ "graphical-session.target" ];
      };
      Timer = {
        OnStartupSec = "5m";
        OnUnitActiveSec = "1h";
        RandomizedDelaySec = "10m";
        AccuracySec = "2m";
      };
      Install = {
        WantedBy = [ "graphical-session.target" ];
      };
    };

    # Activation script to verify setup
    home.activation.verifyIntuneNixSetup =
      lib.hm.dag.entryAfter [ "writeBoundary" "linkGeneration" ] ''
        if [[ -f "$HOME/.local/share/dbus-1/services/com.microsoft.identity.broker1.service" ]]; then
          noteEcho "User broker D-Bus service installed (Nix-managed, version ${brokerPkg.version})"
        else
          warnEcho "User broker D-Bus service not found in ~/.local/share/dbus-1/services/"
        fi

        noteEcho "Run 'intune-setup' to configure system-level settings (os-release, pcscd)"
        noteEcho "Then run 'intune-portal' to enroll"
      '';
  };
}
