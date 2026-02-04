# modules/home/linux/intune.nix -- Microsoft Intune Portal + Identity Brokers (Unified)
#
# Supports both native x86_64 and aarch64/Rosetta modes via auto-detection.
# Components: intune-portal, user broker (SSO), device broker (system), gnome-keyring
#
# MODES: native-x86_64 | rosetta | (future) native-arm64
# CAVEATS: OpenSSL 3.3.2 required (fixes Code:1200), fake Ubuntu os-release needed
# DEBUG: modules.linux.intune.debug = true; intune-logs; intune-status
# See: https://github.com/recolic/microsoft-intune-archlinux

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.linux.intune;

  # ============================================================================
  # ARCHITECTURE DETECTION
  # Detect operating mode once at top, everything downstream uses the mode.
  # NOTE: For aarch64-linux we ASSUME Rosetta mode since native arm64 Intune
  # packages don't exist yet. The Rosetta binary check is done at runtime by
  # the prerequisites script, not here (builtins.pathExists runs at Nix eval
  # time on the build machine, not the target).
  # ============================================================================

  mode =
    if pkgs.stdenv.hostPlatform.isx86_64 then "native-x86_64"
    else if pkgs.stdenv.hostPlatform.isAarch64 then "rosetta"
    else null;  # Future: native-arm64 when Microsoft ships arm64 packages

  isRosetta = mode == "rosetta";
  isNativeX86 = mode == "native-x86_64";

  # Package source varies by mode (only import pkgsX86 when needed)
  pkgsX86 = if isRosetta then import pkgs.path {
    system = "x86_64-linux";
    config.allowUnfree = true;
  } else null;

  pkgSource = if isRosetta then pkgsX86 else pkgs;

  # Wrapper suffix for architecture-aware binary names
  wrapperSuffix = if isRosetta then "-rosetta" else "";

  # ============================================================================
  # PACKAGE SOURCES
  # ============================================================================

  # Microsoft Identity Broker package (x86_64 binaries from Microsoft .deb)
  brokerPkg = pkgSource.callPackage ../../../packages/microsoft-identity-broker { };

  # Microsoft Intune Portal package (x86_64 binaries from Microsoft .deb)
  intunePkg = pkgSource.callPackage ../../../packages/intune-portal { };

  # Custom curl without HTTP/3 to avoid ngtcp2's OPENSSL_3.5.0 requirement
  curlNoHttp3 = pkgSource.curl.override { http3Support = false; };

  # ============================================================================
  # ARCH LINUX PACKAGES - WORKAROUND SECTION
  # TODO: Remove this section when native arm64 Intune packages are available
  # These packages from Arch archives maintain symbol compatibility.
  # ============================================================================

  # OpenSSL 3.3.2 from Arch Linux archives
  # Required: Newer OpenSSL has X509_REQ_set_version bug causing Code:1200 error
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
  # Required: Nix OpenSC 0.26.1 needs OPENSSL_3.4.0 symbols not in Arch OpenSSL 3.3.2
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

  # ============================================================================
  # LIBRARY PATHS - WORKAROUND SECTION
  # TODO: Remove entire section when native arm64 Intune packages are available
  # These libraries are needed because x86_64 binaries run on Arch Linux which
  # doesn't have these in standard library paths (non-NixOS).
  # ============================================================================

  # OpenSSL 3.3.2 MUST be first - fixes Code:1200 error
  opensslArchPath = "${opensslArch}/lib";

  glibcLibs = [ "${pkgSource.stdenv.cc.cc.lib}/lib" ];

  systemLibs = map (p: "${p}/lib") [
    pkgSource.dbus.lib
    pkgSource.glib.out
    pkgSource.systemdLibs
    pkgSource.util-linux.lib
    pkgSource.zlib.out
    pkgSource.zstd.out
    pkgSource.icu.out
    pkgSource.expat.out
    pkgSource.pcre2.out
  ];

  x11Libs = map (p: "${p}/lib") [
    pkgSource.xorg.libX11.out
    pkgSource.xorg.libXext.out
    pkgSource.xorg.libXrender.out
    pkgSource.xorg.libXi.out
    pkgSource.xorg.libXcursor.out
    pkgSource.xorg.libXrandr.out
    pkgSource.xorg.libXfixes.out
    pkgSource.xorg.libXcomposite.out
    pkgSource.xorg.libXdamage.out
    pkgSource.xorg.libxcb.out
    pkgSource.libxkbcommon.out
  ];

  gtkLibs = map (p: "${p}/lib") [
    pkgSource.gtk3.out
    pkgSource.gdk-pixbuf.out
    pkgSource.cairo.out
    pkgSource.pango.out
    pkgSource.harfbuzz.out
    pkgSource.fontconfig.lib
    pkgSource.freetype.out
    pkgSource.atk.out
    pkgSource.at-spi2-atk.out
    pkgSource.at-spi2-core.out
  ];

  webkitLibs = map (p: "${p}/lib") [
    pkgSource.webkitgtk_4_1.out
    pkgSource.libsoup_3.out
    pkgSource.sqlite.out
    pkgSource.libpsl.out
    pkgSource.libidn.out
    pkgSource.gst_all_1.gstreamer.out
    pkgSource.gst_all_1.gst-plugins-base.out
    pkgSource.libxml2.out
    pkgSource.libxslt.out
    pkgSource.enchant.out
    pkgSource.libnotify.out
  ];

  tlsLibs = map (p: "${p}/lib") [
    pkgSource.gnutls.out
    pkgSource.nettle
    pkgSource.libtasn1
    pkgSource.libidn2
  ];

  pkcs11Libs = [
    "${openscArch}/lib"
    "${pkgSource.libp11}/lib"
    "${pkgSource.pcsclite.lib}/lib"
    "${pkgSource.p11-kit.out}/lib"
    "${pkgSource.libfido2}/lib"
  ];

  mediaLibs = map (p: "${p}/lib") [
    pkgSource.libpng.out
    pkgSource.libjpeg.out
    pkgSource.libwebp.out
    pkgSource.lcms2.out
  ];

  networkLibs = [
    "${curlNoHttp3.out}/lib"
    "${pkgSource.libssh2.out}/lib"
    "${pkgSource.nghttp2.lib}/lib"
    "${pkgSource.brotli.lib}/lib"
  ];

  renderingLibs = [
    "${pkgSource.libglvnd}/lib"
    "${pkgSource.mesa}/lib"
    "${pkgSource.wayland}/lib"
    "${pkgSource.libsecret.out}/lib"
  ];

  # Compose final library path (used once, referenced by all wrappers)
  fullLibraryPath = concatStringsSep ":" (
    [ opensslArchPath ]  # CRITICAL: OpenSSL 3.3.2 must be first
    ++ glibcLibs
    ++ systemLibs
    ++ x11Libs
    ++ gtkLibs
    ++ webkitLibs
    ++ tlsLibs
    ++ pkcs11Libs
    ++ mediaLibs
    ++ networkLibs
    ++ renderingLibs
  );

  # ============================================================================
  # ENVIRONMENT VARIABLE HELPERS
  # ============================================================================

  # Mesa software rendering (required for Rosetta, harmless on native)
  mesaEnvVars = ''
    export LIBGL_ALWAYS_SOFTWARE=1
    export GALLIUM_DRIVER=llvmpipe
    export MESA_LOADER_DRIVER_OVERRIDE=llvmpipe
    export __EGL_VENDOR_LIBRARY_DIRS="${pkgSource.mesa}/share/glvnd/egl_vendor.d"
    export LIBGL_DRIVERS_PATH="${pkgSource.mesa}/lib/dri"
  '';

  # WebKitGTK under Rosetta (X11 mode, no DMA-BUF)
  webkitEnvVars = ''
    export WEBKIT_DISABLE_DMABUF_RENDERER=1
    export GDK_BACKEND=x11
  '';

  # TLS/SSL certificates and GIO modules
  tlsEnvVars = ''
    export GIO_MODULE_DIR="${pkgSource.glib-networking}/lib/gio/modules"
    export SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt"
    export SSL_CERT_DIR="/etc/ssl/certs"
  '';

  # PKCS#11/YubiKey support
  pkcs11EnvVars = ''
    export HOME="''${HOME:-/home/$(whoami)}"
    export XDG_CONFIG_HOME="''${XDG_CONFIG_HOME:-$HOME/.config}"
    export PCSCLITE_CSOCK_NAME="/run/pcscd/pcscd.comm"
    export P11_KIT_MODULE_PATH="${openscArch}/lib/pkcs11:${pkgSource.p11-kit.out}/lib/pkcs11"
  '';

  # Debug output (when cfg.debug is true)
  debugEnvVars = optionalString cfg.debug ''
    export G_MESSAGES_DEBUG=all
    export WEBKIT_DEBUG=all
    export LIBGL_DEBUG=verbose
    export INTUNE_LOG_LEVEL=debug
    export MSAL_LOG_LEVEL=Trace
    export P11_KIT_DEBUG=all
    export GNUTLS_DEBUG_LEVEL=9
    echo "[DEBUG] Starting at $(date)" >&2
    echo "[DEBUG] HOME=$HOME XDG_CONFIG_HOME=$XDG_CONFIG_HOME" >&2
    echo "[DEBUG] LD_LIBRARY_PATH=$LD_LIBRARY_PATH" >&2
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
    MODULE_PATH = ${openscArch}/lib/pkcs11/opensc-pkcs11.so
    init = 0
  '';

  # ============================================================================
  # WRAPPERS
  # ============================================================================

  intuneWrapper = pkgs.writeShellScriptBin "intune-portal${wrapperSuffix}" ''
    #!/usr/bin/env bash
    # intune-portal wrapper: Runs intune-portal with Nix library paths
    export LD_LIBRARY_PATH="${fullLibraryPath}:''${LD_LIBRARY_PATH:-}"
    ${mesaEnvVars}
    ${webkitEnvVars}
    ${tlsEnvVars}
    ${pkcs11EnvVars}
    export OPENSSL_CONF="${opensslConf}"
    export OPENSSL_ENGINES="${pkgSource.libp11}/lib/engines-3"
    ${debugEnvVars}
    ${optionalString cfg.debug ''exec ${intunePkg}/bin/intune-portal "$@" 2>&1 | tee -a /tmp/intune-portal.log''}
    ${optionalString (!cfg.debug) ''exec ${intunePkg}/bin/intune-portal "$@"''}
  '';

  intuneAgentWrapper = pkgs.writeShellScriptBin "intune-agent${wrapperSuffix}" ''
    #!/usr/bin/env bash
    # intune-agent wrapper: Compliance reporting daemon
    export LD_LIBRARY_PATH="${fullLibraryPath}:''${LD_LIBRARY_PATH:-}"
    ${tlsEnvVars}
    export HOME="''${HOME:-/home/$(whoami)}"
    export XDG_RUNTIME_DIR="''${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    export GNOME_KEYRING_CONTROL="''${GNOME_KEYRING_CONTROL:-$XDG_RUNTIME_DIR/keyring}"
    ${optionalString cfg.debug ''echo "[DEBUG] intune-agent starting at $(date)" >&2''}
    exec ${intunePkg}/bin/intune-agent "$@"
  '';

  userBrokerWrapper = pkgs.writeShellScriptBin "microsoft-identity-broker${wrapperSuffix}" ''
    #!/usr/bin/env bash
    # microsoft-identity-broker wrapper: User SSO authentication
    export LD_LIBRARY_PATH="${fullLibraryPath}:''${LD_LIBRARY_PATH:-}"
    ${mesaEnvVars}
    ${webkitEnvVars}
    ${tlsEnvVars}
    ${pkcs11EnvVars}
    export XDG_RUNTIME_DIR="''${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    export GNOME_KEYRING_CONTROL="''${GNOME_KEYRING_CONTROL:-$XDG_RUNTIME_DIR/keyring}"
    export OPENSSL_CONF="${opensslConf}"
    export OPENSSL_ENGINES="${pkgSource.libp11}/lib/engines-3"
    ${debugEnvVars}
    ${optionalString cfg.debug ''echo "[DEBUG] Launching user broker (${brokerPkg.version})..." >&2''}
    exec "${brokerPkg}/bin/microsoft-identity-broker" "$@"
  '';

  deviceBrokerWrapper = pkgs.writeShellScriptBin "microsoft-identity-device-broker${wrapperSuffix}" ''
    #!/usr/bin/env bash
    # microsoft-identity-device-broker wrapper: Device attestation (system service)
    # NOTE: To use this wrapper for the system service:
    #   sudo systemctl edit microsoft-identity-device-broker.service
    #   [Service]
    #   ExecStart=
    #   ExecStart=<nix-store-path>/bin/microsoft-identity-device-broker${wrapperSuffix}
    export LD_LIBRARY_PATH="${fullLibraryPath}:''${LD_LIBRARY_PATH:-}"
    ${debugEnvVars}
    exec "${brokerPkg}/bin/microsoft-identity-device-broker" "$@"
  '';

  # D-Bus service file for user broker
  userBrokerDbusService = pkgs.writeTextFile {
    name = "com.microsoft.identity.broker1.service";
    destination = "/share/dbus-1/services/com.microsoft.identity.broker1.service";
    text = ''
      [D-BUS Service]
      Name=com.microsoft.identity.broker1
      Exec=${userBrokerWrapper}/bin/microsoft-identity-broker${wrapperSuffix}
    '';
  };

  # ============================================================================
  # HELPER SCRIPTS
  # ============================================================================

  logsHelper = pkgs.writeShellScriptBin "intune-logs" ''
    #!/usr/bin/env bash
    case "''${1:---all}" in
      --portal) tail -f /tmp/intune-portal.log 2>/dev/null || echo "No log (run with debug=true)" ;;
      --broker) journalctl --user -f -t microsoft-identity-broker ;;
      --device) sudo journalctl -u microsoft-identity-device-broker -f ;;
      --all|*) (
        tail -F /tmp/intune-portal.log 2>/dev/null | sed 's/^/[portal] /' &
        journalctl --user -f -t microsoft-identity-broker 2>/dev/null | sed 's/^/[broker] /' &
        sudo journalctl -u microsoft-identity-device-broker -f 2>/dev/null | sed 's/^/[device] /' &
        wait
      ) ;;
    esac
  '';

  statusHelper = pkgs.writeShellScriptBin "intune-status" ''
    #!/usr/bin/env bash
    echo "=== INTUNE STATUS (mode: ${if mode != null then mode else "unsupported"}) ==="
    echo ""
    echo "PROCESSES:"; ps aux | grep -E "(intune|microsoft.*broker)" | grep -v grep || echo "  (none)"
    echo ""
    echo "SERVICES:"
    echo "  Device broker:"; systemctl status microsoft-identity-device-broker --no-pager 2>/dev/null | head -3 || echo "    Not found"
    echo "  Agent timer:"; systemctl --user status intune-agent.timer --no-pager 2>/dev/null | head -3 || echo "    Not found"
    echo ""
    echo "D-BUS: $([ -f ~/.local/share/dbus-1/services/com.microsoft.identity.broker1.service ] && echo 'Nix-managed' || echo 'system')"
    echo "VERSIONS: intune-portal ${intunePkg.version}, broker ${brokerPkg.version}"
    echo ""
    echo "For detailed diagnostics: intune-health"
  '';

  healthHelper = pkgs.writeShellScriptBin "intune-health" ''
    #!/usr/bin/env bash
    # intune-health: Comprehensive validation of Intune components
    # Exit 0 if all critical components pass
    # Exit 1 if any critical component fails

    set -uo pipefail

    # Colors for output
    PASS="\033[32m[PASS]\033[0m"
    FAIL="\033[31m[FAIL]\033[0m"
    WARN="\033[33m[WARN]\033[0m"
    INFO="\033[34m[INFO]\033[0m"

    CRITICAL_FAILURES=0

    check() {
      local name="$1"
      local critical="$2"
      shift 2
      if "$@" >/dev/null 2>&1; then
        echo -e "$PASS $name"
        return 0
      else
        if [[ "$critical" == "critical" ]]; then
          echo -e "$FAIL $name"
          ((CRITICAL_FAILURES++))
        else
          echo -e "$WARN $name (optional)"
        fi
        return 1
      fi
    }

    hint() {
      echo -e "      $INFO Hint: $1"
    }

    echo "=== INTUNE HEALTH CHECK (mode: ${if mode != null then mode else "unsupported"}) ==="
    echo ""

    # === SYSTEMD SERVICES ===
    echo "--- Systemd Services ---"
    if ! check "Device broker service running" critical systemctl is-active microsoft-identity-device-broker; then
      hint "Run: intune-prerequisites && sudo systemctl start microsoft-identity-device-broker"
    fi

    if ! check "Device broker enabled at boot" optional systemctl is-enabled microsoft-identity-device-broker; then
      hint "Run: sudo systemctl enable microsoft-identity-device-broker"
    fi

    if ! check "Intune agent timer enabled" optional systemctl --user is-enabled intune-agent.timer; then
      hint "Run: systemctl --user enable --now intune-agent.timer"
    fi
    echo ""

    # === D-BUS SERVICES ===
    echo "--- D-Bus Services ---"
    # Use bash -c for piped commands
    if ! check "Device broker on system bus" critical bash -c "busctl --system list | grep -q devicebroker1"; then
      hint "Run: intune-prerequisites (installs D-Bus policy)"
    fi

    if ! check "User broker service file exists" critical test -f ~/.local/share/dbus-1/services/com.microsoft.identity.broker1.service; then
      hint "Run: home-manager switch --flake .#\$(hostname)"
    fi

    # Test D-Bus activation works (only if in a graphical session)
    if [[ -n "''${DBUS_SESSION_BUS_ADDRESS:-}" ]]; then
      if ! check "User broker D-Bus activates" critical busctl --user call com.microsoft.identity.broker1 /com/microsoft/identity/broker1 org.freedesktop.DBus.Peer Ping; then
        hint "Check: cat ~/.local/share/dbus-1/services/com.microsoft.identity.broker1.service"
      fi
    else
      echo -e "$WARN User broker D-Bus test skipped (no session bus - run in graphical session)"
    fi
    echo ""

    # === PCSCD / SMART CARD ===
    echo "--- Smart Card (pcscd) ---"
    if ! check "pcscd service running" critical systemctl is-active pcscd.service; then
      if ! systemctl is-active pcscd.socket >/dev/null 2>&1; then
        hint "Run: sudo systemctl start pcscd.socket"
      fi
    fi

    if ! check "pcscd socket symlink exists" critical test -L /run/pcscd/pcscd; then
      hint "Run: intune-prerequisites (creates tmpfiles symlink)"
    fi
    echo ""

    # === PKCS#11 MODULE ===
    echo "--- PKCS#11 Module ---"
    OPENSC_MODULE=""
    # Try user config first
    if [[ -f ~/.config/pkcs11/modules/opensc.module ]]; then
      OPENSC_MODULE=$(grep "^module:" ~/.config/pkcs11/modules/opensc.module 2>/dev/null | cut -d: -f2 | tr -d ' ')
    fi
    # Fall back to system config
    if [[ -z "$OPENSC_MODULE" ]] && [[ -d /etc/pkcs11/modules ]]; then
      OPENSC_MODULE=$(grep -h "^module:" /etc/pkcs11/modules/*.module 2>/dev/null | head -1 | cut -d: -f2 | tr -d ' ')
    fi

    if ! check "OpenSC module configured" critical test -n "$OPENSC_MODULE"; then
      hint "Run: intune-prerequisites (installs PKCS#11 modules)"
    else
      if ! check "OpenSC module file exists" critical test -f "$OPENSC_MODULE"; then
        hint "Module path in config does not exist: $OPENSC_MODULE"
      fi
    fi
    echo ""

    # === YUBIKEY (optional) ===
    echo "--- YubiKey (optional) ---"
    if command -v pcsc_scan >/dev/null 2>&1 && pcsc_scan -r 2>/dev/null | grep -qi "yubikey\|piv"; then
      check "YubiKey detected by pcscd" optional true
      if [[ -n "$OPENSC_MODULE" ]] && [[ -f "$OPENSC_MODULE" ]]; then
        if ! check "PIV certificates accessible" optional bash -c "pkcs11-tool --module '$OPENSC_MODULE' --list-objects --type cert 2>/dev/null | grep -q 'Certificate'"; then
          hint "Insert YubiKey and unlock with PIN"
        fi
      fi
    else
      echo -e "$WARN YubiKey not inserted - skipping certificate checks"
      hint "Insert YubiKey for authentication"
    fi
    echo ""

    # === SUMMARY ===
    echo "--- Summary ---"
    if [[ $CRITICAL_FAILURES -eq 0 ]]; then
      echo -e "$PASS All critical components healthy"
      echo ""
      echo "Ready to launch: intune-portal${wrapperSuffix}"
      exit 0
    else
      echo -e "$FAIL $CRITICAL_FAILURES critical failure(s)"
      echo ""
      echo "Run 'intune-prerequisites' to fix common issues"
      exit 1
    fi
  '';

  prereqHelper = pkgs.writeShellScriptBin "intune-prerequisites" ''
    #!/usr/bin/env bash
    # Wrapper to run intune-prerequisites.sh from dotfiles
    DOTFILES="''${DOTFILES:-$HOME/.dotfiles}"
    # Check common mount paths for Parallels shared folders
    if [[ ! -d "$DOTFILES" ]] && [[ -d "/mnt/psf/dotfiles" ]]; then
      DOTFILES="/mnt/psf/dotfiles"
    elif [[ ! -d "$DOTFILES" ]] && [[ -d "/mnt/psf/Home/Documents/dotfiles" ]]; then
      DOTFILES="/mnt/psf/Home/Documents/dotfiles"
    fi
    SCRIPT="$DOTFILES/scripts/intune-prerequisites.sh"
    if [[ -f "$SCRIPT" ]]; then
      exec "$SCRIPT" "$@"
    else
      echo "Error: intune-prerequisites.sh not found at $SCRIPT"
      echo "Set DOTFILES env var to your dotfiles location"
      echo "Checked: ~/.dotfiles, /mnt/psf/dotfiles, /mnt/psf/Home/Documents/dotfiles"
      exit 1
    fi
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

  config = mkIf (cfg.enable && pkgs.stdenv.isLinux && mode != null) {
    # Enable Rosetta binfmt support (only for Rosetta mode)
    modules.linux.rosetta.enable = isRosetta;

    home.packages = with pkgSource; [
      # Tools: keyring, YubiKey, helpers, wrappers
      pkgs.gnome-keyring pkgs.seahorse pkgs.libsecret
      pkgs.yubikey-manager pkgs.pcsc-tools pkgs.nss.tools
      logsHelper statusHelper healthHelper prereqHelper
      intuneWrapper intuneAgentWrapper userBrokerWrapper deviceBrokerWrapper userBrokerDbusService
      # Libraries (pkgSource resolves based on mode)
      libglvnd wayland mesa glib-networking gnutls nettle libtasn1 libidn2
      openscArch libp11 pcsclite.lib p11-kit p11-kit.bin libfido2
      dbus.lib glib.out systemdLibs util-linux.lib curlNoHttp3.out
      zlib.out libssh2.out nghttp2.lib brotli.lib icu.out stdenv.cc.cc.lib
      zstd.out expat.out pcre2.out libxkbcommon.out fontconfig.lib freetype.out
      cairo.out pango.out gdk-pixbuf.out gtk3.out atk.out at-spi2-atk.out at-spi2-core.out harfbuzz.out
      xorg.libX11.out xorg.libXext.out xorg.libXrender.out xorg.libXi.out xorg.libXcursor.out
      xorg.libXrandr.out xorg.libXfixes.out xorg.libXcomposite.out xorg.libXdamage.out xorg.libxcb.out
      webkitgtk_4_1.out libsoup_3.out sqlite.out libpsl.out libidn.out
      libpng.out libjpeg.out libwebp.out lcms2.out
      gst_all_1.gstreamer.out gst_all_1.gst-plugins-base.out
      libxml2.out libxslt.out enchant.out libnotify.out opensslArch
    ];

    # D-Bus service file for user broker
    xdg.dataFile."dbus-1/services/com.microsoft.identity.broker1.service" = {
      source = "${userBrokerDbusService}/share/dbus-1/services/com.microsoft.identity.broker1.service";
    };

    # PKCS#11 module config for p11-kit (YubiKey support)
    xdg.configFile."pkcs11/modules/opensc.module".text = ''
module: ${openscArch}/lib/pkcs11/opensc-pkcs11.so
critical: no
trust-policy: no
'';

    # Systemd user service for intune-agent (compliance reporting)
    systemd.user.services.intune-agent = {
      Unit = {
        Description = "Intune Agent - compliance reporting";
        After = [ "graphical-session.target" "gnome-keyring.service" ];
      };
      Service = {
        Type = "oneshot";
        ExecStart = "${intuneAgentWrapper}/bin/intune-agent${wrapperSuffix}";
        StateDirectory = "intune";
        Slice = "background.slice";
        Environment = [
          "DBUS_SESSION_BUS_ADDRESS=unix:path=%t/bus"
          "GNOME_KEYRING_CONTROL=%t/keyring"
        ];
      };
    };

    # Systemd timer for intune-agent (5min after login, then hourly)
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
    home.activation.verifyIntuneSetup =
      lib.hm.dag.entryAfter [ "writeBoundary" "linkGeneration" ] ''
        if [[ -f "$HOME/.local/share/dbus-1/services/com.microsoft.identity.broker1.service" ]]; then
          noteEcho "Intune: User broker D-Bus service installed (mode: ${if mode != null then mode else "unknown"})"
        else
          warnEcho "Intune: User broker D-Bus service not found"
        fi
        ${optionalString isRosetta ''
        noteEcho "Intune: Rosetta mode - verify binfmt with: cat /proc/sys/fs/binfmt_misc/rosetta"
        ''}
        if ! systemctl is-active microsoft-identity-device-broker >/dev/null 2>&1; then
          noteEcho "Intune: Device broker not running - run: intune-prerequisites"
        fi
        if ! systemctl --user is-enabled intune-agent.timer >/dev/null 2>&1; then
          noteEcho "Intune: Enable agent timer with: systemctl --user enable --now intune-agent.timer"
        fi
      '';
  };
}
