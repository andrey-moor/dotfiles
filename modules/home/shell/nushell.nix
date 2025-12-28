# modules/home/shell/nushell.nix -- Nushell package (config via chezmoi)
#
# Config managed by chezmoi at ~/.config/nushell/
# nu_scripts fetched by nix at ~/.local/share/nushell/nu_scripts

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.shell.nushell;
  isDarwin = pkgs.stdenv.isDarwin;

  # Fetch nu_scripts from GitHub
  nu_scripts = pkgs.fetchFromGitHub {
    owner = "nushell";
    repo = "nu_scripts";
    rev = "main";
    sha256 = "sha256-oxnXzxQkNccCs36j+aMzg4QGHDcX7niJruqxCkeg0LM=";
  };
in {
  options.modules.shell.nushell = {
    enable = mkEnableOption "Nushell shell";
  };

  config = mkIf cfg.enable {
    home.packages = [ pkgs.nushell ];

    # Symlink nu_scripts to ~/.local/share/nushell/nu_scripts
    home.file.".local/share/nushell/nu_scripts".source = nu_scripts;

    # On macOS, nushell defaults to ~/Library/Application Support/nushell/
    # but our config is at ~/.config/nushell/ (managed by chezmoi).
    # XDG_CONFIG_HOME must be set BEFORE nushell starts, but launchctl setenv
    # is blocked by SIP. Symlink is the cleanest solution.
    # On Linux, nushell already defaults to ~/.config/nushell/.
    home.file."Library/Application Support/nushell" = mkIf isDarwin {
      source = config.lib.file.mkOutOfStoreSymlink "${config.home.homeDirectory}/.config/nushell";
    };
  };
}
