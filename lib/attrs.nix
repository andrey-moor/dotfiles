# Attribute set manipulation utilities
# Provides functions for advanced attribute set operations beyond nixpkgs.lib
{ lib }:

with builtins;
with lib;
rec {
  # Convert attrs to list of {name, value} pairs
  # Example: attrsToList { a = 1; b = 2; } => [ { name = "a"; value = 1; } { name = "b"; value = 2; } ]
  attrsToList = attrs:
    mapAttrsToList (name: value: { inherit name value; }) attrs;

  # Map and filter attributes in a single pass for better performance
  # mapFilterAttrs: uses mapAttrs (returns same attr names)
  # mapFilterAttrs': uses mapAttrs' (can change attr names)
  # Example: mapFilterAttrs (n: v: v * 2) (n: v: v > 1) { a = 1; b = 2; c = 3; }
  #          => { b = 4; c = 6; }
  mapFilterAttrs = f: pred: attrs: filterAttrs pred (mapAttrs f attrs);
  mapFilterAttrs' = f: pred: attrs: filterAttrs pred (mapAttrs' f attrs);

  # Deep merge multiple attribute sets with intelligent handling of different types
  # - Single values: takes the last one
  # - Lists: concatenates all lists
  # - Attribute sets: recursively merges
  # Example: mergeAttrs' [
  #   { a = { b = 1; c = 2; }; d = [1]; }
  #   { a = { b = 3; e = 4; }; d = [2]; }
  # ] => { a = { b = 3; c = 2; e = 4; }; d = [1 2]; }
  mergeAttrs' = attrList:
    let f = attrPath:
          zipAttrsWith (n: values:
            if (tail values) == []
            then head values
            else if all isList values
            then concatLists values
            else if all isAttrs values
            then f (attrPath ++ [n]) values
            else last values);
    in f [] attrList;

  # Check if any attribute matches the given predicate
  # Predicate receives (name, value) as arguments
  # Example: anyAttrs (n: v: v > 10) { a = 5; b = 15; } => true
  anyAttrs = pred: attrs:
    any (attr: pred attr.name attr.value) (attrsToList attrs);

  # Count how many attributes match the given predicate
  # Example: countAttrs (n: v: v > 10) { a = 5; b = 15; c = 20; } => 2
  countAttrs = pred: attrs:
    count (attr: pred attr.name attr.value) (attrsToList attrs);
}
