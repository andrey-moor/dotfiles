# home/linux/desktop/apps.nix -- the GUI set and MIME defaults (spec D6, section 6)
#
# The desktop file ids below were read off the built packages, not guessed.
# x-scheme-handler/claude-cli is absent on purpose: no package in this
# configuration ships a desktop file for that scheme.
{ config, pkgs, ... }:
{
  # imv and mpv are not listed here: their programs.* modules below install
  # the packages, and mpv's wraps it once scripts are added.
  home.packages = with pkgs; [
    _1password-gui
    obsidian
    papers
    qalculate-gtk
  ];

  programs.imv.enable = true;
  programs.mpv.enable = true;

  xdg.mimeApps = {
    enable = true;
    defaultApplications = {
      "text/plain" = "nvim.desktop";
      "image/png" = "imv.desktop";
      "image/jpeg" = "imv.desktop";
      "image/webp" = "imv.desktop";
      "video/mp4" = "mpv.desktop";
      "video/x-matroska" = "mpv.desktop";
      "audio/mpeg" = "mpv.desktop";
      "application/pdf" = "org.gnome.Papers.desktop";
      "x-scheme-handler/http" = "firefox.desktop";
      "x-scheme-handler/https" = "firefox.desktop";
      "x-scheme-handler/mailto" = "firefox.desktop";
    };
  };

  # Pictures and Videos are where the capture tools write, so the directories
  # have to exist before the first screenshot.
  xdg.userDirs = {
    enable = true;
    createDirectories = true;
  };

  xdg.terminal-exec = {
    enable = true;
    settings.default = [ config.modules.desktop.terminalDesktopEntry ];
  };

  # The GUI owns ~/.1password/agent.sock, which home/shell/ssh.nix points
  # IdentityAgent at, so it has to be running before the first git push.
  systemd.user.services."1password" = {
    Unit = {
      Description = "1Password, silent start";
      PartOf = [ "graphical-session.target" ];
      After = [ "graphical-session.target" ];
    };
    Service = {
      ExecStart = "${pkgs._1password-gui}/bin/1password --silent";
      Restart = "on-failure";
    };
    Install.WantedBy = [ "graphical-session.target" ];
  };
}
