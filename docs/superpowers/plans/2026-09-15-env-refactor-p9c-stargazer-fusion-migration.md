# Env Refactor P9c: Stargazer on VMware Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Implementer subagents run on Opus. Tasks 2 to 5 are repo work for subagents. Tasks 1 and 6 to 12 need the owner at the Mac, so the controller runs them with the owner.

**Goal:** Make `nixosConfigurations.stargazer` the VMware Fusion machine, rebuild it from the runbook as a fresh VM named `stargazer`, and retire the Parallels VM and the Fusion trial VM.

**Architecture:** The trial proved the Fusion layer as a separate host, `stargazer-fusion`. This plan folds that layer into `hosts/stargazer`, removes the Parallels-only code, and rewrites the VM script and the runbook for Fusion. It then proves them by building the real machine from scratch. Repo tasks come first and are verified on behemoth by evaluation, lint and shellcheck. Operational tasks follow, with the owner typing every passphrase and PIN at the VM console.

**Tech Stack:** NixOS 26.11 flake, disko, lanzaboote, sops-nix, himmelblau 4.0.0, Hyprland 0.56.2 with the vendored vmwgfx patch, open-vm-tools 13.1.0, VMware Fusion 26.0.1 on behemoth.

**Spec:** `docs/superpowers/specs/2026-07-23-environment-refactor-design.md` (§1 stargazer row, §8 step 9) and its plan `docs/superpowers/plans/2026-09-01-env-refactor-p9-stargazer-nixos-vm.md`. The Decisions table below replaces the parts of both that assume Parallels. Trial evidence lives in commits `91458df` and `f9dd791` and in `docs/parallels-workarounds.md`.

## Decisions (2026-09-15)

| # | Decision | Source |
|---|---|---|
| D1 | stargazer runs on VMware Fusion. The trial passed Entra join, Intune compliance, Secure Boot, Firefox SSO, YubiKey WebAuthn, clipboard, resize with Retina, shared folders and audio. | Owner, 2026-09-14: migrate if the spike succeeds. Hand tests passed 2026-09-15. |
| D2 | The machine is named `stargazer`, with no suffix, in the flake, the tailnet and Entra. | Owner, 2026-09-15. |
| D3 | The Parallels VM `stargazer-nixos` is deleted. | Owner, 2026-09-15. |
| D4 | Nostromo stays on Parallels, so Parallels Desktop stays installed. | Standing rule. |
| D5 | Every stargazer signs its boot files with the one db key in `secrets/stargazer-sbctl.yaml`. On Fusion, plain lanzaboote signs, and the VM definition appends the db certificate to the firmware's default db. | Owner, 2026-09-03, for the shared key. Trial, 2026-09-14, for the mode. |
| D6 | The new VM is built only from the rewritten runbook. That build is the fire drill. | Owner, 2026-09-03: stargazer machines must be reproducible. |
| D7 | **Proposed, confirm at review:** Parallels-only code leaves the repo. That is `modules/nixos/parallels-guest.nix`, the shim mode of `modules/nixos/secureboot.nix`, `packages/shim-signed-debian/` and the Parallels VM script. Git history and `docs/parallels-workarounds.md` keep the lineage. If declined, skip Task 3 and keep `shim.enable = false` wherever Task 2 writes Secure Boot settings. | Controller proposal. |
| D8 | **Out of scope:** the old Omarchy VM `Stargazer`, and the P9b desktop spec revision. | Owner to confirm about `Stargazer`. |

## Global Constraints

- NEVER touch the Parallels VMs `Nostromo`, `spike-himmelblau-arm`, `Orrery-Win11-ARM64` or `Stargazer`. The only Parallels mutation in this plan deletes `stargazer-nixos`, UUID `{cd98232e-21b7-4426-90c2-1a0ddcc809e5}`, in Task 6.
- Fusion mutations target only the bundles `stargazer.vmwarevm` (new), `stargazer-drill.vmwarevm` (only if a drill is ever run) and `stargazer-fusion.vmwarevm` (the trial, deleted in Task 11).
- The repo is public. Never commit a tenant id, tenant domain, UPN, Entra or Intune device id, or an AADSTS payload. Tenant facts go to `spikes/intune/notes/`, which is gitignored.
- The owner types the LUKS passphrase and the Hello PIN at the VM console. Neither ever passes through SSH, a script or an agent.
- Owner-run steps: typing at the VM console, YubiKey touches, 1Password Touch ID prompts, and every action in the Tailscale, Intune and Entra admin portals.
- Implementer ceiling: repo edits, `nix eval`, `nix build` of behemoth's system, `just fmt`, `just lint` and `shellcheck`. Guest builds happen only inside a VM. Never run `just switch`. No task changes behemoth.
- At the start of Task 2, record `nix eval --raw .#darwinConfigurations.behemoth.system.drvPath`. Every repo task must leave that value unchanged. If `flake.lock` changed in between, re-record it and say so. Any other change: stop and explain.
- One commit per repo task, conventional style, ending with:
  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01KXGT9GVA7PmREkR6KhTkiu
  ```
- Push only in Tasks 7, 10 and 12, or for a repo fix found while executing Tasks 8 to 11. Every push waits for the owner to say go.
- `just fmt` must leave no diff, and `just lint` must pass on every commit.
- Text people read follows the `plain-prose` skill. That covers comments, docs and commit messages: no em-dashes, no semicolons, short literal sentences.
- Shell commands in docs use the runbook's prefixes: `behemoth$` runs on the Mac from the repo root, `iso#` in the NixOS installer, `vm#` as root in the guest and `vm$` as `andreym` in the guest's graphical session.

## File map (final state)

| Path | Change | Responsibility |
|---|---|---|
| `hosts/stargazer/default.nix` | rewrite | Fusion layer: guest module, Retina scale, Secure Boot switch, SSH on the NAT link |
| `hosts/stargazer/common.nix` | modify | gains the shared db key wiring, loses the two-host wording |
| `hosts/stargazer/disko.nix` | modify | NVMe device |
| `hosts/stargazer/hardware.nix` | modify | header comment |
| `hosts/stargazer-fusion/` | delete | folded into `hosts/stargazer` |
| `flake.nix` | modify | `stargazer-fusion` block removed |
| `modules/nixos/vmware-guest.nix` | modify | header comment |
| `modules/nixos/vm-guest.nix` | modify | header comment |
| `modules/nixos/parallels-guest.nix` | delete (D7) | |
| `modules/nixos/secureboot.nix` | rewrite (D7) | lanzaboote with the shared db key, no shim mode |
| `packages/shim-signed-debian/` | delete (D7) | |
| `scripts/stargazer-vm` | replace | Fusion lifecycle for `stargazer` and `stargazer-drill` |
| `scripts/stargazer-fusion-vm` | delete | renamed to `scripts/stargazer-vm` |
| `hosts/stargazer/README.md` | rewrite | the Fusion install runbook |
| `docs/vmware-fusion-workarounds.md` | create | lineage of every Fusion-specific piece |
| `docs/parallels-workarounds.md` | modify | retirement note |
| `docs/superpowers/specs/2026-07-23-environment-refactor-design.md` | modify | dated amendment for D1 to D4 |
| `CLAUDE.md` | modify | Hosts list and the stargazer section |

---

### Task 1: Park the shared host key in 1Password

stargazer decrypts its secrets with an SSH host key whose age form is the `&stargazer` recipient in `.sops.yaml`. Copies exist only on the two VMs this plan deletes and in a temporary session directory. Every future rebuild needs the key.

**Files:** none in the repo.

**Interfaces:**
- Produces: two 1Password Documents in the Private vault, titled `stargazer ssh host key` (the private key) and `stargazer ssh host key pub` (the public key). Tasks 5 and 8 fetch them by these exact titles.

- [ ] **Step 1: Copy the key from the trial VM into a private temp directory**

```bash
behemoth$ keydir="$(mktemp -d)"; chmod 700 "$keydir"
behemoth$ ip="$(./scripts/stargazer-fusion-vm ip)"
behemoth$ S="-o IdentitiesOnly=yes -i $HOME/.ssh/1p_personal.pub"
behemoth$ ssh $S andreym@"$ip" 'sudo cat /etc/ssh/ssh_host_ed25519_key' > "$keydir/stargazer_host_ed25519_key"
behemoth$ ssh $S andreym@"$ip" 'cat /etc/ssh/ssh_host_ed25519_key.pub' > "$keydir/stargazer_host_ed25519_key.pub"
behemoth$ chmod 600 "$keydir/stargazer_host_ed25519_key"
```

