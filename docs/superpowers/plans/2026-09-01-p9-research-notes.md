# P9 Task 1 — Research notes (tenant-free)

**Date:** 2026-09-01. **Plan:** `2026-09-01-env-refactor-p9-stargazer-nixos-vm.md` Task 1.
**Method:** read-only. Pinned nixpkgs / home-manager / disko store paths, the himmelblau +
libhimmelblau source clones at today's HEAD, upstream docs, and read-only SSH into the
enrolled spike VM `spike-himmelblau-arm` (no VM state changed, no snapshots switched).

Tenant-bearing values (domain, tenant/device IDs, UPN, policy & rule IDs, the verbatim
custom-compliance script) live only in `spikes/intune/notes/p9-tenant-facts.md` and
`spikes/intune/notes/p9-discovery-script.txt` — both under the gitignored
`spikes/intune/notes/` tree (`.gitignore:87`). This file is public-safe.

---

## 0. Reading the spike VM — the documented access path is broken

`spikes/intune/scripts/spike-parallels ip` returns an IPv4 **link-local** address
(169.254.0.0/16). The guest's `dhcpcd` failed to rebind its shared-network lease and fell
back to IPv4LL, so there is no reachable IPv4 address; the Mac's
`/Library/Preferences/Parallels/parallels_dhcp_leases` still lists the old 10.211.55.x
lease for the VM's MAC but nothing answers there.

What works: **IPv6 link-local over the Parallels shared bridge**, e.g.
`ssh -i spikes/intune/spike.key root@fe80::<guest-eui64>%bridge103`
(find the guest link-local with `ndp -an | grep <mac>`; `bridge103` is the interface
holding 10.211.55.2). All findings below were collected that way.

The guest's `enp0s5` MTU is 1400, applied by hand (nothing in `/etc/systemd/network`,
no `/etc/dhcpcd.conf`, empty root shell history) — consistent with P2's "ephemeral
hand-fix". **The broken IPv4 lease is a live warning for `modules/nixos/himmelblau.nix`:
set the MTU declaratively and verify DHCP renewal still works over hours, not minutes.**

**Verdict:** the spike VM is readable but only over IPv6 link-local; `scripts/stargazer-vm ip`
must not copy `spike-parallels`'s IPv4-only `get_ip`, and the MTU rule must be declarative.

---

## 1. Parallels guest tools on aarch64 NixOS

- `nixos/modules/virtualisation/parallels-guest.nix` has **no platform gate**:
  `hardware.parallels.enable` + `hardware.parallels.package` (default `pkgs.prl-tools`)
  work on any Linux system string.
- `pkgs/by-name/pr/prl-tools/package.nix` — version **26.4.1-57516**,
  `meta.platforms = lib.platforms.linux`, `meta.license = unfree`. It explicitly branches
  on architecture: it extracts `prl-tools-lin-arm.iso` when
  `stdenv.hostPlatform.isAarch64` and installs from `tools/tools-arm64`.
  `nix eval` of `prl-tools.drvPath` for `aarch64-linux` succeeds (verified).
- **It ships userspace only.** `dontBuild = true`; the install phase copies
  `bin/*`, `sbin/prl_nettool`, `sbin/prl_snapshot`, `prlfsmountd`, `mount.fuse.prl_fsd`,
  `libPrl*` and a pm-sleep hook. **No kernel modules are built** (`prl_fs`, `prl_tg`,
  `prl_eth` are absent), even though the NixOS module still sets
  `boot.extraModulePackages = [ prl-tools ]` (a no-op here).
- Practical consequences: `prltoolsd`, `prlshprint` (bound to `cups.service`) and the user
  service `prlcc` are started; shared folders go through the FUSE helper; clipboard and
  dynamic resolution depend on the tools daemon and, in practice, on X11 helpers.
- Cost: the source is the full **Parallels Desktop DMG fetched from parallels.com**, and
  it is **unfree** — `nixpkgs.config.allowUnfreePredicate` (or `allowUnfree`) must be set
  for the host, and CI must be able to fetch it.
- The spike VM runs with `GuestTools: state=not_installed` and is perfectly usable:
  virtio-net, virtio-gpu with virgl, and SSH all work without the tools.
