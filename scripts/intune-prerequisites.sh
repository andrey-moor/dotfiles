#!/usr/bin/env bash
# Intune prerequisites script - system-level configuration for Intune on Arch Linux
#
# Configures: D-Bus policy, device broker service, pcscd, PKCS#11, ccid driver, PAM policy
# Prerequisites: Home-manager applied with modules.linux.intune.enable = true
#
# Idempotent: safe to re-run - each section checks if already configured
#
# Usage:
#   intune-prerequisites         # Apply all configurations
#   intune-prerequisites --check # Verify only, no changes

set -euo pipefail

# ============================================================================
# HELPERS
# ============================================================================

log() { echo "[+] $1"; }
warn() { echo "[!] $1"; }
skip() { echo "[=] $1 (already configured)"; }
fail() { echo "[✗] $1"; FAILED=true; }
pass() { echo "[✓] $1"; }

CHECK_ONLY=false
FAILED=false

if [[ "${1:-}" == "--check" ]]; then
    CHECK_ONLY=true
    log "Running in CHECK mode (no changes will be made)"
fi

# ============================================================================
# PRECONDITIONS
# ============================================================================

if [[ $EUID -eq 0 ]]; then
    warn "Running as root. Some user-level operations may fail."
    warn "Consider running as regular user with sudo access."
fi

# Check for Nix profile
if [[ ! -d "$HOME/.nix-profile" ]]; then
    echo "ERROR: Nix profile not found at $HOME/.nix-profile"
    echo "Run home-manager switch first, then run this script."
    exit 1
fi

# ============================================================================
# 1. Device broker D-Bus policy
# ============================================================================
log "Checking device broker D-Bus policy..."

DBUS_POLICY_DEST="/usr/share/dbus-1/system.d/com.microsoft.identity.devicebroker1.conf"
BROKER_PKG=$(find /nix/store -maxdepth 1 -name '*microsoft-identity-broker-2.0.4' -type d 2>/dev/null | head -1)

if [[ -z "$BROKER_PKG" ]]; then
    warn "Broker package not found in Nix store - home-manager switch may not have run"
    BROKER_PKG="NOT_FOUND"
fi

if [[ -f "$DBUS_POLICY_DEST" ]]; then
    skip "Device broker D-Bus policy"
else
    if [[ "$CHECK_ONLY" == "true" ]]; then
        fail "Device broker D-Bus policy not installed"
    else
        if [[ "$BROKER_PKG" == "NOT_FOUND" ]]; then
            fail "Cannot install D-Bus policy - broker package not found"
        else
            log "Installing device broker D-Bus policy..."
            sudo cp "$BROKER_PKG/share/dbus-1/system.d/com.microsoft.identity.devicebroker1.conf" "$DBUS_POLICY_DEST"
            sudo chmod 644 "$DBUS_POLICY_DEST"
            sudo pkill -HUP dbus-daemon || true
            log "D-Bus policy installed and dbus-daemon signaled"
        fi
    fi
fi

# ============================================================================
# 2. Device broker systemd service + override
# ============================================================================
log "Checking device broker systemd service..."

SERVICE_DEST="/etc/systemd/system/microsoft-identity-device-broker.service"
OVERRIDE_DIR="/etc/systemd/system/microsoft-identity-device-broker.service.d"
OVERRIDE_CONF="$OVERRIDE_DIR/rosetta.conf"

if [[ -f "$OVERRIDE_CONF" ]] && grep -q "ExecStart=" "$OVERRIDE_CONF" 2>/dev/null; then
    skip "Device broker systemd service"
