# Rocinante -- x86_64 Linux workstation (Omarchy, standalone home-manager)
#
# Feature modules: the home/{core,dev,linux} bundles plus copilot, hunk,
# lmstudio, python, linux/edge (x86_64 Edge), linux/wayvnc-resolution and
# linux/vhclient, imported below.

{
  config,
  pkgs,
  inputs,
  ...
}:

{
  imports = [
    ../../home/core.nix
    ../../home/dev.nix
    ../../home/linux.nix
    ../../home/dev/copilot.nix
    ../../home/dev/hunk.nix
    ../../home/dev/lmstudio.nix
    ../../home/dev/python.nix
    ../../home/linux/edge.nix
    ../../home/linux/wayvnc-resolution.nix
    ../../home/linux/vhclient.nix
  ];

  # Home-manager state version
  home.stateVersion = "24.05";
  home.enableNixpkgsReleaseCheck = false; # Using pkgs.main for some packages

  # nixGL for GPU acceleration with Nix apps on non-NixOS
  targets.genericLinux.nixGL = {
    packages = inputs.nixgl.packages;
    defaultWrapper = "mesa"; # AMD GPU
  };

  # Additional packages
  home.packages = [
    (pkgs.azure-cli.withExtensions [
      pkgs.azure-cli-extensions.bastion
      pkgs.azure-cli-extensions.ssh
    ])
    pkgs._1password-cli # op CLI for secret management
    pkgs.uv # Python package runner (uvx)
    pkgs.nodejs # Node.js runtime (npx)
    pkgs.dnsutils
    pkgs.netcat-openbsd
    pkgs.grpcurl
    pkgs.shellcheck
    # tailscale: installed via pacman (needs root systemd service)
    (config.lib.nixGL.wrap pkgs.mesa-demos) # provides glxinfo, glxgears, etc.
  ];

  sops = {
    age.keyFile = "${config.home.homeDirectory}/.config/sops/age/keys.txt";
    defaultSopsFile = ../../secrets/wayvnc.yaml;
    secrets."wayvnc-rocinante" = { };
  };

  # Settings for the parameterized modules
  modules.linux = {
    intune.debug = true; # Enable verbose logging for debugging
    wayvnc.passwordFile = config.sops.secrets."wayvnc-rocinante".path;
    wayvnc.address = "0.0.0.0"; # every interface for now, the owner will narrow it
  };
}
