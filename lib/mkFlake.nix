# Flake builder utility
# Supports Darwin (nix-darwin + home-manager) and standalone home-manager configurations
#
# Example usage in flake.nix:
#   outputs = inputs:
#     lib.mkFlake inputs {
#       hosts = {
#         macbook = { system = "aarch64-darwin"; ... };  # -> darwinConfigurations
#         linux = { system = "x86_64-linux"; ... };      # -> homeConfigurations
#       };
#       modules = [ ./modules ];  # Applied to all hosts
#     };
{ lib, modules ? null }@libArgs:

inputs: args @ {
  hosts ? {}        # Host configurations: name -> config
  , systems ? [ "x86_64-linux" "aarch64-linux" "aarch64-darwin" "x86_64-darwin" ]
  , modules ? []    # Modules applied to all hosts (system-level)
  , overlays ? []   # Overlays applied to nixpkgs
  , hostDefaults ? {}  # Default config merged into all hosts
  , packages ? {}   # Per-system packages
  , devShells ? {}  # Per-system development shells
  , apps ? {}       # Per-system apps
  , checks ? {}     # Per-system checks
  , ...             # Additional outputs passed through
}:
let
  inherit (inputs) nixpkgs;
  inherit (lib) mkDefault genAttrs mapAttrs filterAttrs hasSuffix;

  # Our lib's module functions (from first arg, not shadowed by 'modules' arg)
  moduleLib = libArgs.modules;

  # Extract any additional outputs not handled by mkFlake
  extraOutputs = removeAttrs args [
    "hosts" "systems" "modules" "overlays" "hostDefaults"
    "packages" "devShells" "apps" "checks"
  ];

  # Detect host type from system string
  hostType = system:
    if hasSuffix "darwin" system then "darwin"
    else "home";  # Linux = standalone home-manager

  # Create nixpkgs instance for a given system
  mkPkgs = system: import nixpkgs {
    inherit system;
    config.allowUnfree = true;
    overlays = overlays ++ [
      # Make unstable packages available as pkgs.unstable
      (final: prev: if inputs ? nixpkgs-unstable then {
        unstable = import inputs.nixpkgs-unstable {
          inherit system;
          config.allowUnfree = true;
        };
      } else {})
      # Make main branch packages available as pkgs.main
      (final: prev: if inputs ? nixpkgs-main then {
        main = import inputs.nixpkgs-main {
          inherit system;
          config.allowUnfree = true;
        };
      } else {})
    ];
  };

  # Normalize host configuration
  normalizeHost = name: host:
    let
      hostConfig = if builtins.isFunction host
                   then host { inherit lib; }
                   else host;
    in lib.recursiveUpdate hostDefaults hostConfig;

  # Path to home-manager modules
  homeModulesPath = ../modules/home;

  # Build a Darwin host configuration (nix-darwin + home-manager)
  mkDarwinHost = name: host:
    let
      mergedHost = normalizeHost name host;
      system = mergedHost.system or "aarch64-darwin";
      pkgs = mkPkgs system;
      # Home-manager modules to be loaded for each user
      # Include the root default.nix + all recursive modules
      homeModules = [ (import homeModulesPath) ] ++ moduleLib.mapModulesRec' homeModulesPath import;
    in
    inputs.darwin.lib.darwinSystem {
      inherit system;

      specialArgs = {
        inherit inputs;
        inherit (self) lib;
      } // (mergedHost.specialArgs or {});

      modules = [
        # Base Darwin configuration
        {
          nixpkgs.pkgs = mkDefault pkgs;
          networking.hostName = mkDefault name;
        }
        # Home-manager as Darwin module
        inputs.home-manager.darwinModules.home-manager
        {
          home-manager.useGlobalPkgs = true;
          home-manager.useUserPackages = true;
          home-manager.extraSpecialArgs = {
            inherit inputs;
            # Note: Don't override lib here - home-manager needs its own lib.hm
          };
          # Load home-manager modules for all users
          home-manager.sharedModules = homeModules;
        }
        # nix-homebrew if available
      ] ++ (if inputs ? nix-homebrew then [ inputs.nix-homebrew.darwinModules.nix-homebrew ] else [])
      ++ modules
      ++ (mergedHost.modules or [])
      ++ (if mergedHost ? config then [ mergedHost.config ] else []);
    };

  # Build a standalone home-manager configuration (for non-NixOS Linux)
  mkHomeConfiguration = name: host:
    let
      mergedHost = normalizeHost name host;
      system = mergedHost.system or "x86_64-linux";
      pkgs = mkPkgs system;
      username = mergedHost.username or name;
      homeDirectory = mergedHost.homeDirectory or "/home/${username}";
      # Home-manager modules
      homeModules = moduleLib.mapModulesRec' homeModulesPath import;
    in
    inputs.home-manager.lib.homeManagerConfiguration {
      inherit pkgs;

      extraSpecialArgs = {
        inherit inputs;
        # Note: Don't override lib - home-manager needs its own lib.hm
      } // (mergedHost.specialArgs or {});

      modules = [
        # Base home-manager configuration
        {
          home.username = username;
          home.homeDirectory = homeDirectory;
        }
      ]
      # Home-manager modules from modules/home/
      ++ homeModules
      # Host-specific home-manager modules
      ++ (mergedHost.homeModules or [])
      ++ (if mergedHost ? config then [ mergedHost.config ] else []);
    };

  # Split hosts by type
  darwinHosts = filterAttrs (n: h: hostType ((normalizeHost n h).system or "x86_64-linux") == "darwin") hosts;
  homeHosts = filterAttrs (n: h: hostType ((normalizeHost n h).system or "x86_64-linux") == "home") hosts;

  # Build per-system outputs (packages, devShells, etc.)
  perSystemOutputs = genAttrs systems (system:
    let
      pkgs = mkPkgs system;
      callWithPkgs = value:
        if builtins.isFunction value then value pkgs else value;
    in {
      packages = callWithPkgs (packages.${system} or {});
      devShells = callWithPkgs (devShells.${system} or {});
      apps = callWithPkgs (apps.${system} or {});
      checks = callWithPkgs (checks.${system} or {});
    }
  );

  # Build final flake outputs
  self = extraOutputs // {
    darwinConfigurations = mapAttrs mkDarwinHost darwinHosts;
    homeConfigurations = mapAttrs mkHomeConfiguration homeHosts;
    lib = import ./. { inherit nixpkgs; };
  } // genAttrs [ "packages" "devShells" "apps" "checks" ] (
    attr: genAttrs systems (system: perSystemOutputs.${system}.${attr})
  );

in self
