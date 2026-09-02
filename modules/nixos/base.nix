# modules/nixos/base.nix -- baseline every NixOS host in this flake gets
#
# Users, SSH, tailnet, firewall, nix settings, refresh-on-start. Desktop,
# hypervisor and identity concerns live in the sibling modules.

{ pkgs, ... }:

{
  # The one local account. home-manager's NixOS module reads and writes
  # `users.users.<name>`, so this entry is mandatory even though the login
  # itself is brokered by Entra (see modules/nixos/himmelblau.nix).
  # Single-user VM behind LUKS + login: wheel gets passwordless sudo so the
  # host (behemoth) can administer it over key-only SSH. Owner decision
  # 2026-09-02 (P9 Task 4).
  security.sudo.wheelNeedsPassword = false;

  users.users.andreym = {
    isNormalUser = true;
    uid = 1000;
    description = "Andrey Moor";
    extraGroups = [
      "wheel"
      "video"
      "input"
    ];
    # Same public half the fleet already uses; the private key lives in
    # 1Password (see home/shell/onepassword.nix, ~/.ssh/1p_personal.pub).
    openssh.authorizedKeys.keys = [
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICdtwwW6A7j8vesJzYxp06VugC0Go+q1rBCbTXbCzSfs"
    ];
  };

  services.openssh = {
    enable = true;
    settings = {
      PasswordAuthentication = false;
      PermitRootLogin = "no";
    };
  };

  services.tailscale.enable = true;

  # Default-deny at the edge; everything we run (sshd, wayvnc) is reachable
  # only over the tailnet. No port is opened on the Parallels NAT interface.
  networking.firewall = {
    enable = true;
    trustedInterfaces = [ "tailscale0" ];
    # Required for Tailscale's exit-node/subnet routing to survive rp_filter.
    checkReversePath = "loose";
  };

  nix.settings = {
    experimental-features = [
      "nix-command"
      "flakes"
    ];
    trusted-users = [
      "root"
      "andreym"
    ];
  };

  # Refresh-on-start instead of a scheduled keep-alive: `persistent` makes the
  # timer fire on boot/resume when a run was missed, which is the whole point
  # on a VM that is suspended more often than it is running.
  system.autoUpgrade = {
    enable = true;
    flake = "github:andrey-moor/dotfiles#stargazer";
    flags = [ ];
    allowReboot = false;
    persistent = true;
    dates = "daily";
  };

  time.timeZone = "America/Los_Angeles";
  i18n.defaultLocale = "en_US.UTF-8";

  # git ships as a plain package on purpose: `programs.git.enable` would make
  # /etc/gitconfig a read-only store symlink, and one of the tenant's Intune
  # CustomConfig policies runs `git config --system ...` on every check-in.
  environment.systemPackages = with pkgs; [
    git
    vim
    curl
  ];
}
