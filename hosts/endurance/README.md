# Endurance Setup

Encrypted Arch Linux ARM VM in Parallels with LUKS for Intune compliance.

## Manual Prerequisites

After installing Arch via archboot with LUKS (see `docs/rocinante-encrypted-install.md`):

### 1. x86_64 Dynamic Linker (Rosetta)

```bash
sudo mkdir -p /lib64
sudo ln -sf /nix/store/xx7cm72qy2c0643cm1ipngd87aqwkcdp-glibc-2.40-66/lib/ld-linux-x86-64.so.2 /lib64/
```

### 2. Rosetta binfmt

```bash
echo ':rosetta:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x3e\x00:\xff\xff\xff\xff\xff\xfe\xfe\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/mnt/psf/RosettaLinux/rosetta:PFC' | sudo tee /etc/binfmt.d/rosetta.conf
sudo systemctl enable --now systemd-binfmt
```

### 3. Nix x86_64 Support

```bash
echo "extra-platforms = x86_64-linux" | sudo tee -a /etc/nix/nix.custom.conf
sudo systemctl restart nix-daemon
```

### 4. Fake Ubuntu os-release (Intune requirement)

```bash
sudo tee /etc/os-release << 'EOF'
NAME="Ubuntu"
VERSION="22.04.3 LTS (Jammy Jellyfish)"
ID=ubuntu
ID_LIKE=debian
PRETTY_NAME="Ubuntu 22.04.3 LTS"
VERSION_ID="22.04"
VERSION_CODENAME=jammy
UBUNTU_CODENAME=jammy
EOF
```

### 5. Device Broker D-Bus Policy + Systemd Override

```bash
sudo cp /nix/store/1nd6dy206j32vnp4lp16md28n8b852b6-microsoft-identity-broker-2.0.4/share/dbus-1/system.d/com.microsoft.identity.devicebroker1.conf /etc/dbus-1/system.d/
sudo cp /nix/store/1nd6dy206j32vnp4lp16md28n8b852b6-microsoft-identity-broker-2.0.4/lib/systemd/system/microsoft-identity-device-broker.service /etc/systemd/system/

sudo mkdir -p /etc/systemd/system/microsoft-identity-device-broker.service.d
echo -e '[Service]\nExecStart=\nExecStart=/nix/store/0x66mzfg7f1my6jfai3gl2ibd0d2q17r-microsoft-identity-device-broker-rosetta/bin/microsoft-identity-device-broker-rosetta' | sudo tee /etc/systemd/system/microsoft-identity-device-broker.service.d/rosetta.conf

sudo systemctl daemon-reload
sudo systemctl restart dbus
sudo systemctl start microsoft-identity-device-broker
```

### 6. pcscd for YubiKey (Optional)

```bash
echo 'L /run/pcscd/pcscd - - - - /run/pcscd/pcscd.comm' | sudo tee /etc/tmpfiles.d/pcscd-symlink.conf
sudo systemd-tmpfiles --create /etc/tmpfiles.d/pcscd-symlink.conf

sudo mkdir -p /etc/systemd/system/pcscd.service.d
echo -e '[Service]\nExecStart=\nExecStart=/usr/bin/pcscd --foreground --auto-exit --disable-polkit' | sudo tee /etc/systemd/system/pcscd.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl restart pcscd.socket
```

## Apply Configuration

```bash
cd /mnt/psf/Home/Documents/dotfiles
nix run home-manager -- switch --flake .#endurance -b backup
```

## Verify

```bash
intune-status
```