If the trial VM is suspended, resume it first with `./scripts/stargazer-fusion-vm up`.

- [ ] **Step 2: Verify that this key is the sops recipient**

```bash
behemoth$ nix run nixpkgs#ssh-to-age -- -i "$keydir/stargazer_host_ed25519_key.pub"
behemoth$ grep -oE '&stargazer age1[a-z0-9]+' .sops.yaml
behemoth$ diff <(ssh-keygen -y -f "$keydir/stargazer_host_ed25519_key" | cut -d' ' -f1-2) \
               <(cut -d' ' -f1-2 "$keydir/stargazer_host_ed25519_key.pub") && echo PAIR-OK
```

Expected: both age lines show `age12rwzaw0r2spsgzyhhnaa9vmk9q3gel3y695wyc40qa5r44g0jcdqdf4us4`, then `PAIR-OK`.

- [ ] **Step 3: Store both files (owner, Touch ID)**

```bash
behemoth$ op document create "$keydir/stargazer_host_ed25519_key" --title "stargazer ssh host key" --vault Private
behemoth$ op document create "$keydir/stargazer_host_ed25519_key.pub" --title "stargazer ssh host key pub" --vault Private
```

- [ ] **Step 4: Prove the round trip, then delete the local copies**

```bash
behemoth$ op document get "stargazer ssh host key" --vault Private --out-file "$keydir/check" \
            && cmp "$keydir/check" "$keydir/stargazer_host_ed25519_key" && echo ROUNDTRIP-OK
behemoth$ rm -f "$keydir"/*; rmdir "$keydir"
```

Expected: `ROUNDTRIP-OK`. Also delete the session copy if it still exists: `rm -f <session scratchpad>/stargazer_host_ed25519_key*`.

---

### Task 2: Make `stargazer` the Fusion host

**Files:**
- Rewrite: `hosts/stargazer/default.nix`
- Modify: `hosts/stargazer/common.nix`
- Modify: `hosts/stargazer/disko.nix` (header comment, function arguments, `device`)
- Modify: `hosts/stargazer/hardware.nix` (header comment)
- Delete: `hosts/stargazer-fusion/default.nix`
- Modify: `flake.nix` (remove lines 206 to 235, the `stargazer-fusion` block)
- Modify: `modules/nixos/vmware-guest.nix` (header comment)
- Modify: `modules/nixos/vm-guest.nix` (header comment)
- Modify: `CLAUDE.md` (Hosts list line and the stargazer section's opening paragraph)

**Interfaces:**
- Produces: `nixosConfigurations.stargazer` with `networking.hostName = "stargazer"`, disk `/dev/nvme0n1`, `virtualisation.vmware.guest.enable = true`, `modules.nixos.secureboot.enable = true`, monitor line `Virtual-1,preferred,auto,2`, and `sops.secrets."sbctl-db-key".path = "/var/lib/sbctl/keys/db/db.key"`. The flake has no `stargazer-fusion` output.

- [ ] **Step 1: Write the check**

Save as `$SCRATCH/stargazer-host-check.sh`, outside the repo:

```bash
#!/usr/bin/env bash
# Passes only when nixosConfigurations.stargazer is the Fusion host.
set -euo pipefail
cd "$HOME/Documents/dotfiles"
got=$(nix eval --json .#nixosConfigurations.stargazer.config --apply 'c: {
  host = c.networking.hostName;
  disk = c.disko.devices.disk.main.device;
  vmware = c.virtualisation.vmware.guest.enable;
  parallels = c.hardware.parallels.enable;
  secureboot = c.modules.nixos.secureboot.enable;
  dbKey = c.sops.secrets."sbctl-db-key".path;
  monitor = c.modules.nixos.desktop.monitor;
}')
want='{"dbKey":"/var/lib/sbctl/keys/db/db.key","disk":"/dev/nvme0n1","host":"stargazer","monitor":"Virtual-1,preferred,auto,2","parallels":false,"secureboot":true,"vmware":true}'
[ "$got" = "$want" ] || { echo "FAIL: $got"; exit 1; }
hosts=$(nix eval --json .#nixosConfigurations --apply builtins.attrNames)
[ "$hosts" = '["stargazer"]' ] || { echo "FAIL hosts: $hosts"; exit 1; }
nix eval --raw .#nixosConfigurations.stargazer.config.system.build.toplevel.drvPath >/dev/null
echo PASS
```

- [ ] **Step 2: Run it before changing anything**

Run: `bash "$SCRATCH/stargazer-host-check.sh"`
Expected: `FAIL: {...}` with `"disk":"/dev/sda"`, `"parallels":true` and `"vmware":false`.
Also record behemoth's derivation, per Global Constraints.

- [ ] **Step 3: Rewrite `hosts/stargazer/default.nix`**

```nix
# Stargazer -- aarch64 NixOS VM on VMware Fusion (nix-darwin's behemoth hosts it)
#
# Declarative from the ISO up: LUKS+btrfs via disko, integrated home-manager
# reusing the home/ bundles, Hyprland on vmwgfx, Entra join and Intune
# enrollment via himmelblau. Everything that does not depend on the hypervisor
# is in ./common.nix. This file is the Fusion layer. Install and ceremonies are
# in ./README.md, and docs/vmware-fusion-workarounds.md says why each Fusion
# piece exists.

{ ... }:

{
  imports = [
    ./common.nix
    ../../modules/nixos/vmware-guest.nix
  ];

  networking.hostName = "stargazer";

  # scripts/stargazer-vm sets gui.fitGuestUsingNativeDisplayResolution, so
  # Fusion gives the guest the Mac's full Retina pixel count. Scale 2 keeps
  # text at its usual size and makes it sharp. The resize follower reuses this
  # scale for every mode it applies.
  modules.nixos.desktop.monitor = "Virtual-1,preferred,auto,2";

  # Plain lanzaboote. The firmware trusts our db certificate once the VM
  # definition appends it to VMware's default db (`scripts/stargazer-vm
  # secure-boot on`, README §7). ./common.nix wires the signing key.
  modules.nixos.secureboot.enable = true;

  # SSH on Fusion's NAT network (vmnet8, reachable only from behemoth), in
  # addition to the tailnet. VMware's guest operations need a guest password,
  # which does not exist here, so this is how behemoth reaches a fresh install
  # before it joins the tailnet. Key-only as everywhere. The name follows the
  # vmxnet3 PCI slot Fusion assigns, which the .vmx keeps.
  networking.firewall.interfaces.enp2s0.allowedTCPPorts = [ 22 ];
}
```

The wayvnc address pin from the Parallels file is dropped on purpose. The new node gets a new tailnet address, and Task 10 pins it.

- [ ] **Step 4: Update `hosts/stargazer/common.nix`**

1. Replace the header's second paragraph, the one starting `Two hosts share this`, with:

```nix
# ./default.nix adds the hypervisor layer (VMware Fusion) on top: the guest
# module, the Retina scale, the Secure Boot switch and SSH on the NAT link.
```

2. In the `Deliberately absent` paragraph, replace `(a per-host choice: needs OpenGL 4.3, which Parallels does not give Linux)` with `(a per-host choice, revisited by the P9b desktop spec)`.
3. Delete the line `networking.hostName = lib.mkDefault "stargazer";`. Then remove `lib,` from the function arguments if nothing else uses it. deadnix fails on an unused argument.
4. In the `sops` block, replace the sentence `The Fusion trial reuses the same pre-generated host key, as the fire drill does.` with `Every rebuild reuses that host key, parked in 1Password (README §3).`
5. Inside the same `sops = { ... };` block, after `secrets."wayvnc-stargazer".owner = "andreym";`, add the key moved from the Parallels layer:

```nix
    # Secure Boot signing key. One key pair for every stargazer instance, so
    # the db certificate is known before a VM exists and the VM definition can
    # carry it. The private half is age-encrypted here. The public half and
    # sbctl's owner GUID are plain files in ./secureboot, placed by tmpfiles
    # below. Only the db key exists: the firmware keeps VMware's PK and KEK.
    secrets."sbctl-db-key" = {
      sopsFile = ../../secrets/stargazer-sbctl.yaml;
      key = "db.key";
      path = "/var/lib/sbctl/keys/db/db.key";
      mode = "0400";
    };
