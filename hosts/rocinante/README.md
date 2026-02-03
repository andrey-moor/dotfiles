# Rocinante

x86_64 Omarchy (Arch Linux) workstation with LUKS2-encrypted NVMe + btrfs.

**Access:** `ssh rocinante` (Tailscale SSH)

## Setup

```bash
# Clone dotfiles
git clone https://github.com/andrey-moor/dotfiles ~/dotfiles
cd ~/dotfiles
git checkout intune-p11kit  # or main once merged

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

### 2. Run Setup Script

```bash
intune-setup
```

This configures: os-release spoofing, device broker override, pcscd, p11-kit.

### 3. PAM Password Policy

```bash
sudo tee /etc/pam.d/common-password << 'EOF'
password    requisite     pam_pwquality.so retry=3 dcredit=-1 ocredit=-1 ucredit=-1 lcredit=-1 minlen=12
password    required      pam_unix.so sha512 shadow try_first_pass use_authtok
EOF
```

### 4. Keyring Setup

```bash
seahorse  # Create "login" keyring with password
echo -n login > ~/.local/share/keyrings/default
```

### 5. Enroll

```bash
intune-portal
```

### 6. Enable Agent Timer

```bash
systemctl --user enable --now intune-agent.timer
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
