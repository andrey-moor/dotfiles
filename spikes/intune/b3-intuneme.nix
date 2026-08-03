{ pkgs, lib, ... }:
let
  # Step 1 research findings (github:frostyard/intuneme, docs.frostyard.github.io/intuneme,
  # release v0.19.0 — checked 2026-08-03), vs. the brief's guesses:
  #
  #   - The `linux_amd64` release asset is a **tarball**
  #     (`intuneme_0.19.0_linux_amd64.tar.gz`), not a bare binary — it contains
  #     LICENSE/README/shell-completions/manpage alongside `intuneme`. The
  #     brief's `dontUnpack = true; installPhase = "install -Dm755 $src ..."`
  #     snippet assumed a bare-binary asset and would fail against the real
  #     asset shape.
  #   - The binary itself IS a statically linked Go executable (confirmed via
  #     `file`: "ELF 64-bit LSB executable, x86-64, statically linked, Go
  #     BuildID=...") — runs on NixOS as-is, no autoPatchelfHook/FHS wrapper
  #     needed for `intuneme` itself.
  #   - BUT `intuneme` is an *orchestrator*, not a self-contained doorstep.
  #     Per its own docs it requires, on the host: a container engine to pull
  #     an OCI image (podman preferred), systemd-nspawn + machinectl
  #     ("systemd-container" package on Debian/Fedora), polkit (it installs
  #     its own passwordless-machinectl rule at `init` time), a *running*
  #     graphical session (X11 or Wayland — it does not provide one), and
  #     PipeWire/PulseAudio for audio forwarding. None of this is mentioned in
  #     the brief's snippet, which only accounted for the Wayland-kiosk half.
  #   - There is no `provision` subcommand. The real verbs are
  #     `init` (provision: pulls ghcr.io/frostyard/ubuntu-intune, extracts
  #     rootfs, installs Edge + Intune Portal *inside* the container, creates
  #     a container user mapped to the host UID, installs the polkit rule),
  #     `start`/`stop`/`shell`/`status`/`destroy`/`recreate`, and
  #     `open edge` / `open portal` to launch the two UIs. State lives at
  #     `~/.local/share/intuneme/` (config.toml, rootfs/, runtime/) plus a
  #     persistent `~/Intune/` bind-mounted as the container user's home.
  version = "0.19.0";

  intuneme = pkgs.stdenv.mkDerivation {
    pname = "intuneme";
    inherit version;
    src = pkgs.fetchurl {
      url = "https://github.com/frostyard/intuneme/releases/download/v${version}/intuneme_${version}_linux_amd64.tar.gz";
      # Real hash (computed locally with `nix hash file` against the fetched
      # release asset, not printed via a wasted lib.fakeHash build round trip).
      hash = "sha256-IjZYioo+Cm4oCiioFCVfYwMm4dylOSKdhUUMspGHyi0=";
    };
    # The tarball has no single wrapping directory (LICENSE, README.md,
    # completions/, manpages/, and `intuneme` all sit at its top level), so
    # stdenv's default unpackPhase can't auto-select a source root ("unpacker
    # produced multiple directories") -- tell it to stay put instead of
    # guessing.
    sourceRoot = ".";
    installPhase = ''
      runHook preInstall
      install -Dm755 intuneme $out/bin/intuneme
      installManPage manpages/intuneme.1.gz
      installShellCompletion completions/intuneme.bash \
        completions/intuneme.zsh \
        completions/intuneme.fish
      runHook postInstall
    '';
    nativeBuildInputs = [ pkgs.installShellFiles ];
  };
