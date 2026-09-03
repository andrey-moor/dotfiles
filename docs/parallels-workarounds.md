# Parallels workarounds — lineage for the stargazer VM

Every place where stargazer's NixOS configuration, scripts or runbook bends to
Parallels Desktop (27.0.0 on Apple silicon, aa64 EDK II firmware), with the
evidence that forced it and what happens to it on another hypervisor. Kept so a
move away from Parallels is a checklist, not an archaeology dig.

Legend for the last column: **drop** = delete on another hypervisor, **keep** =
hypervisor-agnostic, **re-test** = mechanism is generic but the trigger was
Parallels-specific.

## 1. Firmware / Secure Boot

| # | Workaround | Where | Evidence (date) | Elsewhere |
|---|-----------|-------|-----------------|-----------|
| 1.1 | **Custom Secure Boot keys are unusable.** Enrolling our own PK/KEK/db halts the VM at power-on with the flag set. | `modules/nixos/secureboot.nix` header; README §7 | 2026-09-02: `sbctl enroll-keys --microsoft` → `prlctl set --efi-secure-boot on` → VM halts within seconds, no loader runs. Snapshot `enrolled` rollback. | **drop** — QEMU/OVMF (`secureBoot = true`), VMware and UTM honour a custom PK; use mode A (`enable` without `shim.enable`, plain lanzaboote). |
| 1.2 | **Microsoft-signed shim chain** (`shim.enable`): Debian's `shimaa64.efi` as `BOOTAA64.EFI`, lanzaboote's systemd-boot renamed `grubaa64.efi`, `lzbt` wrapper re-laying the ESP every switch. | `modules/nixos/secureboot.nix` (`lzbtShim`), `packages/shim-signed-debian/` | 2026-09-02: Parallels' db is Microsoft-only (2011 + 2023 CAs); a MS-signed Debian netinst boots with SB on in the drill VM. | **drop** with 1.1. Keep the package around only if a future hypervisor is also Microsoft-CA-only. |
| 1.3 | **MokManager is unusable**, so the MOK is written offline into `NVRAM.dat` with `virt-fw-vars --add-mok`. | `scripts/stargazer-vm enroll-mok`; README §7 | 2026-09-02/03: shim's "Press any key" screen never ticks or reads keys, SB on *or* off, even with `mokutil --timeout -1`; a pending `mokutil --import` is discarded or hangs the boot. | **drop** with 1.2 (no MOK without shim). The technique is generic for any EDK II varstore if ever needed. |
| 1.4 | **`timeout menu-disabled`** — no systemd-boot menu. | `boot.lanzaboote.settings.timeout` in `secureboot.nix` | 2026-09-02: with SB enforcing the firmware stops delivering timer/key events to EFI apps; "Boot in 5s" freezes, Enter ignored. (Same root cause as 1.3.) | **re-test** — on OVMF the menu works under SB; restore the default timeout if it does. Recovery path meanwhile: SB off + `bootctl set-timeout-oneshot 10`. |
| 1.5 | Stale "Linux Boot Manager" NVRAM entry must be deleted so the firmware falls through to `EFI/BOOT/BOOTAA64.EFI`. | README §7 step (c) | 2026-09-02, ceremony design. | **drop** with 1.2 (systemd-boot's own entry is the right one in mode A). |
| 1.6 | `prlctl set --efi-secure-boot on|off` is the only way to flip SB; it re-provisions Microsoft keys at power-on and does not touch `NVRAM.dat`. | `scripts/stargazer-vm secure-boot` | 2026-09-02 (`virt-fw-vars --print` before/after). | **drop**; OVMF keeps SB state in its vars file. |
| 1.7 | **No vTPM for Linux guests** → no TPM2 LUKS unlock; the passphrase slot is the only unlock. | README §1/§7; `hosts/stargazer/disko.nix` | Parallels documents vTPM as Windows-only; himmelblau's Nix build cannot use a TPM anyway (upstream #1656). | **re-test** — QEMU `swtpm`/UTM offer a vTPM; `systemd-cryptenroll --tpm2` becomes possible. |

## 2. Storage and platform

| # | Workaround | Where | Evidence | Elsewhere |
|---|-----------|-------|----------|-----------|
| 2.1 | Disk is **SATA `/dev/sda`**, not virtio-blk. | `hosts/stargazer/disko.nix`, `stargazer-vm create` (`--iface sata`) | Parallels 27 offers no virtio disk interface. | **re-test** — virtio-blk gives `/dev/vda`; disko device path changes. |
| 2.2 | `--bios-type efi-arm64`, `prlctl reset` instead of `restart` (firmware ignores ACPI reboot requests), ISO must be attached `--connect`. | `scripts/stargazer-vm create|iso`; README §10 | 2026-09-01/02 install. | **drop** (all `prlctl`). |
| 2.3 | `/etc/os-release` reports **Ubuntu 24.04** so Intune's AllowedDistros rule passes. | `modules/nixos/intune-identity.nix` | Tenant rule; **not Parallels**. | **keep**. |

## 3. Graphics and desktop

| # | Workaround | Where | Evidence | Elsewhere |
|---|-----------|-------|----------|-----------|
| 3.1 | **virtio-gpu / virgl** stack: `virtio_gpu` in initrd, `hardware.graphics`, `cursor.no_hardware_cursors`. | `modules/nixos/vm-guest.nix`, `desktop-hyprland.nix` | GL 4.0 via virgl → Alacritty instead of Ghostty. | **keep** — identical under QEMU/UTM virtio-gpu-gl. |
| 3.2 | **`virtio-gpu-resize` follower**: polls the connector's preferred mode and pushes it to Hyprland (debounced, >16 px hysteresis). | `modules/nixos/vm-guest.nix` | 2026-09-02: Parallels updates the preferred mode on window resize but emits no hotplug event; it also reports the mode 8 px narrower after every apply (feedback loop → blinking). | **re-test** — QEMU emits hotplug events; the follower may be redundant. Keep the debounce if kept at all. |
| 3.3 | **Parallels Tools** (`hardware.parallels.enable`, `prlcc` autostart) for shared folders and time sync only. | `modules/nixos/parallels-guest.nix` (`guestTools`) | Clipboard (`prlcp`) is dead under Wayland; tools are aarch64 userspace-only. | **drop**; replace with `spice-vdagent`/`qemu-guest-agent` as needed. |
| 3.4 | **Clipboard not coupled to the hypervisor**: OSC 52 in the terminal, wayvnc over the tailnet for a synced GUI clipboard. | `home/linux/wayvnc.nix`, plan amendment 2026-09-02 | Owner decision after 3.3. | **keep**. |

## 4. Networking

| # | Workaround | Where | Evidence | Elsewhere |
|---|-----------|-------|----------|-----------|
| 4.1 | **MTU 1400** on the primary NIC, DHCP `UseMTU` off. | `modules/nixos/parallels-guest.nix` (`mtu`) | Entra/Intune traffic over Parallels shared NAT needs it; harmless on bridged. | **re-test** — probably unnecessary elsewhere. |
| 4.2 | **Bridged adapter** by default; Shared NAT only as fallback. | `stargazer-vm create`; README §10 | Shared DHCP "never issued a lease" during the install — root cause found 2026-09-03: `prl_naptd` had died on a Sep 1 wake-from-sleep (`error 1235`) and Apple's vmnet sharing service was held by another client (Claude desktop app's sandbox VM, stale `InternetSharing`). | **re-test** — UTM and QEMU's `vmnet` backends use the *same* Apple sharing service; the wedge is macOS-side and can recur there. Recipe in README §10. |
| 4.3 | Public resolvers (1.1.1.1/8.8.8.8), opportunistic DoT, `IPv6AcceptRA=false`, `dhcpV4Config.UseDNS=false`. | `modules/nixos/base.nix`, `parallels-guest.nix` | himmelblau's 3 s connect cap tripped on resolved's parallel A+AAAA stalls; **not Parallels-specific**. | **keep**. |

