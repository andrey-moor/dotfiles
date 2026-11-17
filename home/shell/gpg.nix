# home/shell/gpg.nix -- GPG and gpg-agent configuration with Yubikey support

{
  lib,
  pkgs,
  ...
}:

{
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
    # SSH support stays off: 1Password is the SSH agent (onepassword.nix).
    # macOS: GUI pinentry, Linux: tty (curses has terminal size issues)
    pinentry.package =
      if pkgs.stdenv.hostPlatform.isDarwin then pkgs.pinentry_mac else pkgs.pinentry-tty;
    # Cache passphrases for 24 hours (long sessions with AI tools need
    # persistent cache since non-interactive shells can't re-prompt via pinentry)
    defaultCacheTtl = 86400;
    maxCacheTtl = 86400;
    # SSH key cache — matches GPG cache
    defaultCacheTtlSsh = 86400;
    maxCacheTtlSsh = 86400;
    # Don't grab keyboard (can cause issues on macOS)
    grabKeyboardAndMouse = false;
  };

  # gpg-agent --supervised only accepts sockets passed the systemd way, so
  # the launchd agent home-manager declares on macOS exits with code 2 and
  # restarts every 10 seconds. config/nushell/config.nu starts the agent
  # with `gpgconf --launch` instead.
  launchd.agents.gpg-agent.enable = lib.mkIf pkgs.stdenv.hostPlatform.isDarwin (lib.mkForce false);

  # scdaemon config for YubiKey
  home.file.".gnupg/scdaemon.conf".text = ''
    # Disable internal CCID driver to avoid conflicts with system CCID
    disable-ccid
  '';

  # Yubikey/smartcard management tools
  home.packages = with pkgs; [
    yubikey-manager # ykman CLI for Yubikey management
    yubikey-personalization # ykpersonalize for low-level config
  ];
}
