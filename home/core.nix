# home/core.nix -- home-manager modules every host gets
#
# Enable matrix (2026-09-01): behemoth, rocinante and stargazer all had every
# one of these on. Importing a feature file is what enables it.

{
  imports = [
    ./profiles/andreym.nix

    ./shell/alacritty.nix
    ./shell/atuin.nix
    ./shell/bat.nix
    ./shell/direnv.nix
    ./shell/ghostty.nix
    ./shell/git.nix
    ./shell/gpg.nix
    ./shell/lazygit.nix
    ./shell/nushell.nix
    ./shell/onepassword.nix
    ./shell/openvpn.nix
    ./shell/ssh.nix
    ./shell/starship.nix
    ./shell/tmux.nix
  ];
}
