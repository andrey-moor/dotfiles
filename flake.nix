{
  description = "General Purpose Configuration for macOS and NixOS";

  inputs = {
    # Core dependencies
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    nixpkgs-main.url = "github:nixos/nixpkgs/master";

    # Essential modules
    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    sops-nix = {
      url = "github:Mic92/sops-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    # Kept for P7 (NixOS on rocinante's second NVMe).
    disko = {
      url = "github:nix-community/disko";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Platform support
    darwin = {
      url = "github:LnL7/nix-darwin/master";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nix-homebrew.url = "github:zhaofengli-wip/nix-homebrew";
    homebrew-bundle = {
      url = "github:homebrew/homebrew-bundle";
      flake = false;
    };
    homebrew-core = {
      url = "github:homebrew/homebrew-core";
      flake = false;
    };
    homebrew-cask = {
      url = "github:homebrew/homebrew-cask";
      flake = false;
    };

    # macOS app trampoline (makes Nix apps visible in Spotlight/Raycast)
    mac-app-util.url = "github:hraban/mac-app-util";

    # Additional inputs
    catppuccin.url = "github:catppuccin/nix";
    nixgl = {
      url = "github:nix-community/nixGL";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    claude-code-nix = {
      url = "github:sadjow/claude-code-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    copilot-cli-flake = {
      url = "github:scarisey/copilot-cli-flake";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    # goose.url = "github:block/goose";  # BLOCKED: upstream flake broken (issue #8514 — missing cargo outputHashes)

    # Nix User Repository for Firefox addons
    nur.url = "github:nix-community/NUR";
  };

  outputs =
    inputs@{
      nixpkgs,
      darwin,
      home-manager,
      catppuccin,
      sops-nix,
      nur,
      ...
    }:
    let
      inherit (nixpkgs) lib;

      # x86_64-darwin is out: nixpkgs 26.11 dropped it, and importing nixpkgs
      # for it throws (which would fail `nix flake check --all-systems`).
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];
      forAllSystems = lib.genAttrs systems;

      mkPkgs =
        system:
        import nixpkgs {
          inherit system;
          config.allowUnfree = true;
          overlays = [
            (import ./overlays)
            # nixpkgs master as pkgs.main (packages that land there first)
            (final: prev: {
              main = import inputs.nixpkgs-main {
                inherit system;
                config.allowUnfree = true;
              };
            })
            nur.overlays.default
          ];
        };

      # Home-manager modules loaded on every host, before the host's own imports.
      homeBase = [
        ./home
        catppuccin.homeModules.catppuccin
        sops-nix.homeManagerModules.sops
      ];
    in
    {
      # macOS workstation
      darwinConfigurations.behemoth =
        let
          system = "aarch64-darwin";
          pkgs = mkPkgs system;
          dotfilesDir = "/Users/andreym/Documents/dotfiles";
        in
        darwin.lib.darwinSystem {
          inherit system;

          specialArgs = { inherit inputs dotfilesDir; };

          modules = [
            {
              nixpkgs.pkgs = lib.mkDefault pkgs;
              networking.hostName = lib.mkDefault "behemoth";
            }
            home-manager.darwinModules.home-manager
            {
              home-manager.useGlobalPkgs = true;
              home-manager.useUserPackages = true;
              home-manager.extraSpecialArgs = { inherit inputs dotfilesDir; };
              home-manager.sharedModules = homeBase;
            }
            inputs.nix-homebrew.darwinModules.nix-homebrew
            # mac-app-util: trampolines so Nix apps appear in Spotlight/Raycast
            inputs.mac-app-util.darwinModules.default
            ./hosts/behemoth
          ];
        };

      # x86_64 Arch Linux workstation (standalone home-manager)
      homeConfigurations.rocinante =
        let
          dotfilesDir = "/home/andreym/dotfiles";
        in
        home-manager.lib.homeManagerConfiguration {
          pkgs = mkPkgs "x86_64-linux";

          extraSpecialArgs = { inherit inputs dotfilesDir; };

          modules = [
            {
              home.username = "andreym";
              home.homeDirectory = "/home/andreym";
            }
          ]
          ++ homeBase
          ++ [ ./hosts/rocinante ];
        };

      # aarch64 Parallels VM on behemoth (standalone home-manager)
      homeConfigurations.stargazer =
        let
          dotfilesDir = "/home/andreym/dotfiles";
        in
        home-manager.lib.homeManagerConfiguration {
          pkgs = mkPkgs "aarch64-linux";

          extraSpecialArgs = { inherit inputs dotfilesDir; };

          modules = [
            {
              home.username = "andreym";
              home.homeDirectory = "/home/andreym";
            }
          ]
          ++ homeBase
          ++ [ ./hosts/stargazer ];
        };

      formatter = forAllSystems (system: (mkPkgs system).nixfmt-rfc-style);

      devShells = forAllSystems (system: {
        default = import ./shell.nix { pkgs = mkPkgs system; };
      });
    };
}
