# Env Refactor P9 — Stargazer Successor (NixOS aarch64 VM on Parallels) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Implementer subagents run on Opus.

**Goal:** Replace the hand-installed Omarchy/Arch stargazer VM with a NixOS aarch64 VM on Parallels declared as `nixosConfigurations.stargazer` in this flake — integrated home-manager reusing the `home/` bundles, disko LUKS+btrfs, a minimal declarative Hyprland desktop with GPU acceleration and Ghostty, refresh-on-start, himmelblau Entra join + Intune enrollment, and a **fully compliant** Intune device. Prove reproducibility with a fire drill, then delete the old VM.

**Spec:** `docs/superpowers/specs/2026-07-23-environment-refactor-design.md` §1 (stargazer row), §2 fork C, §3, §6 (deferred — see below), §7, §8 step 9, §9; `2026-08-31-p2-spike-verdict.md` (himmelblau recipe facts). Owner reordered P9 ahead of P7 on 2026-09-01 (derisk the NixOS host layer, disko, Parallels on a snapshot-able VM first).

**Architecture (brainstorm decisions, 2026-09-01):**
- **One flake, one host block.** `nixosConfigurations.stargazer = nixpkgs.lib.nixosSystem { system = "aarch64-linux"; specialArgs = { inherit inputs dotfilesDir; }; modules = [ ./hosts/stargazer home-manager.nixosModules.home-manager sops-nix.nixosModules.sops disko.nixosModules.disko himmelblau.nixosModules.himmelblau ... ]; }`. HM integrated (`home-manager.users.andreym`, `sharedModules = homeBase`, same `home/{core,dev,linux}` bundles). The old `homeConfigurations.stargazer` is removed. `hosts/stargazer/{default,hardware,disko}.nix`.
- **NixOS layer** (first real use; P7 is the second): `modules/nixos/base.nix` (users, ssh, tailscale, firewall default-deny with services tailnet-bound, nix settings, `system.autoUpgrade` flake refresh-on-start), `modules/nixos/parallels-guest.nix` (virtio, guest tools if aarch64-capable, virtio-gpu + virgl mesa), `modules/nixos/desktop-hyprland.nix` (programs.hyprland, greetd, waybar, launcher, mako, PipeWire, catppuccin theming, Ghostty), `modules/nixos/himmelblau.nix` (the P2 recipe baked in: MTU 1400 on Parallels shared NAT, daemon ExecStart override for a mutable config, per-domain `tenant_id` pin, `enable_passwordless_security_key=true` + FIDO, `/etc/krb5.conf.d/`, `pam_allow_groups` handling), `modules/nixos/intune-identity.nix` (see Compliance).
- **Desktop scope = minimal declarative Hyprland.** The §6 Omarchy tracked-input port is its OWN later phase built on this VM before P7. Acceptance: Hyprland session on virtio-gpu with hardware acceleration (`glxinfo`/`eglinfo` shows virgl, not llvmpipe), Ghostty runs (OpenGL renderer), wayvnc tailnet-bound.
- **Compliance = fully compliant, route B (owner decision, deliberate reversal of spec §8 step 8):** himmelblau evaluates Intune "Allowed Distributions" client-side from `/etc/os-release` `ID` + `VERSION_ID`; no override option exists (verified in himmelblau HEAD 2026-09-01 + libhimmelblau 2026-08-27; docs' alternative is a tenant-side Custom Compliance policy). Therefore `modules/nixos/intune-identity.nix` overrides `/etc/os-release` to report an allowed distro (Ubuntu 24.04 — `ID=ubuntu VERSION_ID="24.04" ID_LIKE=debian` + matching PRETTY/NAME/VERSION fields), with a header comment recording this as a conscious owner decision and why. Encryption rule = himmelblau `is_disk_encrypted` (dm-crypt fixed writable volumes) → disko LUKS root satisfies. Secure Boot is NOT a himmelblau built-in rule → P2's Secure-Boot failure comes from a tenant custom-compliance script; Task 1 reads what it checks before Task 6 decides lanzaboote + Parallels EFI-SB.
- **Install path:** official NixOS aarch64 minimal ISO booted in a fresh Parallels VM → SSH in → `disko` → `nixos-install --flake github:andrey-moor/dotfiles#stargazer` (public repo; no Mac-side aarch64 builder — behemoth has none under Determinate; P2's QEMU `arm-builder` is the fallback only). LUKS passphrase typed once at install and at each cold boot.
- **Refresh-on-start instead of a scheduled keep-alive (owner decision):** `system.autoUpgrade` (`flake = "github:andrey-moor/dotfiles#stargazer"`, `Persistent` timer → fires on boot/resume if missed, no `--update-input`, `allowReboot = false`); himmelblau checks in at login. Keep-alive is CONDITIONAL: added only if Task 1 finds the tenant's compliance-status validity period shorter than realistic usage gaps, or the stale-device login test shows a Conditional-Access catch-22. No healthchecks ping (nothing left to die silently).
- **LUKS layering:** portable baseline = passphrase (any hypervisor, what the fire drill proves). Optional per-hypervisor layer = Parallels vTPM `systemd-cryptenroll` auto-unlock + lanzaboote Secure Boot (Task 6) — never required to boot; passphrase slot always kept.
- **Secrets:** first host done the §10 way — host SSH key → `ssh-to-age` recipient in `.sops.yaml`; `wayvnc-stargazer` re-encrypted for it. No master-key scp.
- **Dropped with the old VM:** Rosetta (`home/linux/{rosetta,edge-rosetta}.nix` become orphaned → deleted; spec "no Rosetta anywhere"), the armarchy/Limine/GRUB/mkinitcpio hand-fixes, template credentials, ufw, pacman-tailscale, nixGL on stargazer. `home/linux/intune.nix` (portal/broker stack) stays for rocinante until P7/P8 but is NOT imported by the new stargazer.
- **VM sizing (recommendation):** 8 vCPU / 32 GB / 256 GB expanding virtio disk, virtio net (shared NAT initially — MTU 1400 rule applies; bridged is fine too), virtio video 3D "Highest", EFI, vTPM on (for Task 6), Secure Boot off until Task 6, Smart Card sharing on (YubiKey). behemoth = 16 cores/128 GB; Nostromo takes 10/64 — do not oversize.
- **CI:** `build-stargazer` flips to a full `nix build .#nixosConfigurations.stargazer.config.system.build.toplevel` on `ubuntu-24.04-arm` (no x86 .deb derivations anymore).

## Global Constraints

- **NEVER touch `Nostromo`** (domain-joined daily-use Windows VM) or `spike-himmelblau-arm` (enrolled reference VM — Task 1 reads from it over SSH only; no config changes, no snapshots switched). All `prlctl` mutations target ONLY the new VM name `stargazer-nixos` (and the fire-drill clone `stargazer-drill`). Scripts hard-code the name and refuse others.
- **Tenant-bearing content stays local**: tenant domain/id, UPNs, device ids, custom-compliance script text, verbatim AADSTS errors → `spikes/intune/notes/` (gitignored) or `hosts/stargazer/local/` (add to .gitignore). The repo is PUBLIC. `tenant.nix`-style values are read from a gitignored file or a sops secret, never literals in committed .nix.
- **Owner-run steps** (interactive/credentialed): VM creation + install (LUKS passphrase), `sudo`, enrollment ceremony (local-console YubiKey FIDO first factor — SSH-only enrollment is a dead end), old-VM deletion. Controller prepares exact commands; owner executes at the Mac.
- Implementer ceiling: repo edits + `nix eval`/`nix build` of aarch64-linux attrs where possible (eval always works on behemoth; full builds only in CI on the arm runner or inside the VM). Never `just switch` on behemoth in this phase (nothing here changes behemoth except flake.nix — verify behemoth's closure path is unchanged after each repo task; if flake.nix edits change it, STOP and explain).
- Disk headroom: behemoth has ~339 GB free; the new VM + drill clone must stay under ~150 GB combined; check before creating.
- Conventional commits; trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Repo formatted (`just fmt`) and `just lint` green on every commit.

---

### Task 1: Research (read-only) — resolve the unknowns before writing the layer

**Steps:**
- [ ] **Parallels guest on aarch64 NixOS**: does nixpkgs `hardware.parallels.enable` / `prl-tools` support aarch64 (check nixpkgs source for the module's platforms, package meta, version)? If not: what do we lose (shared folders, clipboard, dynamic resolution) and is virtio-gpu + `spice-vdagent`-style fallback enough? Document.
- [ ] **GPU acceleration**: virtio-gpu with virgl on aarch64 NixOS — `hardware.graphics.enable`, mesa virgl driver present in default `mesa`? Hyprland/aquamarine known issues on virtio-gpu (search Hyprland issues); Ghostty OpenGL on virgl. Note kernel params / env (`WLR_RENDERER`, `WLR_NO_HARDWARE_CURSORS` etc.) that matter.
- [ ] **himmelblau on NixOS**: current `nixosModules.himmelblau` option surface (settings shape, version 4.0.0 released 2026-08-31 — pin strategy: flake input `github:himmelblau-idm/himmelblau` at a tag), known NixOS issues open (#1656 TPM, #1640 tests, #981 keyring) and whether they affect us. **User identity design**: how does an Entra login (UPN → himmelblau NSS user) coexist with the home-manager-managed `andreym` account? Options to evaluate: himmelblau `home_alias`/`home_prefix`/idmap so the Entra user IS uid 1000 `andreym` with home `/home/andreym`; vs. a local `andreym` + separate Entra login for check-ins. Recommend one with evidence from himmelblau docs/config.rs.
- [ ] **From `spike-himmelblau-arm` over SSH (read-only)** using `spikes/intune/scripts/spike-parallels ip` + the local spike key: himmelblau version running; `/etc/himmelblau/himmelblau.conf` (redact tenant into local notes); the systemd override / MTU / krb5 hand-fixes exactly as applied; the Intune policy cache (`/var/cache/himmelblau/` or wherever `POLICY_CACHE` points) → list every compliance setting the tenant assigns, incl. the **custom compliance script(s)** — capture what the Secure Boot check actually executes; the reported OS fields; any hint of the compliance-status validity period (else note it must be read from the portal by the owner). Write tenant-free findings to the plan appendix; tenant-bearing text to `spikes/intune/notes/p9-tenant-facts.md` (gitignored).
- [ ] **Secure Boot + vTPM on Parallels ARM Linux guests**: lanzaboote aarch64 status; Parallels docs on vTPM for Linux ARM VMs; `systemd-cryptenroll --tpm2-device=auto` requirements in initrd (`boot.initrd.systemd.enable`, `tpm2-tss`). Verdict: feasible-now / later / no.
- [ ] **os-release override on NixOS**: cleanest mechanism (`environment.etc."os-release".text = lib.mkForce …` vs `system.nixos.{distroId,distroName,release}`) and side effects — anything in nixpkgs/home-manager/nix tooling that reads `/etc/os-release` and would change behavior (e.g. `nixos-version`, `nh`, `nixos-rebuild`, `home-manager` genericLinux detection, `flatpak`, Hyprland/waybar distro icons). Recommend.
- [ ] **NixOS ISO + disko**: the aarch64 minimal ISO URL/channel, `disko` invocation for a LUKS+btrfs single-disk layout on `/dev/vda` (Parallels virtio disk naming — confirm from the spike VM: `lsblk`), ESP size, subvolumes (@, @home, @nix, @log), swapfile or none.
- [ ] Write `docs/superpowers/plans/2026-09-01-p9-research-notes.md` (tenant-free) with each verdict + sources; commit (`docs: P9 research notes`).

### Task 2: NixOS layer + host + flake block (repo only)

**Steps:**
- [ ] Add flake inputs: `himmelblau` (pinned tag from Task 1, `inputs.nixpkgs.follows`), and only if Task 1 says feasible-now, `lanzaboote`. `nix flake lock`.
- [ ] `modules/nixos/base.nix`, `parallels-guest.nix`, `desktop-hyprland.nix`, `himmelblau.nix`, `intune-identity.nix` per Architecture (options only where genuinely parameterized: himmelblau domain/tenant id come from a gitignored local file or sops — module takes them as options; identity module takes `distroId`/`versionId` options with the documented default).
- [ ] `hosts/stargazer/{default,hardware,disko}.nix`: hardware = virtio/EFI generic; disko = LUKS2 on `/dev/vda` (partlabel-based), btrfs subvolumes, ESP; default.nix imports modules + `home/{core,dev,linux}` bundles via `home-manager.users.andreym.imports`, tailnet-bound wayvnc settings, `system.autoUpgrade`, sops (`age.sshKeyPaths` host key), `system.stateVersion = "26.05"` (or current). No rosetta, no intune.nix, no nixGL, no `programs.home-manager.enable` (integrated).
- [ ] `flake.nix`: add `nixosConfigurations.stargazer`; remove `homeConfigurations.stargazer`; behemoth + rocinante closure paths MUST stay unchanged (record before/after).
- [ ] Delete `home/linux/{rosetta,edge-rosetta}.nix` (orphaned); drop `nixgl` input only if rocinante no longer needs it (it does — keep). Update `home/linux.nix` bundle if it referenced them (it doesn't; verify).
- [ ] `.sops.yaml`: add a `stargazer` host recipient placeholder path/comment (actual age key added in Task 4 after first boot); keep admin key.
- [ ] `scripts/stargazer-vm`: adapted from `spikes/intune/scripts/spike-parallels` — verbs `create`, `iso` (download/verify ISO, attach), `up`, `down`, `suspend`, `resume`, `ip`, `snapshot <name>`, `restore <name>`, `destroy` (double-confirm), `status`; VMNAME hard-coded `stargazer-nixos` with a `--drill` flag switching to `stargazer-drill`; refuses anything else. Sizing per Architecture; vTPM on; SB off; smart-card sharing on.
- [ ] CI: `build-stargazer` → full `nix build .#nixosConfigurations.stargazer.config.system.build.toplevel` on `ubuntu-24.04-arm`.
- [ ] Verify: `nix eval --raw .#nixosConfigurations.stargazer.config.system.build.toplevel.drvPath` succeeds on behemoth; `nix flake check --all-systems`; `just lint`; behemoth/rocinante paths unchanged; push a branch or PR-less push and confirm the arm CI build passes (full build).
- [ ] Commit(s): `feat(nixos): stargazer NixOS host, modules/nixos layer, Parallels tooling`.

### Task 3: Runbook

**Steps:**
- [ ] Rewrite `hosts/stargazer/README.md` as the install runbook (replaces the 500-line Arch/armarchy/Rosetta/Intune-portal document): prerequisites; `scripts/stargazer-vm create && iso && up`; SSH into the ISO (`nixos@<ip>`, key or password); `sudo nix run github:nix-community/disko -- --mode disko --flake github:andrey-moor/dotfiles#stargazer` (LUKS passphrase prompt); `sudo nixos-install --flake github:andrey-moor/dotfiles#stargazer --no-root-passwd`; set user password; reboot; post-boot: `tailscale up`, capture host key → `ssh-to-age` → `.sops.yaml` → re-encrypt → `nixos-rebuild switch`; verification checklist (desktop, GPU renderer string, Ghostty, wayvnc over tailnet, autoUpgrade timer, os-release identity); enrollment ceremony section (join-then-Intune ordering, local console + YubiKey, expected prompts, what to capture on error); optional Task 6 section; fire-drill procedure; rollback (`nixos-rebuild --rollback`, Parallels snapshot names).
- [ ] Move superseded docs to `docs/archive/`: `docs/UPGRADE-PROCEDURES.md`, `docs/arch-arm-encrypted-install.md`, `docs/omarchy-grub-install.md`, `docs/rocinante-encrypted-install.md` (misnamed Parallels/Arch guide). Fix any live links.
- [ ] Commit: `docs(stargazer): NixOS install runbook; archive Arch-era docs`.

### Task 4: Install the real VM (OWNER at the Mac, controller-assisted)

- [ ] Headroom check; `scripts/stargazer-vm create && iso && up`; snapshot `blank-iso`.
- [ ] Follow the runbook through first boot + tailnet + sops key + second switch. Snapshot `installed`.
- [ ] Acceptance: Hyprland session; `glxinfo -B`/`eglinfo` renderer = virgl (not llvmpipe); Ghostty launches and renders; wayvnc reachable ONLY via tailnet IP; `systemctl list-timers` shows `nixos-upgrade` persistent; `cat /etc/os-release` shows the intended identity; `sudo cryptsetup status` shows LUKS root; HM applied (`~/.agents/AGENTS.md`, skills, `config/nvim` symlinks resolve into `~/dotfiles`).
- [ ] Any deviation → fix in repo (Task 2 files), push, `nixos-rebuild switch --flake github:…` in the VM, re-verify. Record fixes in the plan appendix.

### Task 5: Enrollment ceremony (OWNER, local console + YubiKey)

- [ ] Snapshot `pre-enroll`. Follow the runbook ceremony: first Entra auth (join) → Intune enrollment → login as the Entra identity per Task 1's identity design → check-in.
- [ ] Verify in the guest: `aad-tool status`, himmelblau journal clean, compliance details (policy cache) show Distribution=Compliant, Encryption=Compliant, custom scripts' results; owner confirms **Compliant** in the Intune portal / Company Portal and that a CA-protected resource opens.
- [ ] If any of the five recipe fixes had to be applied by hand → they were missing from `modules/nixos/himmelblau.nix` → fix in repo, switch, confirm they're no longer manual. The module must make the ceremony hand-fix-free.
- [ ] Stale-device test (informational, parallel): read the tenant's compliance-status validity period (owner, portal); decide whether the conditional keep-alive is needed. Record decision.
- [ ] Snapshot `enrolled`.

### Task 6 (conditional): Secure Boot + TPM auto-unlock

- [ ] Only if Task 1 verdict = feasible-now AND Task 5 shows the custom-compliance Secure Boot check is the remaining failure (or owner wants the convenience). Enable lanzaboote in a per-host optional module (`modules/nixos/secureboot.nix`), enroll keys, flip Parallels EFI Secure Boot on, `systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7`; verify cold boot without passphrase, passphrase fallback still works (test by toggling SB off once → prompt appears → toggle back), compliance re-evaluated.
- [ ] Never a boot requirement; documented as optional in the runbook.

### Task 7: Fire drill + retire the old VM (OWNER gate for deletion)

- [ ] `scripts/stargazer-vm --drill create && iso && up`; follow the runbook from scratch WITHOUT enrollment; time it; success = boots, tailnet up, desktop + Ghostty up, HM applied, autoUpgrade timer present. Fix runbook gaps found; re-run until it passes clean. Destroy the drill VM.
- [ ] Old `Stargazer` VM: owner confirms nothing left inside worth keeping (it was dormant since P1; check `~/dev`, shell history) → `prlctl unregister`/delete `~/Parallels/Stargazer.pvm` (owner-run), plus `ArchBase-Template.pvm.tar.zst` if the owner agrees. Reclaims disk.
- [ ] Repo: remove the stale `spike-himmelblau-arm`-specific bits only if P8 no longer needs them (it does — leave `spikes/intune/` alone). Update `CLAUDE.md`/`README.md` host sections for the new stargazer; `justfile`: add `stargazer-*` recipes wrapping `scripts/stargazer-vm` if useful, remove the wrong `rocinante-switch` prlctl recipe.
- [ ] Memory: P9 complete; spec §1/§8 annotations (compliance route B recorded as owner decision; keep-alive → refresh-on-start); next = the §6 Omarchy tracked-input phase on this VM, then P7.

## Completion checklist (controller)

- [ ] `nixosConfigurations.stargazer` builds in CI (full build, arm runner); behemoth/rocinante closures unchanged by the repo changes.
- [ ] VM installed from the public repo via ISO + disko; LUKS root; tailnet-only services; HM bundles applied; autoUpgrade persistent timer.
- [ ] Hyprland + virgl GPU acceleration + Ghostty verified.
- [ ] Entra joined, Intune enrolled, **Compliant** in the portal with zero hand-fixes (all baked into modules).
- [ ] Fire drill passed from scratch; old Stargazer VM deleted; Arch-era docs archived; runbook is the only install doc.
- [ ] Tenant-bearing facts exist only in gitignored local files; repo public-safe.

## Amendments (2026-09-01, after Task 1 research — see `2026-09-01-p9-research-notes.md`)

- **Disk is `/dev/sda`** (Parallels offers ide/scsi/sata/nvme, no virtio disk; networking IS virtio). disko targets `/dev/sda`, 1 GB ESP (lanzaboote UKIs), LUKS2 interactive passphrase, btrfs `@root/@home/@nix/@log`, no swap.
- **Terminal on stargazer = Alacritty** (owner decision). Parallels caps Linux guests at OpenGL 4.0 (Parallels 27's GL 4.3 Metal driver is Windows-only; spike VM on 27.0.0 confirms 4.0); Ghostty ≥ 1.2 needs GL 4.3. Alacritty (GL 3.3) is GPU-accelerated on virgl. Swap back to `home/shell/ghostty.nix` if Parallels ever extends GL 4.3 to Linux guests. Acceptance: `glxinfo -B` renderer = virgl; Alacritty renders on hardware GL.
- **Secure Boot is REQUIRED for full compliance and feasible-now** (firmware in setup mode, empty PK/KEK/db on the spike). Task 6 is no longer conditional: lanzaboote (aarch64 best-effort) + `sbctl enroll-keys --microsoft` (2023 CAs bundled in sbctl ≥ 0.17) + `mokutil` in systemPackages (the tenant custom script reads `db` via mokutil/efivars). Outstanding check: `prlctl set --efi-secure-boot on` must not install a vendor PK.
- **vTPM dropped** — Windows-only in Parallels, absent on the spike, and himmelblau's Nix build lacks the `tpm` feature (#1656: `hsm_type = "tpm"` kills the daemon; keep the default). LUKS passphrase at cold boot is the design.
- **Identity design**: local `users.users.andreym` (uid 1000, `/home/andreym`) is MANDATORY (home-manager's NixOS module reads/writes `users.users.<name>`); himmelblau `user_map_file` maps `andreym` → the UPN (all four PAM entry points consult it). Set himmelblau `settings.shell` (upstream default `/bin/bash` does not exist on NixOS). Leave `pam_allow_groups` unset.
- **himmelblau pin `github:himmelblau-idm/himmelblau/4.0.0`**; module must add: `ExecStart` override for a mutable config, `/etc/krb5.conf.d/` creation, `himmelblaud-tasks` 226/NAMESPACE fix, **declarative MTU 1400** on the shared-NAT interface (the spike lost DHCP after a hand-set MTU).
- **Parallels guest tools**: aarch64 build exists but is userspace-only and irritates Hyprland → `hardware.parallels.enable` behind an opt-in option, default false. virtio + virtio-gpu only.
- **Hyprland on aquamarine**: `WLR_*` env vars are dead; use `cursor { no_hardware_cursors = true }`, a pinned `monitor=` line (no EDID), `AQ_NO_MODIFIERS` only if needed. `hardware.graphics.enable = true` suffices (do NOT add `virglrenderer` — host-side).
- **os-release override**: `environment.etc."os-release".text = lib.mkForce …` ONLY — never `system.nixos.{distroId,distroName,release}` (feeds boot labels, bootspec, hostName/stateVersion defaults). `ID=ubuntu`, `VERSION_ID="24.04"` satisfies both tenant distro groups after `normalize_version`.
- A tenant CustomConfig policy runs `git config --system` → `/etc/gitconfig` must remain a writable real file (do not declare `environment.etc."gitconfig"`).
- Installer: `nix run github:nix-community/disko …` needs `--extra-experimental-features "nix-command flakes"`; `nixos-install --flake` adds it itself.
- `scripts/stargazer-vm ip` must handle IPv6 link-local / lease loss (the spike's IPv4 lookup returns 169.254.x when dhcpcd loses its lease).
- Compliance gap confirmed = distro ×2 (identity module), encryption (LUKS), Secure Boot (Task 6); password rules already pass; custom script exit code ignored (JSON on stdout required).

## Amendment (2026-09-01, Task 2b) — tenant facts move from a gitignored file to a committed sops secret

Task 2 shipped `hosts/stargazer/{tenant.nix,local/tenant.nix.example}`: a
gitignored `hosts/stargazer/local/tenant.nix`, loaded via `builtins.pathExists`,
with a `warnings` fallback when absent. **That approach cannot work.** A
gitignored path is excluded from the flake source for `github:` *and* `git+file:`
references, so himmelblau would have been silently disabled on the real install
(`nixos-install --flake github:…#stargazer`), in CI, and on every
`system.autoUpgrade` refresh — exactly the three paths that matter. Only a
`path:` reference from the working tree would have seen it.

Replacement: the three tenant facts live in **`secrets/stargazer-tenant.yaml`**,
age-encrypted with the existing `.sops.yaml` creation rule and **committed** to
the public repo, then rendered at activation.

- Keys: `domain`, `tenant_id`, `upn` (flat yaml; sops-nix `key = "<name>"` with
  a per-secret `sopsFile`, so the secret *names* are namespaced
  `stargazer-tenant/<key>`).
- `sops.templates."himmelblau-tenant.conf"` renders the `[<domain>]` section
  with `tenant_id`; `sops.templates."himmelblau-user-map"` renders
  `andreym:<upn>`. Both `restartUnits = [ "himmelblaud.service" ]`.
- `/etc/himmelblau/himmelblau.conf.d/10-tenant.conf` is a **symlink** to the
  rendered template path; `settings.user_map_file` points at the other one.
- `services.himmelblau.settings.domain` is **dropped**: himmelblau's
  `get_configured_domains()` (`src/common/src/config.rs`) treats every INI
  section name other than `[global]`/`[offline_breakglass]` as a configured
  domain, so the encrypted drop-in's section header is the sole declaration and
  the `[global]` store file stays tenant-free.
- Templates render at **mode 0444**, not the sops default 0400: `himmelblaud`
  runs under `DynamicUser`, and `nss_himmelblau`/`pam_himmelblau` read the same
  files from every process that resolves a user. These are tenant identifiers,
  not credentials — encrypted to keep them out of a public git history, not off
  the host.
- Failure mode when the host cannot yet decrypt (before Task 4 adds the
  `&stargazer` recipient): `collect_drop_ins()` follows symlinks and silently
  skips a dangling one, so the machine builds and boots domain-less instead of
  failing. No `warnings`, no assertions, no conditional `enable`.
- `modules.nixos.himmelblau` now takes a single option `tenantSecretFile`
  (default `../../secrets/stargazer-tenant.yaml`) instead of
  `domain`/`tenantId`/`upn`; `modules.nixos.himmelblau.enable = true` is
  unconditional in `hosts/stargazer/default.nix`.
- Deleted: `hosts/stargazer/tenant.nix`, `hosts/stargazer/local/tenant.nix.example`,
  the `hosts/stargazer/local/` `.gitignore` block, and the `warnings` fallback.

**Task 4 must therefore add the host recipient before the second switch** — the
tenant drop-in is empty until it does:

```sh
# in the VM, after first boot (the host key is generated by the installer)
ssh-keyscan -t ed25519 stargazer            # or: cat /etc/ssh/ssh_host_ed25519_key.pub

# on behemoth (holds the admin age private key)
nix run nixpkgs#ssh-to-age -- -i <the pubkey>          # -> age1…
$EDITOR .sops.yaml                                     # &stargazer = age1…, uncomment both refs
nix run nixpkgs#sops -- updatekeys secrets/wayvnc.yaml
nix run nixpkgs#sops -- updatekeys secrets/stargazer-tenant.yaml
git commit -am 'chore(secrets): add stargazer host recipient' && git push

# in the VM
sudo nixos-rebuild switch --flake github:andrey-moor/dotfiles#stargazer
sudo systemctl status himmelblaud
cat /etc/himmelblau/himmelblau.conf.d/10-tenant.conf   # must show the real [domain] + tenant_id
```

Alternative (avoids a reinstall-order dependency): pre-generate the host key on
behemoth, run `ssh-to-age`/`updatekeys`/push **before** `nixos-install`, and
inject the keypair into the installed system during the ISO session —
`install -Dm600 ssh_host_ed25519_key /mnt/etc/ssh/ssh_host_ed25519_key` and
`install -Dm644 ssh_host_ed25519_key.pub /mnt/etc/ssh/ssh_host_ed25519_key.pub`
before `nixos-install` — so the very first boot already decrypts.

## Amendment (2026-09-02, Task 4 execution) — clipboard and hypervisor coupling

- **Parallels Tools on aarch64**: `prltoolsd`, shared folders (`prl_fsd` at `/mnt/psf`), time
  sync and `prlcc` work; **clipboard (`prlcp`) does not** under Hyprland — tested both
  directions, including on the XWayland X11 clipboard. Dynamic resolution needed our own
  `virtio-gpu-resize` user service (the host updates the connector's preferred mode in
  sysfs on window resize but emits no hotplug event; an explicit `hyprctl keyword monitor`
  request works).
- **Owner decision ("do the right thing, no rush")**: clipboard is NOT coupled to the
  hypervisor. Seamless ⌘C/⌘V = use the VM through **wayvnc over the tailnet** with a VNC
  client that syncs clipboards (TigerVNC Viewer, already a behemoth cask) — mature,
  hypervisor-independent. Terminal flow (`ssh stargazer` from Ghostty) uses **OSC 52**
  natively. Inside the Parallels window, `pbcopy`/`pbpaste` SSH shims over the tailnet
  (requires macOS Remote Login) cover the occasional case. Explicitly rejected: custom
  Mac↔Wayland sync daemons and unmaintained tools (lemonade, last release 2021).
- Guest support is split into hypervisor-agnostic `modules/nixos/vm-guest.nix` (virtio,
  virtio-gpu, resize follower) and Parallels-only `modules/nixos/parallels-guest.nix`, so a
  move to UTM/QEMU keeps Hyprland + resizing.

## Amendment (2026-09-02) — Task 6 Secure Boot: Parallels blocks the custom-key path

Ceremony as planned: `sbctl create-keys` → lanzaboote on (signed UKIs + signed systemd-boot,
`sbctl verify` clean) → `sbctl enroll-keys --microsoft` (PK/KEK/db written, firmware left
setup mode, db contained "Microsoft UEFI CA 2023") → `prlctl set --efi-secure-boot on`.
Result: the VM **halts within seconds of power-on** with Secure Boot on (no loader runs), and
with the flag back off the *signed* systemd-boot **hangs at its menu** (countdown frozen, no
input) — the unsigned pre-lanzaboote loader boots fine. Rolled back to snapshot `enrolled`
(pre-lanzaboote, pre-enroll-keys); host sets `modules.nixos.secureboot.enable = false`
(9beaafd). Interpretation: Parallels' EFI Secure Boot does not honour a custom PK/KEK/db on
aarch64 Linux guests (forum reports agree: "secure boot continues not working" for Ubuntu ARM).

Status: **compliant on 3 of 4 rules** (distribution, encryption, password policy); only
"Secure Boot is not enabled" remains. Options recorded for the owner: (1) probe whether Parallels
SB boots *any* Microsoft-signed chain on ARM (Ubuntu Server ARM ISO with SB on in the drill VM;
cheap, decisive); (2) if yes, a shim + MOK chain (Microsoft-signed shim → our key via MokManager
→ lanzaboote UKIs) — medium effort, unsupported by NixOS upstream; (3) accept SB non-compliance
on this VM (Nostromo stays the compliant fallback); (4) a hypervisor where custom keys work
(QEMU/OVMF-secboot) for the compliant role.

## Amendment (2026-09-02) — Task 6 outcome: Secure Boot ON via shim + offline MokList

Option (2) from the previous amendment shipped, with two Parallels-specific twists:

- **Chain**: Debian trixie's Microsoft-signed `shimaa64.efi` (dual-signed, MS UEFI CA 2011 +
  2023) as `EFI/BOOT/BOOTAA64.EFI` → lanzaboote's signed systemd-boot as `EFI/BOOT/grubaa64.efi`
  (shim's compiled-in second-stage name) → lanzaboote UKIs. `modules/nixos/secureboot.nix`
  (`shim.enable`) wraps `lzbt` to re-lay the ESP on every switch;
  `packages/shim-signed-debian` pins the .debs. Parallels' db (provisioned at power-on with the
  flag set) carries "Microsoft UEFI CA 2023", which is what the tenant's discovery script reads.
- **MokManager is unusable on this firmware**: its countdown never ticks and it takes no keys,
  Secure Boot on or off (also with `mokutil --timeout -1`: menu drawn, keyboard dead; real keys
  at the console, not just synthetic ones). A `mokutil --import` request therefore hangs the
  boot, or times out and is discarded. **Enrollment is done offline**: `NVRAM.dat` in the `.pvm`
  is a plain EDK II varstore; `virt-fw-vars --add-mok` writes `MokList` into it
  (`scripts/stargazer-vm enroll-mok <db.pem>`, VM stopped, NVRAM backed up). shim honours it and
  mirrors it to `MokListRT` (`mokutil --list-enrolled` shows "Database Key").
- **Under enforcing Secure Boot the same event freeze hits systemd-boot** ("Boot in 5s" frozen,
  Enter ignored) — this, not custom keys, was the "signed loader hangs" of the previous
  amendment. Fix: `boot.lanzaboote.settings.timeout = "menu-disabled"` (starts the default entry
  without waiting on any event). No boot menu on this host; recovery = Secure Boot off +
  `bootctl set-timeout-oneshot 10`, or `nixos-rebuild switch --rollback`.
- **Verified**: `bootctl status` → "Secure Boot: enabled (user)", `mokutil --sb-state` enabled,
  MokList = Debian CA + Database Key, db = Microsoft CAs incl. UEFI CA 2023. Snapshot `secureboot`.
- **Side effect worth knowing**: restoring the *live* snapshot `mok-staged` rolled
  `/var/cache/himmelblaud` back, and every token refresh since fails with `AADSTS70000` while
  Hello-PIN logins still succeed. Fix: `aad-tool auth-test --name andreym --force-reauth` from
  the graphical session (README §10). Snapshot stopped VMs.
- `stargazer-vm` gained `enroll-mok <pem>` and `secure-boot on|off`.

## Amendment (2026-09-03) — Task 6 closed: `aad-tool compliance-check` → **passed**

With Secure Boot on, the tenant's "Secure Boot is not enabled" rule cleared and a second
custom-compliance rule surfaced: "Microsoft UEFI CA 2023 certificate is missing". Root cause was
not the firmware (Parallels' db has the CA) but himmelblaud-tasks' minimal PATH: the discovery
script probes db with `mokutil` / `efi-readvar` / `openssl`+`strings`, found none, and reported
"Missing". Fixed declaratively in `modules/nixos/himmelblau.nix` (FIX 4:
`systemd.services.himmelblaud-tasks.path = [ mokutil openssl binutils ]`). Note the
`nixos-rebuild switch` restart of the tasks unit came up with the *old* environment; an explicit
`systemctl restart himmelblaud-tasks` was needed before the script saw the tools.

Also fixed: Intune "scripts" policies aborted the whole policy run with "Failed to create cron
file" — `/etc/cron.d` now exists via tmpfiles (FIX 5), but nothing executes those cron entries on
NixOS (open follow-up; the two tenant scripts seen are a git `credential.azreposCredentialType
oauth` setter and one longer script, neither compliance-relevant).

Side quest that cost the morning: **behemoth's Parallels networking was wedged** — `prl_naptd`
had died on a Sep 1 wake-from-sleep (`error 1235`) and could not rebind because Apple's vmnet
sharing service was held (`applevisor status callback: 1009` = busy) by the Claude desktop app's
sandbox VM and a stale `InternetSharing`. This is what made Shared DHCP "never issue a lease"
during the install and, once wedged, broke bridged-over-Wi-Fi too. Recovery recipe in README §10.
Bridged works fine on Wi-Fi with healthy vmnet, so the declared adapter stays bridged.

Also: `aad-tool auth-test --name <UPN> --force-reauth` (the short name resolves as a local user
and fails with "domain in account_id") re-minted the PRT after the snapshot-restore token
rollback. Snapshots: `secureboot`, `compliant`.

## Amendment (2026-09-03) — signing keys as a sops secret (owner decision, reproducibility)

`sbctl create-keys` inside each VM made the MOK certificate unknowable before install. Now one db
key pair serves every stargazer: private half in `secrets/stargazer-sbctl.yaml` (age, admin +
stargazer recipients; encryption needs only the public recipients, no admin key was used), public
half + sbctl GUID committed under `hosts/stargazer/secureboot/`. `hosts/stargazer/default.nix`
places them at `/var/lib/sbctl` (sops `path` symlink for the key, tmpfiles `L+` for pem/GUID).
`stargazer-vm enroll-mok` defaults to the repo certificate, so MokList can be written right after
the first power-on of a new VM. Verified on the live VM: `nixos-rebuild switch` re-signed the shim
chain with the sops key (same certificate, fingerprint F1:8F:56:56…), Secure Boot still enabled.

Two facts learned: (1) NixOS installs the bootloader **before** activation (`nixos-install` runs
`switch-to-configuration boot` only), so the first switch introducing these files needs
`nixos-rebuild test` first, and a fresh install needs the three files pre-placed under `/mnt`
(runbook §4). (2) `sbctl verify` needs `--disable-landlock` to follow the symlinks. The old
in-guest key was moved to `/root/sbctl-db.{key,pem}.pre-sops` (identical material; delete after
the fire drill).
