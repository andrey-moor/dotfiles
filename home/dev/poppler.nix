# home/dev/poppler.nix -- poppler-utils: pdftoppm for the word-docs skill's page previews

{ pkgs, ... }:
{
  home.packages = [ pkgs.poppler-utils ];
}
