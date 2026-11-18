{
  description = "General Purpose Configuration for macOS and NixOS";

  inputs = {
    # Core dependencies
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    nixpkgs-main.url = "github:nixos/nixpkgs/master";
    # stargazer's patched Hyprland, its portal and Mesa come from this set
    # (modules/nixos/vmware-guest.nix). The revision in the URL keeps
    # `nix flake update` from moving it, so the weekly lock bump cannot break
    # the vmwgfx patch. Bump it by hand with the patch: hosts/stargazer/README.md.
    nixpkgs-hyprland.url = "github:nixos/nixpkgs/d5cc6833999746cffdfe0598f7bc801a57b887a9";

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

    # NixOS host layer (stargazer; P7 second)
    himmelblau = {
      url = "github:himmelblau-idm/himmelblau/4.0.4";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    # Only reached through modules/nixos/secureboot.nix, which is off by
    # default, so a first install never needs it.
    lanzaboote = {
      url = "github:nix-community/lanzaboote/v1.1.0";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Platform support
    darwin = {
      url = "github:LnL7/nix-darwin/master";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    # Determinate's nix-darwin module: manages nix.custom.conf and
    # determinate-nixd's config, and runs the Linux builder VM. The flakehub
    # URL is the vendor's documented form and resolves the 3.x range on update.
    # It keeps its own nixpkgs: it ships vendor-built Nix and determinate-nixd,
    # tested against the vendor's pins.
    determinate.url = "https://flakehub.com/f/DeterminateSystems/determinate/3";
    nix-homebrew.url = "github:zhaofengli-wip/nix-homebrew";
    homebrew-core = {
      url = "github:homebrew/homebrew-core";
      flake = false;
    };
    homebrew-cask = {
      url = "github:homebrew/homebrew-cask";
      flake = false;
    };

    # Additional inputs
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
    nur = {
      url = "github:nix-community/NUR";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    inputs@{
      nixpkgs,
      darwin,
      home-manager,
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
            (_final: _prev: {
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
            { nixpkgs.pkgs = lib.mkDefault pkgs; }
            home-manager.darwinModules.home-manager
            {
              home-manager.useGlobalPkgs = true;
              home-manager.useUserPackages = true;
              home-manager.extraSpecialArgs = { inherit inputs dotfilesDir; };
              home-manager.sharedModules = homeBase;
            }
            inputs.determinate.darwinModules.default
            inputs.nix-homebrew.darwinModules.nix-homebrew
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

      # aarch64 NixOS VM on VMware Fusion, hosted by behemoth, with integrated home-manager
      nixosConfigurations =
        let
          system = "aarch64-linux";
          pkgs = mkPkgs system;
          dotfilesDir = "/home/andreym/dotfiles";

          # stargazer and its fire drill twin share every module except the
          # host file, so the drill cannot drift from what it has to prove.
          mkStargazer =
            hostModule:
            nixpkgs.lib.nixosSystem {
              inherit system;

              specialArgs = { inherit inputs dotfilesDir; };

              modules = [
                { nixpkgs.pkgs = lib.mkDefault pkgs; }
                home-manager.nixosModules.home-manager
                {
                  home-manager.useGlobalPkgs = true;
                  home-manager.useUserPackages = true;
                  home-manager.backupFileExtension = "backup";
                  home-manager.extraSpecialArgs = { inherit inputs dotfilesDir; };
                  home-manager.sharedModules = homeBase;
                }
                sops-nix.nixosModules.sops
                inputs.disko.nixosModules.disko
                inputs.himmelblau.nixosModules.himmelblau
                hostModule
              ];
            };
        in
        {
          stargazer = mkStargazer ./hosts/stargazer;
          # README section 8. Same machine, own hostname, no console login.
          stargazer-drill = mkStargazer ./hosts/stargazer/drill.nix;
        };

      formatter = forAllSystems (system: (mkPkgs system).nixfmt);

      devShells = forAllSystems (system: {
        default = import ./shell.nix { pkgs = mkPkgs system; };
      });
    };
}
