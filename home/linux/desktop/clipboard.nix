# home/linux/desktop/clipboard.nix -- clipboard history
#
# vicinae keeps the history (spec section 2). cliphist is not installed unless
# that proves insufficient. This module exists so the role has a home. The
# Fusion bridge (modules/nixos/vmware-guest.nix) also watches the clipboard and
# skips CLIPBOARD_STATE=sensitive, which is the rule any history tool here must
# keep.
{ pkgs, ... }:
{
  home.packages = [ pkgs.wl-clipboard ];
}
