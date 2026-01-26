# Custom overlays for extending nixpkgs
final: prev: {
  ghidra-extensions = prev.ghidra-extensions // {
    ghydramcp = final.callPackage ./ghidra-extensions/ghydramcp.nix { };
  };

  # FIXME: upstream bug - missing 'in' in for loop
  # https://github.com/NixOS/nixpkgs/blob/master/pkgs/tools/security/ghidra/default.nix
  # postFixup has: for bin $out/lib/ghidra/support/*
  # should be:     for bin in $out/lib/ghidra/support/*
  ghidra = prev.ghidra.overrideAttrs (oldAttrs: {
    postFixup = builtins.replaceStrings
      [ "for bin $out/lib/ghidra/support/*" ]
      [ "for bin in $out/lib/ghidra/support/*" ]
      oldAttrs.postFixup;
  });
}
