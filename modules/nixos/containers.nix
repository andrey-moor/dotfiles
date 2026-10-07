# modules/nixos/containers.nix -- Docker, rootless unless a host flips it
#
# The docker group is root-equivalent, so rootless is the default (spec D5).
# A compose stack that needs the rootful daemon sets rootful = true.
{
  lib,
  config,
  ...
}:

with lib;
let
  cfg = config.modules.nixos.containers;
in
{
  options.modules.nixos.containers.rootful = mkOption {
    type = types.bool;
    default = false;
    description = "Run the rootful daemon and put andreym in the docker group instead of rootless Docker.";
  };

  config = {
    virtualisation.docker.rootless = mkIf (!cfg.rootful) {
      enable = true;
      setSocketVariable = true;
    };
    virtualisation.docker.enable = cfg.rootful;
    users.users.andreym.extraGroups = mkIf cfg.rootful [ "docker" ];
    # isNormalUser already defaults this to true on this nixpkgs, as long as no
    # subUid/subGid range is set by hand. Said here because rootless Docker
    # cannot start without the /etc/subuid and /etc/subgid entries.
    users.users.andreym.autoSubUidGidRange = true;
  };
}