else
    if [[ "$CHECK_ONLY" == "true" ]]; then
        fail "Device broker systemd service not configured"
    else
        if [[ "$BROKER_PKG" == "NOT_FOUND" ]]; then
            fail "Cannot configure service - broker package not found"
        else
            log "Installing device broker systemd service..."

            # Copy base service file
            sudo cp "$BROKER_PKG/lib/systemd/system/microsoft-identity-device-broker.service" "$SERVICE_DEST"

            # Create override directory
            sudo mkdir -p "$OVERRIDE_DIR"

            # Find the wrapper from Nix profile
            WRAPPER=$(readlink -f "$HOME/.nix-profile/bin/microsoft-identity-device-broker-rosetta" 2>/dev/null || \
                      readlink -f "$HOME/.nix-profile/bin/microsoft-identity-device-broker" 2>/dev/null || \
                      echo "")

            if [[ -z "$WRAPPER" ]]; then
                fail "Device broker wrapper not found in Nix profile"
            else
                # Create override with Rosetta wrapper and MSAL environment
                cat << EOF | sudo tee "$OVERRIDE_CONF" > /dev/null
[Service]
ExecStart=
ExecStart=$WRAPPER
Environment=HOME=/root
Environment=XDG_CONFIG_HOME=/root/.config
Environment=XDG_CACHE_HOME=/root/.cache
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
                sudo systemctl daemon-reload
                sudo systemctl enable microsoft-identity-device-broker
                sudo systemctl start microsoft-identity-device-broker || warn "Service start failed (may need reboot)"
                log "Device broker systemd service installed and enabled"
            fi
        fi
    fi
fi

# ============================================================================
# 3. pcscd socket symlink
# ============================================================================
log "Checking pcscd socket symlink..."

TMPFILES_CONF="/etc/tmpfiles.d/pcscd-symlink.conf"
SYMLINK_TARGET="/run/pcscd/pcscd"

if [[ -L "$SYMLINK_TARGET" ]]; then
    skip "pcscd socket symlink"
elif [[ -f "$TMPFILES_CONF" ]]; then
    skip "pcscd tmpfiles config (symlink will be created on next boot)"
else
    if [[ "$CHECK_ONLY" == "true" ]]; then
        fail "pcscd socket symlink not configured"
    else
        log "Installing pcscd socket symlink configuration..."
        echo 'L /run/pcscd/pcscd - - - - /run/pcscd/pcscd.comm' | sudo tee "$TMPFILES_CONF" > /dev/null
        sudo systemd-tmpfiles --create "$TMPFILES_CONF" || warn "tmpfiles create failed (may need pcscd running)"
        log "pcscd socket symlink configured"
    fi
fi

# ============================================================================
# 4. pcscd polkit disable
# ============================================================================
log "Checking pcscd polkit override..."

PCSCD_OVERRIDE_DIR="/etc/systemd/system/pcscd.service.d"
PCSCD_OVERRIDE="$PCSCD_OVERRIDE_DIR/override.conf"

if [[ -f "$PCSCD_OVERRIDE" ]] && grep -q "disable-polkit" "$PCSCD_OVERRIDE" 2>/dev/null; then
    skip "pcscd polkit override"
else
    if [[ "$CHECK_ONLY" == "true" ]]; then
        fail "pcscd polkit not disabled"
    else
        log "Installing pcscd polkit override..."
        sudo mkdir -p "$PCSCD_OVERRIDE_DIR"
        cat << 'EOF' | sudo tee "$PCSCD_OVERRIDE" > /dev/null
[Service]
ExecStart=
ExecStart=/usr/bin/pcscd --foreground --auto-exit --disable-polkit
EOF
        sudo systemctl daemon-reload
        sudo systemctl restart pcscd.socket pcscd.service 2>/dev/null || \
            sudo systemctl enable pcscd.socket 2>/dev/null || \
            warn "pcscd restart failed (install pcscd package: sudo pacman -S pcsclite ccid)"
        log "pcscd polkit override installed"
    fi
fi

# ============================================================================
# 5. System PKCS#11 modules
# ============================================================================
log "Checking system PKCS#11 modules..."

PKCS11_DIR="/etc/pkcs11/modules"
OPENSC_X86_MODULE="$PKCS11_DIR/opensc-x86.module"
OPENSC_MODULE="$PKCS11_DIR/opensc.module"
OPENSC_NIX=$(find /nix/store -maxdepth 1 -name '*opensc-arch-0.25.1' -type d 2>/dev/null | head -1)

