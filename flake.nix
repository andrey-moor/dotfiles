{
  description = "A grossly incandescent nixos config.";

  inputs =
    {
      # Core dependencies.
      nixpkgs.url = "nixpkgs/nixos-unstable";             # primary nixpkgs
      nixpkgs-unstable.url = "nixpkgs/nixpkgs-unstable";  # for packages on the edge
      #agenix.url = "github:ryantm/agenix";
      #agenix.inputs.nixpkgs.follows = "nixpkgs";
      home-manager-unstable = {
        url = "github:nix-community/home-manager/release-22.05";
        inputs.nixpkgs.follows = "nixpkgs-unstable";
      };

      home-manager = {
        url = "github:nix-community/home-manager/release-22.05";
        inputs.nixpkgs.follows = "nixpkgs";
      };


      # Extras
      nixos-hardware.url = "github:nixos/nixos-hardware";
    };

  outputs = inputs @ { self, nixpkgs, nixpkgs-unstable, ... }:
    let
      inherit (lib.my) mapModules mapModulesRec mapHosts;

      system = "aarch64-linux";

      mkPkgs = pkgs: extraOverlays: import pkgs {
        inherit system;
        config.allowUnfree = true;
        overlays = extraOverlays;# ++ (lib.attrValues self.overlays);
      };
      pkgs  = mkPkgs nixpkgs [ self.overlay ];
      pkgs' = mkPkgs nixpkgs-unstable [];

      lib = nixpkgs.lib.extend
        (self: super: { my = import ./lib { inherit pkgs inputs; lib = self; }; });
    in {
      lib = lib.my;

      overlay =
        final: prev: {
          unstable = pkgs';
          my = self.packages."${system}";
        };

      # overlays =
      #   mapModules ./overlays import;

      packages."${system}" =
        mapModules ./packages (p: pkgs.callPackage p {});

      nixosModules =
        { dotfiles = import ./.; } // mapModulesRec ./modules import;

      nixosConfigurations =
        mapHosts ./hosts {};

      # devShell."${system}" =
      #   import ./shell.nix { inherit pkgs; };

      # templates = {
      #  full = {
      #    path = ./.;
      #    description = "A grossly incandescent nixos config";
      #  };
      #  minimal = {
      #    path = ./templates/minimal;
      #    description = "A grossly incandescent and minimal nixos config";
      #  };
      #};
      #defaultTemplate = self.templates.minimal;

      # defaultApp."${system}" = {
      #  type = "app";
      #  program = ./bin/hey;
      #};
    };
}
