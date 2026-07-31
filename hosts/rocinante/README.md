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
git checkout intune-p11kit  # or main once merged
```

### Secrets (sops-nix)

Before switching, copy the sops age key from the admin machine (behemoth:
`~/Library/Application Support/sops/age/keys.txt`) to
`~/.config/sops/age/keys.txt` (mode 600) on this host — otherwise the switch
will fail at sops activation.

```bash
mkdir -p ~/.config/sops/age
scp behemoth:'~/Library/Application Support/sops/age/keys.txt' ~/.config/sops/age/keys.txt
chmod 600 ~/.config/sops/age/keys.txt
```

```bash
# Install home-manager and switch
nix run home-manager -- switch --flake .#rocinante -b backup

# Apply chezmoi (nushell config, etc.)
chezmoi apply
```

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
