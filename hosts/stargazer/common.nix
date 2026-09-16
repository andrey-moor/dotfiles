# hosts/stargazer/common.nix -- everything about stargazer that does not depend
# on the hypervisor.
#
# ./default.nix adds the hypervisor layer (VMware Fusion) on top: the guest
# module, the Retina scale, the Secure Boot switch and SSH on the NAT link.
#
# Deliberately absent: Rosetta, nixGL, home/linux/intune.nix (the Arch-era
# portal/broker stack, which stays for rocinante) and Ghostty as the terminal
# (a per-host choice, revisited by the P9b desktop spec).

{
  config,
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

  # Tenant facts (domain, tenant id, UPN) come from the committed, age-encrypted
  # secrets/stargazer-tenant.yaml and are rendered at activation -- so this is
  # unconditional and works identically from `github:andrey-moor/dotfiles#…`.
  modules.nixos.himmelblau.enable = true;

  sops = {
    # First host done the §10 way: the recipient is derived from this machine's
    # SSH host key (ssh-to-age), so no master key is ever copied in. Every
    # rebuild reuses that host key, parked in 1Password (README §3).
    age.sshKeyPaths = [ "/etc/ssh/ssh_host_ed25519_key" ];
    # Per-secret `sopsFile` overrides this; modules/nixos/himmelblau.nix points
    # its three tenant secrets at secrets/stargazer-tenant.yaml.
    defaultSopsFile = ../../secrets/wayvnc.yaml;
    secrets."wayvnc-stargazer".owner = "andreym";

    # Secure Boot signing key. One key pair for every stargazer instance, so
    # the db certificate is known before a VM exists and the VM definition can
    # carry it. The private half is age-encrypted here. The public half and
    # sbctl's owner GUID are plain files in ./secureboot, placed by tmpfiles
    # below. Only the db key exists: the firmware keeps VMware's PK and KEK.
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
