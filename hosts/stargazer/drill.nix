# hosts/stargazer/drill.nix -- the fire drill's configuration (README section 8)
#
# Everything stargazer is, with three differences that make the drill safe to
# run next to the real machine. On 2026-09-18 the drill booted the production
# configuration itself. Someone logged in at its greeter with the YubiKey, and
# it joined the tenant as a second device named `stargazer`.

{ lib, ... }:

{
  imports = [ ./default.nix ];

  # Its own name, so a stray tailnet node, device record or log line says which
  # machine it came from.
  networking.hostName = lib.mkForce "stargazer-drill";

  # Nothing can authenticate at this console, so the drill cannot join the
  # tenant. `andreym` has no local password and modules/nixos/himmelblau.nix
  # already takes pam_unix out of this stack. With himmelblau gone too, only
  # pam_deny is left. greetd uses this stack as a substack. SSH is unaffected:
  # it takes keys only, and every drill check runs over it.
  security.pam.services.login.rules.auth.himmelblau.enable = lib.mkForce false;

  modules.nixos.desktop.greeting = "FIRE DRILL. Console login is disabled here. Verify over SSH.";
}
