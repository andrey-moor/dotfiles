# Behemoth -- macOS workstation (nix-darwin + home-manager)

{ lib, ... }:

with lib;
{
  system = "aarch64-darwin";

  config = { config, pkgs, ... }: {
    # Disable nix-darwin's Nix management (Determinate Nix handles this)
    nix.enable = false;

    networking.hostName = "behemoth";
    networking.computerName = "Behemoth";

    # User configuration
    user.name = "andreym";

    # Darwin system-level modules
    modules.darwin.containers = {
      enable = true;
      runtime = "orbstack";
    };

    modules.darwin.homebrew = {
      enable = true;
      casks = [
        # Development
        "ghostty"
        "cursor"
        # Productivity
        "1password"
        "raycast"
        "craft"
        "fantastical"
        "granola"
        "ia-presenter"
        # Communication
        "zoom"
        # AI/ML
        "lm-studio"
        # System
        "parallels"
        "little-snitch"
        # Design
        "monodraw"
      ];
      brews = [
        # CLI tools better via Homebrew
        "azure-cli"
        "openssh"  # FIDO2/Yubikey SSH support (macOS default lacks it)
      ];
    };

    # Home-manager user configuration
    home-manager.users.andreym = { lib, pkgs, ... }: {
      home.stateVersion = "24.05";
      home.enableNixpkgsReleaseCheck = false;  # Using pkgs.main for some packages
      home.username = lib.mkForce "andreym";
      home.homeDirectory = lib.mkForce "/Users/andreym";

      # Common packages (not tied to specific modules)
      home.packages = with pkgs; [
        _1password-cli  # op CLI for secret management
        uv              # Python package runner (uvx)
        nodejs          # Node.js runtime (npx)
      ];

      # Home-manager modules (shell, dev, profiles)
      modules = {
        # Override default ~/.dotfiles path for this host
        dotfilesDir = "/Users/andreym/Documents/dotfiles";

        profiles.user = "andreym";

        shell = {
          default = "nushell";
          nushell.enable = true;
          git.enable = true;
          ssh.enable = true;
          direnv.enable = true;
          starship.enable = true;
          tmux.enable = true;
          bat.enable = true;
          lazygit.enable = true;
          ghostty.enable = true;
          gpg.enable = true;
          chezmoi.enable = true;
          openvpn.enable = true;
        };

        dev = {
          nix.enable = true;
          neovim.enable = true;
          jj.enable = true;
          go.enable = true;
          rust.enable = true;
          kubernetes.enable = true;
          claude.enable = true;
        };
      };
    };
  };
}
