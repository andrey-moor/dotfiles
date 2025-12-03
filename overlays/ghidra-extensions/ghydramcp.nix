# GhydraMCP - Ghidra MCP bridge extension
# https://github.com/starsong-consulting/GhydraMCP
{ lib, stdenv, fetchurl, unzip }:

stdenv.mkDerivation rec {
  pname = "ghydramcp";
  version = "2.1.0";

  src = fetchurl {
    url = "https://github.com/starsong-consulting/GhydraMCP/releases/download/v${version}/GhydraMCP-v${version}-20251114-121920.zip";
    hash = "sha256-1adXHOn9PW0MHC8aUcN7R4JbA5TUPpiedjlxe9kh/lM=";
  };

  nativeBuildInputs = [ unzip ];

  dontUnpack = true;

  installPhase = ''
    runHook preInstall

    mkdir -p $out/lib/ghidra/Ghidra/Extensions
    unzip -d $out/lib/ghidra/Ghidra/Extensions $src

    # Prevent attempted creation of plugin lock files in the Nix store
    touch $out/lib/ghidra/Ghidra/Extensions/GhydraMCP/.dbDirLock

    runHook postInstall
  '';

  meta = with lib; {
    description = "MCP bridge for AI-assisted reverse engineering with Ghidra";
    homepage = "https://github.com/starsong-consulting/GhydraMCP";
    license = licenses.asl20;
    platforms = platforms.all;
  };
}
