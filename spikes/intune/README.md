# P2 Intune Spike

This directory contains the **P2 Intune spike implementation** — a temporary experimentation space for validating Microsoft Entra (Intune) integration architecture before production rollout. The complete plan lives at `.superpowers/sdd/2026-08-03-env-refactor-p2-intune-spikes/`. Everything here is throwaway — the entire directory will be deleted at P2 close except for the final architecture verdict recorded in the plan document.

**Never commit:**
- `tenant.nix` — fill in from `tenant.nix.example` with your Entra tenant domain; it is gitignored
- `*.key` and `*.key.pub` — spike SSH keypair (generated once, rsync'd to build host); gitignored
- `notes/` — session notes and experimental output; gitignored
- `result` — nix build symlink; gitignored

**The `spike` CLI contract** (runs on rocinante):
```bash
spike <build|up|down|ssh|reset|destroy|status|vnc> <b4|b3>
```
- `build`: rebuild base image from flake
- `up`: boot VM with overlay
- `down`: stop VM cleanly
- `ssh`: jump into running VM as root via Tailscale
- `reset`: stop VM and discard overlay (back to doorstep)
- `destroy`: stop VM and delete entire directory
- `status`: show running/stopped state and image sizes
- `vnc`: print VNC connection details for b3 while running

VM variants: `b4` (headless, SSH only, port 2241), `b3` (Hyprland desktop, VNC, port 2231).
