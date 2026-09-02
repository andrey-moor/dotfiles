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

  # Reliable DNS. The DHCP-provided LAN resolvers intermittently fail to answer
  # (cold lookups measured up to 5 s while systemd-resolved waits to fail over);
  # himmelblau's Entra probe caps connect+DNS at 3 s, so every unlucky login
  # ended in PAM_ABORT "Network down" (2026-09-02). Public resolvers answer in
  # ~65 ms; resolved caches; Tailscale keeps MagicDNS via split DNS.
  networking.nameservers = [
    "1.1.1.1"
    "8.8.8.8"
  ];
  services.resolved = {
    enable = true;
    dnssec = "false";
    # DNS-over-TLS: one TCP session per resolver instead of parallel UDP
    # queries. With plain UDP, resolved's A+AAAA pair stalled ~5 s about once
    # in 30 lookups (second reply lost/mishandled) — enough to trip
    # himmelblau's 3 s probe cap at login. Direct UDP bursts to the resolver
    # never stalled, so it is resolved-side, and TLS sidesteps it.
    dnsovertls = "opportunistic"; # TLS preferred; plain fallback so a TLS hiccup is never a full outage
    llmnr = "false";
    fallbackDns = [
      "9.9.9.9"
      "1.0.0.1"
    ];
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
