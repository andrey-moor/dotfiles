# Custom overlays for extending nixpkgs
final: prev: {
  # FIXME: nushell 0.110.0 test fails in sandbox with I/O permission error
  # Test: shell::environment::env::path_is_a_list_in_repl
  # Skip tests until upstream fixes or cached binary is available
  nushell = prev.nushell.overrideAttrs (oldAttrs: {
    doCheck = false;
  });
  lan-mouse-app = final.callPackage ../packages/lan-mouse-app { };

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
