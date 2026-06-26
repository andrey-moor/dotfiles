# Remote Desktop (Sunshine/Moonlight) on rocinante — Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.
> Steps are marked **🧑 USER** (needs sudo / reboot / a physical client device — a human runs it) or **🤖 AGENT** (runnable from this session). This is a host-config runbook, not a unit-tested codebase: each task's "test" is a concrete verification command with expected output.

**Goal:** Replace wayvnc on rocinante with a hardware-encoded, headless Sunshine/Moonlight remote desktop reachable over Tailscale from macOS + iOS, at game-streaming-class latency.

**Architecture:** A persistent auto-login Hyprland session bound to an EDID-forced output (always alive regardless of the physical monitor). Sunshine does KMS capture → AMD VCN4 hardware HEVC encode → native Moonlight clients + a browser proxy. Sunshine is installed via pacman/AUR (KMS capture needs `CAP_SYS_ADMIN`, which cannot be `setcap`'d on a Nix-store binary), following the existing "tailscale via pacman" precedent; config is tracked in the dotfiles.

**Tech Stack:** Sunshine (AUR), Moonlight (macOS/iOS App Store; `moonlight-qt` in Arch `extra` for Linux clients), AMD VAAPI/Mesa 26, Hyprland/wlroots, Limine (kernel cmdline), SDDM (autologin), Tailscale, chezmoi (config), Nix home-manager (module disable + client helper scripts).

---

## ⚠️ Deviations from the spec (`docs/superpowers/specs/2026-06-26-remote-desktop-design.md`)

Grounding in the real repo changed two spec assumptions. Both are reflected below:

1. **Packaging:** Spec §5.5 said "home-manager installs sunshine." Not viable — KMS capture needs `CAP_SYS_ADMIN` and you cannot `setcap` an immutable `/nix/store` path. **Sunshine is installed via AUR** (its package does the `setcap` + uinput udev rule), config tracked in chezmoi. Matches the established `tailscale`-via-pacman pattern. (Recommend updating spec §5.5 to match.)
2. **wayvnc retention:** Spec §2/§5.5 said "remove the wayvnc module entirely." **Keep it** — `hosts/stargazer/default.nix:87-91` enables it (aarch64 VM, no Strix Halo encoder). We only **disable wayvnc on rocinante**.

**Open decision resolved:** streaming resolution = **dynamic per-client** (Sunshine resizes the output to the client's request on connect). Easily changed later.

---

## File structure

| File | Action | Responsibility |
|---|---|---|
| `chezmoi/dot_config/sunshine/sunshine.conf` | Create | Sunshine static config (KMS capture, VAAPI, codec, bitrate) |
| `chezmoi/dot_config/sunshine/apps.json` | Create | Sunshine "Desktop" app + dynamic-resolution prep commands |
| `hosts/rocinante/default.nix` | Modify (`108-111`) | Disable wayvnc; add sunshine client-helper module enable |
| `modules/home/linux/sunshine-helpers.nix` | Create | Home-manager module: client-side helper scripts only (no binary, no caps) |
| `hosts/rocinante/README.md` | Modify | Document the system prerequisites (AUR, EDID, limine, autologin) |
| `hosts/rocinante/setup-sunshine.md` | Create | Copy-paste runbook for the sudo/system steps (EDID, limine, sddm) |
| `modules/home/linux/wayvnc.nix` | Unchanged | Kept for stargazer |

State files Sunshine writes at runtime (`sunshine_state.json`, credentials) are **not** tracked by chezmoi — only the two static files above.

---

## Milestone 0 — Branch

### Task 0: Create the working branch

**Files:** none

- [ ] **Step 1 (🤖 AGENT): Create and switch to a feature branch**

```bash
cd /home/andreym/dotfiles && git switch -c feat/remote-desktop-sunshine
```

- [ ] **Step 2 (🤖 AGENT): Verify**

Run: `git branch --show-current`
Expected: `feat/remote-desktop-sunshine`

- [ ] **Step 3 (🤖 AGENT): Commit the already-written spec onto the branch**

```bash
git add docs/superpowers/specs/2026-06-26-remote-desktop-design.md docs/superpowers/plans/2026-06-26-remote-desktop-sunshine.md
git commit -m "docs: remote desktop (sunshine) design spec + implementation plan"
```

---

## Milestone 1 — Headless capture foundation (THE GATE)

> Everything downstream assumes Sunshine can KMS-capture a monitor-independent output. Do not proceed past Task 1.6 until the headless regression test (Task 1.6) passes. Fallbacks are in Task 1.7.

### Task 1.1: Install Sunshine via AUR

**Files:** none (system package)

- [ ] **Step 1 (🤖 AGENT): Confirm it's not already installed**

Run: `command -v sunshine || echo "absent"`
Expected: `absent`

- [ ] **Step 2 (🧑 USER): Install Sunshine (interactive — yay needs your sudo password)**

Run in your terminal:
```
yay -S --noconfirm sunshine
```

- [ ] **Step 3 (🤖 AGENT): Verify binary + the CAP_SYS_ADMIN file capability the AUR package set**

Run: `getcap "$(command -v sunshine)"; sunshine --version 2>&1 | head -1`
Expected: a line like `/usr/bin/sunshine cap_sys_admin=p` (the capability is present) and a version string. If `getcap` prints nothing, KMS capture will fail — fix with `sudo setcap cap_sys_admin+p /usr/bin/sunshine` and re-check.

- [ ] **Step 4 (🤖 AGENT): Verify uinput access for input injection**

Run: `ls -l /dev/uinput; id -nG | tr ' ' '\n' | grep -E '^(input|uinput)$' || echo "NOT in input group"`
Expected: `/dev/uinput` exists and you are in `input` (or `uinput`) group. If not in group: **🧑 USER** run `sudo usermod -aG input andreym` and re-login.

### Task 1.2: Forge a monitor-independent output (EDID dump)

**Files:** `/usr/lib/firmware/edid/rocinante-stream.bin` (system)

We reuse the Dell's real, 4K-capable EDID so the forced connector advertises valid modes.

- [ ] **Step 1 (🤖 AGENT): Confirm the Dell EDID is readable and non-empty**

Run: `sudo -n test -s /sys/class/drm/card1-HDMI-A-1/edid && echo OK || echo "needs sudo / or monitor asleep"`
Expected: `OK` (the Dell is currently connected per earlier probe). If the connector is asleep, wake it first.

- [ ] **Step 2 (🧑 USER): Dump the Dell EDID into the firmware dir**

Run in your terminal:
```
sudo install -Dm644 /sys/class/drm/card1-HDMI-A-1/edid /usr/lib/firmware/edid/rocinante-stream.bin
```

- [ ] **Step 3 (🤖 AGENT): Verify the EDID blob**

Run: `sudo -n parse-edid < /usr/lib/firmware/edid/rocinante-stream.bin 2>/dev/null | head -5 || sudo -n stat -c '%s bytes' /usr/lib/firmware/edid/rocinante-stream.bin`
Expected: a valid EDID parse, or a size that's a multiple of 128 bytes (typically 256/384).

### Task 1.3: Force the output via initramfs EDID + Limine cmdline (NO reboot yet)

**Files:** `/etc/mkinitcpio.conf` (`FILES`), `/etc/default/limine` (`KERNEL_CMDLINE`) — both system.

> ⚠️ Do **not** edit `/boot/limine.conf` — it is auto-generated by `limine-entry-tool` and rebuilt into the UKI; edits are clobbered on kernel update. The cmdline source of truth is `/etc/default/limine`. And because `HOOKS=(… kms …)` pulls amdgpu into the initramfs (Plymouth `splash`), the EDID **must be in the initramfs** (`FILES`), else the kernel lacks it when the GPU probes. The forced EDID keeps `HDMI-A-1` enabled even when the Dell is off — the permanent fix for the wayvnc "output went away" failure.

- [ ] **Step 1 (🧑 USER): Add the EDID to the initramfs FILES**

```
sudo sed -i 's|^FILES=()|FILES=(/usr/lib/firmware/edid/rocinante-stream.bin)|' /etc/mkinitcpio.conf
grep '^FILES=' /etc/mkinitcpio.conf   # confirm it now lists the edid
```

- [ ] **Step 2 (🧑 USER): Append the cmdline params in /etc/default/limine** (the `+=` syntax is tool-handled; spacing is automatic)

```
echo 'KERNEL_CMDLINE[default]+="drm.edid_firmware=HDMI-A-1:edid/rocinante-stream.bin video=HDMI-A-1:e"' | sudo tee -a /etc/default/limine
```

- [ ] **Step 3 (🧑 USER): Rebuild UKI + initramfs + limine.conf**

Run: `sudo limine-update`
Expected: it runs `limine-mkinitcpio` (mkinitcpio rebuilds the UKI) with no errors. **Do not reboot yet — Task 1.4 adds autologin, then one combined reboot.**

### Task 1.4: SDDM autologin + the single combined reboot

**Files:** `/etc/sddm.conf.d/10-autologin.conf` (system)

> Omarchy uses UWSM (`loginctl` shows `Desktop=Hyprland`), so the session is `hyprland-uwsm.desktop` (confirmed present in `/usr/share/wayland-sessions/`).

- [ ] **Step 1 (🧑 USER): Write the autologin drop-in**

```
sudo install -d /etc/sddm.conf.d
printf '[Autologin]\nUser=andreym\nSession=hyprland-uwsm.desktop\n' | sudo tee /etc/sddm.conf.d/10-autologin.conf
```

- [ ] **Step 2 (🧑 USER): Reboot once** (applies both the forced-EDID UKI from Task 1.3 and autologin)

Run: `sudo reboot` — then reconnect (`ssh rocinante`) and resume.

- [ ] **Step 3 (🤖 AGENT): Verify forced-EDID cmdline is live**

Run: `cat /proc/cmdline | tr ' ' '\n' | grep -E 'edid_firmware|video=HDMI'`
Expected: both `drm.edid_firmware=HDMI-A-1:edid/rocinante-stream.bin` and `video=HDMI-A-1:e`.

- [ ] **Step 4 (🤖 AGENT): Verify autologin produced a Hyprland session**

Run: `ls /run/user/1000/hypr/ 2>/dev/null && echo "hyprland session present"`
Expected: an instance-signature dir + `hyprland session present`.

- [ ] **Step 5 (🤖 AGENT): Verify the forced output is present even though the Dell may be asleep**

Run: `cat /sys/class/drm/card1-HDMI-A-1/{status,enabled}`
Expected: `connected` + `enabled` (the forced EDID is holding the connector up regardless of the physical monitor).

### Task 1.5: Sunshine KMS capture config + service up

**Files:** `~/.config/sunshine/sunshine.conf` (hand-placed now; chezmoi-tracked in M4)

- [ ] **Step 1 (🤖 AGENT): Write a minimal KMS/VAAPI config**

```bash
mkdir -p ~/.config/sunshine
cat > ~/.config/sunshine/sunshine.conf <<'EOF'
# rocinante Sunshine — KMS capture + AMD VAAPI HEVC (validated by spikes 2026-06-26)
capture = kms
encoder = vaapi
adapter_name = /dev/dri/renderD128
sw_preset = ultrafast
min_log_level = info
# Codec: HEVC default (HW-decodes on all Apple clients). Fallbacks tuned in M2.
EOF
```

- [ ] **Step 2 (🧑 USER): Start Sunshine once in the foreground to set the web-UI credential and confirm capture**

Run in your terminal (inside the Hyprland session, or with `WAYLAND_DISPLAY` set):
```
sunshine ~/.config/sunshine/sunshine.conf
```
Watch the log for a line enumerating the display/output without `Failed to` errors. Open `https://localhost:47990` once to set the admin username/password, then Ctrl-C.

- [ ] **Step 3 (🤖 AGENT): Verify Sunshine saw a capturable output (no KMS errors in log)**

Run: `journalctl --user -u sunshine -n 30 --no-pager 2>/dev/null | grep -iE 'kms|display|encoder|error' | tail -15` (or re-run foreground and inspect)
Expected: display enumerated, VAAPI/HEVC encoder initialized, **no** `Failed to map` / `No KMS` errors. If KMS errors appear → **Task 1.7 fallback**.

- [ ] **Step 4 (🤖 AGENT): Enable the Sunshine user service**

Run: `systemctl --user enable --now sunshine; systemctl --user is-active sunshine`
Expected: `active`. (The AUR package ships the user unit.)

### Task 1.6: 🚦 GATE — headless regression test

**Files:** none

- [ ] **Step 1 (🧑 USER): Put the Dell to sleep / unplug it**

Turn the Dell off (or unplug HDMI). Wait 10s.

- [ ] **Step 2 (🤖 AGENT): Confirm the output and capture survive**

Run: `hyprctl monitors | grep -A2 HDMI-A-1; systemctl --user is-active sunshine`
Expected: `HDMI-A-1` still listed with its mode (forced EDID holding it alive), Sunshine still `active`. This is the exact scenario that wedged wayvnc — it must now pass.

- [ ] **Step 3 (🤖 AGENT): Confirm Sunshine still captures with no monitor**

Run: `journalctl --user -u sunshine --since "1 min ago" --no-pager | grep -iE 'error|capture|output' | tail -10`
Expected: no new capture/output errors. **If this passes, Milestone 1 is complete.**

### Task 1.7: Fallback (only if Task 1.5/1.6 KMS capture failed)

**Files:** `~/.config/sunshine/sunshine.conf`

- [ ] **Step 1 (🤖 AGENT): Switch capture method to wlroots**

```bash
sed -i 's/^capture = kms/capture = wlr/' ~/.config/sunshine/sunshine.conf
systemctl --user restart sunshine
```

- [ ] **Step 2 (🤖 AGENT): Re-run the Task 1.6 gate.** If `wlr` also fails headless, escalate: a $5 HDMI dummy plug replaces the EDID approach (document and pause for hardware).

---

## Milestone 2 — Encode/codec tuning + client pairing

### Task 2.1: Tune codec, bitrate, dynamic resolution

**Files:** `~/.config/sunshine/sunshine.conf`, `~/.config/sunshine/apps.json`

- [ ] **Step 1 (🤖 AGENT): Append encode tuning to sunshine.conf**

```bash
cat >> ~/.config/sunshine/sunshine.conf <<'EOF'

# --- encode tuning (LAN-first; Moonlight client overrides bitrate per-session) ---
hevc_mode = 1        # advertise HEVC (Main). H.264 auto-fallback if client lacks it.
av1_mode = 0         # off by default (Moonlight iOS can't decode AV1); enable for M3+ Mac later
fec_percentage = 10
EOF
```

- [ ] **Step 2 (🤖 AGENT): Write apps.json with a Desktop entry that resizes the output to the client on connect**

```bash
cat > ~/.config/sunshine/apps.json <<'EOF'
{
  "env": {},
  "apps": [
    {
      "name": "Desktop",
      "prep-cmd": [
        {
          "do":   "hyprctl keyword monitor HDMI-A-1,${SUNSHINE_CLIENT_WIDTH}x${SUNSHINE_CLIENT_HEIGHT}@${SUNSHINE_CLIENT_FPS},0x0,1",
          "undo": "hyprctl keyword monitor HDMI-A-1,3840x2160@60,0x0,1"
        }
      ]
    }
  ]
}
EOF
systemctl --user restart sunshine
```

- [ ] **Step 3 (🤖 AGENT): Verify Sunshine reloaded cleanly**

Run: `systemctl --user is-active sunshine && journalctl --user -u sunshine -n 5 --no-pager`
Expected: `active`, no parse errors for apps.json.

### Task 2.2: Pair Moonlight on behemoth (macOS) and measure latency

**Files:** none

- [ ] **Step 1 (🧑 USER): Install Moonlight on the Mac** (Mac App Store "Moonlight Game Streaming") if not present.

- [ ] **Step 2 (🤖 AGENT): Get a fresh pairing PIN endpoint reminder**

Run: `echo "Add host in Moonlight: rocinante (100.80.226.110). It will show a PIN to enter at https://localhost:47990 → PIN tab (or sunshine web UI on the host)."`

- [ ] **Step 3 (🧑 USER): In Moonlight on the Mac**, add host `rocinante` (or `100.80.226.110`), enter the PIN into Sunshine's web UI, then launch **Desktop**. Confirm you see and can control the desktop.

- [ ] **Step 4 (🧑 USER): Latency check** — in Moonlight, enable the on-screen performance overlay (stats). Record: decode time, network latency, host processing. Target on LAN: < ~35 ms total. Paste the numbers back.

- [ ] **Step 5 (🤖 AGENT): Record results** in `hosts/rocinante/setup-sunshine.md` (a "Measured latency" line per client/codec).

### Task 2.3: Pair Moonlight on iPad/iPhone (iOS, HEVC)

- [ ] **Step 1 (🧑 USER): Install Moonlight (iOS App Store) on the iPad/iPhone**, add `rocinante`, pair, launch Desktop. Confirm HEVC (iOS can't use AV1). Note latency from the overlay.

- [ ] **Step 2 (🤖 AGENT): Record results** alongside Task 2.2.

### Task 2.4: Codec matrix / artifact check

- [ ] **Step 1 (🧑 USER): On the Mac, watch for the known AMD-HEVC artifact** (issue #4314: green line / black bars). If present, set `hevc_mode = 0` to force H.264, restart, re-test.

- [ ] **Step 2 (🤖 AGENT): Lock the working codec** in sunshine.conf and note the decision in setup-sunshine.md.

---

## Milestone 3 — Browser path (zero-install)

### Task 3.1: Run moonlight-web-stream proxy

**Files:** `~/.config/sunshine/` (unchanged); a podman container

- [ ] **Step 1 (🤖 AGENT): Confirm podman is available** (rocinante already runs containers per `modules/home/linux/containers.nix`).

Run: `command -v podman && podman --version`
Expected: a version.

- [ ] **Step 2 (🧑 USER): Run the proxy bound to the tailnet** (image per moonlight-web-stream README):
```
podman run -d --name moonlight-web --network host \
  ghcr.io/mrcreativ3001/moonlight-web-stream:latest
```

- [ ] **Step 3 (🤖 AGENT): Verify it's listening**

Run: `ss -tlnp | grep -E ':(8080|47990)' ; podman ps --filter name=moonlight-web --format '{{.Status}}'`
Expected: proxy port listening, container `Up`.

- [ ] **Step 4 (🧑 USER): From a browser on any tailnet device**, open the proxy URL (`http://100.80.226.110:<port>`), pair/connect to Sunshine, confirm the desktop streams in-tab.

- [ ] **Step 5 (🤖 AGENT): If it works, capture the exact `podman run` line** into setup-sunshine.md (later: convert to a quadlet/systemd unit in M4).

---

## Milestone 4 — Declarative integration + retire wayvnc on rocinante

### Task 4.1: Track Sunshine config in chezmoi

**Files:** `chezmoi/dot_config/sunshine/sunshine.conf`, `chezmoi/dot_config/sunshine/apps.json`

- [ ] **Step 1 (🤖 AGENT): Copy the tuned config into the chezmoi source**

```bash
mkdir -p /home/andreym/dotfiles/chezmoi/dot_config/sunshine
cp ~/.config/sunshine/sunshine.conf  /home/andreym/dotfiles/chezmoi/dot_config/sunshine/sunshine.conf
cp ~/.config/sunshine/apps.json       /home/andreym/dotfiles/chezmoi/dot_config/sunshine/apps.json
```

- [ ] **Step 2 (🤖 AGENT): Verify chezmoi would manage them without clobbering runtime state**

Run: `cd /home/andreym/dotfiles && chezmoi diff ~/.config/sunshine/sunshine.conf`
Expected: empty (source matches live). Only these two files are tracked; `sunshine_state.json`/credentials are left untracked.

- [ ] **Step 3 (🤖 AGENT): Commit**

```bash
cd /home/andreym/dotfiles
git add chezmoi/dot_config/sunshine/
git commit -m "feat(rocinante): track sunshine config in chezmoi"
```

### Task 4.2: Client-helper home-manager module (scripts only, no binary)

**Files:** `modules/home/linux/sunshine-helpers.nix`

- [ ] **Step 1 (🤖 AGENT): Create the module** (mirrors the wayvnc module's option/`mkIf` shape, but installs no binary and sets no caps):

```nix
# modules/home/linux/sunshine-helpers.nix -- helper scripts for the AUR-installed Sunshine.
# The sunshine binary, setcap, and uinput udev rule are provided by the AUR package
# (KMS capture needs CAP_SYS_ADMIN, which cannot be setcap'd on a /nix/store path).
{ lib, config, pkgs, ... }:
with lib;
let cfg = config.modules.linux.sunshineHelpers;
in {
  options.modules.linux.sunshineHelpers = {
    enable = mkEnableOption "Sunshine client/host helper scripts (binary installed via AUR)";
  };

  config = mkIf (cfg.enable && pkgs.stdenv.isLinux) {
    home.packages = [
      (pkgs.writeShellScriptBin "sunshine-status" ''
        echo "service: $(systemctl --user is-active sunshine)"
        getcap "$(command -v sunshine)" || echo "WARNING: sunshine missing cap_sys_admin (KMS capture will fail)"
        ${pkgs.coreutils}/bin/cat /proc/cmdline | tr ' ' '\n' | grep -E 'edid_firmware|video=HDMI' || echo "WARNING: forced-output kernel params missing"
      '')
    ];
  };
}
```

- [ ] **Step 2 (🤖 AGENT): Verify the file parses**

Run: `cd /home/andreym/dotfiles && nix-instantiate --parse modules/home/linux/sunshine-helpers.nix >/dev/null && echo OK`
Expected: `OK`.

### Task 4.3: Switch rocinante from wayvnc to sunshine

**Files:** `hosts/rocinante/default.nix:103-112`

- [ ] **Step 1 (🤖 AGENT): Edit the `linux = { … }` block** — replace the wayvnc enablement with the helper module. Change:

```nix
      linux = {
        edge.enable = true;
        firefox.enable = true;
        intune.enable = true;
        intune.debug = true;  # Enable verbose logging for debugging
        wayvnc = {
          enable = true;
          password = "rocinante";
        };
      };
```
to:
```nix
      linux = {
        edge.enable = true;
        firefox.enable = true;
        intune.enable = true;
        intune.debug = true;  # Enable verbose logging for debugging
        # Remote desktop migrated wayvnc -> Sunshine/Moonlight (2026-06-26).
        # Binary + caps via AUR (see hosts/rocinante/setup-sunshine.md); config in chezmoi.
        sunshineHelpers.enable = true;
      };
```

- [ ] **Step 2 (🤖 AGENT): Build the config (no apply yet)**

Run: `cd /home/andreym/dotfiles && nix run home-manager -- build --flake .#rocinante 2>&1 | tail -15`
Expected: builds with no evaluation errors (the `sunshineHelpers` option resolves; `wayvnc` no longer referenced).

- [ ] **Step 3 (🧑 USER): Apply**

Run: `cd ~/dotfiles && nix run home-manager -- switch --flake .#rocinante -b backup`

- [ ] **Step 4 (🤖 AGENT): Stop and disable the old wayvnc service**

Run: `systemctl --user disable --now wayvnc 2>/dev/null; systemctl --user is-active wayvnc || echo "wayvnc stopped"`
Expected: `wayvnc stopped`. Confirm `sunshine-status` script prints healthy output.

- [ ] **Step 5 (🤖 AGENT): Commit**

```bash
cd /home/andreym/dotfiles
git add modules/home/linux/sunshine-helpers.nix hosts/rocinante/default.nix
git commit -m "feat(rocinante): switch remote desktop from wayvnc to sunshine"
```

### Task 4.4: Tailscale ACL for Sunshine ports

**Files:** Tailscale admin policy (out-of-repo) — documented in `setup-sunshine.md`

- [ ] **Step 1 (🧑 USER): In the Tailscale admin console**, ensure the ACL grants only your own devices access to rocinante's Sunshine ports: TCP `47984,47989,47990,48010`, UDP `47998-48000,48002,48010`, plus the web-proxy port. (Tailscale is already the only ingress; this is defense-in-depth.)

- [ ] **Step 2 (🤖 AGENT): Document the exact port list** in setup-sunshine.md.

---

## Milestone 5 — Robustness + docs

### Task 5.1: Capture-loss watchdog

**Files:** `chezmoi/dot_config/systemd/user/sunshine-watchdog.{service,timer}` (or document if you prefer the AUR unit's own Restart)

- [ ] **Step 1 (🤖 AGENT): Create a 60s health-check timer that restarts Sunshine if the output/capture is lost** (the lesson from the wayvnc wedge — and it must *verify the restart helped*, not just fire):

```bash
mkdir -p /home/andreym/dotfiles/chezmoi/dot_config/systemd/user
cat > /home/andreym/dotfiles/chezmoi/dot_config/systemd/user/sunshine-watchdog.service <<'EOF'
[Unit]
Description=Restart Sunshine if its capture output is gone
[Service]
Type=oneshot
ExecStart=/bin/sh -c 'hyprctl monitors | grep -q HDMI-A-1 || systemctl --user restart sunshine'
EOF
cat > /home/andreym/dotfiles/chezmoi/dot_config/systemd/user/sunshine-watchdog.timer <<'EOF'
[Unit]
Description=Run Sunshine watchdog every 60s
[Timer]
OnBootSec=120
OnUnitActiveSec=60
[Install]
WantedBy=timers.target
EOF
```

- [ ] **Step 2 (🧑 USER): Apply via chezmoi + enable the timer**

Run: `chezmoi apply ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now sunshine-watchdog.timer`

- [ ] **Step 3 (🤖 AGENT): Verify the timer is armed**

Run: `systemctl --user list-timers sunshine-watchdog.timer --no-pager`
Expected: the timer is listed with a NEXT time.

- [ ] **Step 4 (🤖 AGENT): Commit**

```bash
cd /home/andreym/dotfiles
git add chezmoi/dot_config/systemd/user/
git commit -m "feat(rocinante): sunshine capture-loss watchdog"
```

### Task 5.2: Document the host setup + final verification

**Files:** `hosts/rocinante/README.md`, `hosts/rocinante/setup-sunshine.md`

- [ ] **Step 1 (🤖 AGENT): Write `setup-sunshine.md`** capturing every 🧑 USER system step (AUR install, EDID dump, limine cmdline, sddm autologin, uinput group, Tailscale ACL, podman proxy line, measured latencies, chosen codec).

- [ ] **Step 2 (🤖 AGENT): Add a short "Remote desktop" section to `hosts/rocinante/README.md`** pointing at setup-sunshine.md and noting wayvnc was retired here (still used by stargazer).

- [ ] **Step 3 (🤖 AGENT): Final verification checklist**

Run: `sunshine-status` and confirm: service `active`, `cap_sys_admin` present, forced-output params present. Re-run the Task 1.6 headless regression test once more.

- [ ] **Step 4 (🤖 AGENT): Commit + open PR**

```bash
cd /home/andreym/dotfiles
git add hosts/rocinante/README.md hosts/rocinante/setup-sunshine.md
git commit -m "docs(rocinante): document sunshine remote-desktop setup"
git push -u origin feat/remote-desktop-sunshine
gh pr create --fill --title "Remote desktop: wayvnc → Sunshine/Moonlight on rocinante"
```

---

## Self-review

- **Spec coverage:** Foundation/headless (M1), capture+codec+clients (M2), browser (M3), Nix/dotfiles + retire-wayvnc + Tailscale (M4), robustness+testing+docs (M5). Audio: Sunshine streams desktop audio by default (no extra task; verify in 2.2). All spec §5 components mapped.
- **Deviations flagged:** packaging (AUR not home-manager) and wayvnc retention — both called out up top and reflected in tasks.
- **Placeholder scan:** every step has concrete commands/config; no TBDs. `<port>` for the web proxy is the one value discovered at runtime (Task 3.1 Step 3 surfaces it) — acceptable, it's image-dependent.
- **Consistency:** `HDMI-A-1`, `/dev/dri/renderD128`, `cap_sys_admin`, `sunshineHelpers` option name, and the EDID filename are used identically across tasks.
