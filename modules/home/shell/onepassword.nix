# modules/home/shell/onepassword.nix -- 1Password SSH agent integration
# Uses 1Password for SSH auth and git commit signing instead of gpg-agent/YubiKey

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.shell.onepassword;
in {
  options.modules.shell.onepassword = {
    enable = mkEnableOption "1Password SSH agent integration";
  };

  config = mkIf cfg.enable {
    # Disable gpg-agent SSH support (1Password handles SSH now)
    # GPG agent still runs for encryption/decryption
    services.gpg-agent.enableSshSupport = mkForce false;

    # 1Password CLI
    home.packages = with pkgs; [ _1password-cli ];

    # SSH agent key routing — controls which keys 1Password offers per host
    home.file.".config/1Password/ssh/agent.toml".text = ''
      [[ssh-keys]]
      item = "GitHub Personal"

      [[ssh-keys]]
      item = "GitHub Microsoft"

      [[ssh-keys]]
      item = "GitHub LinkedIn"
    '';

    # Public keys on disk so SSH can request the right key from 1Password agent.
    # These are NOT secret — just references for IdentityFile in SSH config.
    home.file.".ssh/1p_personal.pub".text = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICdtwwW6A7j8vesJzYxp06VugC0Go+q1rBCbTXbCzSfs";
    home.file.".ssh/1p_microsoft.pub".text = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJIvYOLXV0u6EZgw96emCgaMBCYGQLkiW7lJKmYZTfc/";
    home.file.".ssh/1p_linkedin.pub".text = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJtI2UYmOcRkM+PrENRzpRB+4Nzj1Xj8/7tsXfHelBhY";

    # Allowed signers for local SSH signature verification (git log --show-signature)
    home.file.".ssh/allowed_signers".text = ''
      m@andreym.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICdtwwW6A7j8vesJzYxp06VugC0Go+q1rBCbTXbCzSfs
      amoor@microsoft.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJIvYOLXV0u6EZgw96emCgaMBCYGQLkiW7lJKmYZTfc/
      amoor@linkedin.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJtI2UYmOcRkM+PrENRzpRB+4Nzj1Xj8/7tsXfHelBhY
    '';

    programs.git.settings.gpg.ssh.allowedSignersFile = "~/.ssh/allowed_signers";
  };
}
