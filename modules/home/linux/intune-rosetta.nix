# modules/home/linux/intune-rosetta.nix -- Microsoft Intune Portal + Identity Brokers (aarch64/Rosetta)
#
# Full Nix-managed solution for Microsoft Intune on aarch64-linux via Rosetta emulation.
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
#   - WebKitGTK needs WEBKIT_DISABLE_DMABUF_RENDERER=1 (NOT COMPOSITING_MODE!)
#   - Broker needs OpenSSL 3.3.2 in LD_LIBRARY_PATH (fixes Code:1200 error)
#   - LD_LIBRARY_PATH needed for Nix store libs on non-NixOS (Arch + home-manager)
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
  cfg = config.modules.linux.intune-rosetta;

  #############################################################################
  # PACKAGE SOURCES
  #############################################################################

  # Cross-arch x86_64 packages (run via Rosetta on aarch64)
  pkgsX86 = import pkgs.path {
    system = "x86_64-linux";
    config.allowUnfree = true;
  };

  # Microsoft Identity Broker package (x86_64 binaries from Microsoft .deb)
  brokerPkg = pkgsX86.callPackage ../../../packages/microsoft-identity-broker { };

  # Microsoft Intune Portal package (x86_64 binaries from Microsoft .deb)
  # Using custom package to get latest version (nixpkgs is often outdated)
  intunePkg = pkgsX86.callPackage ../../../packages/intune-portal { };

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

  # OpenSC 0.25.1 from Arch Linux archives
  # Required because Nix OpenSC 0.26.1 requires OPENSSL_3.4.0 symbols,
  # but we use Arch OpenSSL 3.3.2 (which only has up to OPENSSL_3.0.0).
  # This version was built April 2024, before OpenSSL 3.4.0 was released.
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
      # Move usr contents to $out root
      mv $out/usr/* $out/
      rm -rf $out/usr $out/.BUILDINFO $out/.MTREE $out/.PKGINFO $out/etc
    '';
  };


  #############################################################################
  # SHARED ENVIRONMENT SETUP
  #############################################################################

  # Library paths for all wrappers (uses pkgsX86: native on x86_64, cross on aarch64)
  libPaths = {
    glvnd = "${pkgsX86.libglvnd}/lib";
    mesa = "${pkgsX86.mesa}";
    wayland = "${pkgsX86.wayland}/lib";
    gio = "${pkgsX86.glib-networking}/lib/gio/modules";
    gnutls = "${pkgsX86.gnutls.out}/lib";
    nettle = "${pkgsX86.nettle}/lib";
    libtasn1 = "${pkgsX86.libtasn1}/lib";
    libidn2 = "${pkgsX86.libidn2}/lib";
    opensc = "${openscArch}";
    libp11 = "${pkgsX86.libp11}";
    pcsclite = "${pkgsX86.pcsclite.lib}";
    p11kit = "${pkgsX86.p11-kit.out}";
    libfido2 = "${pkgsX86.libfido2}";
    # System libraries needed by broker
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
    # Arch OpenSSL 3.3.2 - fixes Code:1200 error in broker
    opensslArch = "${opensslArch}/lib";
  };

  # Environment variables for Mesa software rendering (required for Rosetta)
  mesaEnvVars = ''
    # Mesa software rendering (llvmpipe) - required for Rosetta
    export LIBGL_ALWAYS_SOFTWARE=1
    export GALLIUM_DRIVER=llvmpipe
    export MESA_LOADER_DRIVER_OVERRIDE=llvmpipe
    export __EGL_VENDOR_LIBRARY_DIRS="${libPaths.mesa}/share/glvnd/egl_vendor.d"
    export LIBGL_DRIVERS_PATH="${libPaths.mesa}/lib/dri"
  '';

  # Environment variables for WebKitGTK under Rosetta
  # NOTE: Do NOT set WEBKIT_DISABLE_COMPOSITING_MODE=1 - causes blank windows!
  webkitEnvVars = ''
    export WEBKIT_DISABLE_DMABUF_RENDERER=1
    export GDK_BACKEND=x11
  '';

  # Environment variables for TLS/SSL
  tlsEnvVars = ''
    # GIO TLS backend (glib-networking) for HTTPS
    # NOTE: The old gnutls-pkcs11 separate backend was removed in glib-networking 2.64+
    # Modern giognutls has PKCS#11 support built-in via GnuTLS PKCS#11 functions
    export GIO_MODULE_DIR="${libPaths.gio}"
    export SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt"
    export SSL_CERT_DIR="/etc/ssl/certs"
  '';

  # Environment variables for PKCS#11 / YubiKey support
  # CRITICAL: XDG_CONFIG_HOME must be set for p11-kit to find module configs in ~/.config/pkcs11/modules/
  # Without this, D-Bus activated services won't find the PKCS#11 modules
  pkcs11EnvVars = ''
    # XDG paths - required for p11-kit to find user module configs
    export HOME="''${HOME:-/home/$(whoami)}"
    export XDG_CONFIG_HOME="''${XDG_CONFIG_HOME:-$HOME/.config}"

    # PKCS#11/YubiKey support
    # NOTE: p11-kit reads module configs from $XDG_CONFIG_HOME/pkcs11/modules/ (managed by home-manager)
    export PCSCLITE_CSOCK_NAME="/run/pcscd/pcscd.comm"
    export P11_KIT_MODULE_PATH="${libPaths.opensc}/lib/pkcs11:${libPaths.p11kit}/lib/pkcs11"
  '';

  # Debug environment variables (when cfg.debug is true)
  debugEnvVars = optionalString cfg.debug ''
    # Debug output
    export G_MESSAGES_DEBUG=all
    export WEBKIT_DEBUG=all
    export LIBGL_DEBUG=verbose
    # Intune/MSAL internal debugging
    export INTUNE_LOG_LEVEL=debug
    export MSAL_LOG_LEVEL=Trace
    # PKCS#11/p11-kit debugging
    export P11_KIT_DEBUG=all
    export GNUTLS_DEBUG_LEVEL=9
    echo "[DEBUG] Starting at $(date)" >&2
    echo "[DEBUG] HOME=$HOME" >&2
    echo "[DEBUG] XDG_CONFIG_HOME=$XDG_CONFIG_HOME" >&2
    echo "[DEBUG] LD_LIBRARY_PATH=$LD_LIBRARY_PATH" >&2
    echo "[DEBUG] LD_PRELOAD=$LD_PRELOAD" >&2
    echo "[DEBUG] P11_KIT_MODULE_PATH=$P11_KIT_MODULE_PATH" >&2
    echo "[DEBUG] PCSCLITE_CSOCK_NAME=$PCSCLITE_CSOCK_NAME" >&2
    echo "[DEBUG] XDG p11-kit config: $XDG_CONFIG_HOME/pkcs11/modules/" >&2
    ls -la "$XDG_CONFIG_HOME/pkcs11/modules/" 2>/dev/null | sed 's/^/[DEBUG]   /' >&2 || echo "[DEBUG]   (not found)" >&2
  '';

  #############################################################################
  # INTUNE-PORTAL (custom package with latest version)
  #############################################################################

  # Use our custom package for latest version (nixpkgs has 1.2503.10, we have 1.2511.7)
  intunePackage = intunePkg;

  wrapperSuffix = "-rosetta";

  # OpenSSL config for PKCS#11 (YubiKey support)
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

  # Wrapper for intune-portal with Nix library paths
  intuneWrapper = pkgs.writeShellScriptBin "intune-portal${wrapperSuffix}" ''
    #!/usr/bin/env bash
    # intune-portal wrapper: Runs intune-portal with Nix library paths
    # Includes Mesa software rendering for Rosetta on aarch64
    #
    # NOTE: Both intune-portal and broker use Arch OpenSSL 3.3.2 from LD_LIBRARY_PATH.

    # LD_LIBRARY_PATH: provides Nix store libraries to the FHS binary
    # OpenSSL 3.3.2 from Arch is needed (fixes Code:1200 error)
    export LD_LIBRARY_PATH="${libPaths.opensslArch}:${libPaths.glvnd}:${libPaths.mesa}/lib:${libPaths.webkitgtk}:${libPaths.libsoup}:${libPaths.libsecret}:${libPaths.gtk3}:${libPaths.gdk-pixbuf}:${libPaths.cairo}:${libPaths.pango}:${libPaths.harfbuzz}:${libPaths.fontconfig}:${libPaths.freetype}:${libPaths.atk}:${libPaths.at-spi2-atk}:${libPaths.at-spi2-core}:${libPaths.xorg-libX11}:${libPaths.xorg-libXext}:${libPaths.xorg-libXrender}:${libPaths.xorg-libXi}:${libPaths.xorg-libXcursor}:${libPaths.xorg-libXrandr}:${libPaths.xorg-libXfixes}:${libPaths.xorg-libXcomposite}:${libPaths.xorg-libXdamage}:${libPaths.xorg-libxcb}:${libPaths.libxkbcommon}:${libPaths.dbus}:${libPaths.glib}:${libPaths.systemd}:${libPaths.util-linux}:${libPaths.curl}:${libPaths.zlib}:${libPaths.libssh2}:${libPaths.nghttp2}:${libPaths.brotli}:${libPaths.icu}:${libPaths.libstdcxx}:${libPaths.zstd}:${libPaths.expat}:${libPaths.pcre2}:${libPaths.sqlite}:${libPaths.libpsl}:${libPaths.libidn}:${libPaths.libpng}:${libPaths.libjpeg}:${libPaths.libwebp}:${libPaths.lcms2}:${libPaths.gstreamer}:${libPaths.gst-plugins-base}:${libPaths.libxml2}:${libPaths.libxslt}:${libPaths.enchant}:${libPaths.libnotify}:${libPaths.wayland}:${libPaths.gnutls}:${libPaths.nettle}:${libPaths.libtasn1}:${libPaths.libidn2}:${libPaths.libfido2}/lib:${libPaths.opensc}/lib:${libPaths.libp11}/lib:${libPaths.pcsclite}/lib:${libPaths.p11kit}/lib:''${LD_LIBRARY_PATH:-}"

    ${mesaEnvVars}
    ${webkitEnvVars}
    ${tlsEnvVars}
    ${pkcs11EnvVars}

    # OpenSSL PKCS#11 engine config (for legacy OpenSSL apps)
    export OPENSSL_CONF="${opensslConf}"
    export OPENSSL_ENGINES="${pkgsX86.libp11}/lib/engines-3"
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
  # INTUNE-AGENT (compliance reporting daemon)
  #############################################################################

  # Wrapper for intune-agent with Nix library paths
  # This agent periodically reports compliance status to Microsoft Intune
  intuneAgentWrapper = pkgs.writeShellScriptBin "intune-agent${wrapperSuffix}" ''
    #!/usr/bin/env bash
    # intune-agent wrapper: Runs intune-agent with Nix library paths
    #
    # This agent collects device compliance data (disk encryption, password policy, etc.)
    # and sends it to Microsoft Intune for evaluation.
    # Runs periodically via intune-agent.timer (every hour after 5min startup delay)

    # LD_LIBRARY_PATH - same as intune-portal for consistency
    export LD_LIBRARY_PATH="${libPaths.opensslArch}:${libPaths.glvnd}:${libPaths.mesa}/lib:${libPaths.webkitgtk}:${libPaths.libsoup}:${libPaths.libsecret}:${libPaths.gtk3}:${libPaths.gdk-pixbuf}:${libPaths.cairo}:${libPaths.pango}:${libPaths.harfbuzz}:${libPaths.fontconfig}:${libPaths.freetype}:${libPaths.atk}:${libPaths.at-spi2-atk}:${libPaths.at-spi2-core}:${libPaths.xorg-libX11}:${libPaths.xorg-libXext}:${libPaths.xorg-libXrender}:${libPaths.xorg-libXi}:${libPaths.xorg-libXcursor}:${libPaths.xorg-libXrandr}:${libPaths.xorg-libXfixes}:${libPaths.xorg-libXcomposite}:${libPaths.xorg-libXdamage}:${libPaths.xorg-libxcb}:${libPaths.libxkbcommon}:${libPaths.dbus}:${libPaths.glib}:${libPaths.systemd}:${libPaths.util-linux}:${libPaths.curl}:${libPaths.zlib}:${libPaths.libssh2}:${libPaths.nghttp2}:${libPaths.brotli}:${libPaths.icu}:${libPaths.libstdcxx}:${libPaths.zstd}:${libPaths.expat}:${libPaths.pcre2}:${libPaths.sqlite}:${libPaths.libpsl}:${libPaths.libidn}:${libPaths.libpng}:${libPaths.libjpeg}:${libPaths.libwebp}:${libPaths.lcms2}:${libPaths.gstreamer}:${libPaths.gst-plugins-base}:${libPaths.libxml2}:${libPaths.libxslt}:${libPaths.enchant}:${libPaths.libnotify}:${libPaths.wayland}:${libPaths.gnutls}:${libPaths.nettle}:${libPaths.libtasn1}:${libPaths.libidn2}:${libPaths.libfido2}/lib:${libPaths.opensc}/lib:${libPaths.libp11}/lib:${libPaths.pcsclite}/lib:${libPaths.p11kit}/lib:''${LD_LIBRARY_PATH:-}"

    ${tlsEnvVars}

    ${optionalString cfg.debug ''
      echo "[DEBUG] intune-agent starting at $(date)" >&2
    ''}

    exec ${intunePackage}/bin/intune-agent "$@"
  '';

  #############################################################################
  # USER BROKER (Nix package + wrapper)
  #############################################################################

  # Wrapper for user broker with OpenSSL fix and Nix library paths
  userBrokerWrapper = pkgs.writeShellScriptBin "microsoft-identity-broker${wrapperSuffix}" ''
    #!/usr/bin/env bash
    # microsoft-identity-broker wrapper: Nix-managed wrapper for broker
    #
    # This wrapper:
    # 1. Provides OpenSSL 3.3.2 via LD_LIBRARY_PATH (fixes Code:1200 error)
    # 2. Provides system libraries (dbus, glib, systemd) from Nix store
    # 3. Sets up Mesa software rendering for WebKitGTK SSO popups (aarch64 only)
    # 4. Configures GIO TLS for HTTPS

    # LD_LIBRARY_PATH construction - comprehensive library set from Nix store
    # NOTE: Arch OpenSSL 3.3.2 is included to fix Code:1200 "credential is invalid" error
    # NOTE: opensc/lib added for libopensc.so.11 needed by opensc-pkcs11.so PKCS#11 module
    # NOTE: pcsclite/lib needed for OpenSC to communicate with native pcscd
    # We use curlNoHttp3 (curl with http3Support=false) to avoid ngtcp2's OPENSSL_3.5.0 requirement
    export LD_LIBRARY_PATH="${libPaths.opensslArch}:${libPaths.opensc}/lib:${libPaths.pcsclite}/lib:${libPaths.glvnd}:${libPaths.mesa}/lib:${libPaths.webkitgtk}:${libPaths.libsoup}:${libPaths.libsecret}:${libPaths.gtk3}:${libPaths.gdk-pixbuf}:${libPaths.cairo}:${libPaths.pango}:${libPaths.harfbuzz}:${libPaths.fontconfig}:${libPaths.freetype}:${libPaths.atk}:${libPaths.at-spi2-atk}:${libPaths.at-spi2-core}:${libPaths.xorg-libX11}:${libPaths.xorg-libXext}:${libPaths.xorg-libXrender}:${libPaths.xorg-libXi}:${libPaths.xorg-libXcursor}:${libPaths.xorg-libXrandr}:${libPaths.xorg-libXfixes}:${libPaths.xorg-libXcomposite}:${libPaths.xorg-libXdamage}:${libPaths.xorg-libxcb}:${libPaths.libxkbcommon}:${libPaths.dbus}:${libPaths.glib}:${libPaths.systemd}:${libPaths.util-linux}:${libPaths.curl}:${libPaths.zlib}:${libPaths.libssh2}:${libPaths.nghttp2}:${libPaths.brotli}:${libPaths.icu}:${libPaths.libstdcxx}:${libPaths.zstd}:${libPaths.expat}:${libPaths.pcre2}:${libPaths.sqlite}:${libPaths.libpsl}:${libPaths.libidn}:${libPaths.libpng}:${libPaths.libjpeg}:${libPaths.libwebp}:${libPaths.lcms2}:${libPaths.gstreamer}:${libPaths.gst-plugins-base}:${libPaths.libxml2}:${libPaths.libxslt}:${libPaths.enchant}:${libPaths.libnotify}:${libPaths.p11kit}/lib:''${LD_LIBRARY_PATH:-}"

    ${mesaEnvVars}
    ${webkitEnvVars}
    ${tlsEnvVars}
    ${pkcs11EnvVars}

    # OpenSSL PKCS#11 engine config (for legacy OpenSSL apps)
    export OPENSSL_CONF="${opensslConf}"
    export OPENSSL_ENGINES="${pkgsX86.libp11}/lib/engines-3"

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
      Exec=${userBrokerWrapper}/bin/microsoft-identity-broker${wrapperSuffix}
    '';
  };

  #############################################################################
  # DEVICE BROKER (Nix package, system service - wrapper for reference)
  #############################################################################

  # Wrapper for device broker (for manual system configuration)
  # NOTE: This is installed to user profile but needs manual systemd config
  deviceBrokerWrapper = pkgs.writeShellScriptBin "microsoft-identity-device-broker${wrapperSuffix}" ''
    #!/usr/bin/env bash
    # microsoft-identity-device-broker wrapper: Nix-managed wrapper for device broker
    #
    # NOTE: Device broker runs as a SYSTEM service. To use this wrapper:
    # 1. sudo systemctl edit microsoft-identity-device-broker.service
    # 2. Add: [Service]
    #         ExecStart=
    #         ExecStart=<nix-store-path>/bin/microsoft-identity-device-broker${wrapperSuffix}
    # 3. sudo systemctl daemon-reload && sudo systemctl restart microsoft-identity-device-broker
    #
    # IMPORTANT: Use the full nix store path (not ~/.nix-profile) because root cannot
    # traverse /home/user directories.

    # Device broker shares same dependencies as user broker (WebKitGTK, GTK, etc.)
    # Use the same comprehensive LD_LIBRARY_PATH (including opensc/lib, pcsclite/lib)
    export LD_LIBRARY_PATH="${libPaths.opensslArch}:${libPaths.opensc}/lib:${libPaths.pcsclite}/lib:${libPaths.glvnd}:${libPaths.mesa}/lib:${libPaths.webkitgtk}:${libPaths.libsoup}:${libPaths.libsecret}:${libPaths.gtk3}:${libPaths.gdk-pixbuf}:${libPaths.cairo}:${libPaths.pango}:${libPaths.harfbuzz}:${libPaths.fontconfig}:${libPaths.freetype}:${libPaths.atk}:${libPaths.at-spi2-atk}:${libPaths.at-spi2-core}:${libPaths.xorg-libX11}:${libPaths.xorg-libXext}:${libPaths.xorg-libXrender}:${libPaths.xorg-libXi}:${libPaths.xorg-libXcursor}:${libPaths.xorg-libXrandr}:${libPaths.xorg-libXfixes}:${libPaths.xorg-libXcomposite}:${libPaths.xorg-libXdamage}:${libPaths.xorg-libxcb}:${libPaths.libxkbcommon}:${libPaths.dbus}:${libPaths.glib}:${libPaths.systemd}:${libPaths.util-linux}:${libPaths.curl}:${libPaths.zlib}:${libPaths.libssh2}:${libPaths.nghttp2}:${libPaths.brotli}:${libPaths.icu}:${libPaths.libstdcxx}:${libPaths.zstd}:${libPaths.expat}:${libPaths.pcre2}:${libPaths.sqlite}:${libPaths.libpsl}:${libPaths.libidn}:${libPaths.libpng}:${libPaths.libjpeg}:${libPaths.libwebp}:${libPaths.lcms2}:${libPaths.gstreamer}:${libPaths.gst-plugins-base}:${libPaths.libxml2}:${libPaths.libxslt}:${libPaths.enchant}:${libPaths.libnotify}:${libPaths.p11kit}/lib:''${LD_LIBRARY_PATH:-}"

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
    echo "  Intune agent timer (user):"
    systemctl --user status intune-agent.timer --no-pager 2>/dev/null | head -5 || echo "    Not found (enable with: systemctl --user enable --now intune-agent.timer)"
    echo ""
    echo "  Next intune-agent run:"
    systemctl --user list-timers intune-agent.timer --no-pager 2>/dev/null | tail -2 || echo "    Timer not active"
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
    echo "  intune-portal${wrapperSuffix}: $(which intune-portal${wrapperSuffix} 2>/dev/null || echo 'not in PATH')"
    echo "  intune-agent${wrapperSuffix}: $(which intune-agent${wrapperSuffix} 2>/dev/null || echo 'not in PATH')"
    echo "  microsoft-identity-broker${wrapperSuffix}: $(which microsoft-identity-broker${wrapperSuffix} 2>/dev/null || echo 'not in PATH')"
    echo ""
  '';

  #############################################################################
  # PKCS#11/YUBIKEY DIAGNOSTIC HELPER
  #############################################################################

  pkcs11DiagHelper = pkgs.writeShellScriptBin "intune-pkcs11-diag" ''
    #!/usr/bin/env bash
    # intune-pkcs11-diag: Diagnose PKCS#11/YubiKey certificate chain
    #
    # Tests each layer: pcscd → OpenSC → p11-kit → GnuTLS
    # Run this to identify where the certificate chain breaks.

    set -euo pipefail

    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    NC='\033[0m' # No Color

    pass() { echo -e "''${GREEN}✓ PASS:''${NC} $1"; }
    fail() { echo -e "''${RED}✗ FAIL:''${NC} $1"; }
    warn() { echo -e "''${YELLOW}⚠ WARN:''${NC} $1"; }
    info() { echo -e "  INFO: $1"; }

    echo "========================================"
    echo "PKCS#11/YubiKey Diagnostic for Intune"
    echo "========================================"
    echo ""

    # Set up environment matching the intune-portal wrapper
    # NOTE: p11-kit reads module configs from ~/.config/pkcs11/modules/ (XDG path)
    export PCSCLITE_CSOCK_NAME="/run/pcscd/pcscd.comm"
    export P11_KIT_MODULE_PATH="${libPaths.opensc}/lib/pkcs11:${libPaths.p11kit}/pkcs11"
    export LD_LIBRARY_PATH="${libPaths.pcsclite}/lib:${libPaths.opensc}/lib:${libPaths.p11kit}/lib:${libPaths.gnutls}:${libPaths.nettle}:${libPaths.libtasn1}:${libPaths.libidn2}:''${LD_LIBRARY_PATH:-}"
    XDG_PKCS11_MODULES="$HOME/.config/pkcs11/modules"

    echo "=== LAYER 1: pcscd (Smart Card Daemon) ==="
    if systemctl is-active pcscd >/dev/null 2>&1; then
      pass "pcscd service is running"
    elif systemctl is-active pcscd.socket >/dev/null 2>&1; then
      pass "pcscd.socket is active (socket activation)"
    else
      fail "pcscd is not running"
      info "Try: sudo systemctl start pcscd"
    fi

    if [[ -S /run/pcscd/pcscd.comm ]]; then
      pass "pcscd socket exists at /run/pcscd/pcscd.comm"
    else
      fail "pcscd socket not found"
    fi
    echo ""

    echo "=== LAYER 2: OpenSC (x86_64) ==="
    OPENSC_LIB="${libPaths.opensc}/lib/pkcs11/opensc-pkcs11.so"
    if [[ -f "$OPENSC_LIB" ]]; then
      pass "OpenSC PKCS#11 module exists"
      info "Path: $OPENSC_LIB"
    else
      fail "OpenSC PKCS#11 module not found at $OPENSC_LIB"
    fi

    PKCS11_TOOL="${openscArch}/bin/pkcs11-tool"
    if [[ -x "$PKCS11_TOOL" ]]; then
      pass "pkcs11-tool available"

      echo "  Testing slot detection..."
      if SLOTS=$("$PKCS11_TOOL" --list-slots 2>&1); then
        if echo "$SLOTS" | grep -qi "yubikey\|token"; then
          pass "YubiKey/token detected in slots"
          echo "$SLOTS" | head -10 | sed 's/^/    /'
        else
          warn "No YubiKey found in slots (is it plugged in?)"
          echo "$SLOTS" | head -5 | sed 's/^/    /'
        fi
      else
        fail "pkcs11-tool --list-slots failed"
        echo "$SLOTS" | sed 's/^/    /'
      fi

      echo "  Testing certificate listing..."
      if CERTS=$("$PKCS11_TOOL" --list-objects --type cert 2>&1); then
        if echo "$CERTS" | grep -qi "certificate"; then
          pass "Certificates found on token"
          echo "$CERTS" | grep -i "label\|subject" | head -10 | sed 's/^/    /'
        else
          warn "No certificates found (or PIN required)"
        fi
      else
        fail "pkcs11-tool --list-objects failed"
      fi
    else
      fail "pkcs11-tool not found"
    fi
    echo ""

    echo "=== LAYER 3: p11-kit ==="
    P11_KIT="${pkgsX86.p11-kit.bin}/bin/p11-kit"
    if [[ -x "$P11_KIT" ]]; then
      pass "p11-kit available"

      echo "  XDG module config directory: $XDG_PKCS11_MODULES"
      if [[ -d "$XDG_PKCS11_MODULES" ]]; then
        pass "XDG module config directory exists"
        for f in "$XDG_PKCS11_MODULES"/*.module; do
          if [[ -f "$f" ]]; then
            info "Found: $(basename "$f")"
            cat "$f" | sed 's/^/      /'
          fi
        done
      else
        fail "XDG module config directory not found"
        info "Expected: ~/.config/pkcs11/modules/"
        info "Run 'home-manager switch' to create it"
      fi

      echo "  Testing module discovery..."
      if MODULES=$("$P11_KIT" list-modules 2>&1); then
        if echo "$MODULES" | grep -qi "opensc"; then
          pass "OpenSC module discovered by p11-kit"
        else
          warn "OpenSC module not found by p11-kit"
        fi
        echo "$MODULES" | head -20 | sed 's/^/    /'
      else
        fail "p11-kit list-modules failed"
        echo "$MODULES" | sed 's/^/    /'
      fi
    else
      fail "p11-kit not found"
    fi
    echo ""

    echo "=== LAYER 4: GnuTLS ==="
    P11TOOL="${pkgsX86.gnutls.bin}/bin/p11tool"
    if [[ -x "$P11TOOL" ]]; then
      pass "GnuTLS p11tool available"

      echo "  Testing token visibility..."
      if TOKENS=$("$P11TOOL" --list-tokens 2>&1); then
        if echo "$TOKENS" | grep -qi "yubikey\|piv\|token"; then
          pass "Token visible to GnuTLS"
          echo "$TOKENS" | head -10 | sed 's/^/    /'
        else
          warn "No tokens visible to GnuTLS p11tool"
          echo "$TOKENS" | head -5 | sed 's/^/    /'
        fi
      else
        fail "p11tool --list-tokens failed"
      fi

      echo "  Testing certificate visibility..."
      if CERTS=$("$P11TOOL" --list-all-certs 2>&1); then
        if echo "$CERTS" | grep -qi "object\|certificate\|label"; then
          pass "Certificates visible to GnuTLS"
          echo "$CERTS" | head -15 | sed 's/^/    /'
        else
          warn "No certificates visible to GnuTLS"
        fi
      else
        fail "p11tool --list-all-certs failed"
      fi
    else
      fail "GnuTLS p11tool not found"
    fi
    echo ""

    echo "=== LAYER 5: System p11-kit Config ==="
    echo "  Checking /etc/pkcs11/modules/..."
    if [[ -d /etc/pkcs11/modules ]]; then
      PERMS=$(stat -c '%a' /etc/pkcs11/modules 2>/dev/null || stat -f '%A' /etc/pkcs11/modules 2>/dev/null)
      if [[ "$PERMS" == "755" ]] || [[ "$PERMS" == "7" ]]; then
        pass "/etc/pkcs11/modules has correct permissions ($PERMS)"
      else
        warn "/etc/pkcs11/modules has permissions $PERMS (should be 755)"
      fi
      for f in /etc/pkcs11/modules/*.module; do
        if [[ -f "$f" ]]; then
          info "System module: $(basename "$f")"
          cat "$f" | sed 's/^/      /'
        fi
      done
    else
      info "/etc/pkcs11/modules does not exist (using Nix config only)"
    fi
    echo ""

    echo "=== SUMMARY ==="
    echo "If all layers pass but intune-portal still says 'No certificate detected':"
    echo "1. The issue may be JavaScript detection (not TLS-level)"
    echo "2. Try clicking 'Use a certificate or smartcard' link manually"
    echo "3. Enable debug mode: modules.linux.intune.debug = true"
    echo "4. Check WebKitGTK TLS client auth support"
    echo ""
    echo "For verbose p11-kit debugging, run:"
    echo "  export P11_KIT_DEBUG=all"
    echo "  intune-portal${wrapperSuffix}"
  '';

  #############################################################################
  # NSS PKCS#11 SETUP HELPER
  #############################################################################

  # Helper to configure NSS database for Chromium-based browsers (Edge, Chrome)
  # This is needed because NSS uses a separate module system from p11-kit
  nssSetupHelper = pkgs.writeShellScriptBin "intune-nss-setup" ''
    #!/usr/bin/env bash
    # intune-nss-setup: Configure NSS database for smart card / YubiKey support
    #
    # This adds the OpenSC PKCS#11 module to the NSS database used by
    # Chromium-based browsers (Edge, Chrome) so they can see YubiKey certificates.
    #
    # NSS database location: ~/.pki/nssdb/
    # After running this, restart your browser.

    set -euo pipefail

    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    NC='\033[0m'

    pass() { echo -e "''${GREEN}✓''${NC} $1"; }
    fail() { echo -e "''${RED}✗''${NC} $1"; }
    warn() { echo -e "''${YELLOW}⚠''${NC} $1"; }
    info() { echo -e "  $1"; }

    NSS_DB="$HOME/.pki/nssdb"
    # OpenSC PKCS#11 module (Arch package for compatibility)
    OPENSC_LIB="${openscArch}/lib/pkcs11/opensc-pkcs11.so"
    MODULE_NAME="OpenSC"

    echo "============================================"
    echo "NSS PKCS#11 Setup for Smart Cards / YubiKey"
    echo "============================================"
    echo ""

    # Check for modutil
    MODUTIL="${pkgs.nss.tools}/bin/modutil"
    if [[ ! -x "$MODUTIL" ]]; then
      fail "modutil not found. Installing nss.tools..."
      exit 1
    fi
    pass "modutil found at $MODUTIL"

    # Ensure NSS database exists
    if [[ ! -d "$NSS_DB" ]]; then
      warn "NSS database not found at $NSS_DB"
      info "Creating new NSS database..."
      mkdir -p "$NSS_DB"
      ${pkgs.nss.tools}/bin/certutil -d sql:"$NSS_DB" -N --empty-password
      pass "Created NSS database"
    else
      pass "NSS database exists at $NSS_DB"
    fi

    # Check if OpenSC module already registered
    if "$MODUTIL" -dbdir sql:"$NSS_DB" -list 2>/dev/null | grep -q "$MODULE_NAME"; then
      warn "Module '$MODULE_NAME' already registered"
      info "Current modules:"
      "$MODUTIL" -dbdir sql:"$NSS_DB" -list 2>/dev/null | grep -A2 "slot:" | head -20 || true
      echo ""
      echo "To remove and re-add, run:"
      echo "  $MODUTIL -dbdir sql:$NSS_DB -delete '$MODULE_NAME'"
      exit 0
    fi

    # Check OpenSC library exists
    if [[ ! -f "$OPENSC_LIB" ]]; then
      fail "OpenSC PKCS#11 library not found at $OPENSC_LIB"
      exit 1
    fi
    pass "OpenSC library found"

    # Add the module
    echo ""
    echo "Adding OpenSC PKCS#11 module to NSS database..."
    echo "  Module name: $MODULE_NAME"
    echo "  Library: $OPENSC_LIB"
    echo ""

    if "$MODUTIL" -dbdir sql:"$NSS_DB" -add "$MODULE_NAME" -libfile "$OPENSC_LIB" -force; then
      pass "Successfully added '$MODULE_NAME' to NSS database"
    else
      fail "Failed to add module"
      exit 1
    fi

    echo ""
    echo "Verifying module registration..."
    if "$MODUTIL" -dbdir sql:"$NSS_DB" -list 2>/dev/null | grep -q "$MODULE_NAME"; then
      pass "Module verified in NSS database"
    else
      fail "Module not found after adding"
      exit 1
    fi

    echo ""
    echo "============================================"
    echo "Setup complete!"
    echo ""
    echo "Next steps:"
    echo "1. Restart your browser (Edge, Chrome, etc.)"
    echo "2. Go to a site requiring certificate auth"
    echo "3. You should now see the YubiKey certificate picker"
    echo ""
    echo "To verify in browser:"
    echo "  Chrome: Settings → Privacy and security → Security → Manage certificates"
    echo "  Edge: edge://settings/security → Manage certificates"
    echo ""
    echo "To check registered modules:"
    echo "  $MODUTIL -dbdir sql:$NSS_DB -list"
  '';

in {
  options.modules.linux.intune-rosetta = {
    enable = mkEnableOption "Microsoft Intune Portal with identity brokers (aarch64/Rosetta)";

    debug = mkOption {
      type = types.bool;
      default = false;
      description = "Enable debug logging for all Intune components";
    };
  };

  config = mkIf (cfg.enable && pkgs.stdenv.isLinux) {
    # Enable Rosetta support (required for x86_64 binaries on aarch64)
    modules.linux.rosetta.enable = true;

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
      pkcs11DiagHelper
      nssSetupHelper

      # NSS tools for browser smart card setup
      pkgs.nss.tools  # provides modutil, certutil

      # Wrappers (architecture-aware names via wrapperSuffix)
      intuneWrapper
      intuneAgentWrapper
      userBrokerWrapper
      deviceBrokerWrapper

      # D-Bus service override for user broker
      userBrokerDbusService

      # Required libraries (pkgsX86 resolves to native or cross-arch)
      pkgsX86.libglvnd
      pkgsX86.wayland
      pkgsX86.mesa
      pkgsX86.glib-networking
      pkgsX86.gnutls
      pkgsX86.nettle
      pkgsX86.libtasn1
      pkgsX86.libidn2
      openscArch
      pkgsX86.libp11
      pkgsX86.pcsclite.lib
      pkgsX86.p11-kit
      pkgsX86.p11-kit.bin  # For p11-kit CLI tools
      pkgsX86.libfido2
      # System libraries for broker
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
    ];

    # Install D-Bus service file to user's local share
    # This overrides /usr/share/dbus-1/services/com.microsoft.identity.broker1.service
    xdg.dataFile."dbus-1/services/com.microsoft.identity.broker1.service" = {
      source = "${userBrokerDbusService}/share/dbus-1/services/com.microsoft.identity.broker1.service";
    };

    # Install PKCS#11 module config for p11-kit
    # This tells p11-kit (used by intune-portal's WebKitGTK) where to find OpenSC
    # NOTE: p11-kit reads from ~/.config/pkcs11/modules/ (XDG path) - not env vars!
    # NOTE: No leading whitespace in text - p11-kit is whitespace-sensitive
    xdg.configFile."pkcs11/modules/opensc.module".text = ''
module: ${openscArch}/lib/pkcs11/opensc-pkcs11.so
critical: no
trust-policy: no
'';

    # NOTE: Do NOT set global sessionVariables for LIBGL_ALWAYS_SOFTWARE or GDK_BACKEND
    # These break Hyprland/Wayland compositors! The wrapper scripts already set these
    # environment variables for the specific binaries that need them.

    # Systemd user service for intune-agent (compliance reporting)
    # This service collects device compliance data and sends it to Microsoft Intune
    systemd.user.services.intune-agent = {
      Unit = {
        Description = "Intune Agent - compliance reporting";
      };
      Service = {
        Type = "oneshot";
        ExecStart = "${intuneAgentWrapper}/bin/intune-agent${wrapperSuffix}";
        StateDirectory = "intune";
        Slice = "background.slice";
      };
    };

    # Systemd user timer for intune-agent
    # Runs after graphical session starts, then every hour with 10min random delay
    systemd.user.timers.intune-agent = {
      Unit = {
        Description = "Intune Agent scheduler";
        PartOf = [ "graphical-session.target" ];
        After = [ "graphical-session.target" ];
      };
      Timer = {
        OnStartupSec = "5m";      # First run 5 minutes after login
        OnUnitActiveSec = "1h";   # Then every hour
        RandomizedDelaySec = "10m"; # Random delay up to 10 minutes
        AccuracySec = "2m";
      };
      Install = {
        WantedBy = [ "graphical-session.target" ];
      };
    };

    # Activation script to verify setup
    home.activation.verifyIntuneSetup =
      lib.hm.dag.entryAfter [ "writeBoundary" "linkGeneration" ] ''
        # Verify D-Bus service file is in place
        if [[ -f "$HOME/.local/share/dbus-1/services/com.microsoft.identity.broker1.service" ]]; then
          noteEcho "User broker D-Bus service installed (Nix-managed, version ${brokerPkg.version})"
        else
          warnEcho "User broker D-Bus service not found in ~/.local/share/dbus-1/services/"
        fi

        # Remind about device broker (system service)
        noteEcho "Device broker runs as system service. To use Nix wrapper:"
        noteEcho "  sudo systemctl edit microsoft-identity-device-broker.service"
        noteEcho "  # Add: ExecStart="
        noteEcho "  # Add: ExecStart=$HOME/.nix-profile/bin/microsoft-identity-device-broker${wrapperSuffix}"

        # Check if intune-agent timer is enabled
        if ! systemctl --user is-enabled intune-agent.timer >/dev/null 2>&1; then
          noteEcho "Intune agent timer not enabled. Enable with:"
          noteEcho "  systemctl --user enable --now intune-agent.timer"
        fi
      '';
  };
}
