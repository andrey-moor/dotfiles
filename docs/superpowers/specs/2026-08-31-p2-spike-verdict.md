# P2 Spike Verdict — himmelblau (B4) vs intuneme (B3)

**Date:** 2026-08-31 (spikes built 2026-08-03; enrollment ceremonies 2026-08-30/31)
**Answers:** fork B of `2026-07-23-environment-refactor-design.md` (§2, §8).
**Sanitized:** no tenant identifiers, device IDs, or UPNs. AADSTS codes retained per plan.

## Verdict

**B4 (himmelblau) wins fork B, with one strategic caveat.** The client technology
passes every rung it was allowed to attempt — Entra join, PRT + Hello PIN, NSS/idmap,
Intune enrollment, compliance evaluation — on both x86_64 and aarch64 NixOS. The
only failed check is *tenant policy*: the compliance verdict flags the honestly
reported distro ("NixOS" is not on the tenant's Linux allowlist), plus two
VM-configuration axes (disk encryption, Secure Boot) that P8/P9 already plan to fix.

**B3 (intuneme) is not viable on NixOS** without upstream work: a systemic
bare-FHS-path exec pattern required a `systemd-nspawn` PATH-injection wrapper to
provision at all, recurred in ≥5 more sites, and the portal UI never launched
(undiagnosed within the time-box). 10 manual interventions vs. B4's 0 to reach
their respective doorsteps.

## Scorecard

| Success-bar cell | B4 x86_64 | B4 aarch64 (Parallels) | B3 x86_64 |
|---|---|---|---|
| Doorstep (services green, no auth) | PASS (0 pokes) | PASS (0 pokes) | PARTIAL (10 pokes; UI never launched) |
| Enrolled (Entra join) | NOT-REACHED* | **PASS** (FIDO console login) | NOT-REACHED |
| Intune-enrolled | — | **PASS** (no 530003!) | NOT-REACHED |
| Compliant | — | **FAIL — tenant policy** (distro allowlist ×2, disk encryption, Secure Boot) | NOT-REACHED |
| CA-gated resource opens | — | Not exercised (gated on Compliant) | NOT-REACHED |
| Survives reboot | — | Not exercised (join state persists on disk; config fixes are ephemeral — see below) | NOT-REACHED |
| Ergonomics | — | First login: FIDO×2 + PIN setup. Subsequent: Hello PIN. Tolerable. | — |

\* B4-x86 was blocked by flows, not tech: the SSH-reachable paths are password-first
(account is passwordless) and device-code (AADSTS53003 — CA blocks the flow itself;
the flow decouples authenticating-device from token-receiving-device, which is
exactly what such policies exist to stop). FIDO is local-console-only in himmelblau,
and the x86 host is remote. Same client enrolled fine at a local console on ARM.

## The five findings that matter for P8

1. **Join-then-Intune ordering defuses the 530003 catch-22.** Intune enrollment
   succeeded with zero CA friction *after* the device already held an Entra
   identity + PRT. Preserve this ordering in P8.
2. **A passwordless account needs a local-console first factor.** himmelblau
   offers FIDO/security-key only for non-remote services. Enrollment ceremony =
   physical/virtual console + hardware key (or QR/Bluetooth, untested). Plan for
   it; SSH-only enrollment is a dead end on this tenant.
3. **The distro allowlist is the strategic decision, not a technical one.**
   Honest "NixOS" fails the LinuxMDM allowed-distros rule. Options for P8:
   (a) request an allowlist addition (owner/tenant-admin conversation);
   (b) report a supported distro string (returns to spoofing, now on a supported
   version — policy call, explicitly out of spike scope);
   (c) genuine Ubuntu VM (B2 baseline from the spec) with himmelblau irrelevant.
   The spike deliberately does not choose.
4. **Two compliance axes are ordinary engineering:** LUKS (P9 design already has
   it) and Secure Boot (Parallels EFI-SB / OVMF-SB). Fix both before revisiting
   the compliance verdict.
5. **NixOS-module fixes P8 must inherit** (all were ephemeral hand-fixes in the
   spike): (a) the daemon reads `--config /nix/store/…` — a mutable config needs
   the ExecStart override baked into the module; (b) `ip_version`/tenant pinning:
   set `tenant_id` per-domain to skip odc federation discovery; (c) **MTU 1400
   on Parallels shared networking** (NAT drops fragmented large TLS ClientHellos —
   himmelblau's rustls hello, not curl's, so it looks daemon-specific);
   (d) `enable_passwordless_security_key=true` + experimental FIDO;
   (e) missing `/etc/krb5.conf.d/` and one tasks-daemon EPERM warning to clean up.

## What P8 inherits

- Parallels VM `spike-himmelblau-arm` — **live, Entra-joined, Intune-enrolled** —
  the P8 seed. Its `doorstep` snapshot predates enrollment (clean rollback point).
- `spikes/intune/` flake + modules (`base.nix`, `b4-himmelblau.nix`,
  `b3-intuneme.nix` with honest status headers) + scripts
  (`spike`, `spike-parallels`, `arm-builder`, `serial_drive.py`).
- A preserved aarch64 image at `~/spike-artifacts/b4-image-aarch64.qcow2`
  (local-only; carries baked config — never publish).
- Full ceremony evidence in `spikes/intune/notes/` (local, gitignored).

## Teardown executed (2026-08-31, owner ruling: keep winners)

Destroyed: b3 + b4-x86 VMs on rocinante (~20G; `~/spikes` now 38M — flake copy +
scripts + key only); arm-builder VM on behemoth (~30G net reclaimed).
Kept: `spike-himmelblau-arm` (enrolled winner), the repo artifacts, the image above.

## Roadmap consequences

- **P8 (work-VM)** builds on himmelblau per the findings above; its first two
  work items are LUKS + Secure Boot, then the allowlist decision (finding 3).
- **P9 (stargazer successor)** gets its answer early: himmelblau works on
  aarch64 — a Mac-side Linux corp VM is viable, same recipe.
- **P7/P9 correction:** behemoth has NO persistent linux-builder and cannot get
  one under Determinate (`nix.linux-builder` hard-requires `nix.enable`;
  Determinate's native builder is invite-only preview). `scripts/arm-builder`
  (throwaway QEMU/HVF) is the working substitute when images must be rebuilt.
- The old `intune.nix` + os-release spoof retire unported once P8 lands
  (per spec §2); the fuse pressure is now understood precisely — it is the
  allowlist, and the allowlist is a policy conversation.