```

6. After the `sops` block, add:

```nix
  systemd.tmpfiles.rules = [
    "d /var/lib/sbctl 0700 root root -"
    "d /var/lib/sbctl/keys 0700 root root -"
    "d /var/lib/sbctl/keys/db 0700 root root -"
    "L+ /var/lib/sbctl/keys/db/db.pem - - - - ${./secureboot/db.pem}"
    "L+ /var/lib/sbctl/GUID - - - - ${./secureboot/GUID}"
  ];
```

- [ ] **Step 5: NVMe in `hosts/stargazer/disko.nix`**

Replace the header's first paragraph (the three lines starting `/dev/sda, not /dev/vda`) with:

```nix
# /dev/nvme0n1: VMware Fusion gives Arm guests an NVMe boot disk.
```

Replace `{ lib, ... }:` with `{ ... }:`. Replace the two lines:

```nix
    # mkDefault: hosts/stargazer-fusion sets /dev/nvme0n1.
    device = lib.mkDefault "/dev/sda";
```

with:

```nix
    device = "/dev/nvme0n1";
```

- [ ] **Step 6: Delete the trial host and its flake output**

```bash
git rm -r hosts/stargazer-fusion
```

In `flake.nix`, delete lines 206 to 235: from `      # The same machine on VMware Fusion (2026-09 re-platform trial); shares` through the `        };` that closes `nixosConfigurations.stargazer-fusion`, plus the blank line after it. The `formatter = forAllSystems ...` line must directly follow the `nixosConfigurations.stargazer` block's closing `};` and one blank line.

- [ ] **Step 7: Header comments**

`hosts/stargazer/hardware.nix`, lines 3 to 5 become:

```nix
# There is no hardware-configuration.nix here on purpose: the machine is a
# VMware Fusion VM whose devices are described by modules/nixos/vmware-guest.nix,
# and every filesystem comes from hosts/stargazer/disko.nix.
```

`modules/nixos/vmware-guest.nix`, lines 3 to 7 become:

```nix
# Imports the hypervisor-agnostic vm-guest.nix and adds what Fusion needs.
# stargazer's hypervisor layer since 2026-09. docs/vmware-fusion-workarounds.md
# records why each piece exists.
#
# What matters on Fusion:
```

In the same header, replace `(see hosts/stargazer-fusion for the disko device)` with `(hosts/stargazer/disko.nix)`.

`modules/nixos/vm-guest.nix`, lines 3 to 7 become:

```nix
# The initrd modules that bring the real DRM driver up before the compositor,
# the graphics stack, and the resize follower that keeps Hyprland's mode in
# step with the host window. modules/nixos/vmware-guest.nix imports this file
# and adds the Fusion plumbing. The option defaults are the tuning Parallels
# needed. Fusion overrides them.
```

- [ ] **Step 8: `CLAUDE.md`**

Hosts list line becomes `- **stargazer**: aarch64 NixOS VM on VMware Fusion (behemoth), LUKS root, Intune-enrolled`.
The heading `### Stargazer (NixOS VM on Parallels)` becomes `### Stargazer (NixOS VM on VMware Fusion)`. Its first paragraph becomes:

```markdown
Fallback devbox: aarch64 NixOS VM on VMware Fusion, declared as `nixosConfigurations.stargazer`
(`hosts/stargazer/` + `modules/nixos/`). disko LUKS2 + btrfs, integrated home-manager,
Hyprland on vmwgfx with a vendored patch, Entra join + Intune enrollment via himmelblau.
```

Leave the VM lifecycle and guest layer lines for Tasks 3 and 4.

- [ ] **Step 9: Run the check again**

Run: `bash "$SCRATCH/stargazer-host-check.sh"`
Expected: `PASS`

- [ ] **Step 10: Format, lint, and confirm behemoth is unchanged**

```bash
just fmt && git diff --stat   # fmt must change nothing it did not already
just lint
nix eval --raw .#darwinConfigurations.behemoth.system.drvPath   # equals the Step 2 value
```

- [ ] **Step 11: Commit**

```bash
git add -A hosts/stargazer hosts/stargazer-fusion flake.nix modules/nixos/vmware-guest.nix modules/nixos/vm-guest.nix CLAUDE.md
git commit
```

Message: `refactor(stargazer): make stargazer the VMware Fusion host`. The body says that the trial host's Fusion layer replaces the Parallels layer and the db key wiring moves into common.nix. It also says the flake loses `stargazer-fusion`, and that the wayvnc address pin is dropped until the new node joins the tailnet.

---

### Task 3: Remove the Parallels-only code (D7)

Skip this task if the owner declines D7.

**Files:**
- Delete: `modules/nixos/parallels-guest.nix`
- Delete: `packages/shim-signed-debian/`
- Rewrite: `modules/nixos/secureboot.nix`
- Modify: `CLAUDE.md` (the "NixOS VM guest layer" paragraph)

**Interfaces:**
- Consumes: Task 2's host, which sets only `modules.nixos.secureboot.enable`.
- Produces: `modules.nixos.secureboot` with exactly the options `enable` and `pkiBundle`.

- [ ] **Step 1: Write the check**

Save as `$SCRATCH/parallels-gone-check.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/Documents/dotfiles"
opts=$(nix eval --json .#nixosConfigurations.stargazer.options.modules.nixos.secureboot --apply builtins.attrNames)
[ "$opts" = '["enable","pkiBundle"]' ] || { echo "FAIL options: $opts"; exit 1; }
[ ! -e modules/nixos/parallels-guest.nix ] || { echo "FAIL: parallels-guest.nix exists"; exit 1; }
[ ! -e packages/shim-signed-debian ] || { echo "FAIL: shim package exists"; exit 1; }
if grep -rn -E 'parallels-guest|shim-signed-debian|shim\.enable|lzbtShim' --include='*.nix' . | grep -v '^./spikes/'; then
  echo "FAIL: references remain"; exit 1
fi
nix eval --raw .#nixosConfigurations.stargazer.config.system.build.toplevel.drvPath >/dev/null
echo PASS
```

- [ ] **Step 2: Run it**

Run: `bash "$SCRATCH/parallels-gone-check.sh"`
Expected: `FAIL options: ["enable","pkiBundle","shim"]`

- [ ] **Step 3: Delete the Parallels files**

```bash
git rm modules/nixos/parallels-guest.nix
git rm -r packages/shim-signed-debian
```

- [ ] **Step 4: Rewrite `modules/nixos/secureboot.nix`**

```nix
# modules/nixos/secureboot.nix -- opt-in Secure Boot via lanzaboote
#
# Off by default, so a host installs with plain systemd-boot. With `enable`,
# lanzaboote signs systemd-boot and the UKIs with the db key under pkiBundle.
# The key is not generated here. stargazer ships one shared db key pair
# (hosts/stargazer/common.nix, sops), and the firmware learns its certificate
# from the VM definition (`scripts/stargazer-vm secure-boot on`), which
# appends it to VMware's default db. PK and KEK stay VMware's.
#
# The bootloader installer runs BEFORE activation. So the first switch that
# introduces the key files must follow a `nixos-rebuild test`, and a fresh
# install needs the files placed under /mnt first (README §4.3b). Otherwise
# lzbt fails with "Failed to read public key" and nothing activates.
#
# Checking signatures: `sbverify --list <file>` prints the signer. Everything
# lanzaboote writes, the UKIs and EFI/systemd/systemd-*.efi, shows
# `CN=Database Key`. `sbctl verify` does not work here: it insists on
# keys/KEK/KEK.key, which the sops layout does not ship, and its Landlock
# sandbox cannot follow the key symlinks.
#
# The LUKS passphrase slot is never removed. Secure Boot serves compliance and
# is never a boot requirement. Parallels needed a shim chain instead. That mode
# was removed when stargazer moved to VMware Fusion in 2026-09, and
# docs/parallels-workarounds.md keeps its history.

{
  lib,
  config,
  pkgs,
  inputs,
  ...
}:

with lib;
let
  cfg = config.modules.nixos.secureboot;
in
{
  imports = [ inputs.lanzaboote.nixosModules.lanzaboote ];

  options.modules.nixos.secureboot = {
    enable = mkEnableOption "lanzaboote-signed boot (Secure Boot with our db key)";

    pkiBundle = mkOption {
      type = types.str;
      default = "/var/lib/sbctl";
      description = "Where sbctl keeps the signing keys.";
    };
  };

  config = mkIf cfg.enable {
    # lanzaboote replaces systemd-boot. Both cannot own the ESP.
    boot.loader.systemd-boot.enable = mkForce false;
    boot.lanzaboote = {
      enable = true;
      inherit (cfg) pkiBundle;
    };

    environment.systemPackages = with pkgs; [
      sbctl
      mokutil
      # sbverify --list is the signature check (see the header).
      sbsigntool
    ];
  };
}
```

