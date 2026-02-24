# packages/lan-mouse-app/default.nix
#
# Lan Mouse macOS .app bundle -- fetched from GitHub releases.
# TCC (Accessibility) permissions are tied to the bundle identifier
# `de.feschber.LanMouse`, so they persist across Nix rebuilds unlike
# bare /nix/store binaries that get a new path every time.
#
# The `latest` tag is a rolling pre-release. When a proper tagged release
# ships .app bundles, switch the URL and hash to that tag.
#
# Usage: pkgs.callPackage ../packages/lan-mouse-app { }

{ lib
, stdenvNoCC
, fetchurl
, unzip
}:

stdenvNoCC.mkDerivation rec {
  pname = "lan-mouse-app";
  version = "latest";

  src = fetchurl {
    url = "https://github.com/feschber/lan-mouse/releases/download/${version}/lan-mouse-macos-aarch64.zip";
    sha256 = "04kfsx2rjbfxgy52rgdgnjfh3gr1rg1v3sq6msrxqbcqr5mycwai";
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
