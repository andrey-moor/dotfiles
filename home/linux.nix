# home/linux.nix -- home-manager modules for the non-NixOS Linux host
#
# Only rocinante imports it. Stargazer is NixOS now and imports
# linux/{firefox,wayvnc}.nix directly, because the Arch-era intune.nix
# (portal/broker stack, x86_64 .debs) must not follow it there.
# Host-specific: edge.nix (rocinante, x86_64).

{
  imports = [
    ./linux/firefox.nix
    ./linux/intune.nix
    ./linux/wayvnc.nix
  ];
}