- [ ] **Step 5: `CLAUDE.md` guest layer paragraph**

Replace the paragraph that starts `**NixOS VM guest layer:**` and ends `Moving to another virtio-gpu hypervisor means importing \`vm-guest.nix\` directly.` with:

```markdown
**NixOS VM guest layer:** `modules/nixos/vm-guest.nix` holds the graphics stack and the
`virtio-gpu-resize` follower (options `modules.nixos.vmGuest.{connector,followResize,resizePollInterval,resizeStablePolls,resizeHysteresis}`).
`modules/nixos/vmware-guest.nix` imports it and adds the Fusion pieces: the vmwgfx Hyprland
patch, open-vm-tools, the copy/paste agent and its clipboard bridge, and fast resize timing.
Another hypervisor means a new guest module that imports `vm-guest.nix`.
```

- [ ] **Step 6: Run the check**

Run: `bash "$SCRATCH/parallels-gone-check.sh"`
Expected: `PASS`

- [ ] **Step 7: Format, lint, and confirm behemoth is unchanged**

Same commands as Task 2 Step 10.

- [ ] **Step 8: Commit**

Message: `refactor(stargazer): remove the Parallels guest module and the shim chain`. The body names the three deleted pieces and points at `docs/parallels-workarounds.md` for their history.

---

### Task 4: `scripts/stargazer-vm` for Fusion

**Files:**
- Delete: `scripts/stargazer-vm` (the Parallels script)
- Rename: `scripts/stargazer-fusion-vm` to `scripts/stargazer-vm`
- Modify: the renamed script
- Modify: `CLAUDE.md` (the "VM lifecycle" line)

**Interfaces:**
- Produces the command surface that Tasks 5 and 8 to 11 use:

```
stargazer-vm [--drill] <verb>
  iso                        download and verify the NixOS aarch64 minimal ISO (no VM needed)
  create                     write the .vmx and a 256GB NVMe disk (needs the ISO)
  up | down | kill           power on in a Fusion window / soft off / hard off
  suspend | resume           suspend / resume in a Fusion window
  status | ip                power state and NAT IPv4
  screenshot <file>          capture the console
  type <text> | key <name>   type text + Return / send one key at the console
  set <key> <value>          set a .vmx entry (VM off)
  cdrom on|off               connect the ISO at the next power-on
  secure-boot on|off         append the repo db certificate and enable Secure Boot (VM off)
  snapshot <name> | restore <name> | destroy
```

- `VMNAME` is `stargazer`, or `stargazer-drill` with `--drill`. The bundle is `$HOME/Virtual Machines.localized/$VMNAME.vmwarevm`.
- The ISO lives at `$HOME/Virtual Machines.localized/iso/nixos-minimal-aarch64-linux.iso`.
- `secure-boot on` writes `$VMDIR/stargazer-db.der` from `hosts/stargazer/secureboot/db.pem`. On the first enable, it moves `$VMNAME.nvram` to `$VMNAME.nvram.pre-sb`. It sets `uefi.secureBoot.enabled = "TRUE"`, `uefi.secureBoot.dbDefault.file0 = "stargazer-db.der"` and `uefi.secureBoot.dbDefault.append = "TRUE"`. `secure-boot off` sets `uefi.secureBoot.enabled = "FALSE"` and keeps the NVRAM.

- [ ] **Step 1: Write the check**

Save as `$SCRATCH/vm-script-check.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail
cd "$HOME/Documents/dotfiles"
s=scripts/stargazer-vm
fail() { echo "FAIL: $*"; exit 1; }
grep -q '^# VMware Fusion lifecycle for the stargazer VM' "$s" || fail "not the Fusion script"
[ ! -e scripts/stargazer-fusion-vm ] || fail "old name still present"
! grep -q 'stargazer-fusion' "$s" || fail "trial name still referenced"
nix shell nixpkgs#shellcheck -c shellcheck "$s" || fail "shellcheck"
out=$("$s" 2>&1); [ $? -eq 1 ] && grep -q 'usage: stargazer-vm \[--drill\]' <<<"$out" || fail "usage"
for v in iso create up down kill suspend resume status ip screenshot type key set cdrom secure-boot snapshot restore destroy; do
  grep -qE "^  ${v}\)" "$s" || fail "verb $v missing"
done
"$s" --drill status 2>&1 | grep -q 'stargazer-drill does not exist' || fail "--drill"
"$s" secure-boot on 2>&1 | grep -q 'stargazer does not exist' || fail "secure-boot guard"
echo PASS
```

The last two checks only hold while no `stargazer` or `stargazer-drill` bundle exists, which is true before Task 8.

- [ ] **Step 2: Run it**

Run: `bash "$SCRATCH/vm-script-check.sh"`
Expected: `FAIL: not the Fusion script`

- [ ] **Step 3: Replace the script**

```bash
git rm scripts/stargazer-vm
git mv scripts/stargazer-fusion-vm scripts/stargazer-vm
sed -i '' 's/stargazer-fusion-vm/stargazer-vm/g' scripts/stargazer-vm
```

GNU sed may be first on PATH. If `sed -i ''` fails, use `sed -i 's/stargazer-fusion-vm/stargazer-vm/g' scripts/stargazer-vm`.

- [ ] **Step 4: Replace lines 1 to 31 (header and constants) with:**

```bash
#!/usr/bin/env bash
# VMware Fusion lifecycle for the stargazer VM.
#
# The VM definition lives here, not in Fusion's GUI: `create` writes the whole
# .vmx. vmcli's own `VM Create` only produces a skeleton, with no disk, NIC or
# CD-ROM. Every command targets $VMX, which can only ever be the stargazer
# bundle or, with --drill, the stargazer-drill bundle.
#
# Fusion itself cannot be declared in the flake. Broadcom's download needs a
# portal account and a trade-compliance form, and the Homebrew cask was
# disabled for that reason (docs/vmware-fusion-workarounds.md).
set -euo pipefail

VMNAME="stargazer"
if [ "${1:-}" = "--drill" ]; then
  VMNAME="stargazer-drill"
  shift
fi
case "$VMNAME" in
  stargazer | stargazer-drill) ;;
  *)
    echo "refusing to operate on '$VMNAME'" >&2
    exit 1
    ;;
esac

VMDIR="$HOME/Virtual Machines.localized/$VMNAME.vmwarevm"
VMX="$VMDIR/$VMNAME.vmx"
PUB="/Applications/VMware Fusion.app/Contents/Public"
VMCLI="$PUB/vmcli"
VMRUN="$PUB/vmrun"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

ISO_DIR="$HOME/Virtual Machines.localized/iso"
ISO="$ISO_DIR/nixos-minimal-aarch64-linux.iso"
ISO_URL="https://channels.nixos.org/nixos-unstable/latest-nixos-minimal-aarch64-linux.iso"

# behemoth is 16 cores / 128 GB, and Nostromo (Parallels) takes 10 / 64.
CPUS=8
MEMSIZE=16384
DISK_SIZE="256GB"
MIN_FREE_GB=150
GRAPHICS_MEMORY_KB=4194304
```

- [ ] **Step 5: Replace the `usage()` function body's text with:**