- Wayland caveat found upstream: with Parallels Tools installed, the clipboard helper
  `prlcp` spawns a ghost window that Hyprland tiles
  (<https://github.com/hyprwm/Hyprland/discussions/11882>).

**Verdict — supported but not worth enabling in v1.** `hardware.parallels.enable` evaluates
and builds on aarch64, but it buys only userspace helpers (no kernel modules), drags in an
unfree ~1 GB DMG fetch, and its clipboard daemon is a known Hyprland irritant. Ship
`modules/nixos/parallels-guest.nix` with virtio + virtio-gpu only and leave
`hardware.parallels.enable` as an **opt-in option, default false**, to be flipped later if
shared folders or dynamic resolution are actually wanted.

---

## 2. GPU acceleration: virtio-gpu + virgl, Hyprland, Ghostty

Measured on the spike VM (`journalctl -k`):

```
[drm] pci: virtio-vga detected at 0000:00:0a.0
[drm] features: +virgl -edid -resource_blob -host_visible
[drm] features: -context_init
[drm] Initialized virtio_gpu 0.1.0 ... on minor 1     (simpledrm holds minor 0)
```

- **virgl/OpenGL: yes.** nixpkgs `mesa` builds the `virgl` gallium driver unconditionally
  for every platform (`pkgs/development/libraries/mesa/default.nix`, flat `galliumDrivers`
  list passed as `mesonOption "gallium-drivers"`), installed as `virtio_gpu_dri.so`.
  `hardware.graphics.enable = true` is sufficient; `virglrenderer` is **host-side** and must
  not be added to the guest closure.
- **Vulkan: no.** Mesa's venus needs `RESOURCE_BLOB` + `CONTEXT_INIT` + a host-visible or
  guest-VRAM window; the guest reports `-resource_blob -host_visible -context_init`, so
  venus cannot initialise. Anything demanding Vulkan falls back to lavapipe (software).
  nixpkgs does build the `virtio` Vulkan driver on aarch64, but it will not bind here.
- **GL version ceiling is 4.0** on Parallels/Apple Silicon (Apple deprecated desktop GL;
  the host cannot forward more). virgl's theoretical ceiling is 4.3/GLES 3.2 and 4.6 needs
  blob+hostmem, which this device lacks.
- **Hyprland: fine.** Hyprland 0.50+ needs only GLES 3.0 (tries 3.2, falls back), and the
  Hyprland wiki explicitly blesses virtio-gpu. The aquamarine 0.4.5 black-screen regression
  on `virtio-vga-gl` (aquamarine #109) was fixed in PR #121 and is long past.
  - All `WLR_*` env vars are **dead** on aquamarine-era Hyprland — `WLR_RENDERER`,
    `WLR_DRM_NO_ATOMIC`, `WLR_NO_HARDWARE_CURSORS` are ignored. Do not copy them from
    VMware/QEMU guides. The replacement for the last one is the config option
    `cursor { no_hardware_cursors = true }`.
  - **`-edid` means no mode list**: pin the mode explicitly, e.g.
    `monitor = Virtual-1, 2560x1600@60, 0x0, 1`.
  - Only if scanout misbehaves, add `env = AQ_NO_MODIFIERS,1` (virtio-gpu KMS is
    effectively linear-only). `AQ_NO_ATOMIC` is a last resort; upstream discourages it.
- **Ghostty: this is the real problem.** Ghostty **1.2.0+ requires desktop OpenGL 4.3**
  (1.1.3 needed only 3.3). The pinned nixpkgs carries **ghostty 1.3.1**. There is a
  closed upstream report of exactly this configuration — Ghostty on arm64 Linux under
  Parallels on Apple Silicon — failing with *"OpenGL version is too old. Ghostty requires
  OpenGL 4.3"* against a reported GL 4.0, closed as a virtualization constraint, not a bug
  (<https://github.com/ghostty-org/ghostty/discussions/12611>). Ghostty has **no software
  fallback of its own**, but llvmpipe has been GL 4.5 conformant since Mesa 20.2, so
  forcing software GL for Ghostty alone clears the bar:
  `LIBGL_ALWAYS_SOFTWARE=1` (or `MESA_LOADER_DRIVER_OVERRIDE=llvmpipe`) in a wrapper plus a
  matching `.desktop` override. Never set it session-wide — that would throw away virgl.

**Verdict — GPU acceleration is available and Hyprland will use it; Ghostty will not.**
Configure `hardware.graphics.enable = true`, a pinned `monitor=` line, and no `WLR_*` vars.
The plan's acceptance criterion *"Ghostty runs (OpenGL renderer)"* is **not achievable on
hardware virgl** and must be restated: either ship Ghostty behind an llvmpipe wrapper
(accepting slow rendering), pin ghostty 1.1.3, or use a GL-lighter terminal (foot/kitty)
inside the VM. Recommendation: **llvmpipe-wrapped Ghostty**, so the terminal stays the same
across hosts, with `glxinfo -B` showing `virgl` for the session as the real GPU acceptance
check.

---

## 3. himmelblau on NixOS

### Version and pin

- Latest release: **`4.0.0`, tagged 2026-08-31** (commit `0b5e078a`); nothing newer as of
  2026-09-01. `main` carries an unreleased `5.0.0` in `Cargo.toml`. A `stable-4.x` branch
  exists at the same commit as the tag with no commits beyond it.
- At tag `4.0.0` the flake exposes `nixosModules.himmelblau`, `packages.<system>.{daemon,
  aad-tool,sso,broker,pam,nss,o365}`, `eachSystem = [ x86_64-linux aarch64-linux ]`, and
  `nix/modules/{himmelblau.nix,himmelblau-options.nix}` exist. Build is crate2nix-based.
  Its own nixpkgs input is `nixos-unstable`, so use
  `inputs.himmelblau.inputs.nixpkgs.follows = "nixpkgs"`.
- The spike VM is already running **4.0.0** (`aad-tool version` → `himmelblau 4.0.0`).

**Pin: `github:himmelblau-idm/himmelblau/4.0.0`.**

### Option surface (from `nix/modules/himmelblau-options.nix`, tag-equivalent HEAD)

`services.himmelblau.enable` + `services.himmelblau.settings.<key>` mirroring
`himmelblau.conf` one-for-one (the module renders an INI via `pkgs.formats.ini`, `[global]`
at the top level and nested attrsets as sections such as `offline_breakglass`). Plus
non-INI escapes: `daemonPackage` / `ssoPackage` / `brokerPackage` / `pamPackage` /
`nssPackage` (all `mkDefault`-wired from the flake), `debugFlag`, `tryUnsealFlag`,
`mfaSshWorkaroundFlag`, `pamServices` (default `[ passwd login systemd-user ]`, plus
`sudo`/`doas`/`sshd` when those are enabled).

Identity-relevant keys and their defaults:
`domain` (`nullOr (listOf str)`), `cn_name_mapping` (true), `id_attr_map`
(`name`|`uuid`|`rfc2307`, default `name`), `idmap_range` (`200000-2000200000`),
`subid_range`, `home_prefix` (`/home/`), `home_attr` (`uuid`|`spn`|`cn`, default `uuid`),
`home_alias` (default `spn`), `shell` (**default `/bin/bash`**), `local_groups`,
`sudo_groups` + `local_sudo_group`, `pam_allow_groups` (default `null` = everyone allowed;
`[ ]` would lock everyone out), `name_mapping_script`, `user_map_file`
(default `/etc/himmelblau/user-map`), `hsm_type`, `apply_policy`.

### Known open NixOS issues

| Issue | State | Impact here |
|---|---|---|
| [#1656](https://github.com/himmelblau-idm/himmelblau/issues/1656) — NixOS build does not enable hardware TPM support | open, no maintainer reply | The flake's daemon is built **without** the `tpm` cargo feature (no `tss`/`tpm2-tss` in `default.nix` at 4.0.0). Setting `hsm_type = "tpm"` makes `himmelblaud` exit at startup. **Do not set it.** Keep the default `tpm_bound_soft_if_possible`. Directly constrains Task 6: even with a Parallels vTPM, himmelblau cannot bind to it today. |
| [#1640](https://github.com/himmelblau-idm/himmelblau/issues/1640) — three `url_handler.rs` tests fail on NixOS | open | Build-time only, on the stable-3.x flake. 4.0.0 builds via crate2nix `workspaceMembers.*.build` with `runTests ? false`, so a plain `services.himmelblau` deploy should not hit it. Watch for it if CI ever enables tests. |
| [#981](https://github.com/himmelblau-idm/himmelblau/issues/981) — GNOME login keyring unusable after PIN change | open, `stale exempt` | Post-login breakage; a contributor calls the NixOS PAM setup "still not ironed out". Workaround is to delete and recreate the keyring. Relevant because the desktop will run a keyring agent. |

No aarch64-specific open issues.

### Two module-level fixes still required at 4.0.0 (both confirmed in source and on the VM)

1. **Mutable config.** `nix/modules/himmelblau.nix` hard-codes
   `ExecStart = "${daemonPackage}/bin/himmelblaud --config ${configFile}"` where
   `configFile` is a `/nix/store` path. himmelblau writes enrollment state back into its
   config directory, so `modules/nixos/himmelblau.nix` must override `ExecStart` to point
   at a writable `/etc/himmelblau/himmelblau.conf`. (The spike does exactly this via a
   `/run/systemd/system/himmelblaud.service.d/override.conf` drop-in.)
2. **`/etc/krb5.conf.d/` must exist.** The tasks daemon's `ReadWritePaths` already lists it,
   but nothing creates it. On the spike this produces, on every login:
   `WARN Task returned an error: Path "/etc/krb5.conf.d/" does not exist` followed by
   `ERROR Kerberos config failed for <user>` and `Kerberos credential cache load failed`.
   Create it declaratively (`systemd.tmpfiles.rules` or an `environment.etc` placeholder),
   and make sure `/etc/krb5.conf` carries `includedir /etc/krb5.conf.d/`.

Also observed and worth fixing in our module: `himmelblaud-tasks.service` fails
`226/NAMESPACE` (`Failed to set up mount namespacing: /./run/himmelblaud`) on every boot
until `himmelblaud` has created its `RuntimeDirectory`, then succeeds on restart. An
`After=himmelblaud.service` (it already has `BindsTo` + a `ConditionPathExists`) removes
the noise.

### USER IDENTITY DESIGN — recommendation

**Recommendation: one account. Declare a local `users.users.andreym` (uid 1000,
`/home/andreym`) and point himmelblau at it with `user_map_file`.**

Evidence:

- **home-manager's NixOS module cannot work with an NSS-only user.** `nixos/common.nix`
  in the pinned home-manager (`/nix/store/cda2…-source`) sets, for each
  `home-manager.users.<name>`:
  `home.username = config.users.users.${name}.name;`,
  `home.homeDirectory = config.users.users.${name}.home;`,
  and probes `config.users.users.${name}.uid`. `nixos/default.nix` also writes back into
  `users.users.<name>.packages`. A user that exists only through NSS has no
  `config.users.users` entry, so evaluation fails outright. **`users.users.andreym` is
  mandatory**, which rules out "the Entra UPN *is* the HM-managed account".
- **himmelblau's `user_map_file` is built for exactly this.** Format: one
  `local_username:upn@domain` per line; comments and blanks ignored; UPNs lowercased;
  first entry wins on duplicates (`src/common/src/user_map.rs`). Its documented purpose:
  *"map local user accounts to Azure Entra ID user accounts, allowing them to authenticate
  using Entra ID credentials"* (`docs-xml/himmelblauconf/base/user_map_file.xml`).
- **Every PAM entry point honours it.** `src/pam/src/pam/mod.rs` resolves
  `user_map.get_upn_from_local(<pam user>)` before falling back to `cn_name_mapping` in
  `sm_authenticate`, `acct_mgmt`, `sm_chauthtok` and `sm_open_session`. So logging in as
  local `andreym` authenticates against Entra (Hello PIN / FIDO), refreshes the PRT, and
  starts a session that Intune sees.
- **NSS yields to `files`.** `nsswitch.conf` on a himmelblau NixOS host is
  `passwd: files systemd himmelblau` / `group: files [success=merge] systemd himmelblau`
  (`system.nssDatabases.* = mkOrder 1501 [ "himmelblau" ]`), so the local uid-1000 entry
  wins for `andreym`. himmelblau's own enumeration explicitly *skips* mapped users
  ("Skip users whose UPN is mapped to a local user (the local NSS module handles these)"),
  while `initgroups` still resolves the UPN and returns the Entra groups — which the
  `[success=merge]` on `group` merges with local groups. Result: uid 1000, `/home/andreym`,
  local groups **plus** Entra group membership.
- **The alternative is measurably worse.** On the spike, the unmapped Entra identity is
  `<short>:x:<hashed-uid>:<hashed-gid>:…:/home/<short>@<domain>:/bin/bash` — a hashed uid in
  the 200000–2000200000 idmap range, a home directory named after the object UUID with a
  UPN symlink alias (`home_attr=uuid`, `home_alias=spn`), and ~180 supplementary Entra
  GIDs. Nothing about that account can carry the home-manager profile, and running two
  accounts means two homes, two dotfile trees, and a desktop session in the wrong one.

Concrete settings to bake into `modules/nixos/himmelblau.nix`:

- `users.users.andreym = { isNormalUser = true; uid = 1000; home = "/home/andreym"; … }`,
  `home-manager.users.andreym` as usual.
- `settings.user_map_file = "/etc/himmelblau/user-map"`, with the file written from a
  gitignored local value or a sops secret (the UPN is tenant-bearing) — **not** a literal
  in a committed `.nix`.
- **`settings.shell` must be set.** The default is `/bin/bash`, which does not exist on
  NixOS (verified: `ls /bin/bash` → No such file). Use
  `"/run/current-system/sw/bin/bash"` (or the user's real shell). This only affects
  unmapped Entra users, but it is a one-line landmine.
- Leave `pam_allow_groups` unset (`null` = allow all); `[ ]` is a populated allow-list with
  zero entries and locks everyone out.
- Do **not** set `hsm_type = "tpm"` (issue #1656).
- Keep `enable_passwordless_security_key = true` + experimental FIDO, per-domain
  `tenant_id`, and `ip_version` as P2 found; and note `allow_console_password_only=true` /
  `password_only_remote_services_deny_list` are already the shipped defaults.
- Expect a stray `/home/<uuid>` + UPN symlink if an unmapped Entra login ever happens;
  with the map in place the session's home is `/home/andreym`.

**Verdict:** pin `4.0.0`; local `users.users.andreym` (uid 1000) + `user_map_file`
mapping `andreym:<upn>`; module must override `ExecStart` for a mutable config, create
`/etc/krb5.conf.d/`, set `shell`, and never set `hsm_type = "tpm"`.

---

## 4. What the enrolled spike VM actually reports

All read-only, 2026-09-01. Tenant-bearing values → local notes.

- **himmelblau version:** 4.0.0 (daemon binary `rust_himmelblaud-4.0.0`, `aad-tool version`
  → `himmelblau 4.0.0`). `aad-tool status` → `working!`.
- **Config in use:** `/etc/himmelblau/himmelblau.conf`, a real hand-written file (not a
  store symlink), with a `[global]` section carrying the full default set plus:
  `apply_policy=true`, `debug=true`, `enable_experimental_mfa=true`,
  `enable_experimental_passwordless_fido=true`, `enable_passwordless_security_key=true`,
  `enable_hello=true`, `enable_kerberos_cache=true`, `enable_sfa_fallback=false`,
  `ip_version=ipv4-only`, `join_type=join`, `hsm_type=tpm_bound_soft_if_possible`,
  `home_attr=uuid`, `home_alias=spn`, `home_prefix=/home/`, `id_attr_map=name`,
  `cn_name_mapping=true`, `shell=/bin/bash`, `use_etc_skel=false`, plus a per-domain
  section pinning `tenant_id`. Runtime state (device id, Intune device id, graph URL) is
  written to `/var/cache/himmelblaud/himmelblau.conf`.
- **Hand-fixes as applied:** (a) a `/run/systemd/system/himmelblaud.service.d/override.conf`
  drop-in replacing `ExecStart` to read `/etc/himmelblau/himmelblau.conf`;
  (b) `mtu 1400` on `enp0s5`, set imperatively (nothing on disk); (c) `/etc/krb5.conf` and
  `/etc/krb5.conf.d/` **do not exist at all** — the krb5 fix was never persisted, and the
  Kerberos config task fails on every login.
- **Policy cache** (`/var/cache/nss-himmelblau/policies.cache.db`, SQLite, table
  `policies(key,value,is_number)`) holds only the *applied* password policy:
  `linux_passwordpolicy_minimumdigits=1`, `minimumlength=12`, `minimumlowercase=1`,
  `minimumsymbols=1`, `minimumuppercase=1`. The full evaluation is not persisted; it is
  visible in the daemon journal because `debug=true`.
- **Compliance settings the tenant assigns** (5 policies; ids in local notes):
  | setting id | expected | actual on the spike | state |
  |---|---|---|---|
  | `linux_distribution_alloweddistros_item_$type` (group 0, policy A) | `rhel` | `nixos` | NonCompliant |
  | `linux_distribution_alloweddistros_item_minimumversion` (group 0, policy A) | `8.0` | — | Compliant (n/a) |
  | `linux_distribution_alloweddistros_item_$type` (group 1, policy A) | `ubuntu` | `nixos` | NonCompliant |
  | `linux_distribution_alloweddistros_item_minimumversion` (group 1, policy A) | `22.4` | — | Compliant (n/a) |
  | `linux_passwordpolicy_minimum{digits,length,lowercase,symbols,uppercase}` | 1 / 12 / 1 / 1 / 1 | same | Compliant |
  | `linux_distribution_alloweddistros_item_$type` (group 0, policy B) | `rhel` (min `6.10`) | `nixos` | NonCompliant |
  | `linux_distribution_alloweddistros_item_$type` (group 1, policy B) | `ubuntu` (min `20.04`) | `nixos` | NonCompliant |
  | `linux_deviceencryption_required` | `True` | `false` | NonCompliant |
  | `linux_customcompliance_discoveryscript` | (base64 script) | see below | client reports `Unknown`; server decides |

  Overall `device_info.compliance_state: NonCompliant`, `count: 4` distinct rules:
  "Upgrade to a supported Linux distribution" ×2 (source `LinuxMDM`), "Encrypt your drives"
  (`LinuxMDM`), and "Secure Boot is not enabled" (source `CustomCompliance`).

  Two further policies are **CustomConfig**, not compliance
  (`linux_customconfig_{executioncontext,executionfrequency,executionretries,script}`);
  one of them runs a small shell script that sets a **system-wide git config key**
  (`git config --system …`). On NixOS that writes `/etc/gitconfig` — keep that path
  writable (i.e. do **not** enable a system-wide `programs.git` that turns it into a
  read-only store symlink) or that script will fail every check-in.

- **The custom-compliance script — what it checks.** Base64 in the detail's
  `expected_value`; himmelblau decodes it, writes it to a temp file mode 0500, runs it
  directly if it starts with `#!` (else via `/bin/sh`), 60 s timeout with a process-group
  kill, **ignores the exit code entirely**, and requires stdout to be a single well-formed
  JSON object (`src/policies/src/custom_compliance_ext.rs`). The client sets the detail's
  state to `Unknown` and ships the JSON; **Intune evaluates the JSON rules server-side.**
  This tenant's script (v `2026.07.01`) reports five keys and determines Secure Boot state
  as follows:
  1. if `mokutil` is on `PATH`, `mokutil --sb-state | grep -qi "SecureBoot enabled"`;
  2. **otherwise, if `/sys/firmware/efi` exists, it reads the `SecureBoot-*` EFI variable
     under `/sys/firmware/efi/efivars` and treats last byte == 1 as enabled** (via `od`).
  It then applies an OEM known-bad-hardware exclusion list (DMI `sys_vendor` /
  `board_name` / `product_name` / `bios_release`, optionally `dmidecode -t 11`) purely to
  decide whether the device can be remediated. Finally it reports whether the
  **"Microsoft UEFI CA 2023"** certificate is in the Secure Boot `db`, looked up via
  `mokutil --db`, else `efi-readvar -v db`, else `strings` over
  `/sys/firmware/efi/efivars/db-*` with `openssl` present. **If Secure Boot is OFF, or the
  hardware is excluded, the cert is reported "Present" so that rule cannot fail.**
  - On the spike the output is
    `{"SecureBootEnabled":"false","SecureBootCA2023":"Present","HardwareExcluded":"false","ExcludeReason":"none","ScriptVersion":"…"}`
    and the *only* custom rule that fires is **"Secure Boot is not enabled"** — so the
    tenant's server-side rule requires `SecureBootEnabled == "true"`.
  - **Consequence for Task 6:** turning Secure Boot on is necessary. But the moment it is
    on, the script stops short-circuiting the cert check and starts evaluating
    `SecureBootCA2023` for real — and on NixOS **none** of `mokutil`, `efi-readvar`,
    `openssl`+`strings` are on the daemon's `PATH`, so it would report `Missing` even if
    the certificate were there. Whether the tenant has a rule bound to `SecureBootCA2023`
    is **unknown** (we have never seen the machine in a state that would trigger it), so
    treat it as if it does. §5 resolves both halves: enroll with
    `sbctl enroll-keys --microsoft` (which includes the 2023 CAs) and install `mokutil`.
  - Note the DMI values Parallels reports: `sys_vendor = Parallels International GmbH.`,
    `product_name = Parallels ARM Virtual Machine`, `board_name = Parallels ARM Virtual
    Platform` — none match the OEM exclusion lists, so the VM is never "hardware excluded".
- **Compliance-status validity period:** not observable from the client. libhimmelblau's
  `DeviceInfo` does carry `InGracePeriodUntilDateTimeUtc` (and `LastContact`,
  `IsCompliantInGraph`) — `libhimmelblau/src/intune.rs` — but himmelblau neither logs nor
  persists the value, and the enrolled device has never been compliant, so there is no
  grace window to read. **The owner must read it from the Intune portal** (Task 5).
- **Disk naming: `sda`, not `vda`.** `lsblk` shows `sda` (SATA) with `sda1` → `/boot`,
  `sda2` → `/` + `/nix/store`. `prlctl set --device-add-hdd --help` on Parallels 27.0.0
  offers `--iface <ide|scsi|sata|nvme>` — **there is no virtio disk option.** The plan's
  `/dev/vda` is wrong for Parallels. Network *is* virtio (`net0 … card=virtio` → `enp0s5`).
- **`/etc/os-release` is honest NixOS** on the spike — `ID=nixos`, `VERSION_ID="26.11"`,
  `PRETTY_NAME="NixOS 26.11 (Zokor)"`. No spoof has been applied there.
- **Kernel / GPU:** Linux 6.18.41 aarch64, `virtio_gpu` DRM driver bound
  (`+virgl -edid -resource_blob -host_visible -context_init`), `simpledrm` on minor 0.
  No `/dev/tpm*` and no `/sys/class/tpm` — the spike VM has **no vTPM**, so himmelblau's
  `tpm_tcti_name=device:/dev/tpmrm0` is unused and the soft HSM is in play.
  `mokutil`, `dmidecode`, `efi-readvar`, `openssl` and `strings` are all **absent**; `od`
  is present (which is why the efivars fallback path worked).

**Verdict:** the compliance gap is exactly three things — distro allowlist (`rhel` or
`ubuntu`), disk encryption, and a tenant custom-compliance rule that requires Secure Boot
to be *enabled*. Route B's os-release identity (`ID=ubuntu`, `VERSION_ID="24.04"`) satisfies
both distro groups (min 20.04 and min 22.4 after himmelblau's version normalisation), disko
LUKS satisfies encryption, and Secure Boot is a genuine Task 6 item with a newly-discovered
follow-on risk (the 2023-CA sub-check). Disko must target `/dev/sda` (or `nvme0n1`), never
`/dev/vda`.

---

## 5. Secure Boot + vTPM on Parallels ARM Linux guests

### The firmware, measured first-hand on the spike VM

```
$ bootctl status
      Firmware: UEFI 2.70 (EDK II 1.00)
 Firmware Arch: aa64
   Secure Boot: disabled (setup)
  TPM2 Support: no
$ ls /sys/firmware/efi/efivars | grep -E '^(PK|KEK|db|dbx|SetupMode|SecureBoot|VendorKeys)-'
SecureBoot-…   SetupMode-…   VendorKeys-…
$ SetupMode = 1 ; SecureBoot = 0 ; VendorKeys = 1
```

This is the decisive fact, and it **contradicts the pessimistic reading of the Parallels
forums** (which is drawn from Windows VMs, where the firmware ships a Parallels-owned PK):
a Parallels ARM VM created with `--efi-boot on` and Secure Boot never enabled has **no
PK, no KEK and no db at all, and reports SetupMode = 1**. In setup mode the platform key
hierarchy is writable from the guest, which is exactly the state `sbctl enroll-keys` (and
systemd-boot's own "Enroll SecureBoot keys" feature, which `bootctl` reports as available)
needs. Custom-key Secure Boot is therefore *available* here — this has to be re-confirmed
on the new VM after `prlctl set --efi-secure-boot on`, because the Parallels docs say
`--efi-secure-boot reset` "clears and reinstalls the Secure Boot certificates
(PK, KEK, DB, DBX)", i.e. `on`/`reset` may populate a vendor PK and drop out of setup mode.

### lanzaboote on aarch64

- `flake.nix` lists `aarch64-linux` with the comment *"Not tested in CI. Best effort
  support."*
- Arch support is real, not incidental: `rust/tool/shared/src/architecture.rs` has
  `enum Architecture { X86, AArch64 }` mapping to the `x64`/`aa64` EFI suffixes, and
  `nix/packages/stub.nix` sets `CARGO_BUILD_TARGET = "${qemuArch}-unknown-uefi"` →
  `aarch64-unknown-uefi`.
- aarch64 support landed in lanzaboote #30/#31 (2023-09) and aarch64 CI in #280 (2024-01).
  Still open and aarch64-specific: **#369 DeviceTree support** — irrelevant for a VM guest
  whose firmware supplies the DTB.
- `sbctl` in the pinned nixpkgs is **0.18**; `enroll-keys --microsoft` has embedded the
  2023 certificates since **0.17** (PR #432): db gains `microsoft uefi ca 2023`,
  `microsoft option rom uefi ca 2023`, `windows uefi ca 2023`; KEK gains
  `microsoft corporation kek 2k ca 2023`. `meta.platforms = linux`, so aarch64 is fine.

**This matters for compliance, not just for boot.** The tenant's discovery script, once
Secure Boot is ON, looks for the string **"Microsoft UEFI CA 2023"** in `db`. Enrolling
only our own keys would report `SecureBootCA2023: Missing`. **Use
`sbctl enroll-keys --microsoft`** so the db carries our key *and* Microsoft's 2011+2023
CAs. And put a tool that can *read* `db` on the system path — the script tries
`mokutil --db`, then `efi-readvar -v db`, then `strings` over
`/sys/firmware/efi/efivars/db-*` gated on `openssl` being present. On the spike **none** of
`mokutil`, `dmidecode`, `efi-readvar`, `openssl` or `strings` exist (only `od`, which is
why the SecureBoot-state fallback worked). Add `mokutil` (0.7.2, `platforms = linux`) to
`environment.systemPackages`; systemd services on NixOS get `/run/current-system/sw/bin`
appended to their PATH, so the tasks daemon will find it.

### vTPM

- `prlctl set <vm> --tpm <on|off|2|crb>` and `--tpm-key` exist in the Parallels 27.0.0 CLI
  with no documented OS restriction, but Parallels' own KB frames vTPM as a Windows
  feature ("Windows 10 and newer Windows VMs with UEFI BIOS"; adding a TPM chip
  auto-enables Secure Boot), and a Parallels support reply on the forum states plainly
  that the virtual TPM chip is supported for Windows only, not Linux. A user who added
  it by hand to a Fedora ARM VM got a non-booting VM.
- The spike VM has no `/dev/tpm*`, no `/sys/class/tpm`, and `bootctl` reports
  `TPM2 Support: no`. Untested for a Linux ARM VM created *with* `--tpm on`.
- Even if a vTPM appears, **himmelblau cannot use it** (upstream #1656: the Nix build omits
  the `tpm` cargo feature; `hsm_type = "tpm"` makes the daemon exit). Its only value would
  be `systemd-cryptenroll` auto-unlock, which the plan already classes as optional
  convenience that must never be a boot requirement.

### systemd-cryptenroll TPM2 on NixOS — minimal requirements

`boot.initrd.systemd.enable = true;` is effectively the whole declarative part.
`nixos/modules/system/boot/systemd/tpm2.nix` defaults `boot.initrd.systemd.tpm2.enable` to
`systemd.package.withTpm2Units` (true for the stock package) and, when on, adds
`tpm-tis` (+ `tpm-crb` off riscv64/armv7) to `boot.initrd.availableKernelModules` and pulls
in `tpm2.target`, `systemd-tpm2-setup-early.service` and `tpm2-tss` — so hand-listing
kernel modules is redundant on current nixpkgs. Enrollment itself is imperative and
one-shot: `systemd-cryptenroll --wipe-slot=tpm2 --tpm2-device=auto --tpm2-pcrs=0+7
/dev/disk/by-uuid/<luks-uuid>`. Optional: `security.tpm2.enable` for userspace tooling;
`boot.initrd.luks.devices.<n>.crypttabExtraOpts = [ "tpm2-device=auto" ]` only if unlock
silently falls through to the passphrase. (Note the 2025 write-ups on bypassing automatic
TPM2 unlock before relying on it.)

**Verdict — split the two:**
- **Secure Boot with custom keys: feasible-now (high confidence, one check outstanding).**
  The firmware is EDK II aa64 in **setup mode with an empty key store**, lanzaboote builds
  and installs `aa64` binaries, and sbctl 0.18 can enroll our key together with the
  Microsoft 2011+2023 CAs the tenant's script looks for. The one thing to verify before
  committing is that `prlctl set --efi-secure-boot on` does not install a vendor PK and
  leave setup mode (`bootctl status` should still say `setup` until we enroll).
  Task 6 is worth attempting, and it must use `sbctl enroll-keys --microsoft`, not
  own-keys-only, and must add `mokutil` so the discovery script can see `db`.
- **vTPM / `systemd-cryptenroll` auto-unlock: no, not on Parallels ARM (defer).** No vTPM
  is present or documented for Linux ARM guests, and it would buy nothing for himmelblau
  (#1656). Keep the LUKS passphrase as the only unlock path; revisit only if Parallels
  ships Linux vTPM.

---

## 6. os-release override on NixOS

How `/etc/os-release` is produced (`nixos/modules/misc/version.nix`):
`environment.etc."os-release".text = attrsToText osReleaseContents;` where
`osReleaseContents` is built from `system.nixos.{distroName,distroId,vendorName,vendorId,
release,codeName,version,variantName,variant_id}` plus `system.image.{id,version}` and is
finally merged with `system.nixos.extraOSReleaseArgs`. All of those options are
`internal = true` but settable. Note two automatic behaviours: setting `distroId` to
anything other than `"nixos"` adds `ID_LIKE="nixos"` and **drops** the NixOS-specific
`HOME_URL`/`VENDOR_URL`/`DOCUMENTATION_URL`/`SUPPORT_URL`/`BUG_REPORT_URL`/`ANSI_COLOR`
fields; and `DEFAULT_HOSTNAME` is hard-wired to `distroId`.

**Blast radius of the `system.nixos.*` route.** Those options feed far more than
`/etc/os-release`:

- `nixos/modules/tasks/network-interfaces.nix` — `networking.hostName` **defaults to
  `distroId`** (harmless once we set a hostname, but it shows the coupling).
- `system/activation/bootspec.nix`, `system/boot/loader/grub/grub.nix`,
  `system/boot/stage-1.nix`, `stage-2.nix`, `plymouth.nix` — boot entry labels and console
  banners become "Ubuntu 24.04 …".
- `system/activation/switchable-system.nix` — passes `DISTRO_ID` into the switch script.
- `misc/documentation.nix`, `virtualisation/lxc-image-metadata.nix`,
  `virtualisation/virtualbox-image.nix` — image/doc metadata.
- `system.nixos.release` additionally drives `system.nixos.version` and the
  `system.stateVersion` default.

**Blast radius of the surgical route.** Nothing in nixpkgs' NixOS modules reads
`/etc/os-release` except `misc/version.nix` itself, `system/boot/systemd/{shutdown,initrd}.nix`
and `system/boot/uki.nix` (all of which use the separately-generated
`boot.initrd.osRelease`, unaffected), plus
`virtualisation/{nixos-containers,lxc-container}.nix` and
`services/misc/amazon-ssm-agent.nix` — none of which apply here. **home-manager reads
`/etc/os-release` nowhere** (`targets.genericLinux` is an explicit opt-in option, not
autodetection). `nixos-version` reads `config.system.nixos.version`, not the file
(`installer/tools/tools.nix`). `nixos-rebuild` does not read it. The repo does not use `nh`.
Consumers that *would* see the lie are third-party: himmelblau (the point of the exercise),
`neofetch`/`fastfetch`-style tools, distro-icon logic in waybar/Hyprland themes, and
anything doing `. /etc/os-release`.

`/etc/lsb-release` is generated separately from the same `system.nixos.*` values and would
stay honest under the surgical route. himmelblau uses the `os_release` crate
(`/etc/os-release`, falling back to `/usr/lib/os-release`, which does not exist on NixOS),
so `lsb-release` does not matter for compliance — leave it truthful.

**Recommendation:**

```nix
environment.etc."os-release".text = lib.mkForce ''
  NAME="Ubuntu"
  ID=ubuntu
  ID_LIKE=debian
  PRETTY_NAME="Ubuntu 24.04.3 LTS"
  VERSION="24.04.3 LTS (Noble Numbat)"
  VERSION_ID="24.04"
  VERSION_CODENAME=noble
  ...
'';
```

with a header comment recording the owner decision and the reason (Intune's
"Allowed Distributions" rule is evaluated **client-side** by himmelblau from `ID` +
`VERSION_ID`, with no override option). Keep `system.nixos.*` honest so boot entries,
`nixos-version`, `nixos-rebuild`, bootspec and `stateVersion` all keep telling the truth,
and keep `/etc/lsb-release` untouched. Expose it as
`modules.nixos.intune-identity.{distroId,versionId}` with these defaults so the lie is one
grep away.

Sanity check against the tenant's rules: himmelblau normalises `VERSION_ID` by stripping
leading zeros per component and padding to semver (`normalize_version`), so `"24.04"` →
`24.4.0`, which satisfies both allowed minimums (`20.04` → `20.4.0` and `22.4` → `22.4.0`)
and both empty maximums. `ID=ubuntu` matches one of the two distro groups in each policy;
himmelblau's `apply_distribution_compliance` then marks the non-matching group
"not applicable / Compliant".

**Verdict:** override `environment.etc."os-release"` with `lib.mkForce`; do **not** touch
`system.nixos.distroId/distroName/release`. Blast radius is limited to programs that read
the file, and nothing in nixpkgs' NixOS modules, home-manager or the Nix tooling we use
does.

---

## 7. NixOS aarch64 ISO + disko layout

- **ISO.** Both channels serve an aarch64 minimal image (verified by following the
  redirect):
  - stable: `https://channels.nixos.org/nixos-26.05/latest-nixos-minimal-aarch64-linux.iso`
  - unstable: `https://channels.nixos.org/nixos-unstable/latest-nixos-minimal-aarch64-linux.iso`

  The flake pins `nixos-unstable` (26.11pre), and `nixos-install --flake` builds everything
  from the flake, so the ISO's own channel barely matters. Prefer the **unstable** minimal
  ISO so the installer's Nix and kernel are closest to what gets installed.
- **Flakes in the installer — the plan's assumption is wrong.** Neither
  `nixos/modules/profiles/installation-device.nix` nor the `installer/cd-dvd` modules set
  `nix.settings.experimental-features`, and nixpkgs has no default that enables flakes.
  What saves `nixos-install` is that it enables them *itself*:
  `pkgs/by-name/ni/nixos-install/nixos-install.sh` sets
  `flakeFlags=(--extra-experimental-features 'nix-command flakes')` as soon as `--flake` is
  passed. **`nix run github:nix-community/disko …` gets no such help** — the runbook must
  write `sudo nix --extra-experimental-features "nix-command flakes" run
  github:nix-community/disko -- --mode disko --flake github:andrey-moor/dotfiles#stargazer`.
- **Device name.** `/dev/sda` (Parallels SATA default) — see §4. `nvme` is the only other
  interface worth considering (`--iface nvme` → `/dev/nvme0n1`); **virtio disk is not
  offered by Parallels 27**. Pin the choice in `scripts/stargazer-vm create` so the disko
  `device` and the VM creation agree, and keep everything downstream partlabel/UUID-based.
- **Layout sketch** (modelled on disko's `example/luks-btrfs-subvolumes.nix`; `askPassword`
  defaults to true when neither `passwordFile` nor `settings.keyFile` is given, which is
  the interactive-passphrase behaviour we want):

```nix
disko.devices.disk.main = {
  type = "disk";
  device = "/dev/sda";
  content = {
    type = "gpt";
    partitions = {
      ESP = {
        size = "1G";                      # 512M is disko's example; 1G leaves room
        type = "EF00";                    # for lanzaboote UKIs + several generations
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
          settings.allowDiscards = true;  # askPassword defaults true -> passphrase prompt
          content = {
            type = "btrfs";
            extraArgs = [ "-f" ];
            subvolumes = {
              "/@root" = { mountpoint = "/";        mountOptions = [ "compress=zstd" "noatime" ]; };
              "/@home" = { mountpoint = "/home";    mountOptions = [ "compress=zstd" "noatime" ]; };
              "/@nix"  = { mountpoint = "/nix";     mountOptions = [ "compress=zstd" "noatime" ]; };
              "/@log"  = { mountpoint = "/var/log"; mountOptions = [ "compress=zstd" "noatime" ]; };
            };
          };
        };
      };
    };
  };
};
```

  - **ESP 1 GB**, not 512 MB: if Task 6 lands, lanzaboote puts full UKIs (kernel + initrd)
    on the ESP, one per generation, and 512 MB fills fast.
  - **No swapfile.** 32 GB of RAM in a VM that is snapshotted and suspended; a btrfs
    swapfile subvolume adds `nodatacow` fiddliness and blocks nothing we need. Add one
    later if hibernation is ever wanted (it isn't — Parallels suspends the whole VM).
  - Subvolume names are cosmetic; `@root/@home/@nix/@log` matches the plan's wording.
  - Keep the LUKS **passphrase slot forever** — it is what the fire drill proves and what
    makes the image portable off Parallels.

**Verdict:** unstable aarch64 minimal ISO; disko on `/dev/sda` with a 1 GB ESP, LUKS2 +
btrfs `@root/@home/@nix/@log`, interactive passphrase, no swap; `nixos-install --flake`
needs no extra flags, but the `disko` invocation **must** carry
`--extra-experimental-features "nix-command flakes"`.

---

## Changes this research forces on the plan

1. **`/dev/vda` → `/dev/sda`.** Parallels has no virtio disk interface (`prlctl` offers
   `ide|scsi|sata|nvme` only). Architecture bullet and Task 2's disko line must change.
2. **Ghostty cannot use hardware GL here.** Parallels/Apple Silicon caps the guest at
   OpenGL 4.0; ghostty 1.3.1 (pinned nixpkgs) demands 4.3. The Task 4 acceptance criterion
   needs restating — GPU acceleration is proven with `glxinfo -B` showing virgl; Ghostty
   ships behind an llvmpipe wrapper (or is swapped for foot/kitty in the VM).
3. **The installer does not have flakes on.** The Task 3 runbook's `nix run …disko` line
   needs `--extra-experimental-features "nix-command flakes"`.
4. **Task 6 is no longer conditional — it is required for "fully compliant."** The tenant's
   custom rule wants `SecureBootEnabled == "true"`, and nothing on the NixOS side can fake
   it (himmelblau just ships the script's JSON; Intune decides). Good news: the Parallels
   ARM firmware is EDK II in **setup mode with an empty PK/KEK/db**, so lanzaboote +
   `sbctl` custom keys should work. Two hard requirements fall out: enroll with
   **`sbctl enroll-keys --microsoft`** (sbctl 0.18 carries the Microsoft UEFI CA **2023**
   the script's second check looks for) and add **`mokutil`** to `environment.systemPackages`
   so the script can read `db` at all.
5. **Drop vTPM from the VM design.** Parallels documents vTPM as Windows-only, the spike VM
   has none, and himmelblau cannot use a TPM anyway (upstream #1656 — the Nix build omits
   the `tpm` cargo feature; `hsm_type = "tpm"` makes the daemon exit). TPM2 auto-unlock is
   deferred, and `hsm_type` stays at its default. LUKS passphrase remains the only
   unlock path.
6. **`services.himmelblau.settings.shell` must be set** — the upstream default `/bin/bash`
   does not exist on NixOS.
7. **The identity design is settled**: local `users.users.andreym` (uid 1000) +
   `user_map_file`, because home-manager's NixOS module hard-requires a
   `config.users.users.<name>` entry.
8. **One Intune CustomConfig script writes `/etc/gitconfig`** — do not make that path a
   read-only store symlink.
9. **`scripts/stargazer-vm ip` must not clone `spike-parallels`'s IPv4-only lookup** — the
   spike is currently only reachable over IPv6 link-local, and the same DHCP fragility
   will apply.
