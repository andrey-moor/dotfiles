# home/linux/firefox-entra-sso.nix -- Entra ID device SSO in the home-manager Firefox
#
# Device-based Conditional Access on Linux works through Siemens'
# linux-entra-sso WebExtension: it asks the local identity broker (D-Bus
# `com.microsoft.identity.broker1`, provided by himmelblau's `broker` package
# on NixOS hosts) for a PRT SSO cookie and injects it into sign-in flows.
# himmelblau's NixOS module wires the extension and its native-messaging host
# into the *system* Firefox (`programs.firefox` at the NixOS level), which this
# repo does not enable -- the browser in use is home-manager's. This module
# attaches the same two pieces to that one. Firefox is the extension's
# first-class target; Chromium support is "limited" upstream.
#
# Import only on hosts running himmelblau (the broker must exist).

{
  inputs,
  pkgs,
  ...
}:

{
  programs.firefox = {
    # On the package, not `programs.firefox.nativeMessagingHosts`: home-manager
    # re-wraps the (already wrapped) pkgs.firefox with `cfg`, `policies` and
    # `pkcs11Modules` only and drops that option on the floor (HM release in
    # flake.lock, 2026-09). The override survives the re-wrap.
    package = pkgs.firefox.override {
      nativeMessagingHosts = [ inputs.himmelblau.packages.${pkgs.stdenv.hostPlatform.system}.sso ];
    };
    # Same release himmelblau's own module pins; the native host speaks this
    # extension version's protocol.
    policies.Extensions.Install = [
      "https://github.com/siemens/linux-entra-sso/releases/download/v1.7.1/linux_entra_sso-1.7.1.xpi"
    ];
  };
}
