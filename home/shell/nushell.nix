# home/shell/nushell.nix -- Nushell shell + out-of-store config
#
# Config lives in <dotfiles>/config/nushell, deployed as individual file
# symlinks. nu_scripts fetched by nix at ~/.local/share/nushell/nu_scripts

{
  lib,
  dotfilesDir,
  config,
  pkgs,
  ...
}:

with lib;
let
  isDarwin = pkgs.stdenv.isDarwin;

  # Out-of-store symlink into the live repo working copy.
  mkNushellLink = name: config.lib.file.mkOutOfStoreSymlink "${dotfilesDir}/config/nushell/${name}";

  # Fetch nu_scripts from GitHub
  nu_scripts = pkgs.fetchFromGitHub {
    owner = "nushell";
    repo = "nu_scripts";
    rev = "main";
    sha256 = "sha256-oxnXzxQkNccCs36j+aMzg4QGHDcX7niJruqxCkeg0LM=";
  };
in
{
  config = {
    home.packages = [
      pkgs.nushell
      pkgs.carapace
    ];

    # Individual file symlinks only — NOT the whole dir: history.txt and
    # vendor/autoload/ are machine-generated and must survive.
    xdg.configFile = {
      "nushell/config.nu".source = mkNushellLink "config.nu";
      "nushell/env.nu".source = mkNushellLink "env.nu";
      "nushell/catppuccin_mocha.nu".source = mkNushellLink "catppuccin_mocha.nu";
    };

    # Symlink nu_scripts to ~/.local/share/nushell/nu_scripts
    home.file.".local/share/nushell/nu_scripts".source = nu_scripts;

    # On macOS, nushell defaults to ~/Library/Application Support/nushell/
    # but our config is at ~/.config/nushell/.
    # XDG_CONFIG_HOME must be set BEFORE nushell starts, but launchctl setenv
    # is blocked by SIP. Symlink is the cleanest solution.
    # On Linux, nushell already defaults to ~/.config/nushell/.
    home.file."Library/Application Support/nushell" = mkIf isDarwin {
      source = config.lib.file.mkOutOfStoreSymlink "${config.home.homeDirectory}/.config/nushell";
    };
  };
}
