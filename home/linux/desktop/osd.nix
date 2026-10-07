# home/linux/desktop/osd.nix -- swayosd, client only
#
# No libinput backend: it needs a privileged unit, and a VM has no backlight or
# caps-lock LED worth showing. Volume and mute come from the key map calling
# swayosd-client.
{ config, pkgs, ... }:
let
  t = config.modules.desktop.theme.data;
in
{
  # The media keys in the key map drive MPRIS players through playerctl.
  home.packages = [ pkgs.playerctl ];

  services.swayosd = {
    enable = true;
    topMargin = 0.9;
    # The server loads this on top of its own sheet, at the user priority, so
    # only the slots below change. Selectors are the ones its
    # data/style/style.scss defines, where the window carries the id osd.
    stylePath = pkgs.writeText "swayosd.css" ''
      window#osd {
        background: alpha(${t.colors.background}, 0.9);
        border: 2px solid ${t.colors.accent};
        border-radius: 0;
      }
      window#osd label,
      window#osd image {
        color: ${t.colors.foreground};
      }
      window#osd progress,
      window#osd segment.active {
        background: ${t.colors.accent};
      }
    '';
  };
}
