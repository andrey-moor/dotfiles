# home/darwin.nix -- home-manager modules only the macOS host gets

{
  imports = [
    ./shell/karabiner.nix
    ./shell/lan-mouse.nix
  ];
}
