# modules/nixos/orbstack.nix -- OrbStack VM integration
#
# Handles OrbStack-specific configuration for NixOS VMs running in OrbStack.
# OrbStack manages these files automatically which we import here:
# - /etc/nixos/orbstack.nix: OrbStack-specific settings (shell, systemd, ssh)
# - /etc/nixos/incus.nix: Container-specific settings (hostname)
#
# We also import the LXC container module from nixpkgs for boot/filesystem.
#
# IMPORTANT: Requires --impure flag for nixos-rebuild to access /etc/nixos paths.

{ lib, config, pkgs, modulesPath, ... }:

with lib;
let
  cfg = config.modules.nixos.orbstack;
  orbstackConfig = /etc/nixos/orbstack.nix;
  incusConfig = /etc/nixos/incus.nix;
in {
  options.modules.nixos.orbstack = {
    enable = mkEnableOption "OrbStack VM integration";
  };

  # Import OrbStack configs if files exist (checked at eval time, before options)
  # Requires --impure flag for builtins.pathExists to access /etc/nixos
  imports =
    # LXC container module provides boot and filesystem configuration
    [ "${modulesPath}/virtualisation/lxc-container.nix" ]
    # OrbStack-managed configs (only if they exist)
    ++ optional (builtins.pathExists orbstackConfig) orbstackConfig
    ++ optional (builtins.pathExists incusConfig) incusConfig;

  config = mkIf cfg.enable {
    # Rosetta x86_64 emulation support
    # Allows running x86_64-linux containers and binaries on aarch64-linux
    nix.settings.extra-platforms = [ "x86_64-linux" ];

    # Network configuration (from OrbStack's configuration.nix)
    # Disable dhcpcd in favor of systemd-networkd
    networking = {
      dhcpcd.enable = false;
      useDHCP = false;
      useHostResolvConf = false;
    };

    # systemd-networkd for eth0 (OrbStack's virtual network interface)
    systemd.network = {
      enable = true;
      networks."50-eth0" = {
        matchConfig.Name = "eth0";
        networkConfig = {
          DHCP = "ipv4";
          IPv6AcceptRA = true;
        };
        linkConfig.RequiredForOnline = "routable";
      };
    };
  };
}
