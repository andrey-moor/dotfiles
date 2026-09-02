# Stargazer — install runbook

> **Last updated:** 2026-09-01 (P9). Replaces the Arch/armarchy/Rosetta guide,
> which is archived under [`docs/archive/`](../../docs/archive/).

Everything below is executed **by the owner, at the Mac**, top to bottom. Steps
marked **(owner/interactive)** need a human at a console, a passphrase, a
password prompt or the YubiKey — no agent can do them.

Conventions: commands prefixed `behemoth$` run on the Mac from the repo root
(`~/Documents/dotfiles`); `vm#` runs inside the guest (as root or via `sudo`);
`iso#` runs in the NixOS installer ISO session.

---

## 1. What this VM is

Fallback devbox: an **aarch64 NixOS VM on Parallels**, hosted on behemoth,
declared in this flake as `nixosConfigurations.stargazer`
(`hosts/stargazer/{default,hardware,disko}.nix` + `modules/nixos/*.nix`).
Installed from the public repo (`github:andrey-moor/dotfiles#stargazer`), disk
formatted by disko (LUKS2 + btrfs), home-manager integrated (same
`home/{core,dev}` bundles as the rest of the fleet), desktop = minimal
declarative Hyprland on virtio-gpu, identity = himmelblau (Entra join + Intune
enrollment).

Nothing here is hand-installed. If a step below requires editing something
inside the VM by hand, that is a bug in the repo, not a step — fix the module,
push, and `nixos-rebuild switch` instead.

**Compliance posture — read this once.** The device must be *fully compliant*
in Intune. Intune's "Allowed Distributions" rule is evaluated **client-side** by
himmelblau from `/etc/os-release`, and the tenant allows only `rhel` and
`ubuntu`; himmelblau exposes no override. `modules/nixos/intune-identity.nix`
therefore makes `/etc/os-release` report **Ubuntu 24.04**. This is a conscious
owner decision, deliberately reversing spec §8 step 8 — see
[the P9 plan](../../docs/superpowers/plans/2026-09-01-env-refactor-p9-stargazer-nixos-vm.md)
and [the research notes](../../docs/superpowers/plans/2026-09-01-p9-research-notes.md) §4/§6.
`system.nixos.*`, `nixos-version` and `/etc/lsb-release` stay honest; only
`/etc/os-release` lies, and only to satisfy that one rule.

### Prerequisites

- [ ] **Parallels Desktop 27** (Pro/Business — `prlctl` required).
- [ ] **≥ 150 GB free** in `~/Parallels` (`scripts/stargazer-vm create` refuses
      below that). The disk is 256 GB *expanding*, so this is headroom, not
      immediate consumption.
- [ ] **1Password unlocked** on the Mac (SSH agent for the `git push` in step 3).
- [ ] **The admin age key** readable for sops:
      `~/Library/Application Support/sops/age/keys.txt` (mode 600). It is the
      only key that can currently decrypt `secrets/*.yaml`.
- [ ] **YubiKey** to hand (step 6 only). Smart-card sharing is turned on by the
      create script; the key must be plugged into the **Mac**, and the Parallels
      window must have focus, for the guest to see it.
- [ ] Network reachable to `channels.nixos.org` and `cache.nixos.org`.

---

## 2. Create the VM and attach the ISO

`scripts/stargazer-vm` is the only thing allowed to touch this VM. It hard-codes
the name `stargazer-nixos` (`--drill` switches it to `stargazer-drill`, step 8)
and refuses anything else — **Nostromo and `spike-himmelblau-arm` must never be
mutated.**

```bash
behemoth$ ./scripts/stargazer-vm create
behemoth$ ./scripts/stargazer-vm iso
behemoth$ ./scripts/stargazer-vm snapshot blank-iso
behemoth$ ./scripts/stargazer-vm up
```

What `create` applies (do not re-do this in the Parallels GUI):

