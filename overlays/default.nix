# Custom overlays for extending nixpkgs
final: prev: {
  # FIXME: nushell 0.110.0 test fails in sandbox with I/O permission error
  # Test: shell::environment::env::path_is_a_list_in_repl
  # Skip tests until upstream fixes or cached binary is available
  nushell = prev.nushell.overrideAttrs (oldAttrs: {
    doCheck = false;
  });
  lan-mouse-app = final.callPackage ../packages/lan-mouse-app { };

  # Pin lan-mouse to match the pre-built .app bundle (latest pre-release)
  # to avoid protocol version mismatch between macOS and Linux hosts.
  lan-mouse = prev.lan-mouse.overrideAttrs (oldAttrs: rec {
    version = "unstable-2026-02-22";
    src = final.fetchFromGitHub {
      owner = "feschber";
      repo = "lan-mouse";
      rev = "27225ed56435681b18cfbb0499320fc626359730";
      hash = "sha256-5pyZQbceDRBh2xYYcMf39WeyMp7z7z7X1ydFpyt+kGU=";
    };
    prePatch = ""; # Don't remove build.rs — new version uses shadow-rs
    env = (oldAttrs.env or { }) // { GIT_DESCRIBE = version; };
    cargoDeps = final.rustPlatform.fetchCargoVendor {
      inherit src;
      name = "${oldAttrs.pname}-${version}-vendor";
      hash = "sha256-9ndm/rRSLiaCHlsTiy1Lxz0Z7n4umXjohqd98bHiWx0=";
    };
  });

  # FIXME: azure-cli ssh extension requires oras==0.1.30 but nixpkgs has 0.2.39
  # Skip the runtime dependency check until upstream fixes the version constraint
  azure-cli-extensions = prev.azure-cli-extensions // {
    ssh = prev.azure-cli-extensions.ssh.overridePythonAttrs (oldAttrs: {
      pythonRuntimeDepsCheck = "disabled";
    });
  };

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
