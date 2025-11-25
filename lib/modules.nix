# Module discovery and loading utilities
# Provides functions to automatically discover and load Nix modules from filesystem
{ lib, attrs }:

let
  inherit (builtins) readDir pathExists concatLists;
  inherit (lib) filterAttrs hasPrefix hasSuffix nameValuePair removeSuffix;
in rec {
  # Scan directory for .nix files and directories with default.nix
  # Automatically filters out:
  #   - Files/dirs starting with underscore (considered private)
  #   - default.nix and flake.nix files
  # Returns an attribute set with module names as keys
  # Example: mapModules ./modules (path: import path)
  #   ./modules/
  #     foo.nix         => { foo = <imported foo.nix>; }
  #     bar/default.nix => { bar = <imported bar/default.nix>; }
  #     _hidden.nix     => (ignored)
  mapModules = dir: fn:
    attrs.mapFilterAttrs'
      (n: v:
        let path = "${toString dir}/${n}"; in
        if v == "directory" && pathExists "${path}/default.nix"
        then nameValuePair n (fn path)
        else if v == "regular" &&
                n != "default.nix" &&
                n != "flake.nix" &&
                hasSuffix ".nix" n
        then nameValuePair (removeSuffix ".nix" n) (fn path)
        else nameValuePair "" null)
      (n: v: v != null && !(hasPrefix "_" n))
      (readDir dir);

  # Same as mapModules but returns a list of values instead of an attribute set
  # Useful when you don't need named access to modules
  # Example: mapModules' ./modules import => [ <module1> <module2> ... ]
  mapModules' = dir: fn:
    builtins.attrValues (mapModules dir fn);

  # Recursively discover and map all modules in nested directories
  # Directories become nested attribute sets
  # Example: mapModulesRec ./modules import
  #   ./modules/
  #     networking/
  #       firewall.nix  => { networking = { firewall = <imported>; }; }
  #       vpn.nix       => { networking = { vpn = <imported>; }; }
  #     services.nix    => { services = <imported>; }
  mapModulesRec = dir: fn:
    attrs.mapFilterAttrs'
      (n: v:
        let path = "${toString dir}/${n}"; in
        if v == "directory"
        then nameValuePair n (mapModulesRec path fn)
        else if v == "regular" &&
                n != "default.nix" &&
                n != "flake.nix" &&
                hasSuffix ".nix" n
        then nameValuePair (removeSuffix ".nix" n) (fn path)
        else nameValuePair "" null)
      (n: v: v != null && !(hasPrefix "_" n))
      (readDir dir);

  # Same as mapModulesRec but returns a flat list of values
  # Useful for importing all modules recursively without nested structure
  # Example: mapModulesRec' ./modules import => [ <module1> <module2> ... ]
  # Note: Directories with default.nix are treated as modules (default.nix is imported)
  #       Regular .nix files (except default.nix and flake.nix) are also imported
  mapModulesRec' = dir: fn:
    let
      recurse = path:
        let entries = readDir path; in
        builtins.concatLists (
          builtins.attrValues (
            attrs.mapFilterAttrs'
              (n: v:
                let fullPath = "${toString path}/${n}"; in
                if v == "directory" && !(hasPrefix "_" n)
                then
                  # If directory has default.nix, import it; then recurse into subdirs
                  let dirDefault = "${fullPath}/default.nix"; in
                  nameValuePair n (
                    (if pathExists dirDefault then [ (fn fullPath) ] else [])
                    ++ recurse fullPath
                  )
                else if v == "regular" &&
                        n != "default.nix" &&
                        n != "flake.nix" &&
                        hasSuffix ".nix" n &&
                        !(hasPrefix "_" n)
                then nameValuePair n [ (fn fullPath) ]
                else nameValuePair "" [])
              (n: v: v != [])
              entries
          )
        );
    in recurse dir;

  # Convenience function for loading NixOS host configurations
  # Each .nix file or directory with default.nix becomes a host
  # Example: mapHosts ./hosts => { desktop = <config>; server = <config>; }
  mapHosts = dir:
    mapModules dir (path: import path);
}
