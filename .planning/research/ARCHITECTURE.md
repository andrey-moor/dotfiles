# Architecture Research: Omarchy Linux VM Setup

## Component Diagram

```
+=========================================================================================================+
|                                         MACOS HOST (behemoth)                                           |
|                                                                                                         |
|  +-------------------+    +---------------------+    +-------------------------------------------+      |
|  | Parallels Desktop |    | Shared Folders      |    | prlctl                                    |      |
|  | - VM lifecycle    |    | - /mnt/psf/Home/... |    | - VM control (start/stop/exec)           |      |
|  | - Rosetta runtime |    | - RosettaLinux/     |    | - Remote command execution               |      |
|  +--------+----------+    +----------+----------+    +-------------------------------------------+      |
|           |                          |                                                                  |
+===========|==========================|==================================================================+
            |                          |
            v                          v
+===========|==========================|==================================================================+
|           |        OMARCHY VM (aarch64-linux)                                                           |
|           |                          |                                                                  |
|  +--------v----------+    +----------v----------+                                                       |
|  | systemd-binfmt    |    | Parallels Tools     |                                                       |
|  | - rosetta handler |    | - prltoolsd         |                                                       |
|  +--------+----------+    | - Shared folders    |                                                       |
|           |               +---------------------+                                                       |
|           |                                                                                             |
|  +--------v--------------------------------------------------------------------------------------------+|
|  |                                  x86_64 EMULATION LAYER                                             ||
|  |                                                                                                     ||
|  |  /mnt/psf/RosettaLinux/rosetta  --->  Translates x86_64 ELF binaries to ARM64                      ||
|  |                                                                                                     ||
|  +-----------------------------------------------------------------------------------------------------+|
|           |                                                                                             |
|           v                                                                                             |
|  +========|============================================================================================+|
|  |        |                     INTUNE STACK (x86_64 binaries via Rosetta)                             ||
|  |        |                                                                                            ||
|  |  +-----v-----------------------+          +-----------------------------+                           ||
|  |  | intune-portal               |  D-Bus   | microsoft-identity-broker   |                           ||
|  |  | - GUI enrollment            |--------->| (user session service)      |                           ||
|  |  | - WebKitGTK for auth flows  |          | - SSO authentication        |                           ||
|  |  | - Compliance display        |          | - Token management          |                           ||
|  |  +-----------------------------+          +------------+----------------+                           ||
|  |                                                        |                                            ||
|  |                                                        | D-Bus                                      ||
|  |                                                        v                                            ||
|  |  +-----------------------------+          +-----------------------------+                           ||
|  |  | intune-agent                |  D-Bus   | microsoft-identity-device-  |                           ||
|  |  | - Compliance reporting      |--------->| broker (system service)     |                           ||
|  |  | - Runs via systemd timer    |          | - Device attestation        |                           ||
|  |  | - Checks encryption, etc.   |          | - Runs as root              |                           ||
|  |  +-----------------------------+          +-----------------------------+                           ||
|  |                                                                                                     ||
|  +=====================================================================================================+|
|           |                                                                                             |
|           v                                                                                             |
|  +========|============================================================================================+|
|  |        |                          CREDENTIAL LAYER                                                  ||
|  |        |                                                                                            ||
|  |  +-----v-----------------------+          +-----------------------------+                           ||
|  |  | gnome-keyring               |          | pcscd (smart card daemon)   |                           ||
|  |  | - "login" keyring           |          | - Native aarch64            |                           ||
|  |  | - Credential storage        |          | - Socket at /run/pcscd/     |                           ||
|  |  | - Auto-unlock at login      |          +------------+----------------+                           ||
|  |  +-----------------------------+                       |                                            ||
|  |                                                        |                                            ||
|  |                                           +------------v----------------+                           ||
|  |                                           | ccid driver                 |                           ||
|  |                                           | - Parallels Proxy CCID      |                           ||
|  |                                           | - 0x203A:0xFFFD             |                           ||
|  |                                           +------------+----------------+                           ||
|  |                                                        |                                            ||
|  +========================================================================================================+
|                                                           |                                             |
|  +========================================================================================================+
|  |                                           | USB PASSTHROUGH                                          |
|  |                                           |                                                          |
|  |                                +----------v-----------+                                              |
|  |                                | YubiKey              |                                              |
|  |                                | - PIV certificate    |                                              |
|  |                                | - 0x203A:0xFFFD      |                                              |
|  |                                +----------------------+                                              |
|  |                                                                                                      |
|  +======================================================================================================+|
|                                                                                                         |
|  +===========================================+  +=====================================================+ |
|  | LIBRARY LAYER (x86_64 from Nix)           |  | NATIVE LAYER (aarch64)                              | |
|  |                                           |  |                                                     | |
|  | - OpenSSL 3.3.2 (Arch archives)           |  | - systemd (nix-daemon, user session)                | |
|  | - WebKitGTK 4.1                           |  | - D-Bus (system + session buses)                    | |
|  | - GTK3, GLib, Cairo, Pango, etc.          |  | - gnome-keyring                                     | |
|  | - Mesa llvmpipe (software rendering)      |  | - pcscd, ccid                                       | |
|  | - OpenSC 0.25.1 (PKCS#11)                 |  | - Parallels Tools                                   | |
|  | - p11-kit, libp11, pcsclite               |  |                                                     | |
|  | - curl (no HTTP/3)                        |  |                                                     | |
|  +===========================================+  +=====================================================+ |
|                                                                                                         |
+=========================================================================================================+
```

