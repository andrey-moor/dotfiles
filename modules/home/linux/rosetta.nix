# modules/home/linux/rosetta.nix -- Rosetta x86_64 emulation for aarch64-linux
#
# Enables x86_64-linux package support on aarch64-linux systems using
# Apple's Rosetta translation layer (Parallels Desktop on Apple Silicon).
#
# Manages:
#   - binfmt registration check (one-time manual setup)
#   - /lib64/ld-linux-x86-64.so.2 symlink (kept current across nix GC)
#   - GC root for x86_64 glibc (prevents garbage collection)
#   - /boot/vmlinuz-linux sync with /boot/Image (Arch ARM kernel naming fix)

{ lib, config, pkgs, ... }:

with lib;
let
  cfg = config.modules.linux.rosetta;

  pkgsX86 = import pkgs.path {
    system = "x86_64-linux";
  };

  glibcX86 = pkgsX86.glibc;
  linkerPath = "${glibcX86}/lib/ld-linux-x86-64.so.2";
in {
  options.modules.linux.rosetta = {
    enable = mkEnableOption "Rosetta x86_64 emulation support";
  };

  config = mkIf (cfg.enable && pkgs.stdenv.isLinux && pkgs.stdenv.hostPlatform.isAarch64) {
    # Note: extra-platforms must be set system-wide in /etc/nix/nix.custom.conf
    # (done by prerequisites script or Determinate Nix installer)
    # Setting it in user config causes warnings since it's a restricted setting

    home.activation.checkRosetta = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      if [[ ! -f /proc/sys/fs/binfmt_misc/rosetta ]]; then
        noteEcho "Rosetta binfmt not configured. Run this once as root:"
        noteEcho "  sudo tee /etc/binfmt.d/rosetta.conf << 'EOF'"
        noteEcho ":rosetta:M::\\x7fELF\\x02\\x01\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x02\\x00\\x3e\\x00:\\xff\\xff\\xff\\xff\\xff\\xfe\\xfe\\x00\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xfe\\xff\\xff\\xff:/mnt/psf/RosettaLinux/rosetta:PFC"
        noteEcho "EOF"
        noteEcho "  sudo systemctl restart systemd-binfmt"
      fi

      # Keep x86_64 glibc alive across nix garbage collection
      mkdir -p "$HOME/.local/state/nix/gcroots"
      ln -sfn ${glibcX86} "$HOME/.local/state/nix/gcroots/rosetta-glibc-x86_64"

      # Ensure /lib64/ld-linux-x86-64.so.2 points to the current x86_64 glibc
      if [[ "$(readlink /lib64/ld-linux-x86-64.so.2 2>/dev/null)" != "${linkerPath}" ]]; then
        noteEcho "Rosetta: /lib64/ld-linux-x86-64.so.2 needs updating"
        if sudo ln -sf ${linkerPath} /lib64/ld-linux-x86-64.so.2 2>/dev/null; then
          noteEcho "Rosetta: Updated /lib64/ld-linux-x86-64.so.2 -> ${linkerPath}"
        else
          warnEcho "Rosetta: Could not update /lib64/ld-linux-x86-64.so.2 (run manually):"
          warnEcho "  sudo ln -sf ${linkerPath} /lib64/ld-linux-x86-64.so.2"
        fi
      fi

      # Sync /boot/vmlinuz-linux with /boot/Image after kernel updates
      # Arch ARM's linux-aarch64 installs to /boot/Image but GRUB expects /boot/vmlinuz-linux.
      # A stale vmlinuz-linux causes initramfs module mismatch → LUKS decrypt failure at boot.
      if [[ -f /boot/Image ]] && [[ -f /boot/vmlinuz-linux ]]; then
        if ! cmp -s /boot/Image /boot/vmlinuz-linux; then
          noteEcho "Rosetta: /boot/vmlinuz-linux is stale, syncing with /boot/Image"
          if sudo cp /boot/Image /boot/vmlinuz-linux 2>/dev/null; then
            noteEcho "Rosetta: Updated /boot/vmlinuz-linux"
          else
            warnEcho "Rosetta: Could not update /boot/vmlinuz-linux (run manually):"
            warnEcho "  sudo cp /boot/Image /boot/vmlinuz-linux"
          fi
        fi
      fi
    '';
  };
}
