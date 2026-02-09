# modules/home/linux/firefox.nix -- Firefox browser with privacy extensions

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.linux.firefox;
in {
  options.modules.linux.firefox = {
    enable = mkEnableOption "Firefox browser with privacy extensions";
  };

  config = mkIf (cfg.enable && pkgs.stdenv.isLinux) {
    # Catppuccin Mocha theme (applies to profiles defined in programs.firefox.profiles)
    catppuccin.firefox = {
      enable = true;
      flavor = "mocha";
      accent = "lavender";
      profiles.default.enable = true;
    };

    programs.firefox = {
      enable = true;

      profiles.default = {
        id = 0;
        isDefault = true;

        # Allow catppuccin to set extension settings
        extensions.force = true;

        # Privacy extensions from NUR
        extensions.packages = with pkgs.nur.repos.rycee.firefox-addons; [
          ublock-origin
          clearurls
          kagi-search
          onepassword-password-manager
          # Firefox Color is required for catppuccin theme
          firefox-color
        ];

        settings = {
          # Auto-enable extensions
          "extensions.autoDisableScopes" = 0;

          # Disable telemetry
          "toolkit.telemetry.enabled" = false;
          "toolkit.telemetry.unified" = false;
          "toolkit.telemetry.archive.enabled" = false;
          "datareporting.healthreport.uploadEnabled" = false;
          "datareporting.policy.dataSubmissionEnabled" = false;
          "browser.ping-centre.telemetry" = false;

          # Disable experiments
          "app.shield.optoutstudies.enabled" = false;
          "app.normandy.enabled" = false;
          "app.normandy.api_url" = "";

          # Enhanced Tracking Protection
          "privacy.trackingprotection.enabled" = true;
          "privacy.trackingprotection.socialtracking.enabled" = true;
          "privacy.trackingprotection.cryptomining.enabled" = true;
          "privacy.trackingprotection.fingerprinting.enabled" = true;

          # Disable Pocket
          "extensions.pocket.enabled" = false;

          # Disable sponsored content
          "browser.urlbar.suggest.quicksuggest.sponsored" = false;
          "browser.urlbar.suggest.quicksuggest.nonsponsored" = false;
          "browser.newtabpage.activity-stream.showSponsored" = false;
          "browser.newtabpage.activity-stream.showSponsoredTopSites" = false;

          # DNS over HTTPS
          "network.trr.mode" = 2;
          "network.trr.uri" = "https://mozilla.cloudflare-dns.com/dns-query";

          # Disable prefetching
          "network.prefetch-next" = false;
          "network.dns.disablePrefetch" = true;
          "network.predictor.enabled" = false;

          # WebRTC leak prevention
          "media.peerconnection.ice.default_address_only" = true;

          # HTTPS-Only mode
          "dom.security.https_only_mode" = true;
          "dom.security.https_only_mode_ever_enabled" = true;

          # Disable form autofill
          "extensions.formautofill.addresses.enabled" = false;
          "extensions.formautofill.creditCards.enabled" = false;
        };
      };
    };
  };
}