| Setting | Value | Why |
|---|---|---|
| CPUs / RAM | 8 vCPU / 32 GB | behemoth is 16 cores / 128 GB and Nostromo takes 10 / 64 |
| Disk | 256 GB expanding, **SATA** | Parallels offers ide/scsi/sata/nvme — *no virtio disk*; `disko.nix` targets `/dev/sda` |
| Firmware | `--bios-type efi-arm64` | |
| Secure Boot | **off** | until step 7 enrolls lanzaboote's keys |
| vTPM | **absent** | Windows-only in Parallels; himmelblau can't use one anyway (upstream #1656) |
| Network | **bridged** (LAN DHCP), **virtio** adapter | Shared NAT is broken on behemoth (its DHCP never issued a lease); MTU 1400 from `modules/nixos/parallels-guest.nix` stays harmless on bridged |
| Video | virtio, 3D "Highest" | virgl acceleration |
| Smart card | shared | YubiKey at the local console |

`iso` downloads the **nixos-unstable aarch64 minimal ISO**, verifies its sha256,
attaches it as `cdrom0` and sets the boot order to `cdrom0 hdd0`.

---

## 3. Pre-generate the host key and register the sops recipient (owner)

**Do this before installing.** The host's secrets — the himmelblau tenant
drop-in and the wayvnc password — are age-encrypted to recipients listed in
`.sops.yaml`, and the recipient for this machine is derived from its **SSH host
key**. Two facts make the ordering matter:

1. The flake is fetched as `github:andrey-moor/dotfiles#stargazer` at install
   time, by CI, and on every `system.autoUpgrade` run. A `github:` reference
   cannot see anything that is not committed and pushed.
2. `modules/nixos/himmelblau.nix` fails *soft*: an undecryptable tenant drop-in
   is a dangling symlink, which himmelblau silently skips. The machine boots
   perfectly and is simply domain-less — no error tells you it happened.

So: generate the keypair here, register it, push, and inject it into the target
during the install (step 4). The first boot then decrypts everything.

```bash
behemoth$ ssh-keygen -t ed25519 -N '' -C 'root@stargazer' \
            -f /tmp/stargazer_host_ed25519_key

behemoth$ nix run nixpkgs#ssh-to-age -- -i /tmp/stargazer_host_ed25519_key.pub
age1........................................................    # copy this
```

Edit `.sops.yaml` — replace the commented placeholder with the real key and
uncomment the reference in the creation rule:

```yaml
keys:
  - &admin age13au8fs9h0p68htzmrggkq9tuc77vlv7h7d3v0n36rp33vz59ja3stlmfj3
  - &stargazer age1...          # <- the ssh-to-age output
creation_rules:
  - path_regex: secrets/.*\.yaml$
    key_groups:
      - age:
          - *admin
          - *stargazer          # <- uncommented
```

Re-encrypt **both** secrets to the new recipient list and publish:

```bash
behemoth$ nix run nixpkgs#sops -- updatekeys secrets/wayvnc.yaml
behemoth$ nix run nixpkgs#sops -- updatekeys secrets/stargazer-tenant.yaml
behemoth$ git commit -am 'chore(secrets): add stargazer host recipient'
behemoth$ git push
```

> The comment block in `.sops.yaml` describes the *other* ordering (derive the
> recipient from the installed machine's key after first boot, then switch a
> second time). That works too, but it means the first boot comes up
> domain-less. Pre-generating is the path this runbook takes.

Keep `/tmp/stargazer_host_ed25519_key*` until step 4 is done; then delete it
from the Mac (`shred -u` / `rm -P`). The same keypair is reused by the fire
drill (step 8), so if a drill is planned, park it somewhere deliberate instead.

---

## 4. Install from the ISO (owner/interactive)

**4.1 — get a shell.** The installer autologs `nixos` at the Parallels console
with an empty password, and empty passwords cannot be used over SSH. At the
console:

```
iso# passwd            # set a throwaway password for the `nixos` user
```

Then find the address and connect:

```bash
behemoth$ ./scripts/stargazer-vm ip
behemoth$ ssh nixos@<ip>
```