if [[ -f "$OPENSC_X86_MODULE" ]] && [[ -f "$OPENSC_MODULE" ]]; then
    skip "System PKCS#11 modules"
else
    if [[ "$CHECK_ONLY" == "true" ]]; then
        fail "System PKCS#11 modules not configured"
    else
        log "Installing system PKCS#11 modules..."
        sudo mkdir -p "$PKCS11_DIR"
        sudo chmod 755 /etc/pkcs11 "$PKCS11_DIR"

        # Nix OpenSC (x86_64 for Rosetta apps)
        if [[ -n "$OPENSC_NIX" ]]; then
            cat << EOF | sudo tee "$OPENSC_X86_MODULE" > /dev/null
module: $OPENSC_NIX/lib/pkcs11/opensc-pkcs11.so
critical: no
EOF
            sudo chmod 644 "$OPENSC_X86_MODULE"
        else
            warn "Nix OpenSC package not found - skipping opensc-x86.module"
        fi

        # System OpenSC (native, if installed)
        if [[ -f "/usr/lib/pkcs11/opensc-pkcs11.so" ]]; then
            cat << EOF | sudo tee "$OPENSC_MODULE" > /dev/null
module: /usr/lib/pkcs11/opensc-pkcs11.so
critical: no
EOF
            sudo chmod 644 "$OPENSC_MODULE"
        else
            warn "System OpenSC not found at /usr/lib/pkcs11/ - install with: sudo pacman -S opensc"
        fi

        log "System PKCS#11 modules installed"
    fi
fi

# ============================================================================
# 6. ccid driver patch (Parallels Proxy CCID)
# ============================================================================
log "Checking ccid driver patch..."

CCID_PLIST="/usr/lib/pcsc/drivers/ifd-ccid.bundle/Contents/Info.plist"

if [[ -f "$CCID_PLIST" ]] && grep -q "0x203A" "$CCID_PLIST" 2>/dev/null; then
    skip "ccid driver patch (Parallels Proxy CCID)"
elif [[ ! -f "$CCID_PLIST" ]]; then
    warn "ccid driver not found - install with: sudo pacman -S ccid"
else
    if [[ "$CHECK_ONLY" == "true" ]]; then
        fail "ccid driver not patched for Parallels Proxy CCID"
    else
        log "Patching ccid driver for Parallels Proxy CCID..."
        sudo cp "$CCID_PLIST" "${CCID_PLIST}.bak"
        sudo sed -i '
            /<key>ifdVendorID<\/key>/,/<\/array>/ {
                /<\/array>/ i\                <string>0x203A</string>
            }
            /<key>ifdProductID<\/key>/,/<\/array>/ {
                /<\/array>/ i\                <string>0xFFFD</string>
            }
            /<key>ifdFriendlyName<\/key>/,/<\/array>/ {
                /<\/array>/ i\                <string>Parallels Proxy CCID</string>
            }
        ' "$CCID_PLIST"
        log "ccid driver patched (backup at ${CCID_PLIST}.bak)"
    fi
fi

# ============================================================================
# 7. PAM password policy (Intune compliance)
# ============================================================================
log "Checking PAM password policy..."

PAM_COMMON_PASSWORD="/etc/pam.d/common-password"

if [[ -f "$PAM_COMMON_PASSWORD" ]] && grep -q "pam_pwquality.so" "$PAM_COMMON_PASSWORD" 2>/dev/null; then
    skip "PAM password policy"
else
    if [[ "$CHECK_ONLY" == "true" ]]; then
        fail "PAM password policy not configured"
    else
        log "Installing PAM password policy..."
        sudo tee "$PAM_COMMON_PASSWORD" > /dev/null << 'EOF'
# /etc/pam.d/common-password - password-related modules for PAM
# Created for Microsoft Intune compliance

# Password strength requirements (Intune compliance)
password    requisite     pam_pwquality.so retry=3 dcredit=-1 ocredit=-1 ucredit=-1 lcredit=-1 minlen=12

