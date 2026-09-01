# Stargazer -- aarch64 NixOS VM on Parallels (nix-darwin's behemoth hosts it)
#
# Successor to the hand-installed Omarchy/Arch VM: declarative from the ISO up,
# LUKS+btrfs via disko, integrated home-manager reusing the home/ bundles,
# minimal Hyprland on virtio-gpu, Entra join + Intune enrollment via himmelblau.
#
# Deliberately absent: Rosetta, nixGL, home/linux/intune.nix (the Arch-era
# portal/broker stack, which stays for rocinante) and Ghostty as the terminal
# (Parallels caps Linux guests at OpenGL 4.0; ghostty >= 1.2 needs 4.3).

{
  config,
  ...
}:

{
  imports = [
    ./hardware.nix
    ./disko.nix
    ../../modules/nixos/base.nix
    ../../modules/nixos/parallels-guest.nix
    ../../modules/nixos/desktop-hyprland.nix
    ../../modules/nixos/himmelblau.nix
    ../../modules/nixos/intune-identity.nix
    ../../modules/nixos/secureboot.nix
  ];

  networking.hostName = "stargazer";

  # Tenant facts (domain, tenant id, UPN) come from the committed, age-encrypted
  # secrets/stargazer-tenant.yaml and are rendered at activation -- so this is
  # unconditional and works identically from `github:andrey-moor/dotfiles#stargazer`.
  modules.nixos.himmelblau.enable = true;

  sops = {
    # First host done the §10 way: the recipient is derived from this machine's
    # SSH host key (ssh-to-age), so no master key is ever copied in.
    age.sshKeyPaths = [ "/etc/ssh/ssh_host_ed25519_key" ];
    # Per-secret `sopsFile` overrides this; modules/nixos/himmelblau.nix points
    # its three tenant secrets at secrets/stargazer-tenant.yaml.
    defaultSopsFile = ../../secrets/wayvnc.yaml;
    secrets."wayvnc-stargazer".owner = "andreym";
  };

  home-manager.users.andreym = {
    # linux/{firefox,wayvnc}.nix rather than the home/linux.nix bundle: the
    # bundle also carries linux/intune.nix, whose x86_64 .deb/Rosetta stack has
    # no place on a NixOS host (himmelblau replaces it here).
    imports = [
      ../../home/core.nix
      ../../home/dev.nix
      ../../home/dev/python.nix
      ../../home/linux/firefox.nix
      ../../home/linux/wayvnc.nix
    ];

    home.stateVersion = "24.05";
    home.enableNixpkgsReleaseCheck = false; # Using pkgs.main for some packages

    modules.linux.wayvnc = {
      passwordFile = config.sops.secrets."wayvnc-stargazer".path;
      monitor = "Virtual-1";
      gpu = false; # virtio-gpu has no DMA-BUF/H.264 path here
      renderCursor = true;
      # Left on the module default 0.0.0.0 on purpose: the tailnet binding is
      # enforced by networking.firewall (default deny, trustedInterfaces =
      # tailscale0) in modules/nixos/base.nix, and this host's 100.x address is
      # not known until it first joins the tailnet (Task 4). Pin it here once
      # it is.
    };
  };

  # Matches the pinned nixpkgs release. Never derived from the spoofed
  # /etc/os-release -- system.nixos.* stays honest (see intune-identity.nix).
  system.stateVersion = "26.11";
}
