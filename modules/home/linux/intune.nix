# modules/home/linux/intune.nix -- Microsoft Intune Portal + Identity Brokers
#
# Full Nix-managed solution for Microsoft Intune on aarch64-linux with Rosetta.
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
#   2. microsoft-identity-broker (Nix 2.0.4): User SSO authentication
#   3. microsoft-identity-device-broker (Nix 2.0.4): Device attestation (system service)
#
# ROSETTA REQUIREMENTS:
#   - All x86_64 binaries run via Rosetta binfmt_misc
#   - libglvnd MUST be first in LD_LIBRARY_PATH for Mesa software rendering
#   - Broker needs OpenSSL 3.3.2 in LD_LIBRARY_PATH (fixes Code:1200 error)
#   - WebKitGTK needs WEBKIT_DISABLE_DMABUF_RENDERER=1 (NOT COMPOSITING_MODE!)
#
# MANUAL PREREQUISITES:
#   1. Fake Ubuntu os-release: sudo tee /etc/os-release << 'EOF'
#      NAME="Ubuntu"
#      VERSION="22.04.3 LTS (Jammy Jellyfish)"
#      ID=ubuntu
#      PRETTY_NAME="Ubuntu 22.04.3 LTS"
#      VERSION_ID="22.04"
#      EOF
#
# DEBUGGING:
#   - Set modules.linux.intune.debug = true for verbose logging
#   - Run: intune-logs (tails all service logs)
#   - Logs: /tmp/intune-portal.log, journalctl --user, journalctl -u microsoft-identity-device-broker
#
# See: https://github.com/recolic/microsoft-intune-archlinux

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.linux.intune;
  isAarch64 = pkgs.stdenv.hostPlatform.isAarch64;

  #############################################################################
  # x86_64 PACKAGES (for Rosetta emulation)
  #############################################################################

  pkgsX86 = import pkgs.path {
    system = "x86_64-linux";
    config.allowUnfree = true;
  };

  # Microsoft Identity Broker package (x86_64 binaries from Microsoft .deb)
  brokerPkg = pkgsX86.callPackage ../../../packages/microsoft-identity-broker { };

  # Custom curl without HTTP/3 support to avoid ngtcp2's OPENSSL_3.5.0 requirement
  # This allows us to use Arch OpenSSL 3.3.2 for the broker without symbol conflicts
  curlNoHttp3 = pkgsX86.curl.override { http3Support = false; };

  #############################################################################
  # OPENSSL 3.3.2 (fixes Code:1200 error in broker)
  #############################################################################

  # OpenSSL 3.3.2 from Arch Linux archives
  # Required because broker on Arch links system OpenSSL 3.6.0 which has
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


  #############################################################################
  # SHARED ENVIRONMENT SETUP
  #############################################################################

  # Common x86_64 library paths for all wrappers
  x86LibPaths = {
    glvnd = "${pkgsX86.libglvnd}/lib";
    mesa = "${pkgsX86.mesa}";
    wayland = "${pkgsX86.wayland}/lib";
    gio = "${pkgsX86.glib-networking}/lib/gio/modules";
    gnutls = "${pkgsX86.gnutls}/lib";
    nettle = "${pkgsX86.nettle}/lib";
    libtasn1 = "${pkgsX86.libtasn1}/lib";
    libidn2 = "${pkgsX86.libidn2}/lib";
    opensc = "${pkgsX86.opensc}";
    libp11 = "${pkgsX86.libp11}";
    pcsclite = "${pkgsX86.pcsclite.lib}";
    p11kit = "${pkgsX86.p11-kit.out}";
    libfido2 = "${pkgsX86.libfido2}";
    # System libraries needed by AUR broker
    dbus = "${pkgsX86.dbus.lib}/lib";
    glib = "${pkgsX86.glib.out}/lib";
    systemd = "${pkgsX86.systemdLibs}/lib";
    util-linux = "${pkgsX86.util-linux.lib}/lib";
    curl = "${curlNoHttp3.out}/lib";
    zlib = "${pkgsX86.zlib.out}/lib";
    libssh2 = "${pkgsX86.libssh2.out}/lib";
    nghttp2 = "${pkgsX86.nghttp2.lib}/lib";
    brotli = "${pkgsX86.brotli.lib}/lib";
    icu = "${pkgsX86.icu.out}/lib";
    libstdcxx = "${pkgsX86.stdenv.cc.cc.lib}/lib";
    zstd = "${pkgsX86.zstd.out}/lib";
    # X11 and GUI libraries
    xorg-libX11 = "${pkgsX86.xorg.libX11.out}/lib";
    xorg-libXext = "${pkgsX86.xorg.libXext.out}/lib";
    xorg-libXrender = "${pkgsX86.xorg.libXrender.out}/lib";
    xorg-libXi = "${pkgsX86.xorg.libXi.out}/lib";
    xorg-libXcursor = "${pkgsX86.xorg.libXcursor.out}/lib";
    xorg-libXrandr = "${pkgsX86.xorg.libXrandr.out}/lib";
    xorg-libXfixes = "${pkgsX86.xorg.libXfixes.out}/lib";
    xorg-libXcomposite = "${pkgsX86.xorg.libXcomposite.out}/lib";
    xorg-libXdamage = "${pkgsX86.xorg.libXdamage.out}/lib";
    xorg-libxcb = "${pkgsX86.xorg.libxcb.out}/lib";
    libxkbcommon = "${pkgsX86.libxkbcommon.out}/lib";
    fontconfig = "${pkgsX86.fontconfig.lib}/lib";
    freetype = "${pkgsX86.freetype.out}/lib";
    expat = "${pkgsX86.expat.out}/lib";
    cairo = "${pkgsX86.cairo.out}/lib";
    pango = "${pkgsX86.pango.out}/lib";
    gdk-pixbuf = "${pkgsX86.gdk-pixbuf.out}/lib";
    gtk3 = "${pkgsX86.gtk3.out}/lib";
    atk = "${pkgsX86.atk.out}/lib";
    at-spi2-atk = "${pkgsX86.at-spi2-atk.out}/lib";
    at-spi2-core = "${pkgsX86.at-spi2-core.out}/lib";
    harfbuzz = "${pkgsX86.harfbuzz.out}/lib";
    pcre2 = "${pkgsX86.pcre2.out}/lib";
    webkitgtk = "${pkgsX86.webkitgtk_4_1.out}/lib";
    libsoup = "${pkgsX86.libsoup_3.out}/lib";
    libsecret = "${pkgsX86.libsecret.out}/lib";
    sqlite = "${pkgsX86.sqlite.out}/lib";
    libpsl = "${pkgsX86.libpsl.out}/lib";
    libidn = "${pkgsX86.libidn.out}/lib";
    libpng = "${pkgsX86.libpng.out}/lib";
    libjpeg = "${pkgsX86.libjpeg.out}/lib";
    libwebp = "${pkgsX86.libwebp.out}/lib";
    lcms2 = "${pkgsX86.lcms2.out}/lib";
    gstreamer = "${pkgsX86.gst_all_1.gstreamer.out}/lib";
    gst-plugins-base = "${pkgsX86.gst_all_1.gst-plugins-base.out}/lib";
    libxml2 = "${pkgsX86.libxml2.out}/lib";
    libxslt = "${pkgsX86.libxslt.out}/lib";
    enchant = "${pkgsX86.enchant.out}/lib";
    libnotify = "${pkgsX86.libnotify.out}/lib";
    # Arch OpenSSL 3.3.2 - fixes Code:1200 error in AUR broker
    opensslArch = "${opensslArch}/lib";
  };

  # Environment variables for Mesa software rendering under Rosetta
  mesaEnvVars = ''
    # Mesa software rendering (llvmpipe) - required for Rosetta
    export LIBGL_ALWAYS_SOFTWARE=1
    export GALLIUM_DRIVER=llvmpipe
    export MESA_LOADER_DRIVER_OVERRIDE=llvmpipe
    export __EGL_VENDOR_LIBRARY_DIRS="${x86LibPaths.mesa}/share/glvnd/egl_vendor.d"
    export LIBGL_DRIVERS_PATH="${x86LibPaths.mesa}/lib/dri"
  '';

  # Environment variables for WebKitGTK under Rosetta
  webkitEnvVars = ''
    # WebKitGTK settings for Rosetta
    # NOTE: Do NOT set WEBKIT_DISABLE_COMPOSITING_MODE=1 - causes blank windows!
    export WEBKIT_DISABLE_DMABUF_RENDERER=1
    export GDK_BACKEND=x11
  '';

  # Environment variables for TLS/SSL
  tlsEnvVars = ''
    # GIO TLS backend (glib-networking) for HTTPS
    export GIO_MODULE_DIR="${x86LibPaths.gio}"
    export SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt"
    export SSL_CERT_DIR="/etc/ssl/certs"
  '';

  # Debug environment variables (when cfg.debug is true)
  debugEnvVars = optionalString cfg.debug ''
    # Debug output
    export G_MESSAGES_DEBUG=all
    export WEBKIT_DEBUG=all
    export LIBGL_DEBUG=verbose
    echo "[DEBUG] Starting at $(date)" >&2
    echo "[DEBUG] LD_LIBRARY_PATH=$LD_LIBRARY_PATH" >&2
    echo "[DEBUG] LD_PRELOAD=$LD_PRELOAD" >&2
  '';

  #############################################################################
  # INTUNE-PORTAL (from Nix)
  #############################################################################

  intunePackage = if isAarch64 then pkgsX86.intune-portal else pkgs.intune-portal;

  # p11-kit module config for x86_64 opensc (YubiKey support)
  p11kitModuleDir = pkgs.runCommand "p11kit-x86-modules" {} ''
    mkdir -p $out
    cat > $out/opensc.module << EOF
    module: ${pkgsX86.opensc}/lib/pkcs11/opensc-pkcs11.so
    critical: no
    EOF
  '';

  # OpenSSL config for PKCS#11 (YubiKey support)
  opensslConf = pkgs.writeText "openssl-pkcs11.cnf" ''
    openssl_conf = openssl_init
    [openssl_init]
    engines = engine_section
    [engine_section]
    pkcs11 = pkcs11_section
    [pkcs11_section]
    engine_id = pkcs11
    MODULE_PATH = ${pkgsX86.opensc}/lib/pkcs11/opensc-pkcs11.so
    init = 0
  '';

  # Wrapper for intune-portal with Rosetta compatibility
  intuneWrapper = pkgs.writeShellScriptBin "intune-portal-rosetta" ''
    #!/usr/bin/env bash
    # intune-portal-rosetta: Runs intune-portal with x86_64 Mesa under Rosetta
    #
    # NOTE: intune-portal bundles OpenSSL 3.0.18, so NO LD_PRELOAD needed here.
    # The LD_PRELOAD is only for the AUR broker which uses system OpenSSL.

    # LD_LIBRARY_PATH: libglvnd MUST be first for Mesa software rendering
    export LD_LIBRARY_PATH="${x86LibPaths.glvnd}:${x86LibPaths.mesa}/lib:${x86LibPaths.libfido2}/lib:${x86LibPaths.wayland}:${x86LibPaths.gnutls}:${x86LibPaths.nettle}:${x86LibPaths.libtasn1}:${x86LibPaths.libidn2}:${x86LibPaths.opensc}/lib:${x86LibPaths.libp11}/lib:${x86LibPaths.pcsclite}/lib:${x86LibPaths.p11kit}/lib:''${LD_LIBRARY_PATH:-}"

    ${mesaEnvVars}
    ${webkitEnvVars}
    ${tlsEnvVars}

    # PKCS#11/YubiKey support
    export OPENSSL_CONF="${opensslConf}"
    export OPENSSL_ENGINES="${x86LibPaths.libp11}/lib/engines-3"
    export PCSCLITE_CSOCK_NAME="/run/pcscd/pcscd.comm"
    export P11_KIT_MODULE_PATH="${x86LibPaths.opensc}/lib/pkcs11:${x86LibPaths.p11kit}/pkcs11"
    export P11_KIT_MODULE_CONFIGS="${p11kitModuleDir}"
    # Tell GnuTLS to use p11-kit proxy for PKCS#11
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
  # USER BROKER (Nix package + wrapper)
  #############################################################################

  # Wrapper for user broker with Rosetta + OpenSSL fix
  userBrokerWrapper = pkgs.writeShellScriptBin "microsoft-identity-broker-rosetta" ''
    #!/usr/bin/env bash
    # microsoft-identity-broker-rosetta: Nix-managed wrapper for broker
    #
    # This wrapper:
    # 1. Provides OpenSSL 3.3.2 via LD_LIBRARY_PATH (fixes Code:1200 error)
    # 2. Provides x86_64 system libraries (dbus, glib, systemd) for Rosetta
    # 3. Sets up Mesa software rendering for WebKitGTK SSO popups
    # 4. Configures GIO TLS for HTTPS

    # LD_LIBRARY_PATH construction - comprehensive x86_64 library set for Rosetta
    # NOTE: Arch OpenSSL 3.3.2 is included to fix Code:1200 "credential is invalid" error
    # We use curlNoHttp3 (curl with http3Support=false) to avoid ngtcp2's OPENSSL_3.5.0 requirement
    export LD_LIBRARY_PATH="${x86LibPaths.opensslArch}:${x86LibPaths.glvnd}:${x86LibPaths.mesa}/lib:${x86LibPaths.webkitgtk}:${x86LibPaths.libsoup}:${x86LibPaths.libsecret}:${x86LibPaths.gtk3}:${x86LibPaths.gdk-pixbuf}:${x86LibPaths.cairo}:${x86LibPaths.pango}:${x86LibPaths.harfbuzz}:${x86LibPaths.fontconfig}:${x86LibPaths.freetype}:${x86LibPaths.atk}:${x86LibPaths.at-spi2-atk}:${x86LibPaths.at-spi2-core}:${x86LibPaths.xorg-libX11}:${x86LibPaths.xorg-libXext}:${x86LibPaths.xorg-libXrender}:${x86LibPaths.xorg-libXi}:${x86LibPaths.xorg-libXcursor}:${x86LibPaths.xorg-libXrandr}:${x86LibPaths.xorg-libXfixes}:${x86LibPaths.xorg-libXcomposite}:${x86LibPaths.xorg-libXdamage}:${x86LibPaths.xorg-libxcb}:${x86LibPaths.libxkbcommon}:${x86LibPaths.dbus}:${x86LibPaths.glib}:${x86LibPaths.systemd}:${x86LibPaths.util-linux}:${x86LibPaths.curl}:${x86LibPaths.zlib}:${x86LibPaths.libssh2}:${x86LibPaths.nghttp2}:${x86LibPaths.brotli}:${x86LibPaths.icu}:${x86LibPaths.libstdcxx}:${x86LibPaths.zstd}:${x86LibPaths.expat}:${x86LibPaths.pcre2}:${x86LibPaths.sqlite}:${x86LibPaths.libpsl}:${x86LibPaths.libidn}:${x86LibPaths.libpng}:${x86LibPaths.libjpeg}:${x86LibPaths.libwebp}:${x86LibPaths.lcms2}:${x86LibPaths.gstreamer}:${x86LibPaths.gst-plugins-base}:${x86LibPaths.libxml2}:${x86LibPaths.libxslt}:${x86LibPaths.enchant}:${x86LibPaths.libnotify}:${x86LibPaths.p11kit}/lib:''${LD_LIBRARY_PATH:-}"

    ${mesaEnvVars}
    ${webkitEnvVars}
    ${tlsEnvVars}

    # PKCS#11/YubiKey support (required for certificate-based auth)
    export OPENSSL_CONF="${opensslConf}"
    export OPENSSL_ENGINES="${x86LibPaths.libp11}/lib/engines-3"
    export PCSCLITE_CSOCK_NAME="/run/pcscd/pcscd.comm"
    export P11_KIT_MODULE_PATH="${x86LibPaths.opensc}/lib/pkcs11"
    export P11_KIT_MODULE_CONFIGS="${p11kitModuleDir}"

    ${debugEnvVars}

    ${optionalString cfg.debug ''
      echo "[DEBUG] Launching user broker (${brokerPkg.version})..." >&2
    ''}

    exec "${brokerPkg}/bin/microsoft-identity-broker" "$@"
  '';

  # D-Bus service file for user broker (overrides system-wide /usr/share/dbus-1/services/)
  userBrokerDbusService = pkgs.writeTextFile {
    name = "com.microsoft.identity.broker1.service";
    destination = "/share/dbus-1/services/com.microsoft.identity.broker1.service";
    text = ''
      [D-BUS Service]
      Name=com.microsoft.identity.broker1
      Exec=${userBrokerWrapper}/bin/microsoft-identity-broker-rosetta
    '';
  };

  #############################################################################
  # DEVICE BROKER (Nix package, system service - wrapper for reference)
  #############################################################################

  # Wrapper for device broker (for manual system configuration)
  # NOTE: This is installed to user profile but needs manual systemd config
  deviceBrokerWrapper = pkgs.writeShellScriptBin "microsoft-identity-device-broker-rosetta" ''
    #!/usr/bin/env bash
    # microsoft-identity-device-broker-rosetta: Nix-managed wrapper for device broker
    #
    # NOTE: Device broker runs as a SYSTEM service. To use this wrapper:
    # 1. sudo systemctl edit microsoft-identity-device-broker.service
    # 2. Add: [Service]
    #         ExecStart=
    #         ExecStart=<nix-store-path>/bin/microsoft-identity-device-broker-rosetta
    # 3. sudo systemctl daemon-reload && sudo systemctl restart microsoft-identity-device-broker
    #
    # IMPORTANT: Use the full nix store path (not ~/.nix-profile) because root cannot
    # traverse /home/user directories.

    # Device broker shares same dependencies as user broker (WebKitGTK, GTK, etc.)
    # Use the same comprehensive LD_LIBRARY_PATH
    export LD_LIBRARY_PATH="${x86LibPaths.opensslArch}:${x86LibPaths.glvnd}:${x86LibPaths.mesa}/lib:${x86LibPaths.webkitgtk}:${x86LibPaths.libsoup}:${x86LibPaths.libsecret}:${x86LibPaths.gtk3}:${x86LibPaths.gdk-pixbuf}:${x86LibPaths.cairo}:${x86LibPaths.pango}:${x86LibPaths.harfbuzz}:${x86LibPaths.fontconfig}:${x86LibPaths.freetype}:${x86LibPaths.atk}:${x86LibPaths.at-spi2-atk}:${x86LibPaths.at-spi2-core}:${x86LibPaths.xorg-libX11}:${x86LibPaths.xorg-libXext}:${x86LibPaths.xorg-libXrender}:${x86LibPaths.xorg-libXi}:${x86LibPaths.xorg-libXcursor}:${x86LibPaths.xorg-libXrandr}:${x86LibPaths.xorg-libXfixes}:${x86LibPaths.xorg-libXcomposite}:${x86LibPaths.xorg-libXdamage}:${x86LibPaths.xorg-libxcb}:${x86LibPaths.libxkbcommon}:${x86LibPaths.dbus}:${x86LibPaths.glib}:${x86LibPaths.systemd}:${x86LibPaths.util-linux}:${x86LibPaths.curl}:${x86LibPaths.zlib}:${x86LibPaths.libssh2}:${x86LibPaths.nghttp2}:${x86LibPaths.brotli}:${x86LibPaths.icu}:${x86LibPaths.libstdcxx}:${x86LibPaths.zstd}:${x86LibPaths.expat}:${x86LibPaths.pcre2}:${x86LibPaths.sqlite}:${x86LibPaths.libpsl}:${x86LibPaths.libidn}:${x86LibPaths.libpng}:${x86LibPaths.libjpeg}:${x86LibPaths.libwebp}:${x86LibPaths.lcms2}:${x86LibPaths.gstreamer}:${x86LibPaths.gst-plugins-base}:${x86LibPaths.libxml2}:${x86LibPaths.libxslt}:${x86LibPaths.enchant}:${x86LibPaths.libnotify}:${x86LibPaths.p11kit}/lib:''${LD_LIBRARY_PATH:-}"

    ${debugEnvVars}

    exec "${brokerPkg}/bin/microsoft-identity-device-broker" "$@"
  '';

  #############################################################################
  # LOGGING HELPER
  #############################################################################

  logsHelper = pkgs.writeShellScriptBin "intune-logs" ''
    #!/usr/bin/env bash
    # intune-logs: Tail all Intune-related logs
    #
    # Usage: intune-logs [--all|--portal|--broker|--device]

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
        echo "=== Portal: /tmp/intune-portal.log | Broker: journalctl --user | Device: journalctl -u ... ==="
        echo ""
        (
          tail -F /tmp/intune-portal.log 2>/dev/null | sed 's/^/[portal] /' &
          journalctl --user -f -t microsoft-identity-broker 2>/dev/null | sed 's/^/[broker] /' &
          sudo journalctl -u microsoft-identity-device-broker -f 2>/dev/null | sed 's/^/[device] /' &
          wait
        )
        ;;
    esac
  '';

  #############################################################################
  # STATUS HELPER
  #############################################################################

  statusHelper = pkgs.writeShellScriptBin "intune-status" ''
    #!/usr/bin/env bash
    # intune-status: Show status of all Intune components

    echo "=== INTUNE COMPONENT STATUS ==="
    echo ""

    echo "PROCESSES:"
    ps aux | grep -E "(intune|microsoft.*broker)" | grep -v grep || echo "  (none running)"
    echo ""

    echo "SERVICES:"
    echo "  Device broker (system):"
    systemctl status microsoft-identity-device-broker --no-pager 2>/dev/null | head -5 || echo "    Not found"
    echo ""

    echo "D-BUS SERVICES:"
    echo "  User broker activation file:"
    if [[ -f ~/.local/share/dbus-1/services/com.microsoft.identity.broker1.service ]]; then
      echo "    ~/.local/share/dbus-1/services/com.microsoft.identity.broker1.service (Nix-managed)"
      cat ~/.local/share/dbus-1/services/com.microsoft.identity.broker1.service | sed 's/^/    /'
    else
      echo "    /usr/share/dbus-1/services/com.microsoft.identity.broker1.service (system)"
    fi
    echo ""

    echo "VERSIONS:"
    echo "  intune-portal: ${intunePackage.version}"
    echo "  user broker: ${brokerPkg.version} (Nix)"
    echo "  device broker: ${brokerPkg.version} (Nix)"
    echo ""

    echo "NIX WRAPPERS:"
    echo "  intune-portal-rosetta: $(which intune-portal-rosetta 2>/dev/null || echo 'not in PATH')"
    echo "  microsoft-identity-broker-rosetta: $(which microsoft-identity-broker-rosetta 2>/dev/null || echo 'not in PATH')"
    echo ""
  '';