```bash
usage() {
  cat >&2 <<EOF
usage: stargazer-vm [--drill] <verb> [args]

  iso                   download and verify the NixOS aarch64 minimal ISO
  create                write the .vmx and a ${DISK_SIZE} growable NVMe disk (refuses if
                        the VM exists, the ISO is missing, or ~ has less than ${MIN_FREE_GB} GB free)
  up                    power on in a Fusion window
  down | kill           soft / hard power off
  suspend | resume      suspend / resume in a Fusion window
  status                power state, IP
  ip                    guest IPv4 from Fusion's NAT DHCP leases
  screenshot <file>     capture the console
  type <text>           type <text> + Return at the console
  key <name>            send one key: enter esc tab backspace space up down left right
                        f1..f12 ctrl-c ctrl-d
  set <key> <value>     set a .vmx entry (VM must be off)
  cdrom on|off          connect or disconnect the installer ISO at next power-on
  secure-boot on|off    append hosts/stargazer/secureboot/db.pem to the firmware db and
                        enable Secure Boot, or disable it (VM must be off)
  snapshot <name>       take a snapshot
  restore <name>        revert to a snapshot (VM is stopped first)
  destroy               delete the VM (double confirmation)

VM: $VMX
EOF
}
```

- [ ] **Step 6: In the `create` heredoc's comment block**

Replace `our keys are enrolled (hosts/stargazer-fusion)` with `\`secure-boot on\` appends our db certificate (README §7)`.

- [ ] **Step 7: Add the new verbs directly before `  snapshot)`**

```bash
  iso)
    mkdir -p "$ISO_DIR"
    tmp="$(mktemp -d "$ISO_DIR/.dl.XXXXXX")"
    trap 'rm -rf "$tmp"' EXIT
    echo "resolving $ISO_URL"
    real_url="$(curl -sIL -o /dev/null -w '%{url_effective}' "$ISO_URL")"
    echo "downloading $real_url"
    curl -fL --progress-bar -o "$tmp/iso" "$real_url"
    echo "verifying sha256"
    want="$(curl -fsSL "${real_url}.sha256" | awk '{print $1}')"
    got="$(shasum -a 256 "$tmp/iso" | awk '{print $1}')"
    if [ "$want" != "$got" ]; then
      echo "sha256 mismatch: expected $want, got $got" >&2
      exit 1
    fi
    mv "$tmp/iso" "$ISO"
    echo "ISO at $ISO"
    ;;

  suspend)
    require_vm
    "$VMRUN" -T fusion suspend "$VMX" hard
    ;;

  resume)
    require_vm
    "$VMRUN" -T fusion start "$VMX" gui
    ;;

  secure-boot)
    require_vm
    require_stopped
    case "${1:-}" in
      on)
        openssl x509 -in "$REPO/hosts/stargazer/secureboot/db.pem" -outform DER -out "$VMDIR/stargazer-db.der"
        # Fusion loads the default key set and dbDefault.file0 when it creates
        # the NVRAM file (seen 2026-09-14), so the first enable moves the old
        # file aside. Later enables keep the NVRAM, which already holds our
        # certificate.
        if [ ! -e "$VMDIR/$VMNAME.nvram.pre-sb" ] && [ -e "$VMDIR/$VMNAME.nvram" ]; then
          mv "$VMDIR/$VMNAME.nvram" "$VMDIR/$VMNAME.nvram.pre-sb"
        fi
        "$VMCLI" "$VMX" ConfigParams SetEntry uefi.secureBoot.enabled TRUE
        "$VMCLI" "$VMX" ConfigParams SetEntry uefi.secureBoot.dbDefault.file0 stargazer-db.der
        "$VMCLI" "$VMX" ConfigParams SetEntry uefi.secureBoot.dbDefault.append TRUE
        ;;
      off)
        "$VMCLI" "$VMX" ConfigParams SetEntry uefi.secureBoot.enabled FALSE
        ;;
      *)
        echo "usage: stargazer-vm secure-boot on|off" >&2
        exit 1
        ;;
    esac
    grep -E '^uefi\.secureBoot' "$VMX"
    ;;

```

`require_vm` must run before the `case` so the guard message wins when no VM exists. That is what the check's last line tests.

- [ ] **Step 8: `CLAUDE.md` VM lifecycle line**

```markdown
**VM lifecycle:** `scripts/stargazer-vm <iso|create|up|down|kill|suspend|resume|status|ip|screenshot|type|key|set|cdrom|secure-boot|snapshot|restore|destroy>`
(VMware Fusion; hard-coded to `stargazer`, `--drill` targets `stargazer-drill`).
```

- [ ] **Step 9: Run the check**

Run: `bash "$SCRATCH/vm-script-check.sh"`
Expected: `PASS`

- [ ] **Step 10: Lint and confirm behemoth is unchanged**

`just lint` and the behemoth `drvPath` check.

- [ ] **Step 11: Commit**

Message: `feat(stargazer): Fusion VM script replaces the Parallels one`. The body lists the verbs added to the trial script (`iso`, `suspend`, `resume`, `secure-boot`, `--drill`) and the new ISO location.

---

### Task 5: The Fusion runbook and lineage record

**Files:**
- Rewrite: `hosts/stargazer/README.md`
- Create: `docs/vmware-fusion-workarounds.md`
- Modify: `docs/parallels-workarounds.md` (a note under the title)

**Interfaces:**
- Consumes: Task 4's verbs, Task 1's 1Password Document titles, and Task 2's disk and host facts.
- Produces: the procedure that Tasks 8 to 10 execute, section by section. Keep the section numbers below, because later tasks cite them.

The runbook keeps its conventions block and its tone. Every section below lists required content. Commands must appear exactly as given.

- [ ] **Step 1: §1 What this VM is**

It is an aarch64 NixOS VM on VMware Fusion, hosted on behemoth, declared as `nixosConfigurations.stargazer`. Keep the "Nothing here is hand-installed" paragraph and the "Compliance posture" paragraph unchanged.

Prerequisites:
- VMware Fusion 26.0.1 or later, installed from Broadcom's portal. There is no Homebrew cask.
- At least 150 GB free under `~/Virtual Machines.localized`.
- 1Password unlocked, holding three items: the SSH agent keys, the Secure Note "sops age key (dotfiles admin)", and the Documents "stargazer ssh host key" and "stargazer ssh host key pub".
- A YubiKey. It is plugged into the Mac and connected to the VM through Fusion's Virtual Machine menu, under USB & Bluetooth. If VirtualHere currently shares it with rocinante, disconnect it there first.
- Network access to `channels.nixos.org`, `cache.nixos.org` and `github.com`.

- [ ] **Step 2: §2 Create the VM**

```bash
behemoth$ ./scripts/stargazer-vm iso
behemoth$ ./scripts/stargazer-vm create
behemoth$ ./scripts/stargazer-vm up
```

Include a table of what `create` writes, with the reason for each row:
- 8 vCPU / 16 GB
- 256 GB growable NVMe (`nvme0:0`), so disko targets `/dev/nvme0n1`
- EFI firmware, with Secure Boot off until §7 because the installer ISO is unsigned
- NAT networking on vmxnet3, with the guest link named `enp2s0`
- SVGA with 3D and 4 GB of graphics memory, for OpenGL 4.3 through SVGA3D
- `gui.fitGuestUsingNativeDisplayResolution`, for Retina pixels (the host sets scale 2)
- `usb.generic.allowHID` and `usb.generic.allowLastHID`, for YubiKey passthrough
- `uuid.action = "keep"`, so a power-on never stops at the "moved or copied" question
- hdaudio sound, USB 3.1 plus EHCI, and the ISO on `sata0:1` connected at power-on

- [ ] **Step 3: §3 The host key**

Explain why the key matters, reusing the existing paragraphs about `github:` refs and the soft failure of undecryptable secrets. Then give the usual path, a rebuild:

```bash
behemoth$ SCRATCH="$(mktemp -d)"; chmod 700 "$SCRATCH"
behemoth$ op document get "stargazer ssh host key" --vault Private --out-file "$SCRATCH/stargazer_host_ed25519_key"
behemoth$ op document get "stargazer ssh host key pub" --vault Private --out-file "$SCRATCH/stargazer_host_ed25519_key.pub"
behemoth$ chmod 600 "$SCRATCH/stargazer_host_ed25519_key"
behemoth$ nix run nixpkgs#ssh-to-age -- -i "$SCRATCH/stargazer_host_ed25519_key.pub"   # must equal &stargazer in .sops.yaml
```

