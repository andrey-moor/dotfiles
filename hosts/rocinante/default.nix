# Rocinante -- Linux workstation (standalone home-manager)

{ lib, ... }:

with lib;
{
  system = "x86_64-linux";
  username = "andreym";
  homeDirectory = "/home/andreym";

  config = { config, pkgs, ... }: {
    # Home-manager state version
    home.stateVersion = "24.05";

    # Enable modules
    modules = {
      profiles.user = "andreym";

      shell = {
        default = "nushell";
        nushell.enable = true;
        fish.enable = true;
        git.enable = true;
        direnv.enable = true;
      };

      dev = {
        nix.enable = true;
        claude.enable = true;
      };
    };
  };
}