If `ip` warns that the guest reports a `169.254.x` address, its DHCP lease is
gone; the script falls back to printing the **IPv6 link-local** address, which
must be used with the Mac-side bridge interface as the scope:

```bash
behemoth$ ssh 'nixos@fe80::xxxx:xxxx:xxxx:xxxx%bridge103'
```

(`bridge103` is whichever `bridgeN` holds `10.211.55.2` — `ifconfig | grep -B5 10.211.55.2`.)

**4.2 — partition and format.** disko formats `/dev/sda` per
`hosts/stargazer/disko.nix`: 1 GB ESP + LUKS2 (`cryptroot`) + btrfs
`@root/@home/@nix/@log`. The installer ISO does **not** have flakes enabled, so
the experimental features have to be passed explicitly (`nixos-install` adds
them itself; `nix run` does not):

```bash
iso# sudo nix --extra-experimental-features "nix-command flakes" \
       run github:nix-community/disko -- \
       --mode disko --flake github:andrey-moor/dotfiles#stargazer
```

You are prompted for the **LUKS passphrase** (twice). This slot is never
removed — it is what makes the image portable off Parallels and what the fire
drill proves. Store it in 1Password now.

disko leaves everything mounted under `/mnt`. Sanity-check before continuing:

```bash
iso# lsblk -f          # sda1 vfat /mnt/boot, sda2 crypto_LUKS -> cryptroot btrfs
iso# findmnt /mnt /mnt/boot /mnt/home /mnt/nix /mnt/var/log
```

**4.3 — inject the pre-generated host key** (this is what makes step 3 pay off):

```bash
behemoth$ scp /tmp/stargazer_host_ed25519_key /tmp/stargazer_host_ed25519_key.pub \
            nixos@<ip>:

iso# sudo install -d -m 755 /mnt/etc/ssh
iso# sudo install -m 600 ~/stargazer_host_ed25519_key     /mnt/etc/ssh/ssh_host_ed25519_key
iso# sudo install -m 644 ~/stargazer_host_ed25519_key.pub /mnt/etc/ssh/ssh_host_ed25519_key.pub
iso# rm ~/stargazer_host_ed25519_key*
```

**4.4 — install.**

```bash
iso# sudo nixos-install --flake github:andrey-moor/dotfiles#stargazer --no-root-passwd
```

Expect a long build (the closure is built from source for anything not in the
binary cache — Hyprland, himmelblau). If it fails on evaluation, the fix belongs
in the repo: push, and re-run the same command (nothing is lost; `--refresh` is
not needed because each `nixos-install` re-resolves the ref).

**4.5 — set the login password** for `andreym` (root has none, and greetd needs
*something* to log in with before Entra is joined):

```bash
iso# sudo nixos-enter --root /mnt -c 'passwd andreym'
```

**4.6 — eject the ISO and boot from disk.** `scripts/stargazer-vm` has no verb
for this; use `prlctl` directly, with the VM stopped:

```bash
iso# sudo poweroff
behemoth$ prlctl set stargazer-nixos --device-set cdrom0 --disconnect
behemoth$ prlctl set stargazer-nixos --device-bootorder "hdd0 cdrom0"
behemoth$ ./scripts/stargazer-vm up
```

---

## 5. First boot and verification (owner/interactive)

At the Parallels console: type the **LUKS passphrase** at the initrd prompt,
then log in as `andreym` at the `tuigreet` screen — the session it starts is
Hyprland.

Bring up the tailnet (SSH is firewalled to `tailscale0` only, so this is the
last thing that needs the console):

```bash
vm# sudo tailscale up
vm# tailscale ip -4          # note the 100.x address
```

From here on `ssh andreym@stargazer` works from behemoth over the tailnet.

### Verification checklist

