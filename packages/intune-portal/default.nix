# packages/intune-portal/default.nix
#
# Microsoft Intune Portal for Linux - fetched directly from Microsoft's repo
# to get the latest version (nixpkgs is often outdated).
#
# Usage: pkgsX86.callPackage ../../../packages/intune-portal { }
#
{ lib
, stdenvNoCC
, fetchurl
, gnutar
, gzip
, binutils
, zstd
}:

stdenvNoCC.mkDerivation rec {
  pname = "intune-portal";
  version = "1.2511.7-noble";

  src = fetchurl {
    url = "https://packages.microsoft.com/ubuntu/24.04/prod/pool/main/i/${pname}/${pname}_${version}_amd64.deb";
    sha256 = "13yaiqg63373xk0znm7039pxhk97f59s0rf56lcnzix68ydc0yrh";
  };

  # No build needed - just extract
  dontBuild = true;
  dontConfigure = true;
  dontFixup = true;  # Don't patch ELF - binaries are x86_64, may run via Rosetta

  nativeBuildInputs = [ gnutar gzip zstd binutils ];

  unpackPhase = ''
    runHook preUnpack
    # .deb is an ar archive containing data.tar (may be .gz, .xz, or .zst)
    ar x $src
    if [ -f data.tar.zst ]; then
      zstd -d data.tar.zst
      tar xf data.tar
    elif [ -f data.tar.gz ]; then
      tar xzf data.tar.gz
    elif [ -f data.tar.xz ]; then
      tar xJf data.tar.xz
    else
      tar xf data.tar
    fi
    runHook postUnpack
  '';

  installPhase = ''
    runHook preInstall

    # Main binaries (intune-portal and intune-agent)
    mkdir -p $out/bin
    if [ -f opt/microsoft/intune/bin/intune-portal ]; then
      cp opt/microsoft/intune/bin/intune-portal $out/bin/
    elif [ -f usr/bin/intune-portal ]; then
      cp usr/bin/intune-portal $out/bin/
    fi

    # intune-agent - compliance reporting daemon
    if [ -f opt/microsoft/intune/bin/intune-agent ]; then
      cp opt/microsoft/intune/bin/intune-agent $out/bin/
    fi

    # Libraries (if any)
    if [ -d opt/microsoft/intune/lib ]; then
      mkdir -p $out/lib
      cp -r opt/microsoft/intune/lib/* $out/lib/
    fi

    # Desktop file and icons
    mkdir -p $out/share/applications
    mkdir -p $out/share/icons
    cp usr/share/applications/* $out/share/applications/ 2>/dev/null || true
    cp -r usr/share/icons/* $out/share/icons/ 2>/dev/null || true

    # Polkit rules (if any)
    if [ -d usr/share/polkit-1 ]; then
      mkdir -p $out/share/polkit-1
      cp -r usr/share/polkit-1/* $out/share/polkit-1/
    fi

    runHook postInstall
  '';

  meta = with lib; {
    description = "Microsoft Intune Portal for Linux device enrollment and compliance";
    homepage = "https://learn.microsoft.com/en-us/mem/intune/user-help/enroll-device-linux";
    license = licenses.unfree;
    platforms = [ "x86_64-linux" ];
    sourceProvenance = with sourceTypes; [ binaryNativeCode ];
    maintainers = [ ];
  };
}
