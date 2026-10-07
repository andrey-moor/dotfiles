# home/linux/desktop/look.nix -- GTK and Qt look, icons
#
# Qt uses the Adwaita style rather than kvantum: catppuccin/nix is not enabled
# here, so there is no kvantum theme to install, and adwaita-qt follows the
# GTK colour scheme. The cursor is set in home/linux/theme.nix.
{ config, pkgs, ... }:
let
  dark = config.modules.desktop.theme.data.mode == "dark";
in
{
  gtk = {
    enable = true;
    theme = {
      name = if dark then "adw-gtk3-dark" else "adw-gtk3";
      package = pkgs.adw-gtk3;
    };
    iconTheme = {
      name = if dark then "Papirus-Dark" else "Papirus";
      package = pkgs.papirus-icon-theme;
    };
    colorScheme = if dark then "dark" else "light";
    # Pins today's behaviour: from stateVersion 26.05 on, gtk.theme stops
    # reaching GTK4 by default.
    gtk4.theme = config.gtk.theme;
  };

  qt = {
    enable = true;
    platformTheme.name = "adwaita";
    style.name = if dark then "adwaita-dark" else "adwaita";
  };
}