Keep the existing generate-and-`updatekeys` procedure as a subsection titled "Rotating the host key". Add one sentence: after a rotation, replace both 1Password Documents.

- [ ] **Step 4: §4 Install from the ISO**

4.1, get a shell. At the console, typed by hand or with `./scripts/stargazer-vm type '<line>'`:

```
iso# sudo sh -c 'echo nameserver 1.1.1.1 > /etc/resolv.conf'; mkdir -p ~/.ssh && curl -fsSL https://github.com/andrey-moor.keys > ~/.ssh/authorized_keys && echo KEYS-OK
```

Explain that Fusion's NAT DNS proxy does not resolve on behemoth. Then:

```bash
behemoth$ ip="$(./scripts/stargazer-vm ip)"
behemoth$ S="-o IdentitiesOnly=yes -i $HOME/.ssh/1p_personal.pub"
behemoth$ ssh $S nixos@"$ip" 'lsblk -dno NAME,SIZE,TYPE; ip -4 addr show enp2s0; curl -sI https://cache.nixos.org | head -1'
# expect: nvme0n1 256G disk / 192.168.x.y on enp2s0 / HTTP/2 200
```

Explain that `IdentitiesOnly` avoids "Too many authentication failures" from the 1Password agent.

4.2, partition at the console, never over SSH:

```
iso# sudo nix run --extra-experimental-features 'nix-command flakes' github:nix-community/disko -- --mode disko --flake github:andrey-moor/dotfiles#stargazer
iso# lsblk -f /dev/nvme0n1 && findmnt -R /mnt
```

4.3, inject the host key:

```bash
behemoth$ scp $S "$SCRATCH/stargazer_host_ed25519_key" "$SCRATCH/stargazer_host_ed25519_key.pub" nixos@"$ip":/tmp/
behemoth$ ssh $S nixos@"$ip" '
  sudo install -Dm600 /tmp/stargazer_host_ed25519_key     /mnt/etc/ssh/ssh_host_ed25519_key
  sudo install -Dm644 /tmp/stargazer_host_ed25519_key.pub /mnt/etc/ssh/ssh_host_ed25519_key.pub
  shred -u /tmp/stargazer_host_ed25519_key'
```

4.3b, place the Secure Boot signing material. Keep today's explanation of why these files must exist before `nixos-install`. The commands:

```bash
behemoth$ agekey="$(mktemp)"; chmod 600 "$agekey"
behemoth$ op item get "sops age key (dotfiles admin)" --vault Private --fields notesPlain --reveal \
            | grep -oE 'AGE-SECRET-KEY-1[A-Z0-9]+' > "$agekey"
behemoth$ SOPS_AGE_KEY_FILE="$agekey" nix run nixpkgs#sops -- -d --extract '["db.key"]' secrets/stargazer-sbctl.yaml \
            | ssh $S nixos@"$ip" 'sudo sh -c "umask 077; mkdir -p /mnt/var/lib/sbctl/keys/db && cat > /mnt/var/lib/sbctl/keys/db/db.key"'
behemoth$ rm -f "$agekey"
behemoth$ scp $S hosts/stargazer/secureboot/db.pem hosts/stargazer/secureboot/GUID nixos@"$ip":/tmp/
behemoth$ ssh $S nixos@"$ip" '
  sudo install -Dm400 /tmp/db.pem /mnt/var/lib/sbctl/keys/db/db.pem
  sudo install -Dm644 /tmp/GUID   /mnt/var/lib/sbctl/GUID'
```

4.4, install detached:

```
iso# nohup sudo nixos-install --flake github:andrey-moor/dotfiles#stargazer --no-root-passwd > /tmp/nixos-install.log 2>&1 &
iso# tail -f /tmp/nixos-install.log        # done at "installation finished!"
```

4.5, set the login password: `iso# sudo nixos-enter --root /mnt -c 'passwd andreym'`.

4.6, eject the ISO and boot from disk:

```bash
iso# sudo poweroff
behemoth$ ./scripts/stargazer-vm cdrom off
behemoth$ ./scripts/stargazer-vm up
behemoth$ rm -rf "$SCRATCH"
```

- [ ] **Step 5: §5 First boot and verification**

Keep the tailnet, secrets, disk and home-manager checks. Replace the GPU and desktop checks with:

```bash
vm$ glxinfo -B | grep -i 'renderer'                                    # SVGA3D, not llvmpipe
vm$ systemctl --user is-active virtio-gpu-resize vmware-clipboard-bridge   # active, active
vm$ pgrep -fa 'vmtoolsd -n vmusr'                                        # the copy/paste agent
vm# tailscale status --self | head -1                                    # node name is exactly stargazer
```

State that resizing only follows the host window while the Fusion window is on screen. Keep the wayvnc pin paragraph. Then snapshot with the VM stopped: `./scripts/stargazer-vm snapshot installed`.

- [ ] **Step 6: §6 Enrollment ceremony**

Keep the ordering explanation and the checks. The security key reaches the guest through Fusion's USB passthrough. Connect it from the Virtual Machine menu, under USB & Bluetooth, before logging in at `tuigreet`. Verify it with `vm# grep -l 'Yubico' /sys/class/hidraw/*/device/uevent`. Snapshot the stopped VM as `enrolled`. Keep the warning that restoring a live snapshot rolls back himmelblau's tokens.

- [ ] **Step 7: §7 Secure Boot**

Explain that the tenant script requires `SecureBootEnabled` and Microsoft UEFI CA 2023 in db. VMware's default db has that CA. The ceremony:

```bash
vm# sudo poweroff
behemoth$ ./scripts/stargazer-vm snapshot pre-sb
behemoth$ ./scripts/stargazer-vm secure-boot on
behemoth$ ./scripts/stargazer-vm up                # LUKS passphrase at the console
vm# bootctl status | grep -i 'secure boot'         # enabled (deployed)
vm# mokutil --sb-state                             # SecureBoot enabled
vm# mokutil --db --short                           # includes Microsoft UEFI CA 2023 and Database Key
vm# for f in /boot/EFI/Linux/*.efi; do sbverify --list "$f" | grep -q 'CN=Database Key' && echo "ok $f" || echo "UNSIGNED $f"; done
vm$ aad-tool compliance-check                      # from the graphical session
```

The systemd-boot menu and its countdown work under Secure Boot on Fusion. Optionally prove enforcement: an unsigned EFI image is refused, and `vmware.log` in the bundle shows `SECUREBOOT: Image DENIED`.

Rollback: stop the VM, run `./scripts/stargazer-vm secure-boot off`, and power on. Or `./scripts/stargazer-vm restore pre-sb`. The passphrase slot is never removed.

- [ ] **Step 8: §8 Fire drill**

Use `--drill` to prove the runbook without touching the real VM:

```bash
behemoth$ ./scripts/stargazer-vm --drill create
behemoth$ ./scripts/stargazer-vm --drill up
```

Then run §4 against `stargazer-drill` with these deltas:
- Reuse the host key from §3.
- Run `sudo tailscale up --hostname stargazer-drill`, and `tailscale logout` before destroying the drill VM.
- Do not log in at the greeter and do not enroll, because a second Entra join would create a duplicate device.
- Run `--drill secure-boot on` after a clean power-off, then check `bootctl status` over SSH on the NAT address.

Success criteria:
- the LUKS prompt reaches greetd
- the secrets decrypt on first boot
- LUKS2 is active
- the upgrade timer is present
- Secure Boot is enabled with our signer

Then run `./scripts/stargazer-vm --drill destroy`. Record the date and duration of the P9c build (Task 8) as the latest run.

- [ ] **Step 9: §9 Day-2 operations**

Keep autoUpgrade and rollback, with the snapshot commands switched to `./scripts/stargazer-vm`. Add:
- `suspend` and `resume` keep LUKS unlocked, and only a cold boot asks for the passphrase.
- After a Hyprland package change, restart greetd while no session is running: `vm# sudo systemctl restart greetd`.
- Every `nixos-rebuild switch` and `hyprctl reload` briefly returns the display to its login-time size. The follower restores it within 2 seconds.