in
{
  # --- intuneme's real prerequisites ---

  # Container engine: podman is upstream's preferred choice for pulling +
  # extracting the Ubuntu OCI rootfs at `init` time. NixOS auto-assigns
  # subuid/subgid ranges to normal users by default (isNormalUser + no
  # explicit subUidRanges/subGidRanges => autoSubUidGidRange = true), so no
  # extra rootless-podman wiring should be needed beyond enabling it and
  # putting the spike user in the right group.
  virtualisation.podman.enable = true;
  virtualisation.containers.enable = true;

  # systemd-nspawn + machinectl ("systemd-container" package on Debian/
  # Fedora) — the binaries ship with `systemd` itself either way, but this
  # wires machines.target and documents the intent explicitly.
  boot.enableContainers = true;

  # intuneme's `init` installs its own polkit rule for passwordless
  # machinectl use by the container user — needs polkit actually running.
  security.polkit.enable = true;

  # PipeWire audio forwarding into the container (upstream prefers PipeWire
  # over PulseAudio).
  security.rtkit.enable = true;
  services.pipewire = {
    enable = true;
    alsa.enable = true;
    pulse.enable = true;
  };

  # intuneme expects "a running graphical session" already present on the
  # host — it does not start one itself. cage (minimal wlroots kiosk
  # compositor) + foot (terminal, to drive the CLI over the same session)
  # stand in for a desktop environment, on the virtio-vga KMS device the
  # `spike` CLI already wires up for b3's VNC display. Runs as the normal
  # "spike" user (not root) via a real login session, since intuneme itself
  # must run as a normal host user (it maps host UID -> container UID) and
  # rootless podman needs a real user session too.
  environment.systemPackages = [ pkgs.cage pkgs.foot pkgs.mesa intuneme ];

  users.users.spike = {
    isNormalUser = true;
    uid = 1000;
    extraGroups = [ "wheel" "podman" "video" "render" "audio" ];
  };
  security.sudo.wheelNeedsPassword = false;

  systemd.services."cage-spike" = {
    description = "Kiosk Wayland session for the intuneme spike (tty1)";
    wantedBy = [ "multi-user.target" ];
    conflicts = [ "getty@tty1.service" ];
    after = [ "systemd-user-sessions.service" "getty@tty1.service" ];
    serviceConfig = {
      ExecStart = "${pkgs.cage}/bin/cage -- ${pkgs.foot}/bin/foot";
      User = "spike";
      PAMName = "login";
      TTYPath = "/dev/tty1";
      TTYReset = true;
      TTYVHangup = true;
      TTYVTDisallocate = true;
      StandardInput = "tty";
      StandardOutput = "journal";
      StandardError = "journal";
      Restart = "on-failure";
      UtmpIdentifier = "tty1";
      UtmpMode = "user";
    };
    # QEMU/virtio-vga-specific breakage found live (Aug 3, cage-spike crash-
    # looping, `systemctl --failed`): the `spike` CLI's frozen `-device
    # virtio-vga` has no virgl/GBM ("[drm] features: -virgl ..." in dmesg),
    # so wlroots' EGL/GLES2 path can't get a context, and its Vulkan
    # fallback finds only a software (llvmpipe/CPU) device that it refuses
    # to pair with the virtio_gpu DRM node ("Could not match drm and vulkan
    # device") -- cage exits 1 immediately, every time (verbatim journal in
    # notes/b3-doorstep.md). Forcing wlroots' third renderer backend
    # (Pixman, pure software, no GBM/EGL/Vulkan needed at all) sidesteps
    # both failed paths; this is a documented wlroots env var, not a
    # workaround, and does not touch the frozen `spike` CLI/QEMU invocation.
    environment.WLR_RENDERER = "pixman";
    # No hand-rolled XDG_RUNTIME_DIR here (unlike the brief's /run/spike) --
    # PAMName=login opens a real logind session for uid 1000, which sets up
    # the standard /run/user/1000 runtime dir (and the wayland-N socket
    # inside it) the same way a normal desktop login would. That's also
    # what podman/pipewire's per-user systemd units expect.
  };

  # nspawn's `--network-veth` mode names the host-side interface
  # `ve-<machine_name>`; intuneme's default machine_name is `intuneme`
  # (config.toml default, confirmed in the reference docs). NAT + firewall
  # trust it explicitly for container egress (the OCI pull itself goes out
  # over the *host's* own NAT'd nic via podman as user "spike", independent
  # of this — this is for the nspawn container's own network once started).
  networking.nat = {
    enable = true;
    internalInterfaces = [ "ve-intuneme" ];
  };
  networking.firewall.trustedInterfaces = [ "ve-intuneme" ];

  # The base qcow-efi image sizes its disk from the *build-time* closure
  # only (podman/cage/foot/pipewire/intuneme — no Ubuntu yet). intuneme's
  # `init` downloads the Ubuntu 24.04 rootfs + Edge + Intune Portal into the
  # guest's own disk at *runtime*, well past whatever "auto" would have
  # sized. Explicit headroom (sparse qcow2 — this does not cost real disk on
  # rocinante until written).
  virtualisation.diskSize = 20 * 1024;
}