## Dependency Map

### Boot-Time Dependencies (Order Critical)

```
1. LUKS decrypt (GRUB encrypt hook)
   └── cryptsetup opens /dev/mapper/cryptroot

2. Parallels Tools Service (prltoolsd)
   └── Mounts shared folders to /mnt/psf/
       ├── /mnt/psf/RosettaLinux/rosetta
       └── /mnt/psf/Home/Documents/dotfiles

3. systemd-binfmt
   └── DEPENDS ON: Rosetta binary exists at /mnt/psf/RosettaLinux/rosetta
   └── RACE CONDITION: May try to register before prltoolsd mounts
   └── SOLUTION: rosetta-binfmt.path watches for binary, triggers binfmt restart

4. nix-daemon
   └── Requires: extra-platforms = x86_64-linux in config
   └── Can now build/run x86_64 packages via Rosetta
```

### Session-Time Dependencies

```
graphical-session.target
├── D-Bus session bus
│   ├── XDG_RUNTIME_DIR/bus socket
│   └── DBUS_SESSION_BUS_ADDRESS env var
│
├── gnome-keyring-daemon
│   ├── GNOME_KEYRING_CONTROL socket
│   ├── "login" keyring (must be default)
│   └── Auto-unlocked at PAM login
│
├── pcscd.socket (system service)
│   ├── /run/pcscd/pcscd.comm socket
│   ├── ccid driver with Parallels Proxy CCID
│   └── YubiKey accessible to user
│
└── microsoft-identity-device-broker.service (system)
    ├── D-Bus system policy in /usr/share/dbus-1/system.d/
    ├── Uses Nix wrapper (override in systemd)
    ├── HOME=/root for MSAL initialization
    └── Rosetta binfmt MUST be registered
```

### Intune Component Dependencies

