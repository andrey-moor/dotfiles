# hosts/stargazer/common.nix -- everything about stargazer that does not depend
# on the hypervisor.
#
# Two hosts share this: ./default.nix (Parallels, the machine in use) and
# ../stargazer-fusion (VMware Fusion, the 2026-09 re-platform trial). Each
# adds its guest module, disk device, Secure Boot mode and hostname on top.
#
# Deliberately absent: Rosetta, nixGL, home/linux/intune.nix (the Arch-era
# portal/broker stack, which stays for rocinante) and Ghostty as the terminal
# (a per-host choice: needs OpenGL 4.3, which Parallels does not give Linux).

{
  config,
  lib,
  pkgs,
  ...
}:

{
  imports = [
    ./hardware.nix
    ./disko.nix
    ../../modules/nixos/base.nix
    ../../modules/nixos/desktop-hyprland.nix
    ../../modules/nixos/himmelblau.nix
    ../../modules/nixos/intune-identity.nix
    ../../modules/nixos/secureboot.nix
  ];

  networking.hostName = lib.mkDefault "stargazer";

  # Tenant facts (domain, tenant id, UPN) come from the committed, age-encrypted
  # secrets/stargazer-tenant.yaml and are rendered at activation -- so this is
  # unconditional and works identically from `github:andrey-moor/dotfiles#…`.
  modules.nixos.himmelblau.enable = true;

  sops = {
    # First host done the §10 way: the recipient is derived from this machine's
    # SSH host key (ssh-to-age), so no master key is ever copied in. The Fusion
    # trial reuses the same pre-generated host key, as the fire drill does.
    age.sshKeyPaths = [ "/etc/ssh/ssh_host_ed25519_key" ];
    # Per-secret `sopsFile` overrides this; modules/nixos/himmelblau.nix points
    # its three tenant secrets at secrets/stargazer-tenant.yaml.
    defaultSopsFile = ../../secrets/wayvnc.yaml;
    secrets."wayvnc-stargazer".owner = "andreym";
  };

  # FIDO2/WebAuthn in the browser (Firefox has CTAP built in) needs the user
  # to reach the security key's hidraw node; libfido2's udev rules tag them
  # `uaccess` so the seat owner gets an ACL. Without them access depends on
  # whatever logind happens to grant.
  services.udev.packages = [ pkgs.libfido2 ];

  home-manager.users.andreym = {
    # linux/{firefox,wayvnc}.nix rather than the home/linux.nix bundle: the
    # bundle also carries linux/intune.nix, whose x86_64 .deb/Rosetta stack has
    # no place on a NixOS host (himmelblau replaces it here).
    imports = [
      ../../home/core.nix
      ../../home/dev.nix
      ../../home/dev/python.nix
      ../../home/linux/firefox.nix
      ../../home/linux/firefox-entra-sso.nix
      ../../home/linux/wayvnc.nix
    ];

    home.stateVersion = "24.05";
    home.enableNixpkgsReleaseCheck = false; # Using pkgs.main for some packages

    modules.linux.wayvnc = {
      passwordFile = config.sops.secrets."wayvnc-stargazer".path;
      monitor = "Virtual-1";
      gpu = false; # no DMA-BUF/H.264 path on a virtual GPU
      renderCursor = true;
      # The firewall (default deny, trustedInterfaces = tailscale0) enforces
      # tailnet-only reach; hosts pin the address once they have joined.
    };
  };

  # Matches the pinned nixpkgs release. Never derived from the spoofed
  # /etc/os-release -- system.nixos.* stays honest (see intune-identity.nix).
  system.stateVersion = "26.11";
}
