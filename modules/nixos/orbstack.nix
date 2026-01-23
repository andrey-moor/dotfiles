# modules/nixos/orbstack.nix -- OrbStack VM integration
#
# Handles OrbStack-specific configuration for NixOS VMs running in OrbStack.
# OrbStack manages /etc/nixos/orbstack.nix automatically - we import it here.
#
# The OrbStack-managed file provides:
# - Boot configuration (systemd-boot)
# - Filesystem mounts (including macOS shared folders at /Users)
# - Rosetta x86_64 emulation support
# - Network configuration

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.nixos.orbstack;
  orbstackConfig = /etc/nixos/orbstack.nix;
in {
  options.modules.nixos.orbstack = {
    enable = mkEnableOption "OrbStack VM integration";
  };

  # Import OrbStack config if file exists (checked at eval time, before options)
  # This provides boot, filesystem, networking, and Rosetta configuration
  imports = optional (builtins.pathExists orbstackConfig) orbstackConfig;

  config = mkIf cfg.enable {
    # Rosetta x86_64 emulation support
    # Allows running x86_64-linux containers and binaries on aarch64-linux
    nix.settings.extra-platforms = [ "x86_64-linux" ];
  };
}