```bash
# Secrets decrypted (this is the step-3 payoff — an empty/dangling file here
# means the &stargazer recipient never landed; see Troubleshooting)
vm# cat /etc/himmelblau/himmelblau.conf.d/10-tenant.conf     # [<domain>] + tenant_id
vm# sudo cat /run/secrets/rendered/himmelblau-user-map       # andreym:<upn>
vm# systemctl status himmelblaud himmelblaud-tasks           # both active

# Disk + identity
vm# sudo cryptsetup status cryptroot                          # active, LUKS2
vm# cat /etc/os-release                                       # ID=ubuntu VERSION_ID="24.04"
vm# nixos-version                                             # still honest NixOS

# GPU + desktop
vm# glxinfo -B | grep -i renderer     # "virgl" — NOT llvmpipe
vm# alacritty                          # launches, renders, no software-GL warning

# Services
vm# systemctl --user status wayvnc
vm# systemctl list-timers nixos-upgrade.timer    # present, persistent, daily

# home-manager
vm# ls -l ~/.agents/AGENTS.md ~/.config/nvim
```

**The HM symlinks are out-of-store symlinks into `~/dotfiles`** (`dotfilesDir =
/home/andreym/dotfiles` in `flake.nix`). Until the repo is cloned they dangle —
that is expected, not a failure:

```bash
vm# git clone https://github.com/andrey-moor/dotfiles ~/dotfiles
vm# ls -l ~/.config/nvim         # -> /home/andreym/dotfiles/config/nvim, now resolves
```

**Which flake ref to rebuild from — pick deliberately:**

- `sudo nixos-rebuild switch --flake github:andrey-moor/dotfiles#stargazer --refresh`
  — the canonical path. Identical to what `nixos-install` and
  `system.autoUpgrade` use, so the machine can never drift from what CI builds.
  `--refresh` defeats the flake eval cache for the moving `main` ref.
- `sudo nixos-rebuild switch --flake ~/dotfiles#stargazer` — iterating on a
  change from inside the VM. Faster (no fetch), but only sees **git-tracked**
  files, so `git add` anything new first, and remember `autoUpgrade` will still
  pull `github:` on its next run and quietly replace your local state.

**Pin wayvnc to the tailnet address.** `hosts/stargazer/default.nix` leaves
`modules.linux.wayvnc.address` at the module default `0.0.0.0` with a marker
comment saying to pin it once the host has joined the tailnet. Do that now, on
behemoth, using the `tailscale ip -4` output:

```nix
    modules.linux.wayvnc = {
      # ...
      address = "100.x.y.z";   # pinned after the first `tailscale up` (P9 Task 4)
    };
```

Commit, push, `nixos-rebuild switch` in the VM. (The firewall already restricts
it to `tailscale0`; this makes the binding explicit rather than relying on the
firewall alone.)

Then, with the VM stopped: **`./scripts/stargazer-vm snapshot installed`**.

---

## 6. Enrollment ceremony (owner, local console + YubiKey)

```bash
behemoth$ ./scripts/stargazer-vm snapshot pre-enroll
```

**This must happen at the Parallels console, not over SSH.** The first factor is
a FIDO security key (passwordless), and a `pam_himmelblau` FIDO prompt over SSH
is a dead end — `enable_passwordless_security_key` needs a local console. Plug
the YubiKey into the **Mac** and keep the Parallels window focused so smart-card
sharing hands it through.

**Ordering: join first, Intune second.** himmelblau runs with
`join_type = "join"`; the very first successful Entra authentication performs
the *device join*, and Intune enrollment follows from it on the same
authentication. Do not try to enroll before a successful login.

1. At `tuigreet`, log in as **`andreym`** — the local uid-1000 account. All four
   PAM entry points consult `user_map_file` and translate `andreym` to the
   tenant UPN before authenticating, so you never type the UPN.
2. Expect, in order: an Entra authentication prompt → a security-key prompt
   (touch the YubiKey; enter its PIN if configured) → device join → session
   start. Subsequent logins reuse the cached PRT and are much faster.
3. Watch it happen from a second console or over the tailnet:

```bash
vm# journalctl -u himmelblaud -f          # `debug = true`, so evaluation is visible here
vm# journalctl -u himmelblaud-tasks -f
```

### Checks after the ceremony