# Standard password handling
password    required      pam_unix.so sha512 shadow try_first_pass use_authtok
EOF
        # Make readable by intune-agent (runs as user)
        sudo chmod 644 "$PAM_COMMON_PASSWORD"
        log "PAM password policy installed"
    fi
fi

# ============================================================================
# 8. Keyring default
# ============================================================================
log "Checking keyring default..."

KEYRING_DEFAULT="$HOME/.local/share/keyrings/default"

if [[ -f "$KEYRING_DEFAULT" ]] && [[ "$(cat "$KEYRING_DEFAULT" 2>/dev/null)" == "login" ]]; then
    skip "Keyring default"
else
    if [[ "$CHECK_ONLY" == "true" ]]; then
        fail "Keyring default not set"
    else
        log "Setting keyring default..."
        mkdir -p "$(dirname "$KEYRING_DEFAULT")"
        echo -n login > "$KEYRING_DEFAULT"
        log "Keyring default set to 'login'"
    fi
fi

# ============================================================================
# VERIFICATION SUMMARY
# ============================================================================

echo ""
echo "============================================"
echo "INTUNE PREREQUISITES VERIFICATION"
echo "============================================"

check_item() {
    local name="$1"
    local condition="$2"
    if eval "$condition" >/dev/null 2>&1; then
        pass "$name"
        return 0
    else
        fail "$name"
        return 1
    fi
}

# Variant that uses sudo for permission-restricted files
check_item_sudo() {
    local name="$1"
    local condition="$2"
    if sudo bash -c "$condition" >/dev/null 2>&1; then
        pass "$name"
        return 0
    else
        fail "$name"
        return 1
    fi
}

echo ""
echo "D-Bus & Systemd:"
check_item_sudo "Device broker D-Bus policy" "[[ -f '$DBUS_POLICY_DEST' ]]"
check_item_sudo "Device broker service file" "[[ -f '$SERVICE_DEST' ]]"
check_item_sudo "Device broker override" "[[ -f '$OVERRIDE_CONF' ]]"
check_item "Device broker running" "systemctl is-active microsoft-identity-device-broker"

echo ""
echo "pcscd & Smart Card:"
check_item_sudo "pcscd tmpfiles config" "[[ -f '$TMPFILES_CONF' ]]"
check_item_sudo "pcscd socket symlink" "[[ -L '$SYMLINK_TARGET' ]] || [[ -f '$TMPFILES_CONF' ]]"
check_item_sudo "pcscd polkit override" "[[ -f '$PCSCD_OVERRIDE' ]]"
check_item "pcscd running" "systemctl is-active pcscd.service || systemctl is-active pcscd.socket"

echo ""
echo "PKCS#11:"
check_item_sudo "System PKCS#11 modules dir" "[[ -d '$PKCS11_DIR' ]]"
check_item_sudo "OpenSC x86 module" "[[ -f '$OPENSC_X86_MODULE' ]]"

echo ""
echo "Intune Compliance:"
check_item_sudo "PAM password policy" "[[ -f '$PAM_COMMON_PASSWORD' ]]"
check_item "Keyring default" "[[ -f '$KEYRING_DEFAULT' ]]"

echo ""
echo "ccid Driver:"
if [[ -f "$CCID_PLIST" ]] || sudo test -f "$CCID_PLIST"; then
    check_item_sudo "Parallels Proxy CCID patch" "grep -q '0x203A' '$CCID_PLIST'"
else
    fail "ccid driver not installed"
fi

echo ""
echo "============================================"

if [[ "$FAILED" == "true" ]]; then
    if [[ "$CHECK_ONLY" == "true" ]]; then
        echo "Some checks FAILED. Run without --check to apply fixes."
        exit 1
    else
        echo "Some configurations may need manual intervention or a reboot."
        exit 1
    fi
else
    echo "All Intune prerequisites configured successfully!"
    echo ""
    echo "Next steps:"
    echo "  1. Enable intune-agent timer: systemctl --user enable --now intune-agent.timer"
    echo "  2. Launch portal: intune-portal-rosetta"
    echo "  3. Check status: intune-status"
    exit 0
fi
