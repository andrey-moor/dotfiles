# modules/home/shell/gpg.nix -- GPG and gpg-agent configuration with Yubikey support

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.shell.gpg;
in {
  options.modules.shell.gpg = {
    enable = mkEnableOption "GPG with gpg-agent and SSH support";
  };

  config = mkIf cfg.enable {
    programs.gpg = {
      enable = true;
      settings = {
        # Display
        keyid-format = "0xlong";
        with-fingerprint = true;

        # Charset
        charset = "utf-8";
        utf8-strings = true;

        # Algorithms (modern defaults)
        personal-cipher-preferences = "AES256 AES192 AES";
        personal-digest-preferences = "SHA512 SHA384 SHA256";
        personal-compress-preferences = "ZLIB BZIP2 ZIP Uncompressed";
        default-preference-list = "SHA512 SHA384 SHA256 AES256 AES192 AES ZLIB BZIP2 ZIP Uncompressed";
        cert-digest-algo = "SHA512";
        s2k-digest-algo = "SHA512";
        s2k-cipher-algo = "AES256";

        # Behavior
        no-emit-version = true;
        no-comments = true;
        require-cross-certification = true;
        no-symkey-cache = true;
        throw-keyids = true;

        # Keyserver
        keyserver = "hkps://keys.openpgp.org";
        keyserver-options = "no-honor-keyserver-url include-revoked";
      };
    };

    services.gpg-agent = {
      enable = true;
      enableSshSupport = true;
      # Terminal-based pinentry
      pinentry.package = pkgs.pinentry-curses;
      # Cache passphrases for 1 hour
      defaultCacheTtl = 3600;
      maxCacheTtl = 7200;
      # SSH key cache
      defaultCacheTtlSsh = 3600;
      maxCacheTtlSsh = 7200;
    };

    # Yubikey/smartcard management tools
    home.packages = with pkgs; [
      yubikey-manager  # ykman CLI for Yubikey management
    ];
  };
}
