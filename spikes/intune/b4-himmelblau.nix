{ pkgs, himmelblauFlake, ... }:
let
  tenant = import ./tenant.nix;
  system = pkgs.stdenv.hostPlatform.system;
in
{
  imports = [ himmelblauFlake.nixosModules.himmelblau ];

  # Upstream's real option namespace (verified against
  # github:himmelblau-idm/himmelblau@main, nix/modules/himmelblau-options.nix,
  # 2026-08-03) differs from the brief's guess:
  #   - the key is `domain` (singular), not `domains` -- but it is still
  #     `nullOr (listOf str)`, so a one-element list is correct.
  #   - `pam_allow_groups` defaults to `null`, which upstream's own docs
  #     define as "all Entra ID users are permitted to authenticate." The
  #     brief's snippet set it to `[ ]` intending "no group gating," but an
  #     *empty* allow-list is a populated allow-list with zero entries --
  #     i.e. it would lock every user out, the opposite of the stated intent.
  #     We omit the setting entirely so it stays at its true "no gating"
  #     default instead.
  services.himmelblau = {
    enable = true;
    settings = {
      domain = [ tenant.domain ];
    };
  };

  # The daemon/pam/nss/broker/sso packages are already wired in by
  # himmelblauFlake.nixosModules.himmelblau itself (via mkDefault against its
  # own `self.packages.${system}`). aad-tool is explicitly *not* auto-installed
  # upstream ("optional and need to be installed by you" -- README) so it's
  # added here for the doorstep CLI check and for Task 7's enrollment ceremony.
  environment.systemPackages = [
    himmelblauFlake.packages.${system}.aad-tool
  ];
}
