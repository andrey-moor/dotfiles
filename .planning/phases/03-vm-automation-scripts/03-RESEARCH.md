# Phase 3: VM Automation Scripts - Research

**Researched:** 2026-02-02
**Domain:** Parallels prlctl CLI, VM cloning, post-clone configuration, shell scripting
**Confidence:** HIGH

## Summary

This phase creates automation scripts for cloning the encrypted Arch Linux VM template and configuring clones post-creation. The core workflow is: (1) Clone from `EncryptedBase-GRUB` template, (2) Configure VM settings via prlctl, (3) Run armarchy installer and GRUB fix inside the VM.

The repository already has working examples in `scripts/create-arch-vm.sh` that demonstrate prlctl patterns. This phase extends that approach to the clone-and-configure workflow. Key insight from Phase 1: the "Option B" approach (clone encrypted base, run armarchy fresh) was chosen over template generalization, so scripts must handle both cloning AND running the armarchy installer.

**Primary recommendation:** Create two scripts: (1) `clone-encrypted-vm.sh` for prlctl clone + configure from macOS, (2) `setup-clone.sh` for post-clone setup inside the VM (armarchy + GRUB fix + prerequisites). Scripts must work without interactive VM console access for the prlctl operations.

## Standard Stack

### Core Tools
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| prlctl | Parallels 19+ | VM management CLI | Only CLI option for Parallels Desktop |
| bash | 5.x | Scripting | Universal, no dependencies needed |
| curl | system | Download scripts | Available on both macOS and Arch |

### Supporting Tools
| Tool | Purpose | When to Use |
|------|---------|-------------|
| prlctl clone | Create VM copy | Initial clone from template |
| prlctl set | Configure VM | CPU, memory, shared folders |
| prlctl start/stop | VM lifecycle | Start/stop during setup |
| prlctl exec | Run commands in VM | Execute scripts without console |
| prlctl capture | Screenshots | Debugging/verification |

### Not Used
| Instead of | Why Not |
|------------|---------|
| Packer | Overkill for single-VM workflow, requires learning new tool |
| Vagrant | Parallels plugin exists but adds complexity |
| Ansible | Too heavy for simple script execution |
| expect | prlctl exec is simpler than scripting console |

## Architecture Patterns

### Recommended Script Structure

```
scripts/
├── clone-encrypted-vm.sh    # macOS: Clone template, configure VM settings
├── setup-clone.sh           # VM: armarchy + GRUB fix + prerequisites
└── prerequisites.sh         # VM: Rosetta/Nix/etc (already exists)
```

### Pattern 1: Two-Phase Clone Workflow

**What:** Separate macOS-side operations (clone, configure) from VM-side operations (armarchy, GRUB fix).

**Why:**
- prlctl exec runs as root inside VM, causing permission issues
- LUKS passphrase must be entered manually at boot (cannot automate)
- armarchy installer is interactive (username, email, password prompts)

**Implementation:**

```bash
# Phase 1: From macOS (clone-encrypted-vm.sh)
#!/usr/bin/env bash
VM_NAME="$1"
SOURCE_VM="ArchBase-Template"
SOURCE_SNAPSHOT="EncryptedBase-GRUB"

# Clone from snapshot
prlctl clone "$SOURCE_VM" --name "$VM_NAME"

# Configure resources
prlctl set "$VM_NAME" --cpus 4 --memsize 8192

# Enable Rosetta and shared folders (already on from template, verify)
prlctl set "$VM_NAME" --rosetta-linux on
prlctl set "$VM_NAME" --shf-host on

# Start VM
prlctl start "$VM_NAME"

echo "Manual steps required:"
echo "  1. Enter LUKS passphrase at boot"
echo "  2. Run: /mnt/psf/Home/Documents/dotfiles/scripts/setup-clone.sh"
```

```bash
# Phase 2: Inside VM (setup-clone.sh)
#!/usr/bin/env bash
# Must run as root after LUKS unlock and login

# Run armarchy
curl -fsSL hdwy.link/armarchy-3-x | bash

# After armarchy completes, fix GRUB (critical!)
cp /boot/EFI/GRUB/grubaa64.efi /boot/EFI/BOOT/BOOTAA64.EFI

# Reboot for GRUB
reboot
```

### Pattern 2: prlctl exec Usage

**What:** Execute commands inside VM without SSH or console access.

**When to use:** Post-reboot configuration after graphical login is available.

**Limitations:**
- Runs as root by default
- Working directory is `/` not `/root`
- Commands wrapped in `bash -c`
- Files created have root ownership (must fix with chown)
- Cannot enter LUKS passphrase

