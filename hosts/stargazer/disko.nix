# hosts/stargazer/disko.nix -- single-disk LUKS2 + btrfs layout
#
# /dev/nvme0n1: VMware Fusion gives Arm guests an NVMe boot disk.
#
# The LUKS passphrase slot is the portable baseline and is never removed --
# it is what the fire drill proves and what makes the image hypervisor-neutral.
# `askPassword` is disko's default when neither passwordFile nor a keyFile is
# given, which is the interactive prompt we want at install and at cold boot.

_: {
  disko.devices.disk.main = {
    type = "disk";
    device = "/dev/nvme0n1";
    content = {
      type = "gpt";
      partitions = {
        ESP = {
          # 1G, not disko's example 512M: lanzaboote (Task 6) puts a full UKI
          # -- kernel plus initrd -- on the ESP for every generation.
          size = "1G";
          type = "EF00";
          content = {
            type = "filesystem";
            format = "vfat";
            mountpoint = "/boot";
            mountOptions = [ "umask=0077" ];
          };
        };
        luks = {
          size = "100%";
          content = {
            type = "luks";
            name = "cryptroot";
            settings.allowDiscards = true;
            content = {
              type = "btrfs";
              extraArgs = [ "-f" ];
              subvolumes = {
                "/@root" = {
                  mountpoint = "/";
                  mountOptions = [
                    "compress=zstd"
                    "noatime"
                  ];
                };
                "/@home" = {
                  mountpoint = "/home";
                  mountOptions = [
                    "compress=zstd"
                    "noatime"
                  ];
                };
                "/@nix" = {
                  mountpoint = "/nix";
                  mountOptions = [
                    "compress=zstd"
                    "noatime"
                  ];
                };
                "/@log" = {
                  mountpoint = "/var/log";
                  mountOptions = [
                    "compress=zstd"
                    "noatime"
                  ];
                };
              };
            };
          };
        };
      };
    };
  };
}
