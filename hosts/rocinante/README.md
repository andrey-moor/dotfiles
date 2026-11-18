# Rocinante

> **⚠️ FROZEN (2026-07): do not run `omarchy-update` or system updates on this install.**
> This Omarchy system is being replaced by NixOS on the second NVMe
> (see `docs/superpowers/specs/2026-07-23-environment-refactor-design.md`).
> It remains the fallback of record until 30 days after cutover.

x86_64 Omarchy (Arch Linux) workstation with LUKS2-encrypted NVMe + btrfs.

**Access:** `ssh rocinante` (Tailscale SSH)

## Setup

```bash
# Clone dotfiles
git clone https://github.com/andrey-moor/dotfiles ~/dotfiles
cd ~/dotfiles
git checkout main
```

### Secrets (sops-nix)

This host has its own age key. It decrypts `secrets/wayvnc.yaml` and nothing
else. Never copy the admin key from behemoth here: that key opens every secret
in the repo.

The key is `~/.config/sops/age/keys.txt` (mode 600). On a rebuilt host,
generate a new one before the first switch:

```bash
mkdir -p ~/.config/sops/age
nix shell nixpkgs#age -c age-keygen -o ~/.config/sops/age/keys.txt
chmod 600 ~/.config/sops/age/keys.txt
```

The command prints the public key. On behemoth, put it in `.sops.yaml` as
`&rocinante`, run `sops updatekeys secrets/wayvnc.yaml`, and commit both files.
Until that commit is pulled here, the switch fails at sops activation.

```bash
# Install home-manager and switch (also symlinks nvim/nushell/alacritty configs from config/)
nix run home-manager -- switch --flake .#rocinante -b backup
```

Keep Determinate Nix current with `sudo determinate-nixd upgrade`. Version
3.15.2 ran out of open files at the default limit, and 3.24.2 does not.

`~/.claude/skills/<name>` entries become symlinks into `agents/skills/`. A real
folder of the same name blocks the switch, so remove any hand-installed copy
first. The repo is the source of truth for skills: edit them there.

## Intune Enrollment

The `intune` module provides full Nix library chain to avoid ABI issues with Arch system libs.
It auto-detects x86_64-linux and uses native packages (no Rosetta emulation needed).

### 1. Install AUR Packages

```bash
yay -S microsoft-identity-broker-bin intune-portal-bin microsoft-edge-stable-bin
```

### 2. Run Prerequisites

```bash
intune-prerequisites
```

This configures: D-Bus policy, device broker service, pcscd, PKCS#11, PAM policy,
keyring, NSS browser module (YubiKey), Azure VPN polkit rules.

### 3. Keyring Setup

```bash
seahorse  # Create "login" keyring with password
```

### 4. Enroll

```bash
intune-portal
```

### 5. Enable Agent Timer

```bash
systemctl --user enable --now intune-agent.timer
```

## Azure VPN

### 1. Install AUR Package

```bash
yay -S microsoft-azure-vpn-client-bin
```

### 2. System Prerequisites

Already handled by `intune-prerequisites` (polkit rules, network group, client ID patch, os-release VERSION):

```bash
intune-prerequisites
```

### 3. Launch

```bash
microsoft-azurevpnclient
```

## Verify

```bash
intune-status   # Check all components
intune-agent    # Run compliance check
```

## Troubleshooting

```bash
intune-logs              # Tail all logs
intune-logs --broker     # User broker only
intune-logs --device     # Device broker only

# Clear data and re-enroll
rm -rf ~/.Microsoft ~/.cache/intune-portal ~/.config/intune ~/.local/share/intune-portal
```
