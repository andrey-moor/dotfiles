{ pkgs, himmelblauFlake, ... }:
# =============================================================================
# STATUS (2026-08-03): B4 REACHES THE DOORSTEP, on both architectures.
#
# x86_64 (Task 3, on rocinante): the image builds, boots, and `himmelblaud`
# comes up healthy — `systemctl is-active himmelblaud` reports active and
# `aad-tool status` reports the broker working. Nothing was enrolled and no
# authentication was attempted.
#
# aarch64 (Tasks 5-6, on behemoth): the SAME module list builds for
# aarch64-linux on a throwaway QEMU/HVF builder VM
# (`scripts/arm-builder` — behemoth has no aarch64-linux builder of its own),
# was independently verified by booting the result under `-accel hvf`, and was
# then adopted into the Parallels VM `spike-himmelblau-arm`
# (`scripts/spike-parallels`) where it reaches the same healthy doorstep. That
# VM holds a `doorstep` snapshot of the clean pre-enrollment state.
#
# The one finding that changes the ceremony: himmelblau has NO `aad-tool
# enroll` subcommand. There is no enrollment step distinct from
# authentication — the Entra device join happens as a side effect of the FIRST
# SUCCESSFUL AUTHENTICATION of an Entra user through the daemon, governed by
# `join_type` (default `join`). So "enrollment" IS "first login", and it is
# not something an autonomous task can rehearse halfway.
#
# Outcome summary for the public record: `spikes/intune/README.md`.
# Verbatim evidence and the step-by-step ceremony (both contain the real
# tenant domain, both gitignored, both local to the owner's machine):
# `spikes/intune/notes/b4-doorstep.md` and
# `.superpowers/sdd/2026-08-03-env-refactor-p2-intune-spikes/task-{3,5,6}-report*.md`.
# =============================================================================
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
