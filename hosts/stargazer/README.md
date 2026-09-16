# Stargazer install runbook

> **Last updated:** 2026-09-16 (P9c Task 5). Rewritten for VMware Fusion. The
> Parallels version is in git history, and `docs/parallels-workarounds.md` keeps
> its lineage. `docs/vmware-fusion-workarounds.md` records what Fusion costs us
> and what to re-test on another hypervisor. This text has not been run end to
> end yet. P9c Task 8 is the first run and records its date and duration in §8.

Everything below is executed **by the owner, at the Mac**, top to bottom. Steps
marked **(owner/interactive)** need a human at a console, a passphrase, a
password prompt or the YubiKey. No agent can do them.

Conventions: commands prefixed `behemoth$` run on the Mac from the repo root
(`~/Documents/dotfiles`). `vm#` runs inside the guest as root or through `sudo`.
`vm$` runs inside the guest as `andreym`, from the graphical session where the
step says so. `iso#` runs in the NixOS installer ISO session.

---

## 1. What this VM is

Fallback devbox: an **aarch64 NixOS VM on VMware Fusion**, hosted on behemoth,
declared in this flake as `nixosConfigurations.stargazer`
(`hosts/stargazer/{default,common,hardware,disko}.nix` + `modules/nixos/*.nix`).
Installed from the public repo (`github:andrey-moor/dotfiles#stargazer`), disk
formatted by disko (LUKS2 + btrfs), home-manager integrated (same
`home/{core,dev}` bundles as the rest of the fleet), desktop = minimal
declarative Hyprland on vmwgfx, identity = himmelblau (Entra join + Intune
enrollment).

Nothing here is hand-installed. If a step below requires editing something
inside the VM by hand, that is a bug in the repo, not a step. Fix the module,
push, and `nixos-rebuild switch` instead.

**Compliance posture, read this once.** The device must be *fully compliant* in
Intune. Intune's "Allowed Distributions" rule is evaluated **client-side** by
himmelblau from `/etc/os-release`, and the tenant allows only `rhel` and
`ubuntu`. himmelblau exposes no override. `modules/nixos/intune-identity.nix`
therefore makes `/etc/os-release` report **Ubuntu 24.04**. This is a conscious
owner decision, deliberately reversing spec §8 step 8. See
[the P9 plan](../../docs/superpowers/plans/2026-09-01-env-refactor-p9-stargazer-nixos-vm.md)
and [the research notes](../../docs/superpowers/plans/2026-09-01-p9-research-notes.md) §4/§6.
`system.nixos.*`, `nixos-version` and `/etc/lsb-release` stay honest. Only
`/etc/os-release` lies, and only to satisfy that one rule.

### Prerequisites

- [ ] **VMware Fusion 26.0.1 or later**, installed from Broadcom's portal. There
      is no Homebrew cask, so the download is manual and needs a portal account.
- [ ] **At least 150 GB free** under `~/Virtual Machines.localized`
      (`scripts/stargazer-vm create` refuses below that). The disk is 256 GB
      growable, so this is headroom, not immediate consumption.
- [ ] **1Password unlocked** on the Mac, holding three things: the SSH agent
      keys (§4.1 uses them to reach the installer), the Secure Note
      **"sops age key (dotfiles admin)"** (§4.3b), and the Documents
      **"stargazer ssh host key"** and **"stargazer ssh host key pub"** (§3).
- [ ] **A YubiKey** (§6 only). It is plugged into the **Mac** and connected to
      the VM from Fusion's **Virtual Machine** menu, under **USB & Bluetooth**.
      If VirtualHere is sharing it with rocinante, disconnect it there first.
- [ ] Network access to `channels.nixos.org`, `cache.nixos.org` and
      `github.com`.

---

## 2. Create the VM

`scripts/stargazer-vm` is the only thing allowed to touch this VM, and it writes
the whole `.vmx` itself. Fusion's own `vmcli VM Create` produces a skeleton with
no disk, NIC or CD-ROM. The script hard-codes the name `stargazer` (`--drill`
switches it to `stargazer-drill`, §8) and refuses any other name, so no
other VM on this Mac can be touched.

```bash
behemoth$ ./scripts/stargazer-vm iso
behemoth$ ./scripts/stargazer-vm create
behemoth$ ./scripts/stargazer-vm up
```

`iso` downloads the **nixos-unstable aarch64 minimal ISO** into
`~/Virtual Machines.localized/iso` and verifies its sha256. It comes first
because `create` refuses to run without it.

What `create` writes. Do not re-do any of it in the Fusion GUI:

| Setting | Value | Why |
|---|---|---|
| CPUs / RAM | 8 vCPU / 16 GB | behemoth is 16 cores / 128 GB and Nostromo takes 10 / 64 |
| Disk | 256 GB growable NVMe (`nvme0:0`) | Fusion gives Arm guests NVMe, so `hosts/stargazer/disko.nix` targets `/dev/nvme0n1` |
| Firmware | EFI, Secure Boot **off** | the installer ISO is unsigned. §7 turns Secure Boot on afterwards |
| Network | NAT on `vmxnet3` | the guest link is `enp2s0` and the address is reachable from behemoth only |
| Video | SVGA with 3D, 4 GB graphics memory | OpenGL 4.3 through SVGA3D |
| Display | `gui.fitGuestUsingNativeDisplayResolution` | the guest gets Retina pixels, and `hosts/stargazer/default.nix` sets Hyprland scale 2 to match |
| USB | `usb.generic.allowHID`, `usb.generic.allowLastHID` | YubiKey passthrough. Fusion keeps HID devices on the Mac without both keys |
| Identity | `uuid.action = "keep"` | a power-on never stops at the "moved or copied" question |
| Rest | hdaudio sound, USB 3.1 plus EHCI, the ISO on `sata0:1` connected at power-on | sound for the hand tests, and the ISO so the first boot lands in the installer |

`up` powers the VM on in a Fusion window. `create` does not.

---

## 3. The host key

**Do this before installing.** The host's secrets (the himmelblau tenant
drop-in, the wayvnc password and the Secure Boot signing key) are age-encrypted
to the recipients listed in `.sops.yaml`, and the recipient for this machine is
derived from its **SSH host key**. Every stargazer install reuses the same one,
which is why it lives in 1Password. Two facts make the ordering matter:

1. The flake is fetched as `github:andrey-moor/dotfiles#stargazer` at install
   time, by CI, and on every `system.autoUpgrade` run. A `github:` reference
   cannot see anything that is not committed and pushed.
2. `modules/nixos/himmelblau.nix` fails *soft*. An undecryptable tenant drop-in
   is a dangling symlink, which himmelblau silently skips. The machine boots
   perfectly and is simply domain-less. No error tells you it happened.

So fetch the key now and inject it into the target during the install (§4.3).
The first boot then decrypts everything. Use a scratch directory that is **not**
the repo. The private key must never be committed.

```bash
behemoth$ SCRATCH="$(mktemp -d)"; chmod 700 "$SCRATCH"
behemoth$ op document get "stargazer ssh host key" --vault Private --out-file "$SCRATCH/stargazer_host_ed25519_key"
behemoth$ op document get "stargazer ssh host key pub" --vault Private --out-file "$SCRATCH/stargazer_host_ed25519_key.pub"
behemoth$ chmod 600 "$SCRATCH/stargazer_host_ed25519_key"
behemoth$ nix run nixpkgs#ssh-to-age -- -i "$SCRATCH/stargazer_host_ed25519_key.pub"   # must equal &stargazer in .sops.yaml
```

`op` triggers a **Touch ID prompt**, so 1Password must be unlocked. Do not run
it while typing at the VM console: the prompt steals focus and the rest of the
keystrokes go to whatever is in front.

### Rotating the host key

Only needed when the key leaks. It regenerates the `&stargazer` recipient, so
every secret has to be re-encrypted and both 1Password Documents replaced.

```bash
behemoth$ ssh-keygen -q -t ed25519 -N '' -C stargazer \
            -f "$SCRATCH/stargazer_host_ed25519_key"

behemoth$ nix run nixpkgs#ssh-to-age -- -i "$SCRATCH/stargazer_host_ed25519_key.pub"
age1........................................................    # copy this
```

Edit `.sops.yaml` and put that value on the `&stargazer` anchor:

```yaml
keys:
  - &admin age13au8fs9h0p68htzmrggkq9tuc77vlv7h7d3v0n36rp33vz59ja3stlmfj3
  - &stargazer age1...          # <- the ssh-to-age output
creation_rules:
  - path_regex: secrets/.*\.yaml$
    key_groups:
      - age:
          - *admin
          - *stargazer
```

Re-encrypt **all three** secrets to the new recipient list. `updatekeys` has to
*decrypt* first, so it needs the **admin private key**. That key lives in
1Password, so hand it to sops through a short-lived temp file rather than
installing it:

```bash
behemoth$ agekey="$(mktemp)"; chmod 600 "$agekey"
behemoth$ op item get "sops age key (dotfiles admin)" --vault Private --fields notesPlain --reveal \
            | grep -oE 'AGE-SECRET-KEY-1[A-Z0-9]+' > "$agekey"
#          (`op read op://…` rejects the parentheses in the item name, and the
#          note's raw value does not parse as an age identity file as-is)
behemoth$ export SOPS_AGE_KEY_FILE="$agekey"
behemoth$ nix run nixpkgs#sops -- updatekeys -y secrets/wayvnc.yaml
behemoth$ nix run nixpkgs#sops -- updatekeys -y secrets/stargazer-tenant.yaml
behemoth$ nix run nixpkgs#sops -- updatekeys -y secrets/stargazer-sbctl.yaml
behemoth$ rm -f "$agekey"; unset SOPS_AGE_KEY_FILE
```

Check that all three files list **two** recipients, publish, and replace both
1Password Documents with the new pair so the next install finds the current key:

```bash
behemoth$ grep -c 'recipient:' secrets/*.yaml            # 2, 2 and 2
behemoth$ git commit -am 'chore(secrets): rotate the stargazer host recipient'
behemoth$ git push
behemoth$ op document edit "stargazer ssh host key"     "$SCRATCH/stargazer_host_ed25519_key"     --vault Private
behemoth$ op document edit "stargazer ssh host key pub" "$SCRATCH/stargazer_host_ed25519_key.pub" --vault Private
```

**Push before `nixos-install`.** The installer fetches `github:`. An unpushed
recipient is an invisible no-op, and the first boot comes up domain-less.

---

## 4. Install from the ISO (owner/interactive)

**4.1 get a shell.** The installer autologs `nixos` at the console with an
**empty password**, and sshd rejects empty passwords, so SSH is closed until the
guest has a key. There are no guest tools on the ISO, so this line goes in at
the console:

```
iso# sudo sh -c 'echo nameserver 1.1.1.1 > /etc/resolv.conf'; mkdir -p ~/.ssh && curl -fsSL https://github.com/andrey-moor.keys > ~/.ssh/authorized_keys && echo KEYS-OK
```

Type it by hand, or send it from behemoth. The single quotes survive if the
whole line is one double-quoted argument, and nothing in it needs escaping:

```bash
behemoth$ ./scripts/stargazer-vm type "sudo sh -c 'echo nameserver 1.1.1.1 > /etc/resolv.conf'; mkdir -p ~/.ssh && curl -fsSL https://github.com/andrey-moor.keys > ~/.ssh/authorized_keys && echo KEYS-OK"
```

Either way, look at the console before moving on. The line ends in
`echo KEYS-OK` so that one glance settles whether it arrived intact.

The resolv.conf half comes first because **Fusion's NAT DNS proxy does not
resolve on behemoth**. The lease hands the guest the gateway as its only
resolver, and that resolver answers nothing, so `curl` fails before it starts.
1.1.1.1 works. The second half pulls the 1Password-held public keys into the
installer, so `ssh` then works straight off the unlocked agent. (`iso# passwd`
and a throwaway password is the equivalent alternative.)

```bash
behemoth$ ip="$(./scripts/stargazer-vm ip)"
behemoth$ S="-o IdentitiesOnly=yes -i $HOME/.ssh/1p_personal.pub"
behemoth$ ssh $S nixos@"$ip" 'lsblk -dno NAME,SIZE,TYPE; ip -4 addr show enp2s0; curl -sI https://cache.nixos.org | head -1'
# expect: nvme0n1 256G disk / 192.168.x.y on enp2s0 / HTTP/2 200
```

`IdentitiesOnly=yes` with the public key file pins the agent to one identity.
Without it the 1Password agent offers every key it holds and sshd closes the
connection with "Too many authentication failures". Keep `$S` for the rest of
§4. `./scripts/stargazer-vm ip` reads Fusion's NAT DHCP lease file, so it
answers a few seconds after the guest takes its lease.

**4.2 partition and format.** disko formats `/dev/nvme0n1` per
`hosts/stargazer/disko.nix`: 1 GB ESP + LUKS2 (`cryptroot`) + btrfs
`@root/@home/@nix/@log`. The installer ISO does **not** have flakes enabled, so
the experimental features have to be passed explicitly (`nixos-install` adds
them itself, `nix run` does not).

**Run this at the console, never over SSH.** It prompts for the LUKS
passphrase, which should be typed into the VM window and nowhere else:

```
iso# sudo nix run --extra-experimental-features 'nix-command flakes' github:nix-community/disko -- --mode disko --flake github:andrey-moor/dotfiles#stargazer
iso# lsblk -f /dev/nvme0n1 && findmnt -R /mnt
```

The passphrase is asked twice. That slot is never removed. It is what makes the
image portable off Fusion and what the fire drill proves. Store it in 1Password
now.

`lsblk -f` shows `nvme0n1p1` vfat on `/mnt/boot` and `nvme0n1p2` crypto_LUKS
opened as `cryptroot`. `findmnt -R /mnt` shows the whole tree at once: `@root`
on `/mnt`, `@home` on `/mnt/home`, `@nix` on `/mnt/nix` and `@log` on
`/mnt/var/log`, all btrfs with `compress=zstd` and `noatime`.

**4.3 inject the host key** (this is what makes §3 pay off):

```bash
behemoth$ scp $S "$SCRATCH/stargazer_host_ed25519_key" "$SCRATCH/stargazer_host_ed25519_key.pub" nixos@"$ip":/tmp/
behemoth$ ssh $S nixos@"$ip" '
  sudo install -Dm600 /tmp/stargazer_host_ed25519_key     /mnt/etc/ssh/ssh_host_ed25519_key
  sudo install -Dm644 /tmp/stargazer_host_ed25519_key.pub /mnt/etc/ssh/ssh_host_ed25519_key.pub
  shred -u /tmp/stargazer_host_ed25519_key'
```

**4.3b place the Secure Boot signing material.** `nixos-install` runs
lanzaboote's bootloader step *without* activating the system, so the files that
sops-nix and tmpfiles would create at activation must already be under `/mnt`.
Otherwise the install fails with `Failed to read public key from
/var/lib/sbctl/keys/db/db.pem`. The private half needs the admin age key. The
public half and the GUID are plain files in the repo. sops-nix replaces the
regular key file with its symlink on the first activation, so nothing is left
behind.

```bash
behemoth$ agekey="$(mktemp)"; chmod 600 "$agekey"
behemoth$ op item get "sops age key (dotfiles admin)" --vault Private --fields notesPlain --reveal \
            | grep -oE 'AGE-SECRET-KEY-1[A-Z0-9]+' > "$agekey"
behemoth$ SOPS_AGE_KEY_FILE="$agekey" nix run nixpkgs#sops -- -d --extract '["db.key"]' secrets/stargazer-sbctl.yaml \
            | ssh $S nixos@"$ip" 'sudo sh -c "umask 077; mkdir -p /mnt/var/lib/sbctl/keys/db && cat > /mnt/var/lib/sbctl/keys/db/db.key"'
behemoth$ rm -f "$agekey"
behemoth$ ssh $S nixos@"$ip" 'sudo wc -c /mnt/var/lib/sbctl/keys/db/db.key'   # must not be 0
behemoth$ scp $S hosts/stargazer/secureboot/db.pem hosts/stargazer/secureboot/GUID nixos@"$ip":/tmp/
behemoth$ ssh $S nixos@"$ip" '
  sudo install -Dm400 /tmp/db.pem /mnt/var/lib/sbctl/keys/db/db.pem
  sudo install -Dm644 /tmp/GUID   /mnt/var/lib/sbctl/GUID'
```

Check that byte count. The key is written through a pipe with nothing watching
it, so a failed 1Password lookup or a `grep` that matched nothing leaves a zero
byte file. Nothing notices until lanzaboote refuses it at the very end of 4.4,
after the whole build.

**4.4 install.** Run it **detached**, so an SSH drop cannot kill the build:

```
iso# nohup sudo nixos-install --flake github:andrey-moor/dotfiles#stargazer --no-root-passwd > /tmp/nixos-install.log 2>&1 &
iso# tail -f /tmp/nixos-install.log        # done at "installation finished!"
```

Expect a long build. Anything outside the binary cache is compiled here, which
includes the patched Hyprland and himmelblau's Rust crates. If it fails on
evaluation, the fix belongs in the repo: push, and re-run the same command.
Nothing is lost, and `--refresh` is not needed because each `nixos-install`
re-resolves the ref.

**4.5 set the login password** for `andreym`. root has none, and greetd needs
something to log in with before Entra is joined:

```
iso# sudo nixos-enter --root /mnt -c 'passwd andreym'
```

**4.6 eject the ISO and boot from disk.**

```bash
iso# sudo poweroff
behemoth$ ./scripts/stargazer-vm cdrom off
behemoth$ ./scripts/stargazer-vm up
behemoth$ rm -rf "$SCRATCH"
```

`$SCRATCH` holds the private host key, so it goes as soon as the install is
done. A fire drill (§8) fetches the same key from 1Password again.

---

## 5. First boot and verification (owner/interactive)

At the Fusion console: type the **LUKS passphrase** at the initrd prompt, then
log in as `andreym` at the `tuigreet` screen with the §4.5 password. The session
it starts is Hyprland. The console runs at 1280x800 until the VMware tools start
inside the session, which is expected.

Bring up the tailnet. SSH is firewalled to `tailscale0` and `enp2s0` only, so
this is the last thing that needs the console:

```bash
vm# sudo tailscale up
vm# tailscale ip -4          # note the 100.x address
```

From here on `ssh andreym@stargazer` works from behemoth over the tailnet.

### Verification checklist

```bash
# Secrets decrypted (the §3 payoff. An empty or dangling file here means the
# &stargazer recipient never landed. See Troubleshooting)
vm# cat /etc/himmelblau/himmelblau.conf.d/10-tenant.conf     # [<domain>] + tenant_id
vm# sudo cat /run/secrets/rendered/himmelblau-user-map       # andreym:<upn>
vm# systemctl status himmelblaud himmelblaud-tasks           # both active

# Disk + identity
vm# sudo cryptsetup status cryptroot                          # active, LUKS2
vm# cat /etc/os-release                                       # ID=ubuntu VERSION_ID="24.04"
vm# nixos-version                                             # still honest NixOS

# GPU + desktop
vm$ glxinfo -B | grep -i 'renderer'                                    # SVGA3D, not llvmpipe
vm$ systemctl --user is-active virtio-gpu-resize vmware-clipboard-bridge   # active, active
vm$ pgrep -fa 'vmtoolsd -n vmusr'                                        # the copy/paste agent
vm# tailscale status --self | head -1                                    # node name is exactly stargazer

# Services
vm$ systemctl --user status wayvnc
vm# systemctl list-timers nixos-upgrade.timer    # present, persistent, daily

# home-manager
vm$ ls -l ~/.agents/AGENTS.md ~/.config/nvim
```

**The desktop follows the host window only while that window is on screen.**
Fusion reports a new size when someone drags the window, and it stops reporting
while the window is hidden or minimized. So test a resize with the Fusion window
in front, and expect a desktop that was resized behind your back to keep its old
size until the window is visible again.

**The HM symlinks are out-of-store symlinks into `~/dotfiles`** (`dotfilesDir =
/home/andreym/dotfiles` in `flake.nix`). Until the repo is cloned they dangle.
That is expected, not a failure:

```bash
vm$ git clone https://github.com/andrey-moor/dotfiles ~/dotfiles
vm$ ls -l ~/.config/nvim         # -> /home/andreym/dotfiles/config/nvim, now resolves
```

**Which flake ref to rebuild from, pick deliberately:**

- `sudo nixos-rebuild switch --flake github:andrey-moor/dotfiles#stargazer --refresh`
  is the canonical path. Identical to what `nixos-install` and
  `system.autoUpgrade` use, so the machine can never drift from what CI builds.
  `--refresh` defeats the flake eval cache for the moving `main` ref.
- `sudo nixos-rebuild switch --flake ~/dotfiles#stargazer` is for iterating on a
  change from inside the VM. Faster (no fetch), but it only sees **git-tracked**
  files, so `git add` anything new first. Remember that `autoUpgrade` will pull
  `github:` on its next run and quietly replace your local state.

**Pin wayvnc to the tailnet address.** `hosts/stargazer/common.nix` leaves
`modules.linux.wayvnc.address` at the module default `0.0.0.0` and says hosts
pin it once they have joined. Do that now, on behemoth, using the
`tailscale ip -4` output. In `hosts/stargazer/default.nix`:

```nix
  # Tailnet address, pinned once the node joined (README §5).
  home-manager.users.andreym.modules.linux.wayvnc.address = "100.x.y.z";
```

Commit, push, `nixos-rebuild switch` in the VM. The firewall already restricts
wayvnc to `tailscale0`. This makes the binding explicit rather than relying on
the firewall alone.

Then snapshot the stopped VM:

```bash
vm# sudo poweroff
behemoth$ ./scripts/stargazer-vm snapshot installed
```

---

## 6. Enrollment ceremony (owner, local console + YubiKey)

Start from a snapshot, taken with the VM stopped. A failed Entra join is much
cheaper to retry from one than to unpick by hand:

```bash
vm# sudo poweroff                                    # if it is still running
behemoth$ ./scripts/stargazer-vm snapshot pre-enroll
behemoth$ ./scripts/stargazer-vm up
```

**This must happen at the Fusion console, not over SSH.** The first factor is a
FIDO security key (passwordless), and a `pam_himmelblau` FIDO prompt over SSH is
a dead end. `enable_passwordless_security_key` needs a local console.

The security key reaches the guest through Fusion's **USB passthrough**, not
smart-card sharing. Plug the YubiKey into the **Mac**, then connect it from the
**Virtual Machine** menu, under **USB & Bluetooth**, before logging in at
`tuigreet`. Confirm it arrived:

```bash
vm# grep -l 'Yubico' /sys/class/hidraw/*/device/uevent
```

**Ordering: join first, Intune second.** himmelblau runs with
`join_type = "join"`. The very first successful Entra authentication performs
the *device join*, and Intune enrollment follows from it on the same
authentication. Do not try to enroll before a successful login.

1. At `tuigreet`, log in as **`andreym`**, the local uid-1000 account. All four
   PAM entry points consult `user_map_file` and translate `andreym` to the
   tenant UPN before authenticating, so you never type the UPN.
2. Expect, in order: an Entra authentication prompt, a security-key prompt
   (touch the YubiKey, enter its PIN if configured), the device join, then the
   session start. Subsequent logins reuse the cached PRT and are much faster.
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

Compliance state itself is **not** persisted client-side. It is evaluated in the
daemon journal and decided server-side. Grep the journal for the rule names
(distribution, encryption, custom compliance) and confirm in the **Intune
portal** that the device is *Compliant*. Expected at this point: distribution
passes (os-release), encryption passes (LUKS), and **Secure Boot fails until
§7**.

Also read, from the portal, the **compliance-status validity period and grace
window**. It is invisible to the client, and it is what decides whether the
refresh-on-start design needs a keep-alive at all. Record the answer in the
plan.

**On any error, capture it verbatim**, the AADSTS code and the full journal
excerpt, into `spikes/intune/notes/` (gitignored). Never paste a tenant id,
domain, UPN, device id or an AADSTS payload into a committed file. This repo is
public.

Then snapshot the stopped VM:

```bash
vm# sudo poweroff
behemoth$ ./scripts/stargazer-vm snapshot enrolled
```

Snapshot it **stopped**. A live snapshot captures himmelblau's token cache, and
restoring it later hands Entra a refresh token it has since rotated. Everything
then fails with `AADSTS70000` while logins keep working. See §10.

---

## 7. Secure Boot (required for full compliance)

The tenant runs a custom-compliance discovery script that reports
`SecureBootEnabled` and looks for **Microsoft UEFI CA 2023** in the firmware's
`db`. The tenant-side rule requires both. Nothing on the NixOS side can fake
either, because himmelblau only ships the script's JSON and Intune decides. So
this step is **required**, not optional.

VMware's default key set already carries that CA, and
`./scripts/stargazer-vm secure-boot on` adds ours next to it: it converts
`hosts/stargazer/secureboot/db.pem` to DER inside the VM bundle, sets
`uefi.secureBoot.dbDefault.file0` and `dbDefault.append`, and moves the existing
NVRAM file aside the first time so the firmware regenerates its variable store
with both certificates. PK and KEK stay VMware's. On the guest side
`modules/nixos/secureboot.nix` is plain lanzaboote: it signs systemd-boot and
every UKI with the db key whose private half comes from sops.

A fresh install already carries the signing material from §4.3b. A system that
switches to this layout for the first time needs a `nixos-rebuild test` before
the switch, because lanzaboote installs the loader before activation and fails
with "Failed to read public key" if the files are not there yet.

### The ceremony

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

`sbverify --list <file>` is the signature check in general: `EFI/systemd/*.efi`
and every `EFI/Linux/*.efi` must show `CN=Database Key`. Do not use
`sbctl verify` on this host. It wants `keys/KEK/KEK.key`, which the sops layout
deliberately omits, and its Landlock sandbox cannot follow the key symlinks.

The systemd-boot menu and its countdown keep working under Secure Boot on
Fusion, so an older generation stays one keypress away at boot.

Then force a check-in (log out and back in) and confirm **Compliant** in the
portal.

**Optional, prove enforcement.** Put an unsigned EFI binary on the ESP and boot
it. The firmware refuses it, and `vmware.log` in
`~/Virtual Machines.localized/stargazer.vmwarevm` records
`SECUREBOOT: Image DENIED`.

**Rollback.** Secure Boot is never a boot requirement:

```bash
vm# sudo poweroff
behemoth$ ./scripts/stargazer-vm secure-boot off
behemoth$ ./scripts/stargazer-vm up          # boots again
```

Or `./scripts/stargazer-vm restore pre-sb`. Either way a later
`secure-boot on` regenerates the firmware's variable store from scratch, so our
certificate reaches `db` again. The LUKS **passphrase slot is never removed**,
so the disk is always openable regardless of firmware state.

---

## 8. Fire drill

The point is to prove this document, from scratch, without touching the real VM.
Last run: **not yet on Fusion.** P9c Task 8 builds the real machine from this
runbook and records its date and duration here.

```bash
behemoth$ ./scripts/stargazer-vm --drill create
behemoth$ ./scripts/stargazer-vm --drill up
```

The ISO is shared between the two VMs, so §2's download serves the drill too.
Every `./scripts/stargazer-vm` command below takes `--drill` as well.

Then run **§4** (4.1 through 4.6, including 4.3b) against `stargazer-drill`,
with these deltas:

- **Reuse the host key from §3.** It is already a sops recipient, so no repo
  change is needed and the drill VM decrypts on its first boot exactly like the
  real one. Two live machines sharing a host key is fine for a VM that lives for
  an hour and is then destroyed.
- **`sudo tailscale up --hostname stargazer-drill`**, otherwise it fights the
  real host for the `stargazer` node name. Run `tailscale logout` before
  destroying the drill VM.
- **Do not log in at the greeter, and do not enroll.** A second Entra join would
  create a duplicate device object. Check everything over SSH on the NAT
  address instead.
- **Secure Boot too.** Run `./scripts/stargazer-vm --drill secure-boot on` after
  a clean power-off, power on, and check `bootctl status` over SSH.

Success criteria, all of them, or the runbook has a gap that must be fixed here
before it is trusted:

- [ ] the LUKS prompt appears and greetd comes up behind it
- [ ] `10-tenant.conf`, the user map and `/run/secrets/sbctl-db-key` decrypt on
      the first boot (the §3 payoff)
- [ ] `cryptsetup status cryptroot` is active, LUKS2
- [ ] `systemctl list-timers nixos-upgrade.timer` lists it
- [ ] with Secure Boot on: `bootctl status` says enabled, and `sbverify --list`
      says `CN=Database Key` on the UKI

Not provable in the drill: the Hyprland session, SVGA3D rendering, the clipboard
bridge and wayvnc, which all need a logged-in user. They are verified on the
real VM in §5.

Record the actual time. Any hand-fix you had to invent is a repo bug. Fix the
module, push, and re-run the drill until it passes clean.

```bash
behemoth$ ./scripts/stargazer-vm --drill destroy      # double confirmation
```

---

## 9. Day-2 operations

**Updates.** `system.autoUpgrade` (see `modules/nixos/base.nix`) runs
`nixos-rebuild switch --flake github:andrey-moor/dotfiles#stargazer` daily, with
`persistent = true` so a missed run fires on the next boot or resume. That is
the whole point on a VM that is suspended more than it runs.
`allowReboot = false`, so a kernel change lands on the next manual reboot.

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
behemoth$ ./scripts/stargazer-vm restore installed     # stops the VM first
```

Snapshots this runbook creates, in order: `installed`, `pre-enroll`,
`enrolled`, `pre-sb`.

**Suspend and resume.** `./scripts/stargazer-vm suspend` and
`./scripts/stargazer-vm resume`. A resumed VM keeps LUKS unlocked and its
session alive. Only a cold boot (`down` then `up`) asks for the passphrase.
`./scripts/stargazer-vm status` prints the power state and the NAT address.

**After a Hyprland package change, restart greetd while no session is running:**

```bash
vm# sudo systemctl restart greetd
```

**Display size after a reload.** Every `nixos-rebuild switch` and every
`hyprctl reload` briefly returns the display to its login-time size. The resize
follower puts the current size back within 2 seconds.

---

## 10. Troubleshooting

**Power-on stops at "moved or copied".** `uuid.action` is missing from the
`.vmx`. Answer **"I Moved It"**, never "I Copied It", which gives the VM a new
hardware UUID and MAC address. Then fix it for good, with the VM off:

```bash
behemoth$ ./scripts/stargazer-vm set uuid.action keep
```

**The installer cannot resolve hosts.** Fusion's NAT DNS proxy fails on
behemoth: the lease points the guest at the gateway, which answers nothing.
Use the resolv.conf line from §4.1.

**The desktop stays small or does not follow a resize.** Fusion sends the window
size to the guest only while its window is on screen. Switch to the window, or
drag a corner, and the follower picks the new size up within about a second.
Check `systemctl --user status virtio-gpu-resize` if it does not.

**GPU apps fail with "invalid arguments for wl_surface.attach".** Hyprland is
running without the vmwgfx DMA-BUF patch, so it rejects every GPU client buffer
while shared-memory clients such as waybar keep working. Check
`modules/nixos/vmware-guest.nix`, which pins the patch to one Hyprland version,
then restart greetd with no session running.

**Copy and paste does not reach the Mac or the VM.** Hyprland refuses clipboard
access to X11 clients that do not have focus, and the VMware copy/paste agent
has no window at all, so the bridge in `modules/nixos/vmware-guest.nix` carries
text between the X11 and Wayland clipboards. Check both halves first:

```bash
vm$ systemctl --user status vmware-clipboard-bridge
vm$ pgrep -fa 'vmtoolsd -n vmusr'
```

Then test the boundary the bridge covers, without involving the Mac:

```bash
vm$ XC=$(nix build --no-link --print-out-paths nixpkgs#xclip)/bin/xclip
vm$ printf 'x11-probe' | setsid "$XC" -selection clipboard -t UTF8_STRING >/dev/null 2>&1 & sleep 1.5
vm$ [ "$(wl-paste -n --type text)" = x11-probe ] && echo X11-TO-WAYLAND-OK
vm$ printf 'wl-probe' | setsid wl-copy >/dev/null 2>&1; sleep 1.5
vm$ [ "$("$XC" -o -selection clipboard -t UTF8_STRING)" = wl-probe ] && echo WAYLAND-TO-X11-OK
```

**The YubiKey is not in the guest.** Connect it from Fusion's **Virtual
Machine** menu, under **USB & Bluetooth**. The `.vmx` must contain both
`usb.generic.allowHID` and `usb.generic.allowLastHID`, or Fusion keeps every HID
device on the Mac. VirtualHere may also be holding the key for rocinante, in
which case disconnect it there first.

**greetd loops back to the login prompt.** Almost always the session command
failing instantly. Read `journalctl -u greetd -b` and
`journalctl -b | grep -i hyprland`. If it started after the himmelblau module
landed, it is a PAM problem, not a compositor one: read
`journalctl -u himmelblaud -b` and try logging in on a TTY (`Ctrl-Alt-F2`) to
separate the two. `pam_allow_groups` is deliberately unset (null = allow all),
because an empty list would lock everyone out.

**`/etc/himmelblau/himmelblau.conf.d/` has no `10-tenant.conf`, or it is
empty.** The host cannot decrypt `secrets/stargazer-tenant.yaml`. Either its age
recipient is missing from `.sops.yaml`, or the host key on disk is not the one
§3 registered. This fails **silently by design**: `collect_drop_ins()` follows
symlinks and skips dangling ones, so the machine boots domain-less rather than
refusing to build. Diagnose:

```bash
vm# ls -l /etc/himmelblau/himmelblau.conf.d/ /run/secrets/rendered/
behemoth$ ssh-keyscan -t ed25519 stargazer \
            | nix run nixpkgs#ssh-to-age          # compare with .sops.yaml
```

sops-nix runs as an activation script (`setupSecrets`), not a unit, so its
errors appear in the `nixos-rebuild` or `nixos-upgrade` output rather than a
service log: `journalctl -u nixos-upgrade -n 100`, or re-run the switch and read
it. Fix by re-installing the 1Password host key (§3, §4.3), or by re-deriving
the recipient from the installed key and rotating.

**`himmelblaud-tasks` fails with status 226/NAMESPACE.** It mounts
`/run/himmelblaud`, which only exists once `himmelblaud` has created its
`RuntimeDirectory`. `modules/nixos/himmelblau.nix` adds the missing ordering
(`after = [ "himmelblaud.service" ]`). If you still see it, the unit raced on a
cold boot: `systemctl restart himmelblaud-tasks`, then check whether the drop-in
survived (`systemctl cat himmelblaud-tasks`).

**Compliance fails only on "Microsoft UEFI CA 2023 certificate is missing"
although `mokutil --db` lists it.** The tenant's discovery script probes db with
`mokutil`, `efi-readvar` or `openssl` plus `strings`, and himmelblaud-tasks runs
it with the unit's PATH. The module puts those tools on that PATH
(`systemd.services.himmelblaud-tasks.path`). If the rule still fails, the daemon
is running with a stale environment: `sudo systemctl restart himmelblaud-tasks`,
then `aad-tool compliance-check`. The first verdict after a report can still be
the server's previous state, so run it twice.

**Login works but `aad-tool compliance-check` fails with "could not acquire
tokens", and the journal shows `AADSTS70000: Provided grant is invalid` on every
refresh.** The cached refresh token is one Entra has since rotated. This is what
restoring a *live* snapshot does: it rolls `/var/cache/himmelblaud` back to an
older token. Hello-PIN logins keep succeeding, because they unseal the cached
PRT locally, so it looks healthy until something needs Graph or Intune. Fix from
inside the graphical session, then re-run the check:

```bash
vm$ aad-tool auth-test --name andreym --force-reauth   # password + MFA, mints a fresh PRT
vm$ aad-tool compliance-check
```

Prefer snapshots of a *stopped* VM for anything you expect to restore.

**Everything builds but nothing changed.** `--flake github:…` is a moving ref
behind the flake eval cache. Add `--refresh`.
