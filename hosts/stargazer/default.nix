# Stargazer -- Linux workstation (standalone home-manager)
# Parallels VM on Apple Silicon with LUKS encryption
#
# Feature modules are listed in flake.nix: home/{core,dev,linux} bundles plus
# python, linux/edge-rosetta (aarch64 Edge) and linux/containers.

{
  config,
  pkgs,
  inputs,
  dotfilesDir,
  ...
}:

{
  # Home-manager state version
  home.stateVersion = "24.05";
  home.enableNixpkgsReleaseCheck = false; # Using pkgs.main for some packages

  # nixGL for GPU acceleration with Nix apps on non-NixOS
  # Required for ghostty and other OpenGL apps to work with virtio_gpu
  targets.genericLinux.nixGL = {
    packages = inputs.nixgl.packages;
    defaultWrapper = "mesa"; # virtio_gpu in Parallels
  };

  # Additional packages
  home.packages = [
    (pkgs.azure-cli.withExtensions [
      pkgs.azure-cli-extensions.bastion
      (pkgs.azure-cli-extensions.ssh.overridePythonAttrs (old: {
        # nixpkgs has oras 0.2.x but extension pins 0.1.30 — works fine with newer
        # https://github.com/NixOS/nixpkgs/issues/495901
        pythonRelaxDeps = [ "oras" ];
        nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ [
          pkgs.python3Packages.pythonRelaxDepsHook
        ];
      }))
    ])
    pkgs.dnsutils
    # tailscale: installed via pacman (needs root systemd service)
    (config.lib.nixGL.wrap pkgs.mesa-demos) # provides glxinfo, glxgears, etc.
  ];

  sops = {
    age.keyFile = "${config.home.homeDirectory}/.config/sops/age/keys.txt";
    defaultSopsFile = ../../secrets/wayvnc.yaml;
    secrets."wayvnc-stargazer" = { };
  };

  # Settings for the parameterized modules
  modules.linux = {
    intune.debug = true; # Enable verbose logging for debugging

    wayvnc.passwordFile = config.sops.secrets."wayvnc-stargazer".path;
    wayvnc.monitor = "Virtual-1";
    wayvnc.gpu = false;
    wayvnc.renderCursor = true;

    containers.containers.litellm = {
      image = "ghcr.io/berriai/litellm:main-latest";
      ports = [ "4000:4000" ];
      pull = true;
      volumes = [
        "${dotfilesDir}/config/litellm/config.yaml:/app/config.yaml:ro"
        "${config.home.homeDirectory}/.local/share/litellm:/root/.config/litellm" # Persist auth tokens
      ];
      cmd = [
        "--config"
        "/app/config.yaml"
        "--num_workers"
        "4"
      ];
    };
  };
}