```bash
vm# aad-tool status                       # "working!"
vm# sudo cat /var/cache/himmelblaud/himmelblau.conf   # device id / Intune device id / graph URL
vm# sudo nix run nixpkgs#sqlite -- /var/cache/nss-himmelblau/policies.cache.db \
      'select * from policies;'          # the applied password policy
vm# id andreym                            # uid 1000, local groups + Entra groups merged
```

Compliance state itself is **not** persisted client-side — it is evaluated in
the daemon journal and decided server-side. Grep the journal for the rule names
(distribution, encryption, custom compliance) and confirm in the **Intune
portal** that the device is *Compliant*. Expected at this point: distribution
✅ (os-release), encryption ✅ (LUKS), **Secure Boot ❌ until step 7**.

Also read, from the portal, the **compliance-status validity period / grace
window** — it is invisible to the client, and it is what decides whether the
refresh-on-start design needs a keep-alive at all. Record the answer in the
plan.

**On any error, capture it verbatim** — the AADSTS code and the full journal
excerpt — into `spikes/intune/notes/` (gitignored). Never paste a tenant id,
domain, UPN, device id or an AADSTS payload into a committed file; this repo is
public.

```bash
behemoth$ ./scripts/stargazer-vm snapshot enrolled
```

---

## 7. Secure Boot (required for full compliance)

The tenant runs a custom-compliance discovery script that reports
`SecureBootEnabled`, and the tenant-side rule requires `"true"`. Nothing on the
NixOS side can fake it — himmelblau only ships the script's JSON, Intune
decides. So this step is **required**, not optional. See
`modules/nixos/secureboot.nix` for the module-side contract.

Two facts make it work here: the Parallels EDK II aa64 firmware boots in **setup
mode with an empty PK/KEK/db**, and `sbctl enroll-keys --microsoft` enrolls the
Microsoft 2011 **and 2023** CAs alongside our own key — the 2023 one is what the
discovery script's second check looks for once Secure Boot is on. `mokutil` (the
only reader of `db` that script can use) is installed by
`modules/nixos/himmelblau.nix`.

```bash
# 1. Confirm the firmware is still in setup mode. If this says anything other
#    than "disabled (setup)", STOP — Parallels installed a vendor PK and the
#    custom-key path is closed.
vm# bootctl status | head -20

# 2. Create the signing keys BEFORE enabling the module — lanzaboote signs at
#    switch time and needs /var/lib/sbctl to exist. sbctl is only in
#    systemPackages once the module is on, so run it from nixpkgs:
vm# sudo nix run nixpkgs#sbctl -- create-keys
```

3. Enable the module in `hosts/stargazer/default.nix` (on behemoth), commit,
   push:

```nix
  modules.nixos.secureboot.enable = true;
```

```bash
vm# sudo nixos-rebuild switch --flake github:andrey-moor/dotfiles#stargazer --refresh
vm# sudo sbctl verify           # the ESP's files should all be signed
```

4. Enroll the keys, including Microsoft's, then flip Secure Boot on in Parallels
   (VM stopped — there is no script verb for this):

```bash
vm# sudo sbctl enroll-keys --microsoft
vm# sudo poweroff
behemoth$ prlctl set stargazer-nixos --efi-secure-boot on
behemoth$ ./scripts/stargazer-vm up
```

5. After the LUKS prompt and login, verify:

```bash
vm# bootctl status | head -20       # Secure Boot: enabled (user)
vm# mokutil --sb-state              # SecureBoot enabled
vm# mokutil --db | grep -i '2023'   # Microsoft UEFI CA 2023 present
```

6. Force a check-in (log out and back in) and confirm **Compliant** in the
   portal. The discovery script now evaluates `SecureBootCA2023` for real — if
   it reports `Missing`, `enroll-keys` was run without `--microsoft`; re-run it.

**Rollback.** Secure Boot is never a boot requirement. If the VM will not boot:

```bash
behemoth$ prlctl set stargazer-nixos --efi-secure-boot off
behemoth$ ./scripts/stargazer-vm up          # boots again, unsigned
```