Replace "Retiring the old VM" with one sentence: the old Omarchy `Stargazer` VM stays on Parallels until the owner decides.

- [ ] **Step 10: §10 Troubleshooting**

Keep these entries as they are:
- compliance fails on "Microsoft UEFI CA 2023"
- AADSTS70000 after a live snapshot restore
- no `10-tenant.conf`
- 226/NAMESPACE
- greetd loops
- builds that change nothing

Remove every Parallels entry. Add these entries:
- **Power-on stops at "moved or copied".** `uuid.action` is missing from the `.vmx`. Answer "I Moved It", never "I Copied It", which changes the hardware UUID and MAC. Then run `./scripts/stargazer-vm set uuid.action keep` with the VM off.
- **The installer cannot resolve hosts.** Fusion's NAT DNS proxy fails on behemoth. Use the resolv.conf line from 4.1.
- **The desktop stays small or does not follow a resize.** Fusion sends the window size only while its window is on screen. Switch to the window, or drag a corner.
- **GPU apps fail with "invalid arguments for wl_surface.attach".** Hyprland is running without the vmwgfx patch. Check `modules/nixos/vmware-guest.nix` and restart greetd.
- **Copy/paste does not reach the Mac or the VM.** Hyprland refuses clipboard access to X11 clients without focus, and the bridge covers that. Check `systemctl --user status vmware-clipboard-bridge` and `pgrep -fa 'vmtoolsd -n vmusr'`. Include this boundary check:

```bash
vm$ XC=$(nix build --no-link --print-out-paths nixpkgs#xclip)/bin/xclip
vm$ printf 'x11-probe' | setsid "$XC" -selection clipboard -t UTF8_STRING >/dev/null 2>&1 & sleep 1.5
vm$ [ "$(wl-paste -n --type text)" = x11-probe ] && echo X11-TO-WAYLAND-OK
vm$ printf 'wl-probe' | setsid wl-copy >/dev/null 2>&1; sleep 1.5
vm$ [ "$("$XC" -o -selection clipboard -t UTF8_STRING)" = wl-probe ] && echo WAYLAND-TO-X11-OK
```

- **The YubiKey is not in the guest.** Connect it from the Virtual Machine menu. The `.vmx` must contain both `usb.generic.allowHID` keys. VirtualHere may be holding the key for rocinante.

- [ ] **Step 11: `docs/vmware-fusion-workarounds.md`**

Use the table shape of `docs/parallels-workarounds.md`: #, Workaround, Where, Evidence (date), Elsewhere, where Elsewhere is **drop**, **keep** or **re-test**. Include one row per item:

1. The Hyprland 0.56.2 vmwgfx DMA-BUF patch, with its version guard. Where: `modules/nixos/vmware-guest.nix` and the patch file. Evidence: 2026-09-14, GPU clients rejected. Elsewhere: drop when Hyprland discussion #12966 lands upstream.
2. Resize follower timing of 0.5 s, 1 poll and 0 px. Where: `vmware-guest.nix`. Evidence: 2026-09-14, 8 s down to 1 s, no drift. Elsewhere: re-test.
3. Retina key plus Hyprland scale 2. Where: `scripts/stargazer-vm`, `hosts/stargazer/default.nix`. Evidence: 2026-09-14. Elsewhere: re-test.
4. The boot console is 1280x800 until Tools start, and resize needs a visible window. Where: README §5 and §10. Evidence: 2026-09-15. Elsewhere: keep as notes.
5. `headless = false` and the agent autostart through `extraExecOnce`. Where: `vmware-guest.nix`. Evidence: 2026-09-15. Elsewhere: drop.
6. The clipboard bridge. Where: `vmware-guest.nix`. Evidence: 2026-09-15, Hyprland XWM.cpp focus checks, verified. Elsewhere: drop if Hyprland relaxes the rule or open-vm-tools gains Wayland support.
7. The HID passthrough keys. Where: `scripts/stargazer-vm`. Evidence: 2026-09-15, WebAuthn passed. Elsewhere: drop.
8. `uuid.action = "keep"`. Where: `scripts/stargazer-vm`. Evidence: 2026-09-15, a power-on blocked. Elsewhere: drop.
9. Secure Boot through `dbDefault.file0` append and NVRAM regeneration. Where: `scripts/stargazer-vm secure-boot`. Evidence: 2026-09-14, a negative test passed. Elsewhere: re-test.
10. Installer DNS via 1.1.1.1 and the host's own resolvers. Where: README §4.1 and `vmware-guest.nix`. Evidence: 2026-09-14. Elsewhere: re-test.
11. SSH on `enp2s0`. Where: `hosts/stargazer/default.nix`. Evidence: 2026-09-14, no guest operations without a password. Elsewhere: re-test.
12. greetd must restart after a Hyprland package change. Where: README §9. Evidence: 2026-09-14. Elsewhere: keep.
13. `vmcli MKS sendKeyEvent` needs `(usage << 16) | 7`. Where: `scripts/stargazer-vm`. Evidence: 2026-09-14. Elsewhere: drop.
14. Fusion has no Homebrew cask and needs the Broadcom portal. Where: README §1. Evidence: 2026-09-14. Elsewhere: drop.

- [ ] **Step 12: `docs/parallels-workarounds.md` note**

Directly under the title, add:

```markdown
> **Retired 2026-09.** stargazer moved to VMware Fusion (`docs/vmware-fusion-workarounds.md`).
> The Parallels code this record points at was removed in the P9c migration. Find it with
> `git log --diff-filter=D --oneline -- modules/nixos/parallels-guest.nix`.
```

If D7 was declined, write instead that the Parallels code stays in the repo, unused.

- [ ] **Step 13: Check the docs**

```bash
grep -n -E 'prlctl|Parallels Desktop|enroll-mok|MokList|/dev/sda|virgl|stargazer-nixos|stargazer-fusion' hosts/stargazer/README.md
```

Expected: matches only in the §9 sentence about the old `Stargazer` VM and in history notes that say they are history.

```bash
for v in $(grep -oE 'stargazer-vm (--drill )?[a-z-]+' hosts/stargazer/README.md | awk '{print $NF}' | sort -u); do
  grep -qE "^  ${v}\)" scripts/stargazer-vm || echo "MISSING VERB: $v"
done
```

Expected: no output.

- [ ] **Step 14: Commit**

Message: `docs(stargazer): Fusion install runbook and workaround lineage`.

---

### Task 6: Retire the Parallels VM `stargazer-nixos`

Controller with the owner. It depends on Task 1.

- [ ] **Step 1: Record the Parallels inventory (read-only)**

Run: `prlctl list -a`
Expected: `Nostromo`, `Orrery-Win11-ARM64`, `Stargazer`, `spike-himmelblau-arm` and `stargazer-nixos` `{cd98232e-21b7-4426-90c2-1a0ddcc809e5}`. Save the output to compare in Step 5.

- [ ] **Step 2 (owner): Remove the tailnet node**

In the Tailscale admin console, remove the machine `stargazer`, the Parallels VM. Keep `stargazer-fusion`.

- [ ] **Step 3 (owner): Delete the device records**

In the Intune admin center, delete the Linux device `stargazer`. In the Entra admin center, delete the device `stargazer`. Leave `stargazer-fusion` in both. Nothing from this step goes into the repo.

- [ ] **Step 4 (controller, after the owner says go): Delete the VM by exact name**

```bash
behemoth$ prlctl list -a | grep -F '{cd98232e-21b7-4426-90c2-1a0ddcc809e5}' | grep -q stargazer-nixos && echo TARGET-OK
behemoth$ prlctl stop stargazer-nixos --kill 2>/dev/null || true
behemoth$ prlctl delete stargazer-nixos
```

Run the last two commands only after `TARGET-OK`.

- [ ] **Step 5: Verify**

Run: `prlctl list -a`
Expected: the other four VMs have the same UUIDs and states as in Step 1, and `stargazer-nixos` is gone.

---

### Task 7: Push

- [ ] **Step 1: Show what will be pushed**

Run: `git log --oneline origin/main..main`
Expected: this plan's commits plus the earlier unpushed commits. Those are `ea027b5`, `9eb79e1`, `f9dd791`, `91458df`, `7dd0721` and the plan commit.

- [ ] **Step 2 (owner says go): Push**