```bash
# Source: Parallels documentation
# Good: Simple non-interactive commands
prlctl exec "$VM_NAME" hostname

# Good: With user context (requires Parallels Tools)
prlctl exec "$VM_NAME" --user andreym whoami

# Problematic: Interactive commands (don't work via exec)
# prlctl exec "$VM_NAME" passwd  # FAILS - needs terminal

# Fix permission issues from prlctl exec
prlctl exec "$VM_NAME" "chown -R andreym:andreym /home/andreym"
```

### Pattern 3: Shared Folder Script Access

**What:** Access scripts via Parallels shared folders instead of copying.

**Why:**
- No network/SSH required
- Scripts stay in sync with git repo
- Available immediately after boot

**Implementation:**

```bash
# Scripts accessible at /mnt/psf/Home/Documents/dotfiles/scripts/
# VM can run them directly:
/mnt/psf/Home/Documents/dotfiles/scripts/setup-clone.sh

# Note: May need to wait for prltoolsd to mount (5-10 seconds after boot)
# Can check with: ls /mnt/psf/Home 2>/dev/null || sleep 5
```

### Pattern 4: Hostname Customization

**What:** Set unique hostname for each cloned VM.

**When:** After clone, before or after armarchy install.

```bash
# From macOS via prlctl exec (after VM is booted and logged in)
prlctl exec "$VM_NAME" "hostnamectl set-hostname endurance"
prlctl exec "$VM_NAME" "sed -i 's/archbase/endurance/g' /etc/hosts"

# Or from inside VM
sudo hostnamectl set-hostname endurance
```

### Anti-Patterns to Avoid

- **Using prlctl exec for interactive commands:** armarchy prompts for user input - must run in VM console
- **Running prlctl exec before LUKS unlock:** VM must be fully booted first
- **Assuming prlctl exec preserves environment:** Working directory is `/`, many env vars missing
- **Skipping GRUB fix after armarchy:** Critical! Limine will break LUKS boot

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| VM cloning | rsync of .pvm | `prlctl clone` | Handles VM registration, UUID regeneration |
| VM configuration | Edit .pvs XML | `prlctl set` | Proper locking, validation |
| Script execution | SSH setup | `prlctl exec` | Works without network config |
| Screenshot capture | VNC/screen | `prlctl capture` | Built-in, no dependencies |

**Key insight:** prlctl provides everything needed. The complexity is in orchestrating the steps that require manual intervention (LUKS, armarchy prompts).

## Common Pitfalls

### Pitfall 1: prlctl exec Permission Issues

**What goes wrong:** Files created by prlctl exec are owned by root, breaking user config.

**Why it happens:** prlctl exec runs as root by default.

**How to avoid:**
```bash
# Use --user flag when possible
prlctl exec "$VM_NAME" --user andreym "touch ~/test"

# Or fix ownership after
prlctl exec "$VM_NAME" "chown -R andreym:andreym /home/andreym"
```

**Warning signs:** "Permission denied" errors when user tries to access ~/.config or ~/.local.

### Pitfall 2: Shared Folders Not Mounted

**What goes wrong:** /mnt/psf empty or doesn't exist when script tries to access it.

**Why it happens:**
- prltoolsd takes time to start after boot
- Path unit race condition (fixed in Phase 2, but relevant for new clones)

**How to avoid:**
```bash
# Wait for mount in script
for i in {1..30}; do
    [[ -d /mnt/psf/Home ]] && break
    sleep 1
done
[[ -d /mnt/psf/Home ]] || { echo "Shared folders not mounted"; exit 1; }
```

**Warning signs:** "No such file or directory" for /mnt/psf paths.

### Pitfall 3: Cloning Running VM

**What goes wrong:** Clone fails or corrupts source VM.

**Why it happens:** prlctl clone requires source VM to be stopped.

**How to avoid:**
```bash
# Verify source is stopped
STATE=$(prlctl list -a -o name,status | grep "$SOURCE_VM" | awk '{print $2}')
[[ "$STATE" != "stopped" ]] && { prlctl stop "$SOURCE_VM" || true; sleep 5; }
```

**Warning signs:** Clone command fails with "VM is running" error.

### Pitfall 4: Forgetting GRUB Fix After Armarchy

**What goes wrong:** Clone boots to Limine, fails to decrypt LUKS, drops to emergency shell.

**Why it happens:** armarchy installs Limine to fallback boot path, overwriting GRUB.

**How to avoid:** Critical step in setup-clone.sh after armarchy completes:
```bash
cp /boot/EFI/GRUB/grubaa64.efi /boot/EFI/BOOT/BOOTAA64.EFI
```

**Warning signs:** Boot shows "Omarchy Bootloader" instead of GRUB menu.

### Pitfall 5: Clone from Wrong Snapshot

