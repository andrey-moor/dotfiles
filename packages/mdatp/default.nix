# packages/mdatp/default.nix
#
# Microsoft Defender for Endpoint (mdatp), the official arm64 Ubuntu 24.04
# package from packages.microsoft.com. The output is the deb's
# /opt/microsoft/mdatp tree, nothing else from the deb.
#
# The binaries stay exactly as Microsoft ships them. Defender's anti-tamper
# code checks /proc/<pid>/exe and file integrity, so patchelf, wrapProgram
# and any rename would break it. The ELF interpreter /lib/ld-linux-aarch64.so.1
# comes from nix-ld at runtime (modules/nixos/defender.nix). The bundled
# libraries resolve through the binaries' own RUNPATH, $ORIGIN/../lib.
#
# Precedent: NitorCreations/nix-mdatp and robertjarske/nix-dots (x86_64).
#
# Bump: pick the newest `Package: mdatp` entry from
#   https://packages.microsoft.com/ubuntu/24.04/prod/dists/noble/main/binary-arm64/Packages
# set `version`, then convert its SHA256 field with
#   nix hash convert --hash-algo sha256 --to sri <hex>
# Check the new postinst's NetFilterDependencies list against the links below.
{
  lib,
  stdenvNoCC,
  fetchurl,
  dpkg,
}:

stdenvNoCC.mkDerivation rec {
  pname = "mdatp";
  version = "101.26101.0000";

  src = fetchurl {
    url = "https://packages.microsoft.com/ubuntu/24.04/prod/pool/main/m/mdatp/mdatp_${version}_arm64.deb";
    hash = "sha256-FuM9Ynjpa6oZSvkc6euO6P7zg99KMRmwlBD2ObPcXxU=";
  };

  nativeBuildInputs = [ dpkg ];

  unpackPhase = ''
    runHook preUnpack
    dpkg-deb -x $src .
    runHook postUnpack
  '';

  dontConfigure = true;
  dontBuild = true;
  # No fixup at all: no strip, no patchelf, no patchShebangs on the bundled
  # scripts, and no moveSbin. sensecm insists its peers run from sbin/, so
  # sbin/ must stay a real directory.
  dontFixup = true;

  installPhase = ''
    runHook preInstall
    cp -a opt/microsoft/mdatp $out

    # The deb's postinst makes these soname links inside lib/ on every
    # install (SetLibfuse and NetFilterDependencies). Same pairs, same
    # condition: link only when the versioned file ships.
    link() {
      if [ -f "$out/lib/$1" ]; then
        ln -sf "$1" "$out/lib/$2"
      fi
    }
    link libfuse.so.2.9.2 libfuse.so.2
    link libpcre2-8.so.0.14.0 libpcre2-8.so.0
    link libpcre2-8.so libpcre2-8.so.0
    link libpcre2-posix.so.3.0.4 libpcre2-posix.so.3
    link libnfnetlink.so.0.2.0 libnfnetlink.so.0
    link libnetfilter_queue.so.1.5.0 libnetfilter_queue.so.1
    link libmnl.so.0.2.0 libmnl.so.0
    link libffi.so.8.1.0 libffi.so.8
    link libglib-2.0.so.0.7302.0 libglib-2.0.so.0

    runHook postInstall
  '';

  meta = {
    description = "Microsoft Defender for Endpoint on Linux";
    homepage = "https://learn.microsoft.com/en-us/defender-endpoint/microsoft-defender-endpoint-linux";
    license = lib.licenses.unfree;
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
    platforms = [ "aarch64-linux" ];
  };
}