Run: `git push`

- [ ] **Step 3: Watch CI**

Run: `gh run watch --exit-status`
Expected: lint and all three host builds pass. The stargazer build now compiles the patched Hyprland, so it takes longer than before.

---

### Task 8: Build `stargazer` from the runbook

Controller with the owner at the console. It depends on Tasks 1 and 4 to 7. Follow `hosts/stargazer/README.md` §2 to §5 exactly. Any hand-fix is a repo bug: fix it, push with the owner's go, and redo the step.

- [ ] **Step 1: Free memory by suspending the trial VM**

```bash
behemoth$ "/Applications/VMware Fusion.app/Contents/Public/vmrun" -T fusion suspend "$HOME/Virtual Machines.localized/stargazer-fusion.vmwarevm/stargazer-fusion.vmx" hard
```

- [ ] **Step 2: Record the start time, then run §2** (`iso`, `create`, `up`)
- [ ] **Step 3: Run §3** (host key from 1Password)
- [ ] **Step 4: Run §4.1 to §4.6** (the owner types the disko passphrase at the console)
- [ ] **Step 5: Run §5** (the owner types the LUKS passphrase and logs in with the 4.5 password)

Success criteria, all of them:
- [ ] the greeter appears after the LUKS prompt
- [ ] `10-tenant.conf`, the user map and `/run/secrets/sbctl-db-key` decrypt on first boot
- [ ] `cryptsetup status cryptroot` shows LUKS2
- [ ] `glxinfo -B` shows SVGA3D
- [ ] `virtio-gpu-resize` and `vmware-clipboard-bridge` are active
- [ ] the tailnet node name is exactly `stargazer`
- [ ] `nixos-upgrade.timer` is listed
- [ ] `~/.config/nvim` resolves after cloning `~/dotfiles`
- [ ] snapshot `installed` exists

---

### Task 9: Enrollment and Secure Boot

Controller with the owner at the console. It depends on Task 8.

- [ ] **Step 1: Run §6** (YubiKey through Fusion USB, login at `tuigreet`, `aad-tool status` says working)
- [ ] **Step 2: Snapshot the stopped VM as `enrolled`**
- [ ] **Step 3: Run §7**

Success criteria:
- [ ] `bootctl status` shows Secure Boot enabled
- [ ] `mokutil --db --short` lists Microsoft UEFI CA 2023 and Database Key
- [ ] every UKI shows `CN=Database Key`
- [ ] `aad-tool compliance-check` passes from the graphical session
- [ ] the owner confirms **Compliant** for device `stargazer` in the Intune portal

---

### Task 10: Hand tests and the wayvnc pin

Controller with the owner. It depends on Task 9.

- [ ] **Step 1 (owner): Hand tests in the VM**
  - [ ] Firefox opens `myapps.microsoft.com` without a password prompt.
  - [ ] `webauthn.io` registration and authentication work with the YubiKey.
  - [ ] Copy on the Mac and paste in the VM, then copy in the VM with Ctrl+C (Ctrl+Shift+C in a terminal) and paste on the Mac.
  - [ ] Dragging the visible Fusion window's corner resizes the desktop within about 1 second, and text is sharp.
  - [ ] A video in Firefox plays sound.
- [ ] **Step 2 (controller): Clipboard boundary check** from README §10. Expected: `X11-TO-WAYLAND-OK` and `WAYLAND-TO-X11-OK`.
- [ ] **Step 3 (controller): Shared folder**

```bash
behemoth$ R="/Applications/VMware Fusion.app/Contents/Public/vmrun"; X="$HOME/Virtual Machines.localized/stargazer.vmwarevm/stargazer.vmx"
behemoth$ d="$(mktemp -d)"; echo "hello from behemoth" > "$d/from-host.txt"
behemoth$ "$R" -T fusion enableSharedFolders "$X" && "$R" -T fusion addSharedFolder "$X" p9c "$d"
vm$ mkdir -p /tmp/hgfs && vmhgfs-fuse .host:/p9c /tmp/hgfs -o subtype=vmhgfs-fuse && cat /tmp/hgfs/from-host.txt
vm$ fusermount -u /tmp/hgfs
behemoth$ "$R" -T fusion removeSharedFolder "$X" p9c; rm -rf "$d"
```

Expected: `hello from behemoth`.

- [ ] **Step 4: Pin wayvnc to the new tailnet address**

```bash
behemoth$ addr="$(ssh andreym@stargazer tailscale ip -4)"; echo "$addr"   # a 100.x address
behemoth$ python3 - "$addr" <<'PY'
import pathlib, sys
p = pathlib.Path("hosts/stargazer/default.nix"); s = p.read_text()
anchor = "  networking.firewall.interfaces.enp2s0.allowedTCPPorts = [ 22 ];\n"
assert s.count(anchor) == 1
pin = ('\n  # Tailnet address, pinned once the node joined (README §5).\n'
       f'  home-manager.users.andreym.modules.linux.wayvnc.address = "{sys.argv[1]}";\n')
p.write_text(s.replace(anchor, anchor + pin))
PY
behemoth$ git diff hosts/stargazer/default.nix
```

Expected: the diff adds exactly the comment and the address line.

- [ ] **Step 5: Lint, commit, push with the owner's go, and switch in the VM**

```bash
just lint
git commit -am 'feat(stargazer): pin wayvnc to the new tailnet address'
git push
vm# sudo nixos-rebuild switch --flake github:andrey-moor/dotfiles#stargazer --refresh
vm$ systemctl --user is-active wayvnc
```

---

### Task 11: Retire the trial VM `stargazer-fusion`

Controller with the owner. It depends on Tasks 1 and 10.

- [ ] **Step 1 (owner): Remove the tailnet node** `stargazer-fusion`.
- [ ] **Step 2 (owner): Delete the device records** named `stargazer-fusion` in Intune and Entra.
- [ ] **Step 3 (controller, after the owner says go): Delete the bundle**

```bash
behemoth$ R="/Applications/VMware Fusion.app/Contents/Public/vmrun"; X="$HOME/Virtual Machines.localized/stargazer-fusion.vmwarevm/stargazer-fusion.vmx"
behemoth$ "$R" -T fusion deleteVM "$X" && echo DELETED
```

If `deleteVM` refuses because the trial VM is suspended, suspend the new VM too, quit Fusion, and remove the bundle:

```bash
behemoth$ ./scripts/stargazer-vm suspend
behemoth$ osascript -e 'quit app "VMware Fusion"'; sleep 3
behemoth$ rm -rf "$HOME/Virtual Machines.localized/stargazer-fusion.vmwarevm"
behemoth$ ./scripts/stargazer-vm resume
```

- [ ] **Step 4: Verify**

Run: `ls "$HOME/Virtual Machines.localized"`
Expected: `iso` and `stargazer.vmwarevm` only.

---

### Task 12: Close out

- [ ] **Step 1: Amend the design spec**

In `docs/superpowers/specs/2026-07-23-environment-refactor-design.md`, change the §1 stargazer row's location to "VMware Fusion VM on behemoth". Add at the end:

```markdown
## Amendment 2026-09-15: stargazer on VMware Fusion

stargazer moved from Parallels to VMware Fusion after a trial passed every compliance and
desktop test (plan `docs/superpowers/plans/2026-09-15-env-refactor-p9c-stargazer-fusion-migration.md`).
Nostromo stays on Parallels, so behemoth keeps both hypervisors. The "Parallels dependency
for both Mac VMs" risk now applies to Nostromo only. Fusion's own costs are a vendored
Hyprland patch, a clipboard bridge and a manual Broadcom download
(`docs/vmware-fusion-workarounds.md`).
```

- [ ] **Step 2: Update the runbook's "Last updated" note** with the Task 8 date and duration, and add any lessons from Tasks 8 to 11 to the lineage record.
- [ ] **Step 3: Commit** as `docs: stargazer migration to VMware Fusion completed`, then push after the owner says go.
- [ ] **Step 4: Update project memory.** In `project_env_refactor.md` and `MEMORY.md`, record that P9c is done and list what remains: the P9b spec revision for Fusion, the owner's call on the old `Stargazer` VM, the rocinante skill cleanup before its next switch, the Little Snitch filter, sudo hardening, and Intune script policies.
