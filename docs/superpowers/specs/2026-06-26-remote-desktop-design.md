# Remote Desktop for rocinante — Design Spec

- **Date:** 2026-06-26
- **Status:** Approved design, pre-implementation (validated by spikes)
- **Host:** rocinante (x86_64 Arch / Omarchy, Hyprland, AMD Strix Halo "Radeon 8060S")
- **Supersedes:** the `wayvnc` module (to be removed)

## 1. Goal

Replace VNC (wayvnc) with a low-latency, hi-res remote desktop that feels close to
local for interactive dev work — browsers, IDEs, terminals, occasional video — at
"game-streaming class" responsiveness. Reachable from macOS and iOS clients over
Tailscale, both on the home LAN and fully remote. **Must work with no monitor
attached** (or with the attached monitor asleep/disconnected).

## 2. Requirements

**Functional**
- Stream the full Hyprland desktop (not a single forwarded app).
- Hi-res *and* very responsive for text + images (browser sessions especially).
- Reachable over Tailscale from behemoth (macOS) and iPhone/iPad (iOS).
- Both **native** client (best perf) *and* **browser / zero-install** access.
- Works **headless** — independent of the physical Dell's power/connection state.
- Audio (browser/video) included.
- Input: keyboard, mouse, clipboard.

**Quality / constraints**
- LAN: "very responsive" — target < ~35 ms glass-to-glass.
- WAN: usable/good (network-RTT bound), adaptive bitrate/codec.
- Declarative & reproducible via the Nix dotfiles — no untracked drift. System-level
  bits that cannot live in home-manager are documented as explicit prerequisites.
- Remove the `wayvnc` module entirely.

**Non-goals (YAGNI)**
- Pixel-perfect 4:4:4 colored-text "reading mode" (RDP/AVC444). AMD has **no hardware
  4:4:4**, and the software path sacrifices the responsiveness we are optimizing for.
  Deferred; revisit only if 4:2:0 text proves annoying in practice.
- Greenfield custom protocol. Research showed it cannot beat tuned Sunshine/Moonlight
  on latency — capture + encode + decode dominate, not transport.
- Multi-user / concurrent sessions.

## 3. Validated assumptions (spikes run on the box, 2026-06-26)

All three load-bearing assumptions proven on rocinante (kernel 6.19.9, Mesa 26.0.3,
GPU `/dev/dri/card1` + `renderD128`, Secure Boot disabled, SDDM, Limine bootloader):

1. **Hardware video encode** (`ffmpeg` VAAPI): H.264 7.0×, HEVC 8.1×, AV1 8.1×
   real-time @1080p60; **HEVC 4K60 @ 127 fps (2.1× real-time)** — all clean. → 4K60
   with headroom; 4K120 plausible.
2. **KMS capture → VAAPI** (the highest risk — AMD tiled-scanout import on day-one
   Strix Halo + Hyprland): `ffmpeg -f kmsgrab -device /dev/dri/card1 …
   hwmap=derive_device=vaapi … hevc_vaapi` sustained ~60 fps real-time capture+encode
   of the live Hyprland scanout. AMD tiled-buffer → VAAPI import works first try.
   (Non-monotonic-DTS lines are cosmetic `null`-muxer artifacts.) → KMS capture is
   viable; **no wlr-screencopy fallback needed.**
3. **Network floor** (Tailscale, behemoth↔rocinante): direct path (not DERP), 5 ms;
   WiFi LAN 5.5 ms avg / 1.3 ms jitter / 8.5 ms max on an excellent WiFi-6 link
   (−36 dBm, 1.2 Gbit/s). → ~20–35 ms glass-to-glass budget on LAN, even over WiFi.

**Remaining unproven (low risk, validated at Milestone 1):** EDID-forced headless
output persistence — needs a kernel cmdline change + reboot.

## 4. Architecture

Single capture/stream plane, two client "doors," over Tailscale.

