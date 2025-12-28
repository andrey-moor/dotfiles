# modules/home/linux/rosetta.nix -- Rosetta x86_64 emulation for aarch64-linux
#
# Enables x86_64-linux package support on aarch64-linux systems using
# Apple's Rosetta translation layer (Parallels Desktop on Apple Silicon).
#
# Requires one-time manual setup for binfmt registration (see activation warning).

{ lib, config, pkgs, ... }:

with lib;
let cfg = config.modules.linux.rosetta;
in {
  options.modules.linux.rosetta = {
    enable = mkEnableOption "Rosetta x86_64 emulation support";
  };

  config = mkIf (cfg.enable && pkgs.stdenv.isLinux && pkgs.stdenv.hostPlatform.isAarch64) {
    # Configure Nix to support x86_64-linux packages
    xdg.configFile."nix/nix.conf".text = ''
      extra-platforms = x86_64-linux
    '';

    # Activation script to check binfmt registration
    home.activation.checkRosetta = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      if [[ ! -f /proc/sys/fs/binfmt_misc/rosetta ]]; then
        noteEcho "Rosetta binfmt not configured. Run this once as root:"
        noteEcho "  sudo tee /etc/binfmt.d/rosetta.conf << 'EOF'"
        noteEcho ":rosetta:M::\\x7fELF\\x02\\x01\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x02\\x00\\x3e\\x00:\\xff\\xff\\xff\\xff\\xff\\xfe\\xfe\\x00\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xfe\\xff\\xff\\xff:/media/psf/RosettaLinux/rosetta:PFC"
        noteEcho "EOF"
        noteEcho "  sudo systemctl restart systemd-binfmt"
      fi
    '';
  };
}
