# Stargazer -- OrbStack NixOS VM for monorepo builds
#
# Converted from standalone home-manager to full NixOS to enable
# declarative Docker management via virtualisation.docker.enable.

{ lib, ... }:

with lib;
{
  # CRITICAL: Explicit type to trigger NixOS builder (not standalone home-manager)
  type = "nixos";
  system = "aarch64-linux";

  config = { config, pkgs, lib, ... }: {
    # User configuration
    user.name = "andreym";

    # OrbStack mounts macOS /Users at same path
    modules.dotfilesDir = "/Users/andreym/Documents/dotfiles";

    # OrbStack integration (imports /etc/nixos/orbstack.nix for boot, fs, networking)
    modules.nixos.orbstack.enable = true;

    # Docker - the primary reason for NixOS conversion!
    modules.nixos.docker = {
      enable = true;
      users = [ "andreym" ];
    };

    # Create user account
    users.users.andreym = {
      isNormalUser = true;
      home = "/home/andreym";
      shell = pkgs.nushell;
      extraGroups = [ "wheel" "docker" ];
    };

    # Passwordless sudo for dev VM convenience
    security.sudo.wheelNeedsPassword = false;

    # nix-ld: Enable running pre-built binaries (e.g., bazel downloaded by bazelisk)
    # This provides a compatible dynamic linker for external binaries
    programs.nix-ld = {
      enable = true;
      libraries = with pkgs; [
        # Common libraries needed by pre-built binaries
        stdenv.cc.cc.lib
        zlib
        glib
        openssl
      ];
    };

    # System packages for monorepo builds (C/C++ toolchain)
    # python3 is required because rules_pkg's build_tar uses #!/usr/bin/env python3
    # which bypasses Bazel's hermetic Python toolchain
    # coreutils provides mktemp needed by npm lifecycle hooks
    environment.systemPackages = with pkgs; [
      gcc
      binutils
      gnumake
      cmake
      pkg-config
      python310  # Required for rules_pkg pkg_tar
      coreutils  # Required for mktemp in npm lifecycle hooks
    ];

    # Create /bin/bash symlink for scripts with hardcoded shebangs (common in Bazel)
    system.activationScripts.binbash = ''
      mkdir -p /bin
      ln -sf /run/current-system/sw/bin/bash /bin/bash
    '';

    # Ensure bash profile sets up PATH correctly for SSH sessions
    # This fixes OrbStack SSH not setting user profile paths
    environment.etc."profile.d/nix-user-path.sh".text = ''
      export PATH="/etc/profiles/per-user/andreym/bin:$PATH"
    '';

    # Also set up bashrc for non-login shells (e.g., ssh -T user@host 'bash -c ...')
    programs.bash.interactiveShellInit = ''
      export PATH="/etc/profiles/per-user/andreym/bin:$PATH"
    '';

    # Set BASH_ENV so non-interactive bash also gets the PATH
    environment.variables.BASH_ENV = "/etc/profile.d/nix-user-path.sh";

    # Home-manager user configuration (follows Behemoth pattern)
    home-manager.users.andreym = { config, pkgs, lib, ... }: {
      home.stateVersion = "24.05";
      home.enableNixpkgsReleaseCheck = false;

      modules = {
        # OrbStack mounts macOS /Users at same path
        dotfilesDir = "/Users/andreym/Documents/dotfiles";

        profiles.user = "andreym";

        shell = {
          default = "nushell";
          nushell.enable = true;
          git.enable = true;
          ssh.enable = true;
          direnv.enable = true;  # Critical for monorepo .envrc
          starship.enable = true;
          tmux.enable = true;
          bat.enable = true;
          lazygit.enable = true;
          gpg.enable = true;
          chezmoi.enable = true;
        };

        dev = {
          nix.enable = true;
          neovim.enable = true;
          jj.enable = true;
          bazel.enable = true;     # PRIMARY: monorepo build system
          go.enable = true;        # For Go services
          rust.enable = true;      # For consensus/storage services
          terraform.enable = true; # For infra deployments
        };
      };

      # Additional packages for monorepo builds
      home.packages = with pkgs; [
        # Python (Bazel hermetic, but useful for scripts)
        python310
        uv

        # Node.js (Bazel hermetic, but useful for scripts)
        nodejs_20
        nodePackages.pnpm

        # Protocol Buffers
        protobuf

        # Azure authentication
        azure-cli

        # Pre-commit hooks
        pre-commit
      ];
    };
  };
}
