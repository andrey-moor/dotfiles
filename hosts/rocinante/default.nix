# Rocinante -- x86_64 Linux workstation (Omarchy, standalone home-manager)
#
# Feature modules: the home/{core,dev,linux} bundles plus copilot, hunk,
# lmstudio, python and linux/edge (x86_64 Edge), imported below.
#
# lan-mouse is deliberately NOT imported: the rolling-main daemon held an
# input-capture overlay that stopped Wayland from seeing keyboard/mouse here
# (2026-05-06). Re-add ../../home/shell/lan-mouse.nix here once fixed;
# behemoth's config has this host's fingerprint.

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
      (pkgs.azure-cli-extensions.ssh.overridePythonAttrs (old: {
        # nixpkgs has oras 0.2.x but extension pins 0.1.30 — works fine with newer
        pythonRelaxDeps = [ "oras" ];
        nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ [
          pkgs.python3Packages.pythonRelaxDepsHook
        ];
      }))
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
  };
}
