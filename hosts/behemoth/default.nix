# Behemoth -- macOS workstation (nix-darwin + home-manager)
#
# Home-manager feature modules: the home/{core,dev,darwin} bundles plus copilot,
# herdr and hunk, imported below in the home-manager user block.
#
# README.md in this directory is the new-Mac runbook. It lists everything this
# file cannot declare: manual apps, sign-ins and permission prompts.

{
  config,
  pkgs,
  dotfilesDir,
  ...
}:

let
  # Named once, in modules/darwin/default.nix.
  user = config.system.primaryUser;
  inherit (config.users.users.${user}) home;
in
{
  imports = [
    ../../modules/darwin/default.nix
    ../../modules/darwin/containers.nix
    ../../modules/darwin/homebrew.nix
    ../../modules/darwin/yubikey-share.nix
  ];

  # Determinate Nix owns /etc/nix/nix.conf. This module turns nix-darwin's
  # Nix management off for us and manages the custom settings file and
  # determinate-nixd's config.json instead.
  determinateNix = {
    enable = true;
    # Determinate's native Linux builder (Virtualization framework). It builds
    # aarch64-linux and x86_64-linux derivations on this Mac. Access is per
    # FlakeHub account and was granted on 2026-10-07. Keep cpuCount at 1, the
    # vendor measured more CPUs as slower. The nixpkgs VM builder is not used:
    # the module allows only one of the two.
    determinateNixd.builder = {
      state = "enabled";
      memoryBytes = 16 * 1024 * 1024 * 1024;
    };
  };

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

  # Darwin system-level modules
  modules.darwin.containers = {
    runtime = "orbstack";
    containers.litellm = {
      image = "ghcr.io/berriai/litellm:main-latest";
      ports = [ "4000:4000" ];
      pull = true;
      volumes = [
        "${dotfilesDir}/config/litellm/config.yaml:/app/config.yaml:ro"
        "${home}/.local/share/litellm:/root/.config/litellm" # Persist auth tokens
      ];
      cmd = [
        "--config"
        "/app/config.yaml"
        "--num_workers"
        "4"
      ];
    };

    # RTMP/WebRTC streaming server for screen sharing
    # OBS: rtmp://localhost:1935 with stream key (e.g., "stream")
    # View: http://localhost:8889/<key> (WebRTC, <1s latency)
    # Note: OBS must use x264 with bframes=0 or tune=zerolatency for WebRTC
    containers.mediamtx = {
      image = "bluenviron/mediamtx:latest";
      ports = [
        "1935:1935" # RTMP input
        "8889:8889" # WebRTC player
        "8189:8189/udp" # WebRTC ICE/UDP
        "8888:8888" # HLS (fallback)
        "8554:8554" # RTSP
      ];
      environment.MTX_WEBRTCADDITIONALHOSTS = "10.0.0.239,10.0.0.157";
      autoStart = true;
    };
  };

  modules.darwin.homebrew = {
    casks = [
      # Development
      "ghostty"
      "cursor"
      # Browsers
      "google-chrome"
      "firefox"
      # Productivity
      "1password"
      "raycast"
      "craft"
      "fantastical"
      "granola"
      "ia-presenter"
      "libreoffice" # word-docs skill previews
      "obsidian"
      # Communication
      "zoom"
      # AI/ML
      "chatgpt" # includes the Codex desktop app since 2026-07
      "claude"
      "lm-studio"
      # System
      "betterdisplay"
      "crossover"
      "karabiner-elements"
      "monitorcontrol"
      "parallels"
      "little-snitch"
      "mullvad-vpn" # its daemon breaks the Linux builder's DNS, see README.md
      "tailscale-app"
      # Design
      "figma"
      "monodraw"
      # Media
      "obs"
      "imaging-edge"
      # Cloud CLIs. Homebrew moved azure-cli and vercel-cli from formulae to
      # casks in 2026-10. The vercel cask replaces the vercel-cli formula.
      "azure-cli"
      "gcloud-cli" # renamed upstream from google-cloud-sdk
      "vercel"
      # Utilities
      "balenaetcher"
      "tigervnc" # renamed upstream from tigervnc-viewer
    ];
    brews = [
      # CLI tools better via Homebrew
      "agent-browser"
      "openssh" # FIDO2/Yubikey SSH support (macOS default lacks it)
      "firebase-cli"
      "supabase"
    ];
    # Mac App Store apps are installed by hand, see README.md.
    # nix-homebrew's brew-bundle mas integration is flaky on Apple Silicon.
    masApps = { };
  };

  # Home-manager user configuration
  home-manager.users.${user} =
    {
      config,
      pkgs,
      dotfilesDir,
      ...
    }:
    {
      imports = [
        ../../home/core.nix
        ../../home/dev.nix
        ../../home/darwin.nix
        ../../home/dev/copilot.nix
        ../../home/dev/herdr.nix
        ../../home/dev/hunk.nix
      ];

      # home.stateVersion comes from home/default.nix. Username and home
      # directory come from users.users (home-manager's nix-darwin module).
      home.enableNixpkgsReleaseCheck = false; # Using pkgs.main for some packages

      # Copy Nix GUI apps into ~/Applications/Home Manager Apps so Spotlight
      # and Raycast index them. Symlinks (linkApps, the default below state
      # version 25.11) are not indexed. The terminal that runs `just switch`
      # needs App Management permission, see README.md.
      targets.darwin.copyApps.enable = true;
      targets.darwin.linkApps.enable = false;

      # Canonical fleet-wide dotfiles path (spec §4): the repo lives in
      # ~/Documents/dotfiles here; Linux hosts already have it at ~/dotfiles.
      home.file."dotfiles".source = config.lib.file.mkOutOfStoreSymlink dotfilesDir;

      # Common packages (not tied to specific modules)
      home.packages = with pkgs; [
        _1password-cli # op CLI for secret management
        uv # Python package runner (uvx)
        nodejs # Node.js runtime (npx)
        # goose-cli  # AI coding agent — BLOCKED: nixpkgs v1.23.2 broken, upstream flake broken (block/goose#8514)
        main.ollama # Local LLM inference
        qemu # VM emulation (qemu-img, qemu-system-*)
        (ghidra.withExtensions (_exts: [ ghidra-extensions.ghydramcp ])) # RE toolkit with MCP bridge
        yubikey-manager # ykman CLI for Yubikey management
        sops # this Mac holds the admin age key and is where secrets/ is edited
      ];

      # The admin age key sits where sops looks on macOS by default. Because
      # XDG_CONFIG_HOME is set here, sops would look under ~/.config instead
      # and fail to decrypt, so the path is stated.
      home.sessionVariables.SOPS_AGE_KEY_FILE = "${config.home.homeDirectory}/Library/Application Support/sops/age/keys.txt";

      # Settings for the parameterized modules
      modules.dev.claude.obsidianVault = "${config.home.homeDirectory}/Library/Mobile Documents/iCloud~md~obsidian/Documents";

      modules.shell.lan-mouse = {
        gpu = false;
        authorizedFingerprints = {
          "17:95:15:54:cc:74:7a:63:88:08:57:07:f1:0b:75:b1:a8:89:e2:f5:89:2b:4c:7a:25:88:2d:11:ae:fa:87:a3" =
            "rocinante";
        };
        clients = [
          {
            position = "left";
            ips = [ "10.0.0.6" ];
            activateOnStartup = true;
          }
        ];
      };
    };
}
