# packages/vhclient/default.nix
#
# VirtualHere USB client for x86_64 Linux. scripts/yubikey runs it on
# rocinante to attach the YubiKey that behemoth's server shares.
#
# Upstream publishes one unversioned URL and replaces the file on each
# release. A hash mismatch therefore means a new build came out: fetch it,
# update `sha256` and `version` (the date it was pinned).
#
# The binary is statically linked, so it needs no patching.
#
# Usage: pkgs.callPackage ../../packages/vhclient { }
#
{
  lib,
  stdenvNoCC,
  fetchurl,
}:

stdenvNoCC.mkDerivation {
  pname = "vhclient";
  version = "0-unstable-2026-11-18";

  src = fetchurl {
    url = "https://www.virtualhere.com/sites/default/files/usbclient/vhclientx86_64";
    sha256 = "0m659sf6vkdb8q32hsm95k33ryrbgac53y61vqxcwdqi5shl2vfn";
  };

  dontUnpack = true;
  dontBuild = true;
  dontConfigure = true;
  dontFixup = true; # static binary, see header comment

  installPhase = ''
    runHook preInstall
    install -Dm755 "$src" "$out/bin/vhclientx86_64"
    runHook postInstall
  '';

  meta = with lib; {
    description = "VirtualHere USB client";
    homepage = "https://www.virtualhere.com/usb_client_software";
    license = licenses.unfree;
    mainProgram = "vhclientx86_64";
    platforms = [ "x86_64-linux" ];
    sourceProvenance = with sourceTypes; [ binaryNativeCode ];
  };
}
