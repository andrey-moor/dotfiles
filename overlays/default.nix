# Custom overlays for extending nixpkgs
#
# Every override here changes a derivation hash, so that package is built
# locally on every host and never comes from cache.nixos.org. Keep an override
# only while upstream is broken, and check for a cached build before adding one.
final: prev: {
  lan-mouse-app = final.callPackage ../packages/lan-mouse-app { };

  # Pin lan-mouse so the Linux daemon speaks the same protocol as the macOS
  # .app bundle (packages/lan-mouse-app, the v0.11.0 release). The commit
  # below predates v0.11.0 by 45 commits.
  lan-mouse = prev.lan-mouse.overrideAttrs (oldAttrs: rec {
    version = "unstable-2026-02-22";
    src = final.fetchFromGitHub {
      owner = "feschber";
      repo = "lan-mouse";
      rev = "27225ed56435681b18cfbb0499320fc626359730";
      hash = "sha256-5pyZQbceDRBh2xYYcMf39WeyMp7z7z7X1ydFpyt+kGU=";
    };
    prePatch = ""; # Don't remove build.rs — new version uses shadow-rs
    env = (oldAttrs.env or { }) // {
      GIT_DESCRIBE = version;
    };
    cargoDeps = final.rustPlatform.fetchCargoVendor {
      inherit src;
      name = "${oldAttrs.pname}-${version}-vendor";
      hash = "sha256-9ndm/rRSLiaCHlsTiy1Lxz0Z7n4umXjohqd98bHiWx0=";
    };
  });

  ghidra-extensions = prev.ghidra-extensions // {
    ghydramcp = final.callPackage ./ghidra-extensions/ghydramcp.nix { };
  };
}