## 5. Console and automation

| # | Workaround | Where | Evidence | Elsewhere |
|---|-----------|-------|----------|-----------|
| 5.1 | `stargazer-vm console-type`: AppleScript keystrokes into the Parallels window, `key code 47` for periods, focus re-check before Return. | `scripts/stargazer-vm` | Installer ISO has no guest tools; Parallels swallows `keystroke "."`. | **drop**; QEMU/UTM expose a serial console or QMP `send-key`. |
| 5.2 | `prlctl exec` for in-guest commands when the network is down (Parallels Tools required; `$VAR` and `--` are mangled, use absolute paths and one command per call). | README §10 | 2026-09-03 network debugging. | **drop**; use a serial console / `qemu-guest-agent`. |
| 5.3 | Snapshots via `prlctl snapshot(-switch)`; **live snapshots roll back himmelblau's token cache** (`AADSTS70000` afterwards). | `stargazer-vm snapshot|restore`; README §10 | 2026-09-02/03. | **re-test** — any hypervisor's live snapshot has the same effect; snapshot stopped VMs. |

## What is *not* a Parallels workaround (would survive a move unchanged)

`modules/nixos/{base,desktop-hyprland,himmelblau,intune-identity}.nix`, the
sops tenant secret + templates, himmelblau FIX 1–5 (mutable config, Kerberos
dir, unit ordering, tasks PATH, `/etc/cron.d`), the Hyprland session target and
Lua config, wayvnc, the LUKS/btrfs disko layout (device name aside), and the
Entra/Intune ceremony itself.

## If the hypervisor changes

Verified fallback (2026-09-02 research): **QEMU + HVF** on macOS with
`OVMF.override { secureBoot = true; }` — custom keys work, so Secure Boot
collapses to plain lanzaboote (mode A) and §1 disappears entirely. UTM is a
GUI over the same QEMU and offers a vTPM. Expect to re-test §3.2, §4.1, §4.2
(vmnet is shared with Parallels), replace §3.3/§5 tooling, and change the disko
device to `/dev/vda`. Everything under "not a Parallels workaround" carries over.
