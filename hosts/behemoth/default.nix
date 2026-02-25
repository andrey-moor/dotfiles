# Behemoth -- macOS workstation (nix-darwin + home-manager)

{ lib, ... }:

with lib;
{
  system = "aarch64-darwin";

  config = { config, pkgs, ... }: {
    # Disable nix-darwin's Nix management (Determinate Nix handles this)
    nix.enable = false;

    # Remote Builder: Stargazer OrbStack VM
    # Since Determinate Nix manages nix.conf, add this manually:
    #
    #   sudo tee -a /etc/nix/nix.conf <<EOF
    #   builders = ssh://andreym@stargazer@orb aarch64-linux /Users/andreym/.ssh/id_ed25519 4 2 nixos-test,big-parallel
    #   builders-use-substitutes = true
    #   EOF
    #
    # Or use: just stargazer-builder-setup

    networking.hostName = "behemoth";
    networking.computerName = "Behemoth";

    # Ollama local LLM server
    launchd.user.agents.ollama = {
      command = "${pkgs.main.ollama}/bin/ollama serve";
      serviceConfig = {
        KeepAlive = true;
        RunAtLoad = true;
        StandardOutPath = "/tmp/ollama.log";
        StandardErrorPath = "/tmp/ollama.log";
      };
    };

    # LAN Mouse -- keyboard/mouse sharing with Linux machines
    # Requires: Accessibility permission (System Settings > Privacy & Security > Accessibility)
    # Little Snitch: allow UDP 4242
    launchd.user.agents.lan-mouse = {
      command = "${pkgs.lan-mouse-app}/bin/lan-mouse daemon";
      serviceConfig = {
        KeepAlive = true;
        RunAtLoad = true;
        StandardOutPath = "/tmp/lan-mouse.log";
        StandardErrorPath = "/tmp/lan-mouse.log";
      };
    };

    # User configuration
    user.name = "andreym";

    # Dotfiles location
    modules.dotfilesDir = "/Users/andreym/Documents/dotfiles";

    # Darwin system-level modules
    modules.darwin.containers = {
      enable = true;
      runtime = "orbstack";
      containers.litellm = {
        image = "ghcr.io/berriai/litellm:main-latest";
        ports = [ "4000:4000" ];
        pull = true;
        volumes = [
          "${config.modules.dotfilesDir}/config/litellm/config.yaml:/app/config.yaml:ro"
          "${config.user.dataDir}/litellm:/root/.config/litellm"  # Persist auth tokens
        ];
        cmd = [ "--config" "/app/config.yaml" "--num_workers" "4" ];
      };

      # RTMP/WebRTC streaming server for screen sharing
      # OBS: rtmp://localhost:1935 with stream key (e.g., "stream")
      # View: http://localhost:8889/<key> (WebRTC, <1s latency)
      # Note: OBS must use x264 with bframes=0 or tune=zerolatency for WebRTC
      containers.mediamtx = {
        image = "bluenviron/mediamtx:latest";
        ports = [
          "1935:1935"      # RTMP input
          "8889:8889"      # WebRTC player
          "8189:8189/udp"  # WebRTC ICE/UDP
          "8888:8888"      # HLS (fallback)
          "8554:8554"      # RTSP
        ];
        environment.MTX_WEBRTCADDITIONALHOSTS = "10.0.0.239,10.0.0.157";
        autoStart = true;
      };
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
        "claude"
        "lm-studio"
        # System
        "karabiner-elements"
        "parallels"
        "little-snitch"
        "tailscale"
        # Design
        "figma"
        "monodraw"
        # Media
        "obs"
        "imaging-edge"
        # Utilities
        "balenaetcher"
        "tigervnc-viewer"
      ];
      brews = [
        # CLI tools better via Homebrew
        "azure-cli"
        "openssh"  # FIDO2/Yubikey SSH support (macOS default lacks it)
      ];
      masApps = {
        "Screens 5" = 1663047912;
      };
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
        goose-cli       # AI coding agent
        main.ollama     # Local LLM inference
        (ghidra.withExtensions (exts: [ ghidra-extensions.ghydramcp ]))  # RE toolkit with MCP bridge
        yubikey-manager # ykman CLI for Yubikey management
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
          atuin.enable = true;
          starship.enable = true;
          tmux.enable = true;
          bat.enable = true;
          lazygit.enable = true;
          ghostty.enable = true;
          gpg.enable = true;
          chezmoi.enable = true;
          openvpn.enable = true;
          lan-mouse = {
            enable = true;
            gpu = false;
            authorizedFingerprints = {
              "AD:C3:46:20:70:BB:79:2F:57:76:00:BA:0D:62:8E:D1:19:47:C4:58:76:0F:1F:D3:60:8D:2B:97:F5:1B:A5:83" = "rocinante";
            };
            clients = [{
              position = "left";
              ips = [ "10.0.0.6" ];
              activateOnStartup = true;
            }];
          };
        };

        dev = {
          nix.enable = true;
          neovim.enable = true;
          vscode.enable = true;
          jj.enable = true;
          go.enable = true;
          rust.enable = true;
          kubernetes.enable = true;
          terraform.enable = true;
          claude.enable = true;
          bazel.enable = true;
        };
      };
    };
  };
}
