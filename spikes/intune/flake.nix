{
  description = "P2 Intune spikes (throwaway)";
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    nixos-generators = { url = "github:nix-community/nixos-generators"; inputs.nixpkgs.follows = "nixpkgs"; };
    himmelblau = { url = "github:himmelblau-idm/himmelblau"; inputs.nixpkgs.follows = "nixpkgs"; };
  };
  outputs = { self, nixpkgs, nixos-generators, himmelblau }:
    let
      # specialArgs (not modules-list `_module.args`) is required here: a module's
      # own `imports` list is resolved before `_module.args`-provided args exist,
      # so `imports = [ himmelblauFlake.nixosModules.himmelblau ]` inside
      # b4-himmelblau.nix hits nixpkgs' documented "infinite recursion" trap if
      # `himmelblauFlake` is threaded in via `_module.args` (confirmed by an
      # actual eval attempt -- Task 2's stub-restoration comment suggested
      # `_module.args`, which does not evaluate). `nixosGenerate` forwards
      # `specialArgs` straight to `nixosSystem`/`evalModules`, which resolves
      # `imports` correctly.
      mkImage = { system, modules, specialArgs ? { } }: nixos-generators.nixosGenerate {
        inherit system modules specialArgs; format = "qcow-efi";
      };
      # b4mods un-stubbed (Task 3): b4-himmelblau.nix now exists.
      # b3-image below is STILL STUBBED at [ ./base.nix ] -- that's Task 4's
      # to restore to [ ./base.nix ./b3-intuneme.nix ] once b3-intuneme.nix exists.
      b4mods = [ ./base.nix ./b4-himmelblau.nix ];
      b4specialArgs = { himmelblauFlake = himmelblau; };
    in {
      packages.x86_64-linux = {
        base-image = mkImage { system = "x86_64-linux"; modules = [ ./base.nix ]; };
        b4-image   = mkImage { system = "x86_64-linux"; modules = b4mods; specialArgs = b4specialArgs; };
        b3-image   = mkImage { system = "x86_64-linux"; modules = [ ./base.nix ]; };
      };
      packages.aarch64-linux.b4-image = mkImage { system = "aarch64-linux"; modules = b4mods; specialArgs = b4specialArgs; };
    };
}
