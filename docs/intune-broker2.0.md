# Intune Management with Broker 2.0

> Source: Microsoft Stack Overflow (SO@MS) - Article 468348
> Last edited: September 2024

This article provides instructions for configuring your Linux Desktop to enroll in Intune management, enabling you to access M365/Azure resources secured by Conditional Access via the Edge Browser with a logged-in Edge Profile.

**Bugs:** https://aka.ms/oneauthbug

**NOTE:** Only Ubuntu 22.04 and 24.04 are tested. RHEL support will come after Ubuntu is stabilized.

---

## Broker 2.0 Change Log

### 2.0.2 Release

- **9/19** - Added Telemetry to the header of token requests so we can differentiate broker versions
- **No migration script** from javabroker to broker2.0. To test the new broker, remove the javabroker and all state, then re-register your device via intune + broker2.0
- **Entra Join instead of Registration** - New devices perform an Entra Join (device trust) instead of Entra Registration (user profile). This is a prerequisite for platformSSO in the future
- **Service renamed**: `microsoft-identity-device-broker` → `microsoft-identity-devicebroker`
- **No user broker service** - The user broker is now an executable invoked via D-Bus connection (no longer `microsoft-identity-broker` systemd service)
- **Device certs moved** from Keychain to `/etc/ssl/private`:
  - Device cert per tenant
  - Session transport key per tenant
  - Deviceless key
  - User data (AT/RT) remains in KeyChain via msal/OneAuth

---

## New Install

Assumes you have removed the previous Javabroker (version 2.0.1 or earlier).

### Step 1 - Add apt sources & install Edge and Intune

```bash
# Install Curl
sudo apt install curl

# Install Microsoft's public key
curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg
sudo install -o root -g root -m 644 microsoft.gpg /usr/share/keyrings
rm microsoft.gpg

# Install the production packages:
sudo sh -c 'echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/ubuntu/$(lsb_release -rs)/prod $(lsb_release -cs) main" >> /etc/apt/sources.list.d/microsoft-ubuntu-$(lsb_release -cs)-prod.list'

wget "https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/insiders-fast.list" > /etc/apt/sources.list.d/microsoft-insiders-fast.list
sudo apt update

# Install Edge's dev channel repo
sudo sh -c 'echo "deb [arch=amd64] https://packages.microsoft.com/repos/edge stable main" > /etc/apt/sources.list.d/microsoft-edge-stable.list'
sudo apt update

# Install Edge
sudo apt install microsoft-edge-stable

# Install Microsoft Identity Broker - IMPORTANT! Install broker BEFORE Edge
sudo apt install microsoft-identity-broker

# Install Intune
sudo apt install intune-portal

# List installed packages & versions
sudo dpkg -l microsoft-identity-broker intune-portal microsoft-edge-stable azure-cli
```

### YubiKey / Smart Card Setup

```bash
# Install Smart Card drivers
sudo apt install pcscd yubikey-manager

# YubiKey/Edge Bridge
sudo apt install opensc libnss3-tools openssl
mkdir -p $HOME/.pki/nssdb
chmod 700 $HOME/.pki
chmod 700 $HOME/.pki/nssdb
modutil -force -create -dbdir sql:$HOME/.pki/nssdb
modutil -force -dbdir sql:$HOME/.pki/nssdb -add 'SC Module' -libfile /usr/lib/x86_64-linux-gnu/pkcs11/opensc-pkcs11.so
```

### Step 2 - Login & Configure Intune

Launch Intune (Company Portal) to login & register/enroll your desktop:

```bash
# Run Intune-Portal
/usr/bin/intune-portal

# Or with debug logging (open second terminal window)
cd /opt/microsoft/intune/bin
INTUNE_LOG_LEVEL=debug ./intune-portal
```

1. Log in with your `USER@Microsoft.com` credentials
2. Enroll your desktop
3. Check compliance status in the Intune Agent
4. Verify device appears on https://aka.ms/cpweb

> **Tip:** Launch from command line to see stdout for errors.

### Step 3 - Run Edge

```bash
microsoft-edge
```

1. Login to Edge Profile (click grey person icon → "Sign in to sync data")
2. Enter your `USER@Microsoft.com` account
3. SSO should work for office.com and other M365 sites

> **NOTE:** Currently only Edge Browser supports CA for M365 on Ubuntu.

---

## Optional - Install Azure CLI

```bash
# All in One Command:
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Or Step by Step:
sudo apt-get update
sudo apt-get install ca-certificates curl apt-transport-https lsb-release gnupg
curl -sL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/microsoft.gpg > /dev/null
AZ_REPO=$(lsb_release -cs)
echo "deb [arch=amd64] https://packages.microsoft.com/repos/azure-cli/ $AZ_REPO main" | sudo tee /etc/apt/sources.list.d/azure-cli.list
sudo apt-get update
sudo apt-get install azure-cli
az -v
```

---

## Update to Latest Packages

```bash
# Update package/repo metadata
sudo apt update

# Upgrade packages & clean up dependencies
sudo apt-get dist-upgrade
```

---

## List Installed Versions

```bash
apt list -a intune-portal microsoft-edge-dev microsoft-identity-broker azure-cli
# or
sudo dpkg -l microsoft-identity-broker intune-portal microsoft-edge-stable
```

---

## PRMFA Testing (Smart Card / YubiKey)

p11-kit module config reference: https://p11-glue.github.io/p11-glue/p11-kit/manual/pkcs11-conf.html

```ini
# Example p11-kit module config
module: /usr/lib/x86_64-linux-gnu/libykcs11.so
```

YubiKey/Edge Bridge setup:

```bash
# Set up YubiKey
sudo apt install pcscd yubikey-manager

# YubiKey/Edge Bridge
sudo apt install opensc libnss3-tools openssl
mkdir -p $HOME/.pki/nssdb
chmod 700 $HOME/.pki
chmod 700 $HOME/.pki/nssdb
modutil -force -create -dbdir sql:$HOME/.pki/nssdb
modutil -force -dbdir sql:$HOME/.pki/nssdb -add 'SC Module' -libfile /usr/lib/x86_64-linux-gnu/pkcs11/opensc-pkcs11.so
```

---

## Removing Components / Resetting Configuration

### Remove Intune & Identity Broker

```bash
sudo apt remove microsoft-identity-broker
sudo apt remove intune-portal
```

### Force Remove Broker 2.0 Device Identity

```bash
sudo rm /etc/ssl/private/drs*
sudo rm /etc/ssl/private/stk*
```

### Clear Keychain (MSAL & Intune Cache)

```bash
# Remove secrets stored
secret-tool search --all env 60a144fbac31dfcf32034c112a615303b0e55ecad3a7aa61b7982557838908dc
secret-tool clear env 60a144fbac31dfcf32034c112a615303b0e55ecad3a7aa61b7982557838908dc

secret-tool search --all name LinuxBrokerRegularUserSecretKey --unlock
secret-tool search --all name LinuxBrokerSystemUserSecretKey --unlock
secret-tool clear name LinuxBrokerRegularUserSecretKey
secret-tool clear name LinuxBrokerSystemUserSecretKey
```

### Full Reset Script

```bash
# Uninstall the applications
sudo apt remove microsoft-identity-broker
sudo apt remove intune-portal

# Stop Identity Service
sudo systemctl stop microsoft-identity-devicebroker

# Clean up service state
sudo systemctl clean --what=configuration --what=runtime --what=all microsoft-identity-devicebroker.service

# Clear device keys
sudo rm /etc/ssl/private/drs*
sudo rm /etc/ssl/private/stk*

# Clear file caches
sudo rm -r "$USER_HOME/.cache/microsoft-identity-broker"
sudo rm -r "$USER_HOME/.config/microsoft-identity-broker"
sudo rm -r "$USER_HOME/.local/share/microsoft-identity-broker"
sudo rm -r "$USER_HOME/.local/share/intune"
sudo rm -r "$USER_HOME/.config/intune/registration.toml"
sudo rm -r "$USER_HOME/.local/share/intune-portal"
sudo rm -r "$USER_HOME/.cache/intune-portal"
sudo rm -r "$USER_HOME/.local/share/intune-portal"
sudo rm -r "$USER_HOME/.config/intune"

# Clear intune config
rm -r ~/.config/intune

# Optional: free space by removing dependencies
sudo dnf autoremove  # or apt autoremove

# Remove secrets stored
secret-tool search --all env 60a144fbac31dfcf32034c112a615303b0e55ecad3a7aa61b7982557838908dc
secret-tool clear env 60a144fbac31dfcf32034c112a615303b0e55ecad3a7aa61b7982557838908dc
secret-tool search --all name LinuxBrokerRegularUserSecretKey --unlock
secret-tool search --all name LinuxBrokerSystemUserSecretKey --unlock
secret-tool clear name LinuxBrokerRegularUserSecretKey
secret-tool clear name LinuxBrokerSystemUserSecretKey

# Verify device is removed from Company Portal:
# 1. Browse to https://aka.ms/cpweb
# 2. Click Devices
# 3. Locate the Linux device, select it
# 4. Click Remove
```

---

## Troubleshooting & Reporting Issues

**Bugs:** https://aka.ms/oneauthbug

### Logging

| Item | Command |
|------|---------|
| All Logs | `journalctl --since "10 minutes ago" > logs_last_10_min.txt` |
| Intune | `journalctl -f --user -u intune-agent`<br>`journalctl -f --user -t intune-portal > intune-portal.log` |
| JavaBroker | `journalctl --user -f -u microsoft-identity-broker.service`<br>`sudo journalctl --system -f -u microsoft-identity-devicebroker.service` |
| New Broker | `journalctl --user -f -u microsoft-identity-broker.service` |
| DBUS Logs | `busctl --user monitor com.microsoft.identity.broker1` |

### Services

| Task | Command |
|------|---------|
| Get all running services | `systemctl --type=service --state=running` |
| Restart Broker 2.0 | `sudo systemctl --user restart microsoft-identity-broker.service` |
| Get status of Javabroker | `systemctl --user status microsoft-identity-broker.service` |

### Get Installed Apps & Versions

```bash
sudo dpkg -l microsoft-identity-broker intune-portal microsoft-edge-stable azure-cli
```

### Run Intune with Debug Level

```bash
cd /opt/microsoft/intune/bin
INTUNE_LOG_LEVEL=debug ./intune-portal
```

---

## Known Issues & Tips

> **Black screen?** Add this environment variable:
> ```bash
> WEBKIT_DISABLE_DMABUF_RENDERER=1 intune-portal
> ```
> — Youssef Shahin, Nov 2024

---

## Related Articles

- How do I find out my Intune DeviceId
- How do I capture the broker logs?
- List all the versions of components installed for registering my Linux Desktop in AAD & Intune
- How to reset my Linux desktop from Enrollment in Intune
- On Linux Desktops, how do I safely update/upgrade to the latest Intune Agent?
- Why does the user get a "Are you trying to sign into the Microsoft Authentication Broker" prompt during Linux Desktop Enrollment?
- What does "reset ... to factory setting" actually mean?
