# home/dev.nix -- dev tooling every host gets
#
# Host-specific dev tools are imported by the host instead:
#   copilot   behemoth, rocinante
#   hunk      behemoth, rocinante
#   lmstudio  rocinante
#   python    rocinante, stargazer

{
  imports = [
    ./dev/bazel.nix
    ./dev/claude.nix
    ./dev/codex.nix
    ./dev/go.nix
    ./dev/jj.nix
    ./dev/kubernetes.nix
    ./dev/neovim.nix
    ./dev/nix.nix
    ./dev/opencode.nix
    ./dev/rust.nix
    ./dev/terraform.nix
    ./dev/vscode.nix
  ];
}