in {
  options.modules.linux.intune = {
    enable = mkEnableOption "Microsoft Intune Portal with identity brokers";

    debug = mkOption {
      type = types.bool;
      default = false;
      description = "Enable debug logging for all Intune components";
    };
  };

  config = mkIf (cfg.enable && pkgs.stdenv.isLinux) {
    # Enable Rosetta support on aarch64
    modules.linux.rosetta.enable = mkIf isAarch64 true;

    # Install packages
    home.packages = [
      # Main application
      intunePackage

      # Keyring support (required for credential storage)
      pkgs.gnome-keyring
      pkgs.seahorse
      pkgs.libsecret

      # YubiKey/smart card tools
      pkgs.yubikey-manager
      pkgs.pcsc-tools

      # Helper scripts
      logsHelper
      statusHelper
    ] ++ (if isAarch64 then [
      # Rosetta wrappers (reference brokerPkg binaries directly)
      intuneWrapper
      userBrokerWrapper
      deviceBrokerWrapper

      # D-Bus service override for user broker
      userBrokerDbusService

      # Required x86_64 libraries
      pkgsX86.libglvnd
      pkgsX86.wayland
      pkgsX86.mesa
      pkgsX86.glib-networking
      pkgsX86.gnutls
      pkgsX86.nettle
      pkgsX86.libtasn1
      pkgsX86.libidn2
      pkgsX86.opensc
      pkgsX86.libp11
      pkgsX86.pcsclite.lib
      pkgsX86.p11-kit
      pkgsX86.libfido2
      # System libraries for AUR broker
      pkgsX86.dbus.lib
      pkgsX86.glib.out
      pkgsX86.systemdLibs
      pkgsX86.util-linux.lib
      curlNoHttp3.out
      pkgsX86.zlib.out
      pkgsX86.libssh2.out
      pkgsX86.nghttp2.lib
      pkgsX86.brotli.lib
      pkgsX86.icu.out
      pkgsX86.stdenv.cc.cc.lib
      pkgsX86.zstd.out
      pkgsX86.expat.out
      pkgsX86.pcre2.out
      # X11 and GUI libraries
      pkgsX86.xorg.libX11.out
      pkgsX86.xorg.libXext.out
      pkgsX86.xorg.libXrender.out
      pkgsX86.xorg.libXi.out
      pkgsX86.xorg.libXcursor.out
      pkgsX86.xorg.libXrandr.out
      pkgsX86.xorg.libXfixes.out
      pkgsX86.xorg.libXcomposite.out
      pkgsX86.xorg.libXdamage.out
      pkgsX86.xorg.libxcb.out
      pkgsX86.libxkbcommon.out
      pkgsX86.fontconfig.lib
      pkgsX86.freetype.out
      pkgsX86.cairo.out
      pkgsX86.pango.out
      pkgsX86.gdk-pixbuf.out
      pkgsX86.gtk3.out
      pkgsX86.atk.out
      pkgsX86.at-spi2-atk.out
      pkgsX86.at-spi2-core.out
      pkgsX86.harfbuzz.out
      # WebKitGTK and related
      pkgsX86.webkitgtk_4_1.out
      pkgsX86.libsoup_3.out
      # libsecret already included via webkitgtk dependencies
      pkgsX86.sqlite.out
      pkgsX86.libpsl.out
      pkgsX86.libidn.out
      pkgsX86.libpng.out
      pkgsX86.libjpeg.out
      pkgsX86.libwebp.out
      pkgsX86.lcms2.out
      pkgsX86.gst_all_1.gstreamer.out
      pkgsX86.gst_all_1.gst-plugins-base.out
      pkgsX86.libxml2.out
      pkgsX86.libxslt.out
      pkgsX86.enchant.out
      pkgsX86.libnotify.out
      # OpenSSL 3.3.2 for broker Code:1200 fix
      opensslArch
    ] else []);

    # Install D-Bus service file to user's local share
    # This overrides /usr/share/dbus-1/services/com.microsoft.identity.broker1.service
    xdg.dataFile = mkIf isAarch64 {
      "dbus-1/services/com.microsoft.identity.broker1.service" = {
        source = "${userBrokerDbusService}/share/dbus-1/services/com.microsoft.identity.broker1.service";
      };
    };

    # Set systemd user session environment variables for WebKitGTK
    # These are needed for D-Bus activated services that spawn WebKit subprocesses
    # See: https://github.com/recolic/microsoft-intune-archlinux
    systemd.user.sessionVariables = mkIf isAarch64 {
      WEBKIT_DISABLE_DMABUF_RENDERER = "1";
      LIBGL_ALWAYS_SOFTWARE = "1";
      GDK_BACKEND = "x11";
    };

    # Activation script to verify setup
    home.activation.verifyIntuneSetup = mkIf isAarch64
      (lib.hm.dag.entryAfter [ "writeBoundary" "linkGeneration" ] ''
        # Verify D-Bus service file is in place
        if [[ -f "$HOME/.local/share/dbus-1/services/com.microsoft.identity.broker1.service" ]]; then
          noteEcho "User broker D-Bus service installed (Nix-managed, version ${brokerPkg.version})"
        else
          warnEcho "User broker D-Bus service not found in ~/.local/share/dbus-1/services/"
        fi

        # Remind about device broker (system service)
        noteEcho "Device broker runs as system service. For Rosetta compatibility, run:"
        noteEcho "  sudo systemctl edit microsoft-identity-device-broker.service"
        noteEcho "  # Add: ExecStart="
        noteEcho "  # Add: ExecStart=$HOME/.nix-profile/bin/microsoft-identity-device-broker-rosetta"
      '');
  };
}
