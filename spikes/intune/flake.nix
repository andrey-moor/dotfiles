{
  description = "P2 Intune spikes (throwaway)";
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    nixos-generators = { url = "github:nix-community/nixos-generators"; inputs.nixpkgs.follows = "nixpkgs"; };
    himmelblau = { url = "github:himmelblau-idm/himmelblau"; inputs.nixpkgs.follows = "nixpkgs"; };
  };
  outputs = { self, nixpkgs, nixos-generators, himmelblau }:
    let
      mkImage = system: modules: nixos-generators.nixosGenerate {
        inherit system modules; format = "qcow-efi";
      };
      # STUB (Task 2): b4-himmelblau.nix and b3-intuneme.nix don't exist until
      # Tasks 3/4. b4mods/b3mods temporarily alias ./base.nix so this flake
      # evaluates and base-image can be built/proven end-to-end. When Tasks
      # 3/4 land, restore:
      #   b4mods = [ ./base.nix ./b4-himmelblau.nix { _module.args.himmelblauFlake = himmelblau; } ];
      # and point b3-image at [ ./base.nix ./b3-intuneme.nix ].
      b4mods = [ ./base.nix ];
    in {
      packages.x86_64-linux = {
        base-image = mkImage "x86_64-linux" [ ./base.nix ];
        b4-image   = mkImage "x86_64-linux" b4mods;
        b3-image   = mkImage "x86_64-linux" [ ./base.nix ];
      };
      packages.aarch64-linux.b4-image = mkImage "aarch64-linux" b4mods;
    };
}