**What goes wrong:** Clone has unexpected state (e.g., existing user, wrong packages).

**Why it happens:** Template VM has multiple snapshots; clone defaults to current state, not specific snapshot.

**How to avoid:**
```bash
# Revert to correct snapshot before cloning
prlctl snapshot-switch "$SOURCE_VM" --id "EncryptedBase-GRUB"
# Then clone
prlctl clone "$SOURCE_VM" --name "$VM_NAME"
```

**Warning signs:** Cloned VM has andreym user or Omarchy already installed.

## Code Examples

### Complete Clone Script (macOS Side)

```bash
#!/usr/bin/env bash
# clone-encrypted-vm.sh - Clone encrypted Arch template
# Source: Based on scripts/create-arch-vm.sh patterns

set -euo pipefail

VM_NAME="${1:?Usage: $0 <vm-name> [cpus] [memory-mb]}"
CPUS="${2:-4}"
MEMORY="${3:-8192}"

SOURCE_VM="ArchBase-Template"
SOURCE_SNAPSHOT="EncryptedBase-GRUB"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[x]${NC} $1"; exit 1; }

# Prerequisites
command -v prlctl >/dev/null 2>&1 || error "prlctl not found. Install Parallels Desktop."

# Check source VM exists
prlctl list -a | grep -q "$SOURCE_VM" || error "Source VM '$SOURCE_VM' not found"

# Check target doesn't exist
prlctl list -a | grep -q "$VM_NAME" && error "VM '$VM_NAME' already exists"

# Stop source if running
log "Ensuring source VM is stopped..."
prlctl stop "$SOURCE_VM" 2>/dev/null || true
sleep 2

# Revert to clone snapshot
log "Reverting to snapshot '$SOURCE_SNAPSHOT'..."
prlctl snapshot-switch "$SOURCE_VM" --id "$SOURCE_SNAPSHOT" \
    || error "Snapshot '$SOURCE_SNAPSHOT' not found. Run: prlctl snapshot-list $SOURCE_VM"

# Clone
log "Cloning '$SOURCE_VM' to '$VM_NAME'..."
prlctl clone "$SOURCE_VM" --name "$VM_NAME"

# Configure
log "Configuring VM: ${CPUS} CPUs, ${MEMORY}MB RAM..."
prlctl set "$VM_NAME" --cpus "$CPUS"
prlctl set "$VM_NAME" --memsize "$MEMORY"

# Verify Rosetta and shared folders (should already be on)
prlctl set "$VM_NAME" --rosetta-linux on 2>/dev/null || true
prlctl set "$VM_NAME" --shf-host on 2>/dev/null || true

log "Clone '$VM_NAME' created successfully!"
echo ""
echo "Next steps:"
echo "  1. Start VM:  prlctl start '$VM_NAME'"
echo "  2. Enter LUKS passphrase at boot (default: temppass)"
echo "  3. Login as root"
echo "  4. Run setup script:"
echo "     /mnt/psf/Home/Documents/dotfiles/scripts/setup-clone.sh"
echo ""
warn "After setup, remember to change LUKS passphrase!"
```

### Complete Setup Script (VM Side)

```bash
#!/usr/bin/env bash
# setup-clone.sh - Post-clone setup inside VM
# Run as root after booting cloned VM

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[x]${NC} $1"; exit 1; }

# Must be root
[[ $EUID -eq 0 ]] || error "Run as root: sudo $0"

echo "=================================================="
echo " Omarchy Post-Clone Setup"
echo "=================================================="
echo ""

# Check we're not already set up (Omarchy creates /home/* users)
if [[ -d /home/$(ls /home 2>/dev/null | head -1 2>/dev/null) ]]; then
    warn "Home directory already has users. Omarchy may already be installed."
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] || exit 0
fi

# Step 1: Run armarchy
log "Installing Omarchy (armarchy)..."
echo ""
echo "You will be prompted for:"
echo "  - Your name"
echo "  - Your email"
echo "  - Your username"
echo "  - Your password (must meet Intune requirements: 12+ chars, upper, lower, digit, symbol)"
echo ""
read -p "Press Enter to start armarchy installer..."

# Install wget if needed
pacman -S --noconfirm wget 2>/dev/null || true

# Run armarchy
curl -fsSL hdwy.link/armarchy-3-x | bash

# Step 2: CRITICAL - Fix GRUB (armarchy installs Limine which breaks LUKS)
log "Restoring GRUB bootloader (critical for LUKS)..."
if [[ -f /boot/EFI/GRUB/grubaa64.efi ]]; then
    cp /boot/EFI/GRUB/grubaa64.efi /boot/EFI/BOOT/BOOTAA64.EFI
    log "GRUB restored to fallback boot path"
else
    error "GRUB EFI not found at /boot/EFI/GRUB/grubaa64.efi - boot may fail!"
fi

# Step 3: Instructions for after reboot
echo ""
echo "=================================================="
echo " Omarchy Installation Complete"
echo "=================================================="
echo ""
echo "After reboot, complete these steps:"
echo ""
echo "  1. Login as your new user (NOT root)"
echo "  2. Run prerequisites script:"
echo "     /mnt/psf/Home/Documents/dotfiles/scripts/prerequisites.sh"
echo ""
echo "  3. Apply home-manager:"
echo "     cd /mnt/psf/Home/Documents/dotfiles"
echo "     nix run home-manager -- switch --flake .#endurance -b backup"
echo ""
echo "  4. Complete Intune setup (see hosts/endurance/README.md section 7+)"
echo ""
echo "Ready to reboot? The system will reboot in 10 seconds..."
echo "(Press Ctrl+C to cancel)"
sleep 10

reboot
```

