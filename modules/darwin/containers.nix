# modules/darwin/containers.nix -- containers on the Mac, as one Compose project
#
# config/containers/compose.yaml lists the services. OrbStack runs them. One
# launchd agent applies the file at login, and `just gateway-up` applies it by
# hand after a change.
#
# The Compose directory is copied into the Nix store and used from there, so an
# edit needs `just switch`. That is deliberate: the store is readable by every
# process, while the repo sits under ~/Documents, which macOS guards per app.
#
# What cannot be in a container: the model server. No container on macOS can
# use the Apple GPU, so LM Studio runs on the host and the gateway reaches it at
# host.docker.internal. Its server is started here too.

{ config, pkgs, ... }:

let
  user = config.system.primaryUser;
  inherit (config.users.users.${user}) home;

  composeDir = ../../config/containers;
  envFile = "${home}/.config/behemoth-containers/gateway.env";
  logFile = "${home}/Library/Logs/behemoth-containers.log";

  # OrbStack links its docker CLI here. Tailscale's CLI comes with the cask.
  docker = "/usr/local/bin/docker";
  tailscale = "/usr/local/bin/tailscale";

  up = pkgs.writeShellScript "behemoth-containers-up" ''
    set -u
    say() { echo "$(date '+%F %T') $*"; }

    if [ ! -r ${envFile} ]; then
      say "no ${envFile}. Run 'just gateway-secrets' once, then 'just gateway-up'."
      exit 0
    fi

    # At login OrbStack and Tailscale start in no fixed order. Wait for both.
    for _ in $(seq 1 60); do
      ${docker} info >/dev/null 2>&1 && break
      sleep 5
    done
    ${docker} info >/dev/null 2>&1 || { say "Docker is not running, giving up"; exit 1; }

    TAILSCALE_IP=
    for _ in $(seq 1 24); do
      TAILSCALE_IP=$(${tailscale} ip -4 2>/dev/null | head -1) && [ -n "$TAILSCALE_IP" ] && break
      sleep 5
    done
    [ -n "$TAILSCALE_IP" ] || { say "Tailscale has no address, giving up"; exit 1; }
    export TAILSCALE_IP GATEWAY_ENV_FILE=${envFile}

    say "applying ${composeDir}/compose.yaml"
    ${docker} compose -f ${composeDir}/compose.yaml up -d --wait --wait-timeout 180 --remove-orphans
  '';
in
{
  homebrew.casks = [ "orbstack" ];

  launchd.user.agents.behemoth-containers = {
    command = up;
    serviceConfig = {
      RunAtLoad = true;
      KeepAlive = false;
      StandardOutPath = logFile;
      StandardErrorPath = logFile;
    };
  };

  # LM Studio's server, headless. `lms` wakes the background service and
  # returns, so this is a one-shot. It listens on this Mac only. The gateway is
  # what other machines talk to. Models load on first request and unload after
  # the idle time set in LM Studio.
  launchd.user.agents.lmstudio-server = {
    command = "${home}/.lmstudio/bin/lms server start --port 1234 --bind 127.0.0.1";
    serviceConfig = {
      RunAtLoad = true;
      KeepAlive = false;
      StandardOutPath = "${home}/Library/Logs/lmstudio-server.log";
      StandardErrorPath = "${home}/Library/Logs/lmstudio-server.log";
    };
  };
}