```
            rocinante (Strix Halo, Arch + Hyprland)
 ┌───────────────────────────────────────────────────────────┐
 │  Persistent auto-login Hyprland session                    │
 │  bound to a FORCED display (EDID on a free DP port) —      │
 │  always alive, independent of the physical Dell            │
 │                         │                                  │
 │                  KMS scanout read (CAP_SYS_ADMIN)          │
 │                         │                                  │
 │                 ┌───────▼────────┐                         │
 │                 │ Sunshine       │  VCN4 HW encode         │
 │                 │ HEVC / H264 /  │  (HEVC default)         │
 │                 │ AV1 (VAAPI)    │                         │
 │                 └───┬────────┬───┘                         │
 │      native RTP/ENet│        │ moonlight-web-stream        │
 │                     │        │ (WebRTC proxy)              │
 └─────────────────────┼────────┼────────────────────────────┘
            Tailscale (WireGuard, ACL-gated) — sole path
                       │        │
              ┌────────▼──┐  ┌──▼──────────┐
              │ Moonlight │  │ Browser tab │
              │ Mac / iOS │  │ (zero-inst.)│
              └───────────┘  └─────────────┘
```

## 5. Detailed design

### 5.1 Display foundation (the keystone)
- **Forced output via EDID firmware** on a free DisplayPort connector (e.g. `DP-1`),
  set in the Limine kernel cmdline:
  `drm.edid_firmware=DP-1:edid/rocinante-stream.bin video=DP-1:e`.
  Secure Boot is disabled, so this is unobstructed.
- Provides a **permanent framebuffer** decoupled from the physical Dell (`HDMI-A-1`).
  This permanently eliminates the wayvnc "output went away → capture wedged" failure
  class we debugged.
- **SDDM autologin** for `andreym` → Hyprland session always present on boot, so
  capture has a live desktop without a manual login. (Pair with a lock screen if the
  unlocked-on-boot posture is a concern; rocinante is Tailscale-only + at home.)
- The physical Dell remains usable for local sessions.
- **Resolution: dynamic per-client** — Sunshine resizes the output to the client's
  requested mode on connect (`SUNSHINE_CLIENT_WIDTH/HEIGHT/FPS` do/undo commands),
  base mode 3840×2160. **[OPEN DECISION — see §10.]**

### 5.2 Capture & encode
- **Capture:** Sunshine KMS (`capture = kms`) on the forced output's scanout. Lowest
  latency, compositor-independent. Requires `CAP_SYS_ADMIN`.
- **Encoder:** VAAPI (AMF is unavailable on Linux). Optionally evaluate Sunshine's new
  Vulkan-Video encode path (zero-copy DMA-BUF; lower CPU) once the baseline works.
- **Codec matrix:**
  - **HEVC — default.** HW-decodes on every Apple client.
  - **H.264 — universal fallback.** Cleanest AMD encode; use if HEVC-on-Sunshine-AMD
    artifacts appear (known upstream issue #4314).
  - **AV1 — optional.** Only for M3+ Macs on constrained WAN. *Moonlight iOS cannot
    decode AV1 yet*, so HEVC stays universal.
- **Bitrate:** LAN high (80–150 Mbps HEVC → 4:2:0 chroma loss imperceptible, text
  stays crisp). WAN adaptive via Moonlight rate control.
- **FPS:** 60 default, 120 available.
- **Low-latency knobs:** CBR, small `bufsize`, short GOP, `async_depth 1`.

### 5.3 Clients
- **Native — Moonlight:** macOS (App Store), iOS/iPadOS (App Store); `moonlight-qt` in
  nixpkgs for any Linux client.
- **Browser — `moonlight-web-stream`:** Rust WebRTC proxy co-located with Sunshine →
  zero-install tab from any device. ~2–3× native latency; fine for "from anywhere."

### 5.4 Network & security
- **Tailscale only.** Sunshine binds to the tailnet interface; nothing public.
- **Tailscale ACL** restricting Sunshine's port range (47984–48010 TCP + 47998–48010
  UDP, 47990 web UI) and the browser-proxy port to the user's own devices.
- Sunshine **pairing PIN** retained.
- **Recommendation:** connect `enp191s0` (2.5GbE, currently down) to shave the jitter
  tail and harden against WiFi contention. WiFi-6 is viable as-is.

### 5.5 Nix / dotfiles integration
New module replacing `modules/.../wayvnc`:
- **home-manager:** install `sunshine` (+ `moonlight-web-stream`), define the user
  systemd service(s) (mirror the existing `wayvnc.service` pattern), ship Sunshine
  `config`/`apps.json` declaratively.
