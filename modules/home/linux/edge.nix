# modules/home/linux/edge.nix -- Microsoft Edge Browser
#
# Installs Microsoft Edge browser.
# On aarch64-linux, uses Rosetta emulation with x86_64 Mesa for software rendering.
# Uses bubblewrap to create NixOS-compatible /run/opengl-driver paths.
#
# PKCS#11/Smart Card Support:
#   - Edge uses NSS for certificate handling (not p11-kit/GnuTLS like WebKitGTK)
#   - NSS module config: ~/.pki/nssdb/pkcs11.txt (set up via intune-nss-setup)
#   - LD_LIBRARY_PATH includes nixpkgs OpenSSL for x86_64 OpenSC compatibility
#   - x86_64 OpenSC requires OpenSSL 3.4+ symbols (not compatible with Arch's 3.3.2)

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.linux.edge;

  # x86_64-linux pkgs for Rosetta emulation on aarch64
  pkgsX86 = import pkgs.path {
    system = "x86_64-linux";
    config.allowUnfree = true;
  };

  # Use x86_64 package on aarch64, native otherwise
  edgePackage =
    if pkgs.stdenv.hostPlatform.isAarch64
    then pkgsX86.microsoft-edge
    else pkgs.microsoft-edge;

  # Preload library to ignore SIGTRAP - works around crashpad Rosetta incompatibility
  # Crashpad's ARM signal handler doesn't understand x86_64 INT3 breakpoints under Rosetta
  sigtrapIgnore = pkgsX86.stdenv.mkDerivation {
    name = "sigtrap-ignore";
    dontUnpack = true;
    buildPhase = ''
      cat > sigtrap_ignore.c << 'EOF'
#define _GNU_SOURCE
#include <signal.h>
#include <string.h>
#include <dlfcn.h>

// Override sigaction to prevent crashpad from installing SIGTRAP handler
static int (*real_sigaction)(int, const struct sigaction*, struct sigaction*) = NULL;

int sigaction(int signum, const struct sigaction *act, struct sigaction *oldact) {
  if (!real_sigaction) {
    real_sigaction = dlsym(RTLD_NEXT, "sigaction");
  }
  // Block any attempts to handle SIGTRAP - just ignore them
  if (signum == SIGTRAP) {
    if (oldact) {
      memset(oldact, 0, sizeof(*oldact));
      oldact->sa_handler = SIG_IGN;
    }
    return 0;
  }
  return real_sigaction(signum, act, oldact);
}
EOF
      $CC -shared -fPIC -o libsigtrap_ignore.so sigtrap_ignore.c -ldl
    '';
    installPhase = ''
      mkdir -p $out/lib
      cp libsigtrap_ignore.so $out/lib/
    '';
  };

  # Create a directory structure that mimics NixOS /run/opengl-driver
  # This is what nixpkgs Edge expects
  openglDriverDir = pkgs.runCommand "opengl-driver-x86" {} ''
    mkdir -p $out/lib/gbm $out/lib/dri $out/lib/vdpau

    # Link Mesa DRI drivers
    for f in ${pkgsX86.mesa}/lib/dri/*.so*; do
      ln -sf "$f" $out/lib/dri/
    done

    # GBM needs the dri_gbm.so in lib/gbm/
    ln -sf ${pkgsX86.mesa}/lib/libgbm.so* $out/lib/
    ln -sf ${pkgsX86.mesa}/lib/libGL.so* $out/lib/
    ln -sf ${pkgsX86.mesa}/lib/libGLX.so* $out/lib/
    ln -sf ${pkgsX86.mesa}/lib/libEGL.so* $out/lib/
    ln -sf ${pkgsX86.mesa}/lib/libglapi.so* $out/lib/

    # Link drivers into gbm dir as well (some lookups check here)
    for f in ${pkgsX86.mesa}/lib/dri/*.so*; do
      ln -sf "$f" $out/lib/gbm/
    done

    # VDPAU drivers if present
    if [ -d "${pkgsX86.mesa}/lib/vdpau" ]; then
      for f in ${pkgsX86.mesa}/lib/vdpau/*.so*; do
        ln -sf "$f" $out/lib/vdpau/ 2>/dev/null || true
      done
    fi
  '';

  # Wrapper using bubblewrap to provide /run/opengl-driver
  edgeWrapper = pkgs.writeShellScriptBin "microsoft-edge-rosetta" ''
    # Use bubblewrap to create namespace with /run/opengl-driver
    # We need tmpfs on /run then bind back specific subdirs we need
    exec ${pkgs.bubblewrap}/bin/bwrap \
      --ro-bind / / \
      --dev /dev \
      --proc /proc \
      --tmpfs /tmp \
      --bind "$HOME" "$HOME" \
      --tmpfs /run \
      --ro-bind /run/user /run/user \
      --ro-bind /run/dbus /run/dbus \
      --ro-bind /run/pcscd /run/pcscd \
      --ro-bind /run/systemd/resolve /run/systemd/resolve \
      --ro-bind /tmp/.X11-unix /tmp/.X11-unix \
      --ro-bind ${openglDriverDir} /run/opengl-driver \
      --setenv DISPLAY "''${DISPLAY:-:0}" \
      --setenv XAUTHORITY "''${XAUTHORITY:-$HOME/.Xauthority}" \
      --setenv LIBGL_ALWAYS_SOFTWARE 1 \
      --setenv GALLIUM_DRIVER llvmpipe \
      --setenv MESA_LOADER_DRIVER_OVERRIDE llvmpipe \
      --setenv __EGL_VENDOR_LIBRARY_DIRS "${pkgsX86.mesa}/share/glvnd/egl_vendor.d" \
      --setenv LD_LIBRARY_PATH "${pkgsX86.openssl.out}/lib:${pkgsX86.libglvnd}/lib:${pkgsX86.mesa}/lib:''${LD_LIBRARY_PATH:-}" \
      --setenv LD_PRELOAD "${sigtrapIgnore}/lib/libsigtrap_ignore.so:''${LD_PRELOAD:-}" \
      --setenv CHROME_CRASHPAD_PIPE_NAME "" \
      -- ${edgePackage}/bin/microsoft-edge \
      --ozone-platform=x11 \
      --disable-breakpad \
      --disable-crash-reporter \
      --disable-features=Crashpad,UseChromeOSDirectVideoDecoder \
      --no-sandbox \
      --no-zygote \
      --disable-gpu \
      --disable-gpu-compositing \
      --disable-gpu-sandbox \
      --in-process-gpu \
      "$@"
  '';

in {
  options.modules.linux.edge = {
    enable = mkEnableOption "Microsoft Edge browser";
  };

  config = mkIf (cfg.enable && pkgs.stdenv.isLinux) {
    # Enable Rosetta support on aarch64
    modules.linux.rosetta.enable = mkIf pkgs.stdenv.hostPlatform.isAarch64 true;

    home.packages = [
      edgePackage
    ] ++ (if pkgs.stdenv.hostPlatform.isAarch64 then [
      # Wrapper with bubblewrap for proper OpenGL paths
      edgeWrapper
      # Dependencies
      pkgs.bubblewrap
      pkgsX86.mesa
      pkgsX86.libglvnd
      # Note: pkgsX86.openssl.out is referenced in LD_LIBRARY_PATH for PKCS#11/OpenSC
      # but NOT added to home.packages to avoid conflict with opensslArch in intune.nix
      # SIGTRAP ignore preload for crashpad Rosetta workaround
      sigtrapIgnore
    ] else []);
  };
}
