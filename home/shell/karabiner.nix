# home/shell/karabiner.nix -- Karabiner-Elements config (macOS)
#
# Config only: the app is a Homebrew cask. The two files in config/karabiner
# are deployed through the Nix store, unlike nvim or nushell. An out-of-store
# symlink would point into ~/Documents, which macOS guards per app, and
# Karabiner's background services are not children of the terminal.
#
# The cost: an edit needs `just switch`, and Karabiner's Settings window can
# show the config but cannot save changes to it.

{
  xdg.configFile = {
    "karabiner/karabiner.json".source = ../../config/karabiner/karabiner.json;
    "karabiner/assets/complex_modifications/1770753489.json".source =
      ../../config/karabiner/assets/complex_modifications/1770753489.json;
  };
}
