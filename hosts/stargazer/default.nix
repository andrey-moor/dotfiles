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
  lib,
  config,
  ...
}:

let
  # null when hosts/stargazer/local/tenant.nix is absent -- see ./tenant.nix.
  tenant = import ./tenant.nix;
in
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

  # Entra/Intune stays off until the tenant facts are available. The warning is
  # the only signal a build from `github:...#stargazer` gets, so keep it loud.
  modules.nixos.himmelblau = lib.mkIf (tenant != null) {
    enable = true;
    inherit (tenant) domain tenantId upn;
  };

  warnings = lib.optional (tenant == null) ''
    stargazer: hosts/stargazer/local/tenant.nix is absent, so himmelblau
    (Entra join + Intune enrollment) is DISABLED in this build.
    Copy hosts/stargazer/local/tenant.nix.example to
    hosts/stargazer/local/tenant.nix and rebuild with a `path:` flake
    reference -- `github:` and `git+file:` references cannot see gitignored
    files. See hosts/stargazer/tenant.nix.
  '';

  sops = {
    # First host done the §10 way: the recipient is derived from this machine's
    # SSH host key (ssh-to-age), so no master key is ever copied in.
    age.sshKeyPaths = [ "/etc/ssh/ssh_host_ed25519_key" ];
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
