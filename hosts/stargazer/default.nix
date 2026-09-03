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

  # Parallels Tools (userspace-only on aarch64): dynamic resolution,

  # clipboard, shared folders. Opt-in; watch for Hyprland irritation.

  modules.nixos.parallels.guestTools = true;

  # P9 Task 6: lanzaboote-signed boot, chained behind a Microsoft-signed shim.
  # Parallels' EDK II aa64 ignores a custom PK/KEK/db (enrolling ours halted the
  # VM with Secure Boot on), so the only path to the tenant's SecureBootEnabled
  # rule is shim -> our-key-signed systemd-boot -> our-key-signed UKIs, with the
  # db cert enrolled as a MOK. Ceremony: hosts/stargazer/README.md §7.
  modules.nixos.secureboot = {
    enable = true;
    shim.enable = true;
  };
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

    # Secure Boot signing key. One key pair for every stargazer instance, so the
    # db certificate is known before a VM exists and `stargazer-vm enroll-mok`
    # can run at creation time instead of after `sbctl create-keys` inside the
    # guest. Private half here (age-encrypted); public half and sbctl's owner
    # GUID are plain files in ./secureboot, placed by tmpfiles below. Only the
    # db key exists: in shim mode nothing is ever enrolled into PK/KEK.
    secrets."sbctl-db-key" = {
      sopsFile = ../../secrets/stargazer-sbctl.yaml;
      key = "db.key";
      path = "/var/lib/sbctl/keys/db/db.key";
      mode = "0400";
    };
  };

  systemd.tmpfiles.rules = [
    "d /var/lib/sbctl 0700 root root -"
    "d /var/lib/sbctl/keys 0700 root root -"
    "d /var/lib/sbctl/keys/db 0700 root root -"
    "L+ /var/lib/sbctl/keys/db/db.pem - - - - ${./secureboot/db.pem}"
    "L+ /var/lib/sbctl/GUID - - - - ${./secureboot/GUID}"
  ];

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
      # Tailnet address (node joined 2026-09-02). The firewall (default deny,
      # trustedInterfaces = tailscale0) enforces tailnet-only reach as well.
      address = "100.114.228.95";
    };
  };

  # Matches the pinned nixpkgs release. Never derived from the spoofed
  # /etc/os-release -- system.nixos.* stays honest (see intune-identity.nix).
  system.stateVersion = "26.11";
}