Then either pick an older generation in the boot menu or
`nixos-rebuild switch --rollback`. The LUKS **passphrase slot is never removed**,
so the disk is always openable regardless of firmware state.

---

## 8. Fire drill

The point is to prove this document, from scratch, without touching the real VM.

```bash
behemoth$ ./scripts/stargazer-vm --drill create
behemoth$ ./scripts/stargazer-vm --drill iso
behemoth$ ./scripts/stargazer-vm --drill up
```

Then repeat **steps 4 and 5** against `stargazer-drill`, with three deltas:

- **Reuse the step-3 host key.** It is already a sops recipient, so no repo
  change is needed and the drill VM decrypts on its first boot exactly like the
  real one. (Two live machines sharing a host key is fine for a VM that lives
  for an hour and is then destroyed.)
- **`tailscale up --hostname stargazer-drill`** — otherwise it fights the real
  host for the `stargazer` node name.
- **Do not enroll.** Skip step 6 entirely; a second Entra join would create a
  duplicate device object in the tenant.

Success criteria — all of them, or the runbook has a gap that must be fixed
here before it is trusted:

- [ ] boots to a Hyprland session after the LUKS passphrase
- [ ] `glxinfo -B` renderer is virgl; Alacritty renders
- [ ] tailnet up, SSH reachable only over it
- [ ] `10-tenant.conf` decrypted (non-empty, real domain)
- [ ] `systemctl list-timers nixos-upgrade.timer` present
- [ ] `~/.config/nvim` resolves after cloning `~/dotfiles`

Target: **under 90 minutes** wall clock, most of it the `nixos-install` build.
Record the actual time. Any hand-fix you had to invent is a repo bug — fix the
module, push, and re-run the drill until it passes clean.

```bash
behemoth$ ./scripts/stargazer-vm --drill destroy      # double confirmation
```

---

## 9. Day-2 operations

**Updates.** `system.autoUpgrade` (see `modules/nixos/base.nix`) runs
`nixos-rebuild switch --flake github:andrey-moor/dotfiles#stargazer` daily, with
`persistent = true` so a missed run fires on the next boot or resume — the whole
point on a VM that is suspended more than it runs. `allowReboot = false`: a
kernel change lands on the next manual reboot.

```bash
vm# systemctl list-timers nixos-upgrade.timer
vm# systemctl status nixos-upgrade
vm# journalctl -u nixos-upgrade -n 100
vm# sudo systemctl start nixos-upgrade          # run it now
```

Manual, when you want the change immediately:

```bash
vm# sudo nixos-rebuild switch --flake github:andrey-moor/dotfiles#stargazer --refresh
```

**Rollback**, cheapest first:

```bash
vm# sudo nixos-rebuild switch --rollback
vm# nix-env --list-generations --profile /nix/var/nix/profiles/system
# or pick an older generation in the systemd-boot menu at the next boot
behemoth$ prlctl snapshot-list stargazer-nixos
behemoth$ ./scripts/stargazer-vm restore installed     # stops the VM first
```

Snapshots this runbook creates, in order: `blank-iso`, `installed`,
`pre-enroll`, `enrolled`.

**Suspend / resume.** `./scripts/stargazer-vm suspend` and `resume` — a resumed
VM keeps LUKS unlocked and its session alive; only a cold boot
(`down` → `up`) asks for the passphrase. `status` prints state, addresses and
boot order.

**Retiring the old VM (owner-run, gated).** Only after the fire drill passes
*and* the new VM is enrolled and Compliant. Confirm nothing is left inside the
old `Stargazer` (it has been dormant since P1 — check `~/dev` and shell
history), then:

```bash
behemoth$ prlctl list -a
behemoth$ prlctl delete Stargazer
behemoth$ rm -rf ~/Parallels/Stargazer.pvm            # if delete left it behind
behemoth$ rm -f ~/Parallels/ArchBase-Template.pvm.tar.zst   # optional, ~big
```