```
intune-portal
├── microsoft-identity-broker (user, D-Bus activated)
│   ├── gnome-keyring (credential storage)
│   ├── Rosetta (x86_64 emulation)
│   ├── LD_LIBRARY_PATH (Nix x86_64 libs)
│   │   ├── OpenSSL 3.3.2 (MUST be first - fixes Code:1200)
│   │   ├── WebKitGTK 4.1
│   │   ├── Mesa llvmpipe
│   │   └── ~60+ other x86_64 libraries
│   └── GIO TLS backend (glib-networking)
│
├── microsoft-identity-device-broker (system)
│   ├── Rosetta (x86_64 emulation)
│   ├── D-Bus system bus
│   └── Same LD_LIBRARY_PATH requirements
│
├── WebKitGTK (for SSO auth flows)
│   ├── WEBKIT_DISABLE_DMABUF_RENDERER=1
│   ├── LIBGL_ALWAYS_SOFTWARE=1
│   ├── GDK_BACKEND=x11
│   └── Mesa llvmpipe (GALLIUM_DRIVER=llvmpipe)
│
└── YubiKey (for cert auth)
    ├── pcscd
    ├── OpenSC PKCS#11 module
    ├── p11-kit (module discovery)
    └── ~/.config/pkcs11/modules/opensc.module

intune-agent (compliance reporting)
├── microsoft-identity-broker (for tokens)
├── Reads system state:
│   ├── /etc/os-release (must show Ubuntu 22.04)
│   ├── /etc/pam.d/common-password (policy check)
│   ├── LUKS encryption state
│   └── Firewall status
└── systemctl --user timer (hourly + startup)
```

## Optimal Build Order

### Phase 1: VM Creation and Base OS (Manual/Parallels)

```
1.1  Create Parallels VM
     - 64GB+ disk, 4+ cores, 8GB+ RAM
     - Enable Rosetta, Enable Shared Folders

1.2  Boot archboot ISO

1.3  Partition disk
     - EFI partition (512MB, FAT32)
     - LUKS partition (rest)

1.4  Setup LUKS encryption
     - cryptsetup luksFormat (LUKS2, aes-xts-plain64)
     - cryptsetup open

1.5  Create filesystem
     - mkfs.btrfs on /dev/mapper/cryptroot

1.6  Install base system
     - pacstrap: base, linux, linux-firmware, btrfs-progs, sudo, networkmanager

1.7  Configure bootloader (GRUB)
     - mkinitcpio HOOKS with 'encrypt'
     - cp /boot/Image /boot/vmlinuz-linux (ARM kernel naming)
     - grub-install + grub-mkconfig
```

### Phase 2: Omarchy Desktop (curl installer)

```
2.1  Reboot into encrypted system

2.2  Configure PAM password policy
     - /etc/security/pwquality.conf (BEFORE user creation)

2.3  Run Omarchy/Armarchy installer
     - curl -fsSL hdwy.link/armarchy-3-x | bash
     - Creates user with compliant password
     - Installs Hyprland desktop
```

### Phase 3: Rosetta Setup (Critical Order)

```
3.1  Register Rosetta binfmt
     - /etc/binfmt.d/rosetta.conf
     - systemctl restart systemd-binfmt

3.2  Create Rosetta path watcher
     - rosetta-binfmt.path (watches /mnt/psf/RosettaLinux/rosetta)
     - rosetta-binfmt.service (restarts systemd-binfmt)
     - Handles boot-time race condition
```

### Phase 4: Nix Setup

```
4.1  Install Determinate Nix
     - curl installer with --extra-conf "extra-platforms = x86_64-linux"

4.2  Configure Nix permissions (if needed)
     - chmod 644 on systemd service files
```

### Phase 5: Intune Prerequisites (System Level)

These require sudo and MUST be done before home-manager:

```
5.1  Fake os-release
     - Copy Ubuntu 22.04 os-release to /usr/lib/os-release
     - Symlink /etc/os-release -> /usr/lib/os-release

5.2  x86_64 dynamic linker
     - Build glibc from Nix
     - ln -sf to /lib64/ld-linux-x86-64.so.2

5.3  pcscd configuration
     - Install pcsc-tools, opensc, ccid from pacman
     - Create socket symlink /run/pcscd/pcscd -> pcscd.comm
     - Override pcscd.service (disable polkit)
     - Add Parallels Proxy CCID to ccid driver
     - Enable pcscd.socket

5.4  D-Bus policy for device broker
     - Copy com.microsoft.identity.devicebroker1.conf
     - pkill -HUP dbus-daemon

5.5  PAM password policy
     - Create /etc/pam.d/common-password
     - chmod 644 (readable by intune-agent)
```

