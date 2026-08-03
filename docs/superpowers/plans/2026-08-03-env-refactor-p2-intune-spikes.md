# Env Refactor P2 — Intune Spikes (himmelblau vs intuneme) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Tasks 7–8 are JOINT/controller tasks — do not dispatch them to autonomous subagents.

**Goal:** Answer fork B with evidence: can a Linux VM that honestly reports its identity get corporate access on the owner's tenant — via himmelblau (B4, x86_64 + aarch64) or intuneme (B3, x86_64) — before the Aug-2026 Ubuntu-22.04 fuse burns.

**Architecture:** Throwaway NixOS guests built from a standalone spike flake (own lockfile — the main flake stays untouched). On rocinante (frozen Omarchy): bare QEMU/KVM from `nix shell`, qcow2 base + overlay disks, SSH via hostfwd, VNC bound to the tailnet only when pixels are required. On behemoth: `nix.linux-builder` (pulled forward from P7) builds the aarch64 image; Parallels VM driven entirely by `prlctl`. Everything is automated except Entra credential/MFA ceremonies, which are a scripted joint session.

**Tech Stack:** QEMU/KVM, qcow2 overlays, nixos-generators, himmelblau (flake), intuneme (Go binary + systemd-nspawn), prlctl, nix-darwin linux-builder, azure-cli.

## Global Constraints

- **Frozen-host rule:** NOTHING persistent on rocinante's Omarchy beyond `~/spikes/` — no pacman, no systemd units, no files outside `$HOME`. All tooling via `nix shell`. Spike VMs never auto-start.
- **Private-key rule:** the flake directory becomes a `/nix/store` path on build (world-readable).
  `spike.key` (private) must NEVER be synced into `~/spikes/flake/` — only `spike.key.pub`.
  Every rsync into the flake dir carries `--exclude spike.key`; verify after any sync:
  `ssh rocinante 'ls ~/spikes/flake/spike.key 2>/dev/null && echo LEAK || echo CLEAN'` → must print CLEAN.
