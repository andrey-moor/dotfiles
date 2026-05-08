# packages/hunk/default.nix
#
# hunk - Review-first terminal diff viewer for agentic coders.
# Fetched directly from GitHub releases; the upstream npm package
# `hunkdiff` ships the same prebuilt binaries (one bun-bundled
# self-contained executable per platform).
#
# Linux binary is dynamically linked against the system glibc/ld
# (`/lib64/ld-linux-x86-64.so.2`). Both target hosts (rocinante,
# stargazer) are non-NixOS Arch with that path available, so we
# rely on the system loader rather than autoPatchelfHook (the
# binary is a ~120 MB bun bundle with its own embedded runtime —
# patching is unnecessary and risks rewriting offsets we don't
# control). Switch to autoPatchelfHook if this ever needs to run
# on NixOS.
#
# Usage: pkgs.callPackage ../../packages/hunk { }
#
{ lib, stdenv, stdenvNoCC, fetchurl }:

let
  version = "0.10.0";

  archives = {
    "x86_64-linux"   = { name = "hunkdiff-linux-x64";    sha256 = "1kwyk04vi9ji1hb99dv746jxi66c1d7bqhl3isz961xlbdpwlg9l"; };
    "aarch64-linux"  = { name = "hunkdiff-linux-arm64";  sha256 = "1hxb1whn7d101w24wr0fx1zz2fig0dchm239mzm7kiykxb98d5ks"; };
    "x86_64-darwin"  = { name = "hunkdiff-darwin-x64";   sha256 = "09lxd54skcssgqapdrissf7spyigl83z39npnacrpvgyil6bhhzg"; };
    "aarch64-darwin" = { name = "hunkdiff-darwin-arm64"; sha256 = "0idd39ygk8929ijs77bf0xczkijnj7vwq1wvjvhpdgnyjdqv1n3i"; };
  };

  archive = archives.${stdenv.hostPlatform.system}
    or (throw "hunk: unsupported system ${stdenv.hostPlatform.system}");
in
stdenvNoCC.mkDerivation {
  pname = "hunk";
  inherit version;

  src = fetchurl {
    url = "https://github.com/modem-dev/hunk/releases/download/v${version}/${archive.name}.tar.gz";
    inherit (archive) sha256;
  };

  dontBuild = true;
  dontConfigure = true;
  dontFixup = true; # see header comment

  installPhase = ''
    runHook preInstall
    install -Dm755 hunk "$out/bin/hunk"
    install -Dm644 metadata.json "$out/share/hunk/metadata.json"
    runHook postInstall
  '';

  meta = with lib; {
    description = "Review-first terminal diff viewer for agentic coders";
    homepage = "https://github.com/modem-dev/hunk";
    license = licenses.mit;
    mainProgram = "hunk";
    platforms = builtins.attrNames archives;
    sourceProvenance = with sourceTypes; [ binaryNativeCode ];
    maintainers = [ ];
  };
}