### Phase 6: Home-Manager (User Level)

```
6.1  Apply home-manager configuration
     - nix run home-manager -- switch --flake .#endurance -b backup
     - Installs intune-rosetta module
     - Creates wrappers, D-Bus services, systemd timer

6.2  Device broker systemd override
     - sudo copy D-Bus policy
     - sudo systemctl edit microsoft-identity-device-broker
     - Point ExecStart to Nix wrapper
     - Add HOME=/root environment

6.3  User broker D-Bus service
     - Created by home-manager in ~/.local/share/dbus-1/services/

6.4  Configure keyring
     - echo -n login > ~/.local/share/keyrings/default
```

### Phase 7: Enrollment

```
7.1  Verify prerequisites
     - intune-status (check all components)
     - intune-pkcs11-diag (verify YubiKey chain)

7.2  Enable intune-agent timer
     - systemctl --user enable --now intune-agent.timer

7.3  Run enrollment
     - intune-portal-rosetta
     - Authenticate with YubiKey PIV certificate
```

## Component Interactions

### Rosetta + pcscd + D-Bus + Keyring

```
                                    ENROLLMENT FLOW
                                    ================

User clicks "Sign in" in intune-portal
        |
        v
intune-portal (x86_64/Rosetta)
        |
        | D-Bus call: com.microsoft.identity.broker1
        v
D-Bus session bus
        |
        | Auto-activates from ~/.local/share/dbus-1/services/
        v
microsoft-identity-broker-rosetta (x86_64/Rosetta)
        |
        +---> WebKitGTK auth popup (x86_64)
        |           |
        |           | HTTPS to login.microsoftonline.com
        |           |
        |           +---> User selects certificate auth
        |                       |
        |                       v
        |               OpenSC PKCS#11 module (x86_64)
        |                       |
        |                       | pcsclite IPC
        |                       v
        |               pcscd (native aarch64)
        |                       |
        |                       | USB via Parallels
        |                       v
        |               YubiKey PIV slot
        |                       |
        |                       | PIN entry, signature
        |                       v
        |               Certificate presented to server
        |
        +---> Token received
        |
        | D-Bus call: com.microsoft.identity.devicebroker1
        v
D-Bus system bus
        |
        v
microsoft-identity-device-broker (x86_64/Rosetta, runs as root)
        |
        +---> Device attestation
        |
        v
Enrollment complete
        |
        | Store credentials
        v
gnome-keyring (native aarch64)
        |
        | "login" keyring, auto-unlocked
        v
Credentials persisted
```

### Critical Path for pcscd (Cross-Architecture)

```
YubiKey (USB)
     |
     | USB passthrough (Parallels)
     v
Parallels Proxy CCID (virtual reader)
     |
     | ccid driver (patched Info.plist with 0x203A:0xFFFD)
     v
pcscd (native aarch64)
     |
     | Socket: /run/pcscd/pcscd.comm
     | Symlink: /run/pcscd/pcscd -> pcscd.comm (for x86_64 compat)
     v
pcsclite client library (x86_64 from Nix)
     |
     | PCSCLITE_CSOCK_NAME=/run/pcscd/pcscd.comm
     v
OpenSC PKCS#11 module (x86_64 from Arch archives)
     |
     | Loaded via p11-kit or directly
     v
p11-kit (x86_64)
     |
     | Config: ~/.config/pkcs11/modules/opensc.module
     v
GnuTLS / Application
```

### D-Bus Activation Chain

