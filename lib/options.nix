# NixOS option creation helpers
# Provides shorthand functions for common option patterns to reduce boilerplate
{ lib }:

let
  inherit (lib) mkOption types;
in
rec {
  # Create an option with just type and default value
  # Example: mkOpt types.str "hello" 
  #   => mkOption { type = types.str; default = "hello"; }
  mkOpt = type: default:
    mkOption { inherit type default; };

  # Create an option with type, default, and description
  # Example: mkOpt' types.int 8080 "Port number for the service"
  mkOpt' = type: default: description:
    mkOption { inherit type default description; };

  # Boolean option with specified default
  # Automatically adds example = true for documentation
  # Example: mkBoolOpt false  # Creates a boolean option defaulting to false
  mkBoolOpt = default: mkOption {
    inherit default;
    type = types.bool;
    example = true;
  };

  # Create an "enable" option (common NixOS pattern)
  # Always defaults to false, requires description
  # Example: mkEnableOpt "Enable the foo service"
  #   => mkOption { 
  #        description = "Enable the foo service";
  #        type = types.bool;
  #        default = false;
  #        example = true;
  #      }
  mkEnableOpt = description:
    mkOption {
      inherit description;
      type = types.bool;
      default = false;
      example = true;
    };
}
