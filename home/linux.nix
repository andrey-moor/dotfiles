# home/linux.nix -- home-manager modules both Linux hosts get
#
# Rocinante only, in practice: stargazer is NixOS now and imports
# linux/{firefox,wayvnc}.nix directly, because the Arch-era intune.nix
# (portal/broker stack, x86_64 .debs under Rosetta) must not follow it there.
# Host-specific: edge.nix (rocinante, x86_64). containers.nix is currently
# unused. rosetta.nix is pulled in by intune.nix.

{
  imports = [
    ./linux/firefox.nix
    ./linux/intune.nix
    ./linux/wayvnc.nix
  ];
}