```
                        D-BUS SERVICE ACTIVATION
                        ========================

User session starts
        |
        v
D-Bus session bus daemon
        |
        | Reads service files from:
        |   1. ~/.local/share/dbus-1/services/ (user, Nix-managed)
        |   2. /usr/share/dbus-1/services/ (system)
        |
        v
Application calls com.microsoft.identity.broker1
        |
        v
D-Bus daemon finds service file
        |
        | ~/.local/share/dbus-1/services/com.microsoft.identity.broker1.service
        | Exec=/nix/store/xxx-microsoft-identity-broker-rosetta/bin/microsoft-identity-broker-rosetta
        |
        v
Fork + exec wrapper script
        |
        +---> Set LD_LIBRARY_PATH (60+ Nix x86_64 libs)
        +---> Set XDG_CONFIG_HOME, HOME
        +---> Set GNOME_KEYRING_CONTROL
        +---> Set Mesa/WebKitGTK env vars
        |
        v
Rosetta translates x86_64 ELF
        |
        v
microsoft-identity-broker runs
        |
        | Registers on D-Bus
        v
D-Bus daemon returns connection
        |
        v
Original caller receives response
```

## Parallelization Opportunities

### Can Run in Parallel

```
Phase 1-2: (Sequential - OS install, single-threaded)

Phase 3-4: Can overlap:
  [3.1 Rosetta binfmt] || [4.1 Nix install]

Phase 5: System setup can partially parallel:
  [5.1 os-release] || [5.2 ld-linux-x86-64] || [5.3 pcscd] || [5.5 PAM]
  [5.4 D-Bus policy] -- depends on having broker package path

Phase 6: Sequential (home-manager builds derivations)

Phase 7: Sequential (enrollment requires all prior)
```

### Blocking Dependencies (Cannot Parallelize)

```
LUKS setup -> pacstrap -> grub -> reboot (strictly sequential)

Rosetta binfmt -> Nix x86_64 builds (binfmt must be registered first)

pcscd + ccid -> OpenSC -> p11-kit -> YubiKey auth (chain must be complete)

D-Bus policy install -> device broker start (policy needed for D-Bus activation)

home-manager switch -> systemd user services (services created by switch)
```

## Race Conditions and Mitigations

### 1. Rosetta Mount Race (Boot-Time)

**Problem:** systemd-binfmt runs before prltoolsd mounts /mnt/psf/RosettaLinux/

**Mitigation:**
```
rosetta-binfmt.path
  PathExists=/mnt/psf/RosettaLinux/rosetta
  Unit=rosetta-binfmt.service

rosetta-binfmt.service
  ExecStart=/usr/bin/systemctl restart systemd-binfmt
```

### 2. Keyring Not Unlocked (Session-Time)

**Problem:** intune-agent timer may run before gnome-keyring unlocks

**Mitigation:**
- Service: After = graphical-session.target gnome-keyring.service
- Environment: GNOME_KEYRING_CONTROL=%t/keyring

### 3. D-Bus Session Bus Not Available (Timer Context)

**Problem:** systemd user timers don't inherit session D-Bus address

**Mitigation:**
- Service Environment: DBUS_SESSION_BUS_ADDRESS=unix:path=%t/bus

### 4. prlctl exec Runs as Root

**Problem:** `prlctl exec` runs commands as root, creating root-owned files

**Mitigation:**
- Use `su andreym -c '...'` within prlctl exec
- Or use SSH instead of prlctl exec for user-context operations

## Summary: Critical Setup Order

```
1. VM + LUKS + GRUB (manual, archboot)
2. Omarchy installer (creates compliant user)
3. Rosetta binfmt + path watcher (x86_64 support)
4. Nix with extra-platforms (package management)
5. System prerequisites (os-release, pcscd, D-Bus policy, ld-linux)
6. home-manager switch (Intune wrappers, user services)
7. Device broker systemd override (sudo, points to Nix wrapper)
8. Keyring setup + intune-agent timer
9. Enrollment via intune-portal-rosetta
```

The most fragile parts are:
1. **Rosetta binfmt timing** - use path watcher
2. **pcscd cross-architecture** - socket symlink + driver patch
3. **OpenSSL version** - MUST be 3.3.2 first in LD_LIBRARY_PATH
4. **D-Bus/keyring context** - environment variables in wrappers and services