### Verification Commands

```bash
# From macOS: Verify clone exists and settings
prlctl list -a | grep "$VM_NAME"
prlctl list -i "$VM_NAME" | grep -E "cpus|memsize|rosetta"

# From macOS: Check VM is running
prlctl list | grep "$VM_NAME"

# From macOS: Take screenshot for debugging
prlctl capture "$VM_NAME" --file /tmp/vm-state.png && open /tmp/vm-state.png

# From inside VM: Verify GRUB is active bootloader
ls -la /boot/EFI/BOOT/BOOTAA64.EFI
# Should be ~160KB (GRUB), not ~90KB (Limine)

# From inside VM: Verify shared folders
ls /mnt/psf/Home/Documents/dotfiles
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Template generalization | Clone-and-configure (Option B) | Phase 1 decision | Simpler, fresh armarchy per clone |
| SSH for remote execution | prlctl exec | Always available | No network config needed |
| Manual VM creation | Scripted with prlctl | This phase | Reproducible, documented |

**Current/recommended:**
- Option B workflow: clone from EncryptedBase-GRUB, run armarchy fresh
- prlctl for all macOS-side automation
- Shared folders for script access (no copying needed)

## Open Questions

1. **Snapshot-switch availability**
   - What we know: `prlctl snapshot-switch` can revert to specific snapshot
   - What's unclear: Does clone then take from that reverted state automatically?
   - Recommendation: Test during implementation, may need to use `--linked` with `--id`

2. **prlctl exec timing after boot**
   - What we know: VM must be fully booted for exec to work
   - What's unclear: Exact detection method for "ready" state
   - Recommendation: Loop until `prlctl exec "$VM" whoami` succeeds

3. **armarchy non-interactive mode**
   - What we know: armarchy prompts for name, email, username, password
   - What's unclear: Is there an env var or config to pre-populate?
   - Recommendation: Accept manual interaction for now; investigate armarchy source if needed

## Sources

### Primary (HIGH confidence)
- [Parallels Clone VM Documentation](https://docs.parallels.com/parallels-desktop-developers-guide/command-line-interface-utility/manage-virtual-machines-from-cli/general-virtual-machine-management/clone-a-virtual-machine) - Clone command syntax
- [Parallels Execute Command Documentation](https://docs.parallels.com/parallels-desktop-developers-guide/command-line-interface-utility/manage-virtual-machines-from-cli/general-virtual-machine-management/execute-a-command-in-a-virtual-machine) - prlctl exec options
- [Parallels Shared Folders Documentation](https://docs.parallels.com/parallels-desktop-developers-guide/command-line-interface-utility/manage-virtual-machines-from-cli/virtual-machine-configuration-tasks/shared-folders) - shf-host options
- `scripts/create-arch-vm.sh` - Existing working prlctl patterns in repository

### Secondary (MEDIUM confidence)
- [Parallels prlctl-scripts GitHub](https://github.com/Parallels/prlctl-scripts) - Community automation patterns
- Phase 1 summaries (01-03-SUMMARY.md, 01-04-SUMMARY.md) - Option B decision context

### Tertiary (LOW confidence)
- Forum discussions about prlctl exec timing - Useful for troubleshooting

## Metadata

**Confidence breakdown:**
- prlctl commands: HIGH - Official documentation verified
- Clone workflow: HIGH - Based on Phase 1 decisions and existing scripts
- Setup script pattern: HIGH - Adapts working armarchy + GRUB fix steps
- prlctl exec limitations: MEDIUM - Documented but edge cases exist

**Research date:** 2026-02-02
**Valid until:** 2026-03-02 (30 days - prlctl API stable, armarchy may change)
