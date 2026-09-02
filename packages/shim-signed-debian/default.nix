# packages/shim-signed-debian/default.nix
#
# Microsoft-signed aarch64 shim + MokManager, lifted out of Debian trixie's
# binary packages. Debian is the source because its shim is dual-signed by
# "Microsoft Corporation UEFI CA 2011" *and* "Microsoft UEFI CA 2023" -- the
# only signatures Parallels' EDK II firmware trusts (it ignores a custom
# PK/KEK/db entirely, see modules/nixos/secureboot.nix).
#
# Nothing is compiled here: re-signing would void exactly the property we want.
#
# Usage: pkgs.callPackage ../../packages/shim-signed-debian { }
#
{
  lib,
  stdenvNoCC,
  fetchurl,
  binutils,
}:

let
  shimSigned = fetchurl {
    url = "http://deb.debian.org/debian/pool/main/s/shim-signed/shim-signed_1.51~1+deb13u1+16.1-2~deb13u1_arm64.deb";
    sha256 = "e228a68b298865e0f1b35f93dac8fc9644a47bde3487419efe305777e2d4a1f0";
  };
  shimHelpers = fetchurl {
    url = "http://deb.debian.org/debian/pool/main/s/shim-helpers-arm64-signed/shim-helpers-arm64-signed_1+16.1+2~deb13u1_arm64.deb";
    sha256 = "0563a90af1f9990a592a79f52845747daff51c1d345769adc07830d2547da325";
  };
in
stdenvNoCC.mkDerivation {
  pname = "shim-signed-debian";
  version = "16.1-2~deb13u1";

  nativeBuildInputs = [ binutils ]; # `ar`, to open the .deb

  dontUnpack = true;
  dontBuild = true;
  dontFixup = true; # PE/COFF EFI binaries, not ELF -- and they must not change

  installPhase = ''
    runHook preInstall

    for deb in ${shimSigned} ${shimHelpers}; do
      ar x "$deb"
      tar xJf data.tar.xz
      rm data.tar.xz
    done

    # shimaa64.efi chain-loads `grubaa64.efi` from its own directory (the name
    # is compiled in); mmaa64.efi is MokManager, which enrolls our db cert as a
    # MOK; fbaa64.efi is the fallback that rebuilds Boot#### entries from
    # BOOT.CSV -- packaged for completeness, deliberately NOT put on the ESP.
    install -Dm444 usr/lib/shim/shimaa64.efi.signed $out/shimaa64.efi
    install -Dm444 usr/lib/shim/mmaa64.efi.signed $out/mmaa64.efi
    install -Dm444 usr/lib/shim/fbaa64.efi.signed $out/fbaa64.efi

    runHook postInstall
  '';

  meta = {
    description = "Microsoft-signed aarch64 shim and MokManager from Debian trixie";
    homepage = "https://tracker.debian.org/pkg/shim-signed";
    license = lib.licenses.bsd2Patent;
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
    platforms = [ "aarch64-linux" ];
  };
}
