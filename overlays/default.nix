# Custom overlays for extending nixpkgs
final: prev: {
  ghidra-extensions = prev.ghidra-extensions // {
    ghydramcp = final.callPackage ./ghidra-extensions/ghydramcp.nix { };
  };
}
