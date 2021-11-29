# flake.nix --- the heart of my dotfiles
#
# Author:  Henrik Lissner <henrik@lissner.net>
# URL:     https://github.com/andrey-moor/dotfiles
# License: MIT
#
# Welcome to ground zero. Where the whole flake gets set up and all its modules
# are loaded.

{
  description = "A grossly incandescent nixos config.";

  inputs =
    {
      # Core dependencies.
      nixpkgs.url = "nixpkgs/nixos-unstable";             # primary nixpkgs
      nixpkgs-unstable.url = "nixpkgs/nixpkgs-unstable";  # for packages on the edge
      # home-manager.url = "github:rycee/home-manager/master";
      # home-manager.inputs.nixpkgs.follows = "nixpkgs";
      #agenix.url = "github:ryantm/agenix";
      #agenix.inputs.nixpkgs.follows = "nixpkgs";
      home-manager-unstable = {
        url = "github:nix-community/home-manager/release-21.05";
        inputs.nixpkgs.follows = "nixpkgs-unstable";
      };

      home-manager = {
        url = "github:nix-community/home-manager/release-21.05";

        # We want home-manager to use the same set of nixpkgs as our system.
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
        config.allowUnfree = true;  # forgive me Stallman senpai
        overlays = extraOverlays ++ (lib.attrValues self.overlays);
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

      overlays =
        mapModules ./overlays import;

      packages."${system}" =
        mapModules ./packages (p: pkgs.callPackage p {});

      nixosModules =
        { dotfiles = import ./.; } // mapModulesRec ./modules import;

      nixosConfigurations =
        mapHosts ./hosts {};

      # devShell."${system}" =
      #   import ./shell.nix { inherit pkgs; };

      templates = {
        full = {
          path = ./.;
          description = "A grossly incandescent nixos config";
        };
        minimal = {
          path = ./templates/minimal;
          description = "A grossly incandescent and minimal nixos config";
        };
      };
      defaultTemplate = self.templates.minimal;

      defaultApp."${system}" = {
        type = "app";
        program = ./bin/hey;
      };
    };
}