---

## 10. Troubleshooting

**`ip` returns `169.254.x`, or SSH to the guest times out.**
The guest's DHCP client lost its lease on the Parallels shared network — the
spike VM does this too. `./scripts/stargazer-vm ip` detects it and prints the
**IPv6 link-local** address instead; use it with the bridge scope:
`ssh 'nixos@fe80::…%bridge103'`. Find the bridge with
`ifconfig | grep -B5 10.211.55.2`.

**MTU.** Entra/Intune traffic over Parallels shared NAT needs **MTU 1400**. This
is declarative (`modules/nixos/parallels-guest.nix`, `linkConfig.MTUBytes` on
`systemd.network`), and networkd's DHCP client has `UseMTU` off, so the lease
cannot undo it. Never set it by hand with `ip link set mtu` — that is exactly
what cost the spike VM its lease. Check with `ip link show enp0s5`.

**`/etc/himmelblau/himmelblau.conf.d/` has no `10-tenant.conf`, or it is empty.**
The host cannot decrypt `secrets/stargazer-tenant.yaml`: its age recipient is
missing from `.sops.yaml`, or the host key on disk is not the one step 3
registered. This fails **silently by design** — `collect_drop_ins()` follows
symlinks and skips dangling ones, so the machine boots domain-less rather than
refusing to build. Diagnose:

```bash
vm# ls -l /etc/himmelblau/himmelblau.conf.d/ /run/secrets/rendered/
behemoth$ ssh-keyscan -t ed25519 stargazer \
            | nix run nixpkgs#ssh-to-age          # compare with .sops.yaml
```

sops-nix runs as an activation script (`setupSecrets`), not a unit, so its errors
appear in the `nixos-rebuild` / `nixos-upgrade` output rather than a service log:
`journalctl -u nixos-upgrade -n 100` or re-run the switch and read it.

Fix: re-derive the recipient from the *installed* key, `sops updatekeys` both
secrets on behemoth, push, `nixos-rebuild switch --refresh`.

**`himmelblaud-tasks` fails with status 226/NAMESPACE.**
It mounts `/run/himmelblaud`, which only exists once `himmelblaud` has created
its `RuntimeDirectory`. `modules/nixos/himmelblau.nix` adds the missing ordering
(`after = [ "himmelblaud.service" ]`); if you still see it, the unit raced on a
cold boot — `systemctl restart himmelblaud-tasks` and check whether the drop-in
survived (`systemctl cat himmelblaud-tasks`).

**`glxinfo -B` says llvmpipe, or GL version is too low.**
virtio-gpu's DRM driver did not bind, and `simpledrm` is still holding the
framebuffer. `modules/nixos/parallels-guest.nix` loads `virtio_gpu` in the
initrd for exactly this reason. Check `dmesg | grep -i 'virtio_gpu\|simpledrm'`
and `ls /dev/dri`. Also confirm the VM really has 3D acceleration
(`prlctl list -i stargazer-nixos | grep -i '3d\|video'`). Note the ceiling:
**Parallels caps Linux guests at OpenGL 4.0**, which is why the terminal is
Alacritty (GL 3.3) and not Ghostty (needs 4.3) — llvmpipe is the *failure*
signal, GL 4.0 is not.

**greetd loops back to the login prompt.**
Almost always the session command failing instantly. Read
`journalctl -u greetd -b` and `journalctl -b | grep -i hyprland`. If it started
after the himmelblau module landed, it is a PAM problem, not a compositor one:
`journalctl -u himmelblaud -b` and try logging in on a TTY
(`Ctrl-Alt-F2`) to separate the two. `pam_allow_groups` is deliberately unset
(null = allow all) — an empty list would lock everyone out.

**Enrollment: FIDO prompt never appears.**
You are on SSH. It only works at the local console, with the YubiKey in the Mac
and the Parallels window focused (smart-card sharing is passthrough, not
network).

**Everything builds but nothing changed.**
`--flake github:…` is a moving ref behind the flake eval cache. Add `--refresh`.