- **Public-repo hygiene:** tenant identifiers, enrollment output, spike SSH keys, images, and raw session notes are NEVER committed. Gitignored: `spikes/intune/tenant.nix`, `spikes/intune/*.key*`, `spikes/intune/notes/`. Run `git status --short` before every commit and verify nothing sensitive is staged.
- **Nostromo (Parallels, Windows) is NEVER touched.** New Parallels VM name: `spike-himmelblau-arm`. The only allowed `prlctl` mutations are on that VM.
- **No enrollment attempt without the owner present.** Autonomous tasks stop at the "doorstep": services green, enrollment command printed, not executed.
- **Known risk to watch:** AADSTS 530003 (CA blocks enrollment of not-yet-compliant device — himmelblau issue #1132). If hit, capture the exact error and STOP that ceremony; it is a finding, not a bug to work around.
- Repo root `/Users/andreym/Documents/dotfiles` (behemoth); rocinante via `ssh rocinante` (`. /etc/profile.d/nix.sh` needed for nix in non-interactive shells). Conventional commits, direct to main, CI must stay green.
- Spike resources on rocinante: ≤ 8G RAM / 4 vCPU per VM, ≤ 60G disk total under `~/spikes/` (753G free; plenty).

---

### Task 1: Spike scaffold in the repo

**Files:**
- Create: `spikes/intune/README.md`, `spikes/intune/tenant.nix.example`, `spikes/intune/scripts/spike`
- Modify: `.gitignore`

**Interfaces:**
- Produces: the `spike` lifecycle CLI contract used by every later task: `spike build|up|down|ssh|reset|destroy|status|vnc <b4|b3>`; the gitignore guarantees; `tenant.nix` shape `{ domain = "<corp-domain>"; }`.

- [ ] **Step 1: Directory + gitignore**

```bash
cd /Users/andreym/Documents/dotfiles && mkdir -p spikes/intune/scripts spikes/intune/notes
printf '\n# P2 spike locals — never commit\nspikes/intune/tenant.nix\nspikes/intune/*.key\nspikes/intune/*.key.pub\nspikes/intune/notes/\nspikes/intune/result\n' >> .gitignore
```

- [ ] **Step 2: `tenant.nix.example`**

```nix
# Copy to tenant.nix (gitignored) and fill in. Never commit tenant.nix.
{
  # The Entra tenant's primary domain, e.g. "contoso.com"
  domain = "CHANGE-ME";
}
```

- [ ] **Step 3: The lifecycle script** — write `spikes/intune/scripts/spike` (mode 755). It runs ON ROCINANTE (task 2 copies it); one file, subcommands, no daemons:

```bash
#!/usr/bin/env bash
# P2 spike VM lifecycle. Runs on rocinante. Usage: spike <cmd> <b4|b3>
set -euo pipefail
CMD="${1:?usage: spike <build|up|down|ssh|reset|destroy|status|vnc> <b4|b3>}"
VM="${2:?usage: spike <cmd> <b4|b3>}"
DIR="$HOME/spikes/$VM"; BASE="$DIR/base.qcow2"; OVL="$DIR/overlay.qcow2"
PID="$DIR/qemu.pid"; MON="$DIR/monitor.sock"
FLAKE="$HOME/spikes/flake"           # synced copy of spikes/intune (task 2)
case "$VM" in b4) SSHPORT=2241; VNC=41;; b3) SSHPORT=2231; VNC=31;; esac
TSIP="$(tailscale ip -4 2>/dev/null | head -1)"
QEMU=(nix shell nixpkgs#qemu --command qemu-system-x86_64)
QIMG=(nix shell nixpkgs#qemu --command qemu-img)

running() { [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; }

case "$CMD" in
  build)
    mkdir -p "$DIR"
    nix build "$FLAKE#$VM-image" -o "$DIR/result"
    cp --no-preserve=mode "$(find -L "$DIR/result" -name '*.qcow2' | head -1)" "$BASE"
    rm -f "$OVL"; echo "base image rebuilt: $BASE" ;;
  up)
    running && { echo "already running (pid $(cat "$PID"))"; exit 0; }
    [ -f "$OVL" ] || "${QIMG[@]}" create -f qcow2 -b "$BASE" -F qcow2 "$OVL"
    GFX=(-display none)
    [ "$VM" = b3 ] && GFX=(-device virtio-vga -display none -vnc "$TSIP:$VNC")
    "${QEMU[@]}" -enable-kvm -machine q35 -cpu host -smp 4 -m 8G \
      -drive file="$OVL",if=virtio \
      -nic user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:$SSHPORT-:22 \
      -monitor unix:"$MON",server,nowait -serial file:"$DIR/serial.log" \
      "${GFX[@]}" -daemonize -pidfile "$PID"
    echo "up: ssh port 127.0.0.1:$SSHPORT (jump via rocinante)"; ;;
  vnc)  # attach a tailnet VNC display to a running b4 too, if ever needed
    echo "b3 serves VNC at $TSIP:$((5900+VNC)) while up. macOS: open vnc://$TSIP:$((5900+VNC))" ;;
  down)    running && kill "$(cat "$PID")"; rm -f "$PID"; echo down ;;
  reset)   running && kill "$(cat "$PID")" || true; rm -f "$PID" "$OVL"; echo "reset to doorstep (overlay dropped)" ;;
  destroy) running && kill "$(cat "$PID")" || true; rm -rf "$DIR"; echo destroyed ;;
  ssh)     exec ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
             -i "$HOME/spikes/spike.key" -p "$SSHPORT" root@127.0.0.1 ;;
  status)  running && echo "RUNNING pid=$(cat "$PID")" || echo STOPPED
           ls -lh "$BASE" "$OVL" 2>/dev/null || true ;;
esac
```

- [ ] **Step 4: Generate the spike SSH keypair (gitignored)**

```bash
ssh-keygen -t ed25519 -N '' -C p2-spike -f /Users/andreym/Documents/dotfiles/spikes/intune/spike.key
git check-ignore spikes/intune/spike.key spikes/intune/spike.key.pub && echo IGNORED-OK
```

Expected: `IGNORED-OK` (both lines printed then the marker).

- [ ] **Step 5: README** — write `spikes/intune/README.md`: one paragraph (what P2 is, pointer to this plan, the never-commit list, the `spike` CLI contract, "everything here is throwaway — deleted at P2 close except the verdict").

- [ ] **Step 6: Commit the scaffold**

```bash
cd /Users/andreym/Documents/dotfiles && git status --short   # VERIFY: no tenant.nix, no *.key anywhere in output
git add .gitignore spikes/intune/README.md spikes/intune/tenant.nix.example spikes/intune/scripts/spike
git commit -m "feat(spikes): P2 scaffold — lifecycle CLI, tenant template, hygiene guards"
git push
```

---

### Task 2: Spike flake + base x86_64 image boots on rocinante

**Files:**
- Create: `spikes/intune/flake.nix`, `spikes/intune/base.nix` (+ `flake.lock` generated)

**Interfaces:**
- Consumes: Task 1's `spike` CLI, keypair, tenant shape.
- Produces: flake outputs `packages.x86_64-linux.{b4-image,b3-image}` and `packages.aarch64-linux.b4-image` (qcow2, EFI); a booted-and-SSH-reachable base proving the whole lifecycle loop.

- [ ] **Step 1: Write `spikes/intune/base.nix`** — shared guest baseline:

```nix
{ lib, pkgs, ... }: {
  services.openssh.enable = true;
  services.openssh.settings.PermitRootLogin = "prohibit-password";
  users.users.root.openssh.authorizedKeys.keyFiles = [ ./spike.key.pub ];
  networking.useDHCP = lib.mkDefault true;
  networking.firewall.enable = false;          # throwaway spike guests only
  time.timeZone = "America/Los_Angeles";
  environment.systemPackages = with pkgs; [ vim curl jq azure-cli ];
  boot.kernelParams = [ "console=ttyS0" ];     # serial.log gets boot output
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;
  system.stateVersion = "25.05";
}
```

- [ ] **Step 2: Write `spikes/intune/flake.nix`** — standalone (own lock; main flake untouched):

```nix
{
  description = "P2 Intune spikes (throwaway)";
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    nixos-generators = { url = "github:nix-community/nixos-generators"; inputs.nixpkgs.follows = "nixpkgs"; };
    himmelblau = { url = "github:himmelblau-idm/himmelblau"; inputs.nixpkgs.follows = "nixpkgs"; };
  };
  outputs = { self, nixpkgs, nixos-generators, himmelblau }:
    let
      mkImage = system: modules: nixos-generators.nixosGenerate {
        inherit system modules; format = "qcow-efi";
      };
      b4mods = [ ./base.nix ./b4-himmelblau.nix { _module.args.himmelblauFlake = himmelblau; } ];
    in {
      packages.x86_64-linux = {
        base-image = mkImage "x86_64-linux" [ ./base.nix ];
        b4-image   = mkImage "x86_64-linux" b4mods;
        b3-image   = mkImage "x86_64-linux" [ ./base.nix ./b3-intuneme.nix ];
      };
      packages.aarch64-linux.b4-image = mkImage "aarch64-linux" b4mods;
    };
}
```

(`b4-himmelblau.nix` / `b3-intuneme.nix` arrive in Tasks 3/4; for THIS task, temporarily point `b4-image`/`b3-image` at `[ ./base.nix ]` so the flake evaluates, or build only `base-image`.)

- [ ] **Step 3: Sync to rocinante and build the base image there**

```bash
rsync -a --delete --exclude notes/ --exclude spike.key /Users/andreym/Documents/dotfiles/spikes/intune/ rocinante:spikes/flake/
rsync -a /Users/andreym/Documents/dotfiles/spikes/intune/scripts/spike rocinante:spikes/spike
rsync -a /Users/andreym/Documents/dotfiles/spikes/intune/spike.key rocinante:spikes/spike.key
ssh rocinante 'chmod 700 spikes && chmod 600 spikes/spike.key && chmod 755 spikes/spike'
ssh rocinante '. /etc/profile.d/nix.sh; cd spikes/flake && nix flake lock && nix build .#base-image -o /tmp/base-test && ls -lh $(find -L /tmp/base-test -name "*.qcow2")'
```

Expected: a qcow2 path, ~2-3 GB. (First build ~10-20 min.) Then copy the generated `flake.lock` back: `rsync rocinante:spikes/flake/flake.lock /Users/andreym/Documents/dotfiles/spikes/intune/flake.lock`.

- [ ] **Step 4: Prove the full lifecycle loop with the base image**

```bash
ssh rocinante '. /etc/profile.d/nix.sh; mkdir -p ~/spikes/b4 && cp --no-preserve=mode $(find -L /tmp/base-test -name "*.qcow2"|head -1) ~/spikes/b4/base.qcow2 && ~/spikes/spike up b4 && sleep 45'
ssh -o ProxyJump=rocinante -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -i /Users/andreym/Documents/dotfiles/spikes/intune/spike.key -p 2241 root@127.0.0.1 'uname -a && systemctl is-system-running'
ssh rocinante '~/spikes/spike reset b4 && ~/spikes/spike status b4'
```

Expected: NixOS uname; `running` (or `degraded` — note why if so); reset reports overlay dropped. This proves: build → up → ssh-from-behemoth → reset. If SSH times out, read `~/spikes/b4/serial.log` for boot state — that's the debugging channel.

- [ ] **Step 5: Commit** — `git add spikes/intune/{flake.nix,flake.lock,base.nix}` (verify `git status --short` clean of secrets) → `git commit -m "feat(spikes): base spike image + proven QEMU lifecycle on rocinante"` → push.

---

### Task 3: B4 guest — himmelblau to the doorstep (x86_64)

**Files:**
- Create: `spikes/intune/b4-himmelblau.nix`
- Modify: `spikes/intune/flake.nix` (point `b4-image` at the real module list, if stubbed)

**Interfaces:**
- Consumes: base image lifecycle; `tenant.nix` (owner fills real domain before the joint session).
- Produces: a b4 VM where `himmelblaud` runs green and the enrollment procedure is a printed checklist. Doorstep = services healthy + `aad-tool`/`himmelblau` CLI present + NO enrollment attempted.

- [ ] **Step 1: Reconcile module options against upstream (research step — upstream API may have moved).**

```bash
cd /Users/andreym/Documents/dotfiles/spikes/intune
nix flake show github:himmelblau-idm/himmelblau 2>/dev/null | head -30
nix eval github:himmelblau-idm/himmelblau#nixosModules --apply builtins.attrNames 2>/dev/null
curl -sL https://raw.githubusercontent.com/himmelblau-idm/himmelblau/main/nix/README.md 2>/dev/null | head -60 || true
```

Record: the exact `nixosModules.<name>` attr and the option namespace (`services.himmelblau.*` expected: `enable`, `settings.domains`, pam/nss wiring). Adapt Step 2 to what upstream actually ships TODAY — the snippet below is the best-known shape, not gospel; keeping the *intent* (enable + tenant domain + PAM/NSS + broker DBus) is the requirement.

- [ ] **Step 2: Write `spikes/intune/b4-himmelblau.nix`**

```nix
{ pkgs, himmelblauFlake, ... }:
let tenant = import ./tenant.nix; in {
  imports = [ himmelblauFlake.nixosModules.himmelblau ];
  services.himmelblau = {
    enable = true;
    settings = {
      domains = [ tenant.domain ];
      pam_allow_groups = [ ];        # spike: no group gating
    };
  };
  # Broker DBus + a browser-less auth test path:
  environment.systemPackages = [ pkgs.azure-cli ];
}
```

- [ ] **Step 3: Owner fills `tenant.nix`** — controller asks the owner for the tenant domain (or copies `tenant.nix.example` and the owner edits). Verify `git check-ignore spikes/intune/tenant.nix` → ignored.

- [ ] **Step 4: Build, boot, verify doorstep**

```bash
rsync -a --delete --exclude notes/ --exclude spike.key /Users/andreym/Documents/dotfiles/spikes/intune/ rocinante:spikes/flake/
ssh rocinante '. /etc/profile.d/nix.sh; ~/spikes/spike destroy b4 || true; ~/spikes/spike build b4 && ~/spikes/spike up b4 && sleep 45'
ssh -o ProxyJump=rocinante -i spikes/intune/spike.key -p 2241 root@127.0.0.1 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  'systemctl status himmelblaud --no-pager | head -8; which aad-tool broker himmelblau 2>/dev/null; journalctl -u himmelblaud --no-pager | tail -15'
```

Expected: `himmelblaud` active (or cleanly waiting for enrollment — record which); CLI tools on PATH; journal shows config parsed for the tenant domain, no crash loop.

- [ ] **Step 5: Produce the doorstep checklist** — write `spikes/intune/notes/b4-doorstep.md` (LOCAL, gitignored): the exact enrollment command sequence per upstream docs (expected shape: `aad-tool enroll --domain <domain>` or first-PAM-login flow + device-code URL), the verification commands for after (`aad-tool status`, `journalctl -u himmelblaud`), and the AADSTS 530003 watch-item. This file is the script for Task 7's ceremony.

- [ ] **Step 6: Commit** (flake + b4 module only; `git status --short` verified) — `git commit -m "feat(spikes): b4 himmelblau guest to enrollment doorstep"` → push.

---

### Task 4: B3 guest — intuneme to the doorstep (x86_64)

**Files:**
- Create: `spikes/intune/b3-intuneme.nix`

**Interfaces:**
- Consumes: base image lifecycle; VNC display path from the `spike` CLI (b3 boots with virtio-vga + tailnet VNC).
- Produces: a b3 VM where intuneme has provisioned its Ubuntu container and can present Edge/Company-Portal UI over VNC. Doorstep = container provisioned + UI reachable + NO sign-in attempted. **This task is exploratory: intuneme is unproven on NixOS — a well-documented failure is a valid deliverable.**

- [ ] **Step 1: Research intuneme's install/run contract (concrete, time-boxed)**

```bash
gh api repos/frostyard/intuneme/releases/latest --jq '.tag_name, (.assets[].name)'
curl -sL https://raw.githubusercontent.com/frostyard/intuneme/main/README.md | head -120
```

Record: binary asset name for linux/amd64, whether it's static (expect Go static → runs on NixOS as-is), the provision/run subcommands, what host paths it binds (Wayland socket, PipeWire, GPU), where state lives (`~/Intune`).

- [ ] **Step 2: Write `spikes/intune/b3-intuneme.nix`** — nspawn prereqs + a minimal Wayland seat for the UI + the pinned binary:

```nix
{ pkgs, lib, ... }:
let
  intuneme = pkgs.stdenv.mkDerivation rec {
    pname = "intuneme"; version = "REPLACE-WITH-LATEST-TAG";
    src = pkgs.fetchurl {
      url = "https://github.com/frostyard/intuneme/releases/download/${version}/REPLACE-ASSET-NAME";
      hash = lib.fakeHash;   # first build prints the real hash; substitute it
    };
    dontUnpack = true; installPhase = "install -Dm755 $src $out/bin/intuneme";
  };
in {
  environment.systemPackages = [ intuneme pkgs.cage pkgs.foot ];
  systemd.services."cage-spike" = {            # minimal kiosk Wayland session on tty1
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {
      ExecStart = "${pkgs.cage}/bin/cage -- ${pkgs.foot}/bin/foot";
      TTYPath = "/dev/tty1"; User = "root"; PAMName = "login";
      StandardInput = "tty"; TTYReset = true; TTYVHangup = true;
    };
    environment.XDG_RUNTIME_DIR = "/run/spike";
  };
  systemd.tmpfiles.rules = [ "d /run/spike 0700 root root" ];
  virtualisation.vmVariant = { };               # no-op; nspawn ships with systemd
  networking.nat.enable = true;                 # container egress
}
```

(Adapt to Step 1 findings — the *requirement* is: intuneme binary present, nspawn workable, a Wayland compositor on the virtio-vga output so Edge can draw, all visible over the b3 VNC display.)

- [ ] **Step 3: Build, boot, provision, verify UI path**

```bash
rsync -a --delete --exclude notes/ --exclude spike.key spikes/intune/ rocinante:spikes/flake/
ssh rocinante '. /etc/profile.d/nix.sh; ~/spikes/spike build b3 && ~/spikes/spike up b3 && sleep 45'
# in-guest: run intuneme provision (downloads Ubuntu rootfs; give it time), then status
ssh -o ProxyJump=rocinante -i spikes/intune/spike.key -p 2231 root@127.0.0.1 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  'WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/spike intuneme provision 2>&1 | tail -20; machinectl list'
```

Then from behemoth: `open vnc://<rocinante-tailnet-ip>:5931` — expected: the cage/foot session visible. Record every friction point in `spikes/intune/notes/b3-doorstep.md` (LOCAL): what worked, what needed manual poking (each manual poke is a scoring demerit for B3 in the verdict), the exact command that will launch the portal UI in the ceremony.

- [ ] **Step 4: If blocked >2 focused hours on NixOS-specific breakage** (nspawn/rootfs/Wayland-binding), STOP: write up the precise failure in the notes, mark B3 "did not reach doorstep on NixOS" — that is a legitimate spike verdict, not a task failure. Report DONE_WITH_CONCERNS.

- [ ] **Step 5: Commit** module (verify no secrets staged) — `git commit -m "feat(spikes): b3 intuneme guest (nspawn + kiosk wayland + vnc)"` → push.

---

### Task 5: linux-builder on behemoth (pulled forward from P7)

**Files:**
- Modify: `hosts/behemoth/default.nix`

**Interfaces:**
- Produces: behemoth can build `aarch64-linux` derivations — Task 6 depends on it; P7/P9 inherit it.

- [ ] **Step 1: Enable the builder** — in `hosts/behemoth/default.nix`, inside the darwin config section (same level as `nix.enable = false;` — note: with Determinate, `nix.enable = false` means nix-darwin does not manage the Nix installation; verify `nix.linux-builder` is still honored, see Step 3 fallback):

```nix
    nix.linux-builder = {
      enable = true;
      ephemeral = true;
      maxJobs = 4;
      config.virtualisation = { cores = 4; memorySize = 6144; };
    };
```

- [ ] **Step 2: Switch**

Run: `just switch` — expected: activation succeeds, `linux-builder` launchd job appears (`launchctl list | grep linux-builder`).

- [ ] **Step 3: Verify an actual aarch64-linux build**

```bash
nix build --impure --expr '(import <nixpkgs> { system = "aarch64-linux"; }).hello' -o /tmp/hello-arm 2>&1 | tail -3 && file $(readlink /tmp/hello-arm)/bin/hello
```

Expected: `... ELF 64-bit LSB executable, ARM aarch64 ...`.
**Fallback if `nix.linux-builder` conflicts with `nix.enable = false`** (evaluation error saying the module requires nix-darwin-managed Nix): use Determinate's native mechanism instead — `determinate-nixd` ships built-in Linux builder support; enable per `docs.determinate.systems` (`nixd` config `builders`), verify with the same `nix build` probe, and record the deviation in the task report.

- [ ] **Step 4: Commit** — `git commit -m "feat(behemoth): aarch64-linux builder (pulled forward from P7 for spike + VM image builds)"` → push; confirm CI `build-behemoth` stays green (the builder config must evaluate on the CI runner even though the VM never starts there).

---

### Task 6: aarch64 B4 image → Parallels VM, fully scripted

**Files:**
- Create: `spikes/intune/scripts/spike-parallels` (mode 755)

**Interfaces:**
- Consumes: Task 5's builder; Task 3's b4 module (same one — that's the point: identical config, second architecture).
- Produces: Parallels VM `spike-himmelblau-arm` bootable to the same doorstep, lifecycle: `spike-parallels <build|create|up|down|reset|destroy|status>`.

- [ ] **Step 1: Build the aarch64 image on behemoth**

```bash
cd /Users/andreym/Documents/dotfiles/spikes/intune && nix build .#packages.aarch64-linux.b4-image -o result-arm && ls -lh $(find -L result-arm -name '*.qcow2')
```

Expected: aarch64 qcow2 (builder does the heavy lifting; first run slow).

- [ ] **Step 2: Write `spikes/intune/scripts/spike-parallels`** — attempt A converts qcow2 → Parallels-native disk via `qemu-img -O parallels`; the script:

```bash
#!/usr/bin/env bash
set -euo pipefail
VMNAME="spike-himmelblau-arm"; PVMDIR="$HOME/Parallels/$VMNAME.pvm"
SRC="$(cd "$(dirname "$0")/.." && pwd)"
CMD="${1:?usage: spike-parallels <build|create|up|down|reset|destroy|status|ip>}"
case "$CMD" in
  build)   (cd "$SRC" && nix build .#packages.aarch64-linux.b4-image -o result-arm) ;;
  create)
    prlctl list "$VMNAME" >/dev/null 2>&1 && { echo "exists — destroy first"; exit 1; }
    QCOW="$(find -L "$SRC/result-arm" -name '*.qcow2' | head -1)"
    prlctl create "$VMNAME" --distribution linux --no-hdd
    prlctl set "$VMNAME" --cpus 4 --memsize 8192 --efi-boot on
    mkdir -p "$PVMDIR/spike.hdd"
    nix shell nixpkgs#qemu --command qemu-img convert -O parallels "$QCOW" "$PVMDIR/spike.hdd/spike.hds"
    # DiskDescriptor: let prlctl adopt the disk
    prl_disk_tool convert --hdd "$PVMDIR/spike.hdd" 2>/dev/null || true
    prlctl set "$VMNAME" --device-add hdd --image "$PVMDIR/spike.hdd"
    prlctl snapshot "$VMNAME" -n doorstep -d "clean pre-enrollment state" ;;
  up)      prlctl start "$VMNAME" ;;
  down)    prlctl stop "$VMNAME" --kill ;;
  reset)   prlctl snapshot-switch "$VMNAME" --id "$(prlctl snapshot-list "$VMNAME" | awk '/doorstep/{print $NF}' | tr -d '{}')" 2>/dev/null \
            || prlctl snapshot-switch "$VMNAME" -n doorstep ;;
  destroy) prlctl stop "$VMNAME" --kill 2>/dev/null || true; prlctl delete "$VMNAME" ;;
  status)  prlctl list -i "$VMNAME" | grep -E 'State|ip_configured' ;;
  ip)      prlctl exec "$VMNAME" ip -4 addr show 2>/dev/null || echo "use: prlctl list -f -o name,ip_configured" ;;
esac
```

- [ ] **Step 3: Create, boot, verify SSH + himmelblaud** — `spike-parallels create && spike-parallels up`, get the IP (`prlctl list -f -o name,ip_configured`), then `ssh -i spikes/intune/spike.key root@<ip> 'systemctl status himmelblaud --no-pager | head -5'`. Expected: same doorstep as Task 3.
  **Fallback (attempt B) if the converted disk won't boot** (qemu-img's parallels writer is old-format; Parallels 26 may reject it): `prlctl create` with the stock NixOS aarch64 ISO attached (`--device-add cdrom --image ~/vm-isos/...`), boot, set a root password at the console (THE one manual step, done by controller via Parallels console), then from behemoth run `nix run github:nix-community/nixos-anywhere -- --flake ./spikes/intune#b4-arm root@<vm-ip>` — requires adding a matching `nixosConfigurations.b4-arm` (base+b4 modules + disko single-disk layout) to the spike flake; add it in this step if attempt B is needed. Record which path won in the notes; snapshot `doorstep` either way.

- [ ] **Step 4: Commit** the script — `git commit -m "feat(spikes): parallels lifecycle for aarch64 himmelblau spike"` → push.

---

### Task 7 [JOINT SESSION — controller + owner; never a subagent]: Enrollment ceremonies

**Files:** `spikes/intune/notes/session.md` (LOCAL) — the live protocol + results log.

**Protocol** (controller drives, owner authenticates; ~30-60 min):

- [ ] **Step 1: Pre-flight** (controller, just before the session): all three VMs at doorstep (`spike status b4`, `spike status b3`, `spike-parallels status`); `tenant.nix` filled; notes files ready; owner confirms Nostromo untouched and available as fallback if anything corporate is needed mid-session.
- [ ] **Step 2: B4-x86 ceremony.** Controller runs the enrollment command from `notes/b4-doorstep.md` in the guest over SSH; expected: a device-code URL + code. Owner opens the URL **in a browser on behemoth**, signs in, MFA. Controller then captures: `aad-tool status` (or equivalent), `journalctl -u himmelblaud | tail -40`, device visible in Entra? (owner checks https://myaccount.microsoft.com/device-list or Company Portal web), compliance state after ~10 min grace. **If AADSTS 530003:** capture verbatim, stop this ceremony, note the finding.
- [ ] **Step 3: B4-x86 acceptance tests** (each PASS/FAIL logged): (a) compliance shows Compliant; (b) CA-gated access: `az login` in-guest via broker (or device-code if broker path unavailable — note which) then `az account get-access-token --resource https://graph.microsoft.com` succeeds; (c) reboot survival: `spike down b4 && spike up b4`, re-check status without re-enrolling; (d) ergonomics notes.
- [ ] **Step 4: B3 ceremony** (if it reached doorstep). Owner connects `open vnc://<rocinante-ts-ip>:5931`; controller launches the portal per `notes/b3-doorstep.md`; owner signs into Company Portal in the container's Edge. Same acceptance battery, plus: does the tenant see a genuine "Ubuntu 24.04" device; SSO brokering to host observed or not.
- [ ] **Step 5: B4-arm ceremony** on the Parallels VM — same as Steps 2-3 with the VM's tailnet-free local IP; owner browser on behemoth. This answers the P9 question (Mac-side Linux corp VM) directly.
- [ ] **Step 6: Reset discipline.** After each failed/aborted attempt: `spike reset <vm>` / `spike-parallels reset` before retrying — every ceremony starts from the clean doorstep snapshot. Log every attempt (timestamp, action, error verbatim) in `notes/session.md`.

---

### Task 8 [Controller]: Verdict + spec update + teardown decision

**Files:**
- Create: `docs/superpowers/specs/2026-08-XX-p2-spike-verdict.md` (SANITIZED — no tenant IDs, no device IDs, no error payloads beyond AADSTS codes)
- Modify: `docs/superpowers/specs/2026-07-23-environment-refactor-design.md` (fork B row: replace "spike-driven" with the verdict)

- [ ] **Step 1: Score both spikes** against the spec's bar — enrolled / Compliant / CA-gated resource opens / survives reboot / ergonomics — as a table with PASS/FAIL/NOT-REACHED per cell, x86 and arm columns for B4. Include: manual-intervention count per spike (the automation demerits), and the P9 implication (himmelblau-on-aarch64 result decides whether stargazer's successor gets a corp layer).
- [ ] **Step 2: Write the verdict doc** with: the winner for P8's work-VM (or "neither — Ubuntu baseline becomes work-VM" per the spec's collapse rule), evidence per cell, risks accepted, and the exact spike-flake modules P8 should inherit.
- [ ] **Step 3: Update the spec's fork-B row** to reference the verdict doc; commit both (sanitization check: `grep -iE 'tenant|@|AADSTS|device-id' <verdict-doc>` reviewed line-by-line before staging).
- [ ] **Step 4: Teardown decision with the owner:** winner VM may stay (it seeds P8); losers destroyed (`spike destroy`, `spike-parallels destroy`); `~/spikes` on rocinante kept only if P8 is imminent. The spike flake + scripts stay in the repo either way (they're P8 inputs).
- [ ] **Step 5: Update project memory** (`project_env_refactor.md`): P2 outcome, verdict pointer, P8 shape now determined.

---

## Completion checklist (report to owner)

- Verdict table (the actual deliverable of P2) + link to sanitized verdict doc.
- Automation audit: every step that required a human beyond Entra ceremonies, listed (target: zero).
- The Aug-fuse status: does the owner now have a post-22.04 corporate path on Linux, and what is it?
- linux-builder live on behemoth (P7 item, done early).
- What was torn down vs kept, and current disk deltas on both machines.
