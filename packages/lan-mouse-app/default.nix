# packages/lan-mouse-app/default.nix
#
# Lan Mouse macOS .app bundle -- fetched from GitHub releases.
# TCC (Accessibility) permissions are tied to the bundle identifier
# `de.feschber.LanMouse`, so they persist across Nix rebuilds unlike
# bare /nix/store binaries that get a new path every time.
#
# Pinned to the stable v0.11.0 release. Upstream retired the rolling `main`
# tag (pre-releases are now tagged `main-<commit>`), so to bump, pick a newer
# tagged release and update `version` + `sha256` below.
#
# Usage: pkgs.callPackage ../packages/lan-mouse-app { }

{
  lib,
  stdenvNoCC,
  fetchurl,
  unzip,
}:

stdenvNoCC.mkDerivation rec {
  pname = "lan-mouse-app";
  version = "v0.11.0";

  src = fetchurl {
    url = "https://github.com/feschber/lan-mouse/releases/download/${version}/lan-mouse-macos-arm64.zip";
    sha256 = "sha256-X/mWXQW+fxJbHXW55yWdh07JiqCGzkABJSK8JUBlAKk=";
  };

  dontBuild = true;
  dontConfigure = true;
  dontFixup = true; # Preserve codesigning

  nativeBuildInputs = [ unzip ];

  sourceRoot = ".";

  installPhase = ''
    runHook preInstall

    mkdir -p "$out/Applications" "$out/bin"
    cp -R "Lan Mouse.app" "$out/Applications/"
    ln -s "$out/Applications/Lan Mouse.app/Contents/MacOS/lan-mouse" "$out/bin/lan-mouse"

    runHook postInstall
  '';

  meta = with lib; {
    description = "LAN Mouse -- mouse and keyboard sharing (macOS .app bundle)";
    homepage = "https://github.com/feschber/lan-mouse";
    license = licenses.gpl3Only;
    platforms = [ "aarch64-darwin" ];
    sourceProvenance = with sourceTypes; [ binaryNativeCode ];
    maintainers = [ ];
  };
}