- **System-level prerequisites** (cannot be done in home-manager on Arch — documented
  and scripted on the Arch/system side):
  - `setcap cap_sys_admin+p` on the Sunshine binary (KMS capture);
  - `uinput` udev rule + group membership (input injection);
  - EDID firmware file + Limine kernel cmdline (forced output);
  - SDDM autologin.
- **Remove** the `wayvnc` module and its service.

### 5.6 Robustness
- Lightweight **watchdog** (lesson from the wayvnc wedge): a health-check that restarts
  Sunshine if capture/output is lost, and **verifies the restart took effect** (avoid
  the "alive but brain-dead" state wayvnc fell into). With KMS + forced EDID output,
  output-loss should not occur — this is a safety net, not the primary mechanism.

## 6. Client × codec compatibility matrix

| Client | HEVC HW-decode | AV1 HW-decode | Moonlight AV1? | Practical codec |
|---|---|---|---|---|
| behemoth (Apple Silicon Mac) | ✅ all | ✅ only M3+ | ✅ (desktop) | HEVC; AV1 if M3+ on WAN |
| iPhone/iPad (iOS) | ✅ all A9+ | ⚠️ A17 Pro+ only | ❌ not in Moonlight iOS | HEVC |
| Any browser (web proxy) | depends on browser/codec | varies | n/a | HEVC/H.264 via WebRTC |

## 7. Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| EDID headless persistence (only unproven piece) | low | Milestone 1 with fallbacks: KMS+EDID → wlr-screencopy → hardware dummy plug |
| HEVC-on-Sunshine-AMD artifacts (#4314) | medium | Fall back to H.264 or AV1; matrix-test during tuning |
| Strix Halo encode + heavy ROCm/compute concurrency GPU hang | low | Kernel 6.19 has the gfx1151 fixes; avoid simultaneous heavy compute+encode if instability appears |
| WiFi jitter under contention | low | Optional Ethernet (`enp191s0`) |

## 8. Milestones (outline; detailed plan via writing-plans)

1. **Capture validation** — EDID forced output + SDDM autologin + Sunshine KMS
   capture, headless, verified (with the §7 fallbacks). *Gate before further work.*
2. **Encode/codec tuning + pairing** — Moonlight on behemoth + iPad; walk the codec
   matrix; measure glass-to-glass latency; tune bitrate/fps/low-latency flags.
3. **Browser path** — `moonlight-web-stream`.
4. **Nix module + system prereqs** — declarative config; **remove wayvnc**.
5. **Robustness + docs** — watchdog; host README updates.

## 9. Testing / verification

- Install `libva-utils`; `vainfo` confirms HEVC/AV1/H264 encode entrypoints.
- ffmpeg HW-encode smoke tests — **done** (§3.1).
- `kmsgrab` capture spike — **done** (§3.2).
- End-to-end: Moonlight on behemoth + iPad; measure latency; walk codec matrix.
- **Headless regression test:** detach/sleep the Dell, confirm the stream survives —
  this is the explicit regression test for the original wayvnc failure.

## 10. Open decisions

- **Streaming resolution:** dynamic per-client (recommended — adapts to Mac vs iPad,
  avoids ultrawide letterboxing) vs. a fixed **5120×2160 ultrawide canvas** matching
  the Dell (consistent window layouts, but letterboxed on 16:10/4:3 clients).

## 11. References (research, 2026-06-26)

- AMD VCN4 / Strix Halo Linux encode: Mesa 25.1.4+/26.x release notes; Frigate
  discussion #20337; ROCm issues #5665/#5724; kernel 6.18 gfx1151 stability.
- Sunshine/Moonlight on Wayland/headless/AMD: LizardByte Sunshine docs & issues
  (#4197 headless, #4314 HEVC-AMD artifacts); CatWithCode EDID-headless guide; nixpkgs
  Sunshine module; Moonlight macOS/iOS apps; moonlight-ios #585 (no AV1 yet).
- Apple VideoToolbox HW decode (HEVC all Apple Silicon; AV1 M3/A17 Pro+).
- Browser path: `moonlight-web-stream`; Selkies (X11-only, rejected).
- Text crispness / AMD no-4:4:4: LizardByte discussion #220; RDP AVC444 (deferred).
