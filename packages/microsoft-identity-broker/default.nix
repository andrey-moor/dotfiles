{ lib
, stdenvNoCC
, fetchurl
, gnutar
, gzip
, binutils
}:

stdenvNoCC.mkDerivation rec {
  pname = "microsoft-identity-broker";
  version = "2.0.4";

  src = fetchurl {
    url = "https://packages.microsoft.com/ubuntu/24.04/prod/pool/main/m/${pname}/${pname}_${version}_amd64.deb";
    sha256 = "00q7wgsa9i0l9h0bbmqzzsyragwwvp2hsa5077y32vh5001yddr5";
  };

  # No build needed - just extract
  dontBuild = true;
  dontConfigure = true;
  dontFixup = true;  # Don't patch ELF - binaries are x86_64, may run via Rosetta

  nativeBuildInputs = [ gnutar gzip binutils ];

  unpackPhase = ''
    runHook preUnpack
    # .deb is an ar archive containing data.tar.gz
    ar x $src
    tar xzf data.tar.gz
    runHook postUnpack
  '';

  installPhase = ''
    runHook preInstall

    # Binaries (x86_64 ELF - don't patch)
    mkdir -p $out/bin
    cp opt/microsoft/identity-broker/bin/microsoft-identity-broker $out/bin/
    cp opt/microsoft/identity-broker/bin/microsoft-identity-device-broker $out/bin/

    # D-Bus service files
    mkdir -p $out/share/dbus-1/services
    mkdir -p $out/share/dbus-1/system-services
    mkdir -p $out/share/dbus-1/system.d
    cp usr/share/dbus-1/services/* $out/share/dbus-1/services/
    cp usr/share/dbus-1/system-services/* $out/share/dbus-1/system-services/
    cp usr/share/dbus-1/system.d/* $out/share/dbus-1/system.d/

    # Systemd service file
    mkdir -p $out/lib/systemd/system
    cp usr/lib/systemd/system/* $out/lib/systemd/system/

    # Desktop file and icons
    mkdir -p $out/share/applications
    mkdir -p $out/share/icons
    cp usr/share/applications/* $out/share/applications/ 2>/dev/null || true
    cp -r usr/share/icons/* $out/share/icons/ 2>/dev/null || true

    runHook postInstall
  '';

  meta = with lib; {
    description = "Microsoft Identity Broker for Linux SSO";
    homepage = "https://learn.microsoft.com/en-us/entra/identity/devices/sso-linux";
    license = licenses.unfree;
    platforms = [ "x86_64-linux" ];
    sourceProvenance = with sourceTypes; [ binaryNativeCode ];
    maintainers = [ ];
  };
}
