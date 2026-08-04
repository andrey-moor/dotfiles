# P2 Intune Spike

Throwaway experiment space answering one question with evidence: **can a Linux
machine that honestly reports its identity get Microsoft Entra / Intune
corporate access?** Two candidate mechanisms are built side by side:

| Candidate | Mechanism | Arch |
|---|---|---|
| **B4** | [himmelblau](https://github.com/himmelblau-idm/himmelblau) — native Entra ID auth (PAM/NSS + broker daemon) on NixOS | x86_64 and aarch64 |
| **B3** | [intuneme](https://github.com/frostyard/intuneme) — the real Intune Portal + Edge inside an Ubuntu 24.04 nspawn container | x86_64 |

Everything under `spikes/intune/` is deleted at P2 close except the verdict.
The committed plan is
[`docs/superpowers/plans/2026-08-03-env-refactor-p2-intune-spikes.md`](../../docs/superpowers/plans/2026-08-03-env-refactor-p2-intune-spikes.md).
(Task briefs/reports live under `.superpowers/sdd/…`, which is **gitignored** —
they are local to the owner's machine and not part of this repo.)

**Autonomous work stops at the "doorstep":** services green, the enrollment
command written down, nothing executed. No sign-in or enrollment is ever
attempted without the owner driving it.

## Never commit

- `tenant.nix` — the real Entra tenant domain. Copy `tenant.nix.example` and fill it in. Gitignored.
- `spike.key` / `spike.key.pub` — the throwaway spike SSH keypair. Gitignored.
- `notes/` — session notes; they contain the tenant domain. Gitignored.
- `result*` — nix build symlinks, and any `.qcow2` / `.hds` / `.iso` image.

## Outcomes so far

| | Result |
|---|---|
| **B4 / x86_64** (`b4-himmelblau.nix`) | **Doorstep reached.** Image builds, boots, `himmelblaud` runs healthy, `aad-tool status` reports working. himmelblau has no separate `enroll` verb — the Entra device join happens as a side effect of the *first successful authentication*, governed by `join_type` (default `join`). Nothing enrolled. |
| **B4 / aarch64** (same module) | **Doorstep reached, on real Apple-silicon virtualization.** Built on a throwaway QEMU/HVF builder VM (`scripts/arm-builder`, since behemoth has no aarch64-linux builder), independently verified by booting under `-accel hvf`, then adopted into a Parallels VM (`scripts/spike-parallels`) with a `doorstep` snapshot of the clean pre-enrollment state. |
| **B3 / x86_64** (`b3-intuneme.nix`) | **Partially reaches the doorstep.** `intuneme init` + `start` succeed: the Ubuntu container is provisioned and runs healthy, with `intune-portal` and `microsoft-edge` present inside it. But `intuneme open portal` / `open edge` exit 0 without producing a visible process — UI reachability is **not** confirmed. Getting this far took roughly ten manual interventions, each a scoring demerit for B3. No sign-in attempted. |

The full narrative for each sits in the status header of the corresponding
`.nix` module. Verbatim evidence (logs, exact commands, the tenant domain)
stays in the gitignored `notes/` and `.superpowers/sdd/…` — deliberately, since
this repo is public.

## Hosts and prerequisites

| Script | Runs on | Drives |
|---|---|---|
| `scripts/spike` | **rocinante** (x86_64 Arch, over Tailscale SSH) | the x86_64 QEMU/KVM guests, b4 and b3 |
| `scripts/spike-parallels` | **behemoth** (macOS) | the aarch64 Parallels VM `spike-himmelblau-arm` |
| `scripts/arm-builder` + `scripts/serial_drive.py` | **behemoth** (macOS) | a throwaway aarch64 QEMU/HVF builder VM that produces the aarch64 image |

`spike` is a **copy** on rocinante, not a checkout — editing this repo does not
update it. rocinante gains nothing persistent outside `~/spikes/`. To (re)seed
or refresh it from behemoth:

```bash
# flake sources the guests are built from — never the private key
rsync -a --delete --exclude notes/ --exclude 'spike.key' \
  ~/Documents/dotfiles/spikes/intune/ rocinante:spikes/flake/
# the CLI itself, and the private key (which lives OUTSIDE ~/spikes/flake:
# that directory gets copied into a world-readable /nix/store path at build time)
rsync -a ~/Documents/dotfiles/spikes/intune/scripts/spike rocinante:spikes/spike
rsync -a ~/Documents/dotfiles/spikes/intune/spike.key      rocinante:spikes/spike.key
ssh rocinante 'chmod 700 spikes && chmod 600 spikes/spike.key && chmod 755 spikes/spike'
# must print CLEAN
ssh rocinante 'ls ~/spikes/flake/spike.key 2>/dev/null && echo LEAK || echo CLEAN'
```

`spike` needs `nix` on PATH, which a non-interactive SSH does not get — prefix
remote invocations with `. /etc/profile.d/nix.sh;`.

## The `spike` CLI (rocinante)

```bash
spike <build|up|down|ssh|reset|doorstep|destroy|status|vnc> <b4|b3> [--force]
```

| Verb | Effect |
|---|---|
| `build` | rebuild the base image from `~/spikes/flake`. Refuses while the VM runs (the copy would corrupt a live guest), and refuses for b3 while a doorstep snapshot exists. |
| `up` | boot the VM on its overlay. For b3 also opens a password-protected VNC display and prints the credentials. |
| `down` | ACPI powerdown via the qemu monitor, escalating to SIGTERM then SIGKILL, and does not return until qemu is actually gone. |
| `ssh` | root shell into the guest. **Only works from rocinante itself** — it connects to `127.0.0.1:<port>`, the qemu user-net hostfwd. From behemoth use `ssh -o ProxyJump=rocinante -i spikes/intune/spike.key -p <port> root@127.0.0.1`. |
| `reset` | back to the doorstep — see the table below, the two variants differ fundamentally. |
| `doorstep` | **b3 only.** Snapshot the current (stopped) overlay as the restore point for `reset`. |
| `destroy` | stop and delete `~/spikes/<vm>/` entirely. Refuses for b3 with a doorstep snapshot unless `--force`. |
| `status` | running state plus image/snapshot sizes. |
| `vnc` | **b3 only.** Rotate the VNC password and print the endpoint. Errors on b4, which has no VNC device. |

Ports: b4 SSH `2241`, b3 SSH `2231`, b3 VNC display `:31` (TCP 5931).

### Where each variant's doorstep lives — read before `reset`

- **b4** — the doorstep (healthy `himmelblaud`) is baked into `base.qcow2` by
  `nix build`. The overlay is disposable, so `reset b4` simply drops it.
- **b3** — the doorstep is built **at runtime inside the guest**: `intuneme
  init` pulls a multi-GB OCI image, unpacks an Ubuntu rootfs and renames the
  container user. All of that lives in the **overlay** (~5 GB). Dropping it
  destroys the doorstep. So b3 requires an explicit `spike doorstep b3`
  snapshot, and `reset b3` **restores** from it — refusing outright if none
  exists, rather than falling back to deletion.

### VNC on b3

b3's display is bound to rocinante's tailnet address, so the wire is encrypted
and off the LAN — but tailnet reachability is not authentication, and this
display is exactly where corporate credentials and MFA get typed. So qemu is
started with `password=on`, which rejects **every** client until `spike` sets a
freshly generated password over the qemu monitor socket. The password is
printed once by `up`, stored nowhere, and can be rotated at any time with
`spike vnc b3`. VNC's classic auth only uses the first 8 bytes of a password,
so the generated one is 8 characters; the tailnet bind remains the real
perimeter.

## The `spike-parallels` CLI (behemoth)

```bash
spike-parallels <build|create|up|down|reset|destroy|status|ip>
```

Only ever touches the VM named `spike-himmelblau-arm`. **Never point it at
another VM** — this Mac also hosts `Nostromo`, a live domain-joined corporate
Windows machine that must never be mutated.

`create` adopts an aarch64 qcow2 (from `build`, or from `arm-builder`'s output)
into a Parallels disk bundle, boots it once to prove the doorstep is real, then
captures the `doorstep` snapshot. `reset` stops the VM and switches back to
that snapshot — the snapshot was taken at poweroff, so stopping first is part
of the operation, not an optimization.

## The `arm-builder` CLI (behemoth)

```bash
arm-builder <up|bootstrap|prep-storage|sync|build|poll|fetch|verify|status|down|destroy>
```

Exists because `nix build .#packages.aarch64-linux.b4-image` cannot run on
behemoth: Determinate Nix owns the install (`nix.enable = false`, no
linux-builder). It boots the **stock** NixOS aarch64 minimal ISO under
`-accel hvf` (native speed, no emulation), installs the spike public key
through the serial console with `serial_drive.py` (macOS's `expect` segfaults
on `spawn -open` against this pty), stacks an on-disk overlay over `/nix/store`
because the live ISO's store is RAM-backed, builds the image, and `verify`
proves the result is genuinely aarch64 by booting it under HVF — which can only
execute same-arch code.

`sync` deliberately excludes `spike.key`, then asserts the guest has no copy.
`destroy` reclaims ~37 GB. Nothing it creates persists outside
`~/spike-arm-builder/`.
