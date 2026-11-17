# modules/darwin/yubikey-share.nix -- lend this Mac's YubiKey to a Linux host
#
# rocinante has no YubiKey of its own, and sign-in there needs one. VirtualHere
# carries the key over the network: a server here, a client on the Linux host.
# `scripts/yubikey` drives both ends (`just yubikey`, `just yubikey-back`).
#
# The server is a root launchd daemon that stays stopped until the script
# starts it. Both points matter:
#   * Root, because only root may take a USB device away from the macOS HID and
#     smart-card drivers. Run as the user (opening the app by hand) it fails
#     with kIOReturnExclusiveAccess and then stays stuck until restarted.
#   * Stopped by default, because the free edition has no password and cannot
#     bind to one interface. While it runs, anyone who can reach TCP 7575 on
#     this Mac can take a shared device.

{ lib, pkgs, ... }:

let
  app = "/Applications/VirtualHereServerUniversal.app";
  stateDir = "/var/db/virtualhere";
  # Developer ID of VirtualHere Pty. Ltd.
  vendor = "N8C8ZTN347";

  # Enforced on every start. The server rewrites config.ini while it runs and
  # keeps its own keys there, so the file is patched, not replaced.
  settings = {
    ServerName = "behemoth";
    # Share YubiKeys only (USB vendor 0x1050). Without this every USB device on
    # the Mac is on offer, microphone and dock included.
    AllowedDevices = "1050/*";
    # No Bonjour advertisement. Clients are pointed at this Mac by address.
    UseAVAHI = "0";
  };

  start = pkgs.writeShellScript "virtualhere-server" ''
    set -eu
    cfg=${stateDir}/config.ini
    mkdir -p ${stateDir}
    touch "$cfg"
    ${lib.concatStrings (
      lib.mapAttrsToList (key: value: ''
        ${pkgs.gnused}/bin/sed -i '/^${key}=/Id' "$cfg"
        echo '${key}=${value}' >> "$cfg"
      '') settings
    )}
    # Homebrew installs the app owned by the user, so any process of the user
    # could swap the binary and have root run it. Run a copy that only root
    # can write, and only if the vendor signed it.
    rm -rf ${stateDir}/server.app
    cp -R ${app} ${stateDir}/server.app
    /usr/bin/codesign --verify --strict \
      -R='anchor apple generic and certificate 1[field.1.2.840.113635.100.6.2.6] exists and certificate leaf[field.1.2.840.113635.100.6.1.13] exists and certificate leaf[subject.OU] = "${vendor}"' \
      ${stateDir}/server.app
    # Same arguments as the vendor's own launchd plist (`vhusbdosx -b`).
    exec ${stateDir}/server.app/Contents/MacOS/vhusbdosx -o -r /var/log/vhusbd.log -c "$cfg"
  '';
in
{
  homebrew.casks = [ "virtualhereserver" ];

  launchd.daemons.virtualhere-server = {
    command = start;
    serviceConfig = {
      RunAtLoad = false;
      KeepAlive = false;
    };
  };
}
