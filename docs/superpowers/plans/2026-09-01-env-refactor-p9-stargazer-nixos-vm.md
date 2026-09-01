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
