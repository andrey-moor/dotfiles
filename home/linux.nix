# home/linux.nix -- home-manager modules both Linux hosts get
#
# Host-specific: edge.nix (rocinante, x86_64), edge-rosetta.nix + containers.nix
# (stargazer). rosetta.nix is pulled in by intune.nix/edge-rosetta.nix.

{
  imports = [
    ./linux/firefox.nix
    ./linux/intune.nix
    ./linux/wayvnc.nix
  ];
}
