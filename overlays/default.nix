# Custom overlays for extending nixpkgs
#
# Every override here changes a derivation hash, so that package is built
# locally on every host and never comes from cache.nixos.org. Keep an override
# only while upstream is broken, and check for a cached build before adding one.
final: prev: {
  ghidra-extensions = prev.ghidra-extensions // {
    ghydramcp = final.callPackage ./ghidra-extensions/ghydramcp.nix { };
  };
}
