# GhidraMCP - Ghidra MCP server extension
# https://github.com/bethington/ghidra-mcp
{ lib, stdenv, fetchurl, unzip }:

stdenv.mkDerivation rec {
  pname = "ghidra-mcp";
  version = "5.3.1";

  src = fetchurl {
    url = "https://github.com/bethington/ghidra-mcp/releases/download/v${version}/GhidraMCP-${version}.zip";
    hash = "sha256-W8bJ9YRPjKsYOAvIEcQRM8D81qRnLE6ra5OI7BI+tvw=";
  };

  nativeBuildInputs = [ unzip ];

  dontUnpack = true;

  installPhase = ''
    runHook preInstall

    mkdir -p $out/lib/ghidra/Ghidra/Extensions
    unzip -d $out/lib/ghidra/Ghidra/Extensions $src

    # Prevent attempted creation of plugin lock files in the Nix store
    touch $out/lib/ghidra/Ghidra/Extensions/GhidraMCP/.dbDirLock

    runHook postInstall
  '';

  meta = with lib; {
    description = "Model Context Protocol server for Ghidra reverse engineering";
    homepage = "https://github.com/bethington/ghidra-mcp";
    license = licenses.asl20;
    platforms = platforms.all;
  };
}
